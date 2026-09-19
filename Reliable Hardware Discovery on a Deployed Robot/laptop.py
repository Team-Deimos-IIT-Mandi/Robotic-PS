#!/usr/bin/env python3
import logging
import secrets
import time
import msvcrt
from dataclasses import dataclass, field
from typing import Optional

import serial
import serial.tools.list_ports
from serial import SerialException

BAUDRATE = 115200
DISCOVERY_INTERVAL = 1.0
IDENTIFY_RETRY_INTERVAL = 1.0
HOST_HEARTBEAT_PERIOD = 0.25
ESP_HEARTBEAT_TIMEOUT = 1.5
PROTOCOL_VERSION = 1

EXPECTED_DEVICES = {
    "LEFT_MOTOR": "ARDUINO_LEFT_01",
    "RIGHT_MOTOR": "ARDUINO_RIGHT_01",
}

logging.basicConfig(
    filename="ps7_windows.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger().addHandler(console)

log = logging.getLogger("PS7")


@dataclass
class DeviceConnection:
    port: str
    serial_port: serial.Serial
    state: str = "IDENTIFYING"
    device_id: Optional[str] = None
    role: Optional[str] = None
    firmware: Optional[str] = None
    protocol: Optional[int] = None
    session_id: Optional[str] = None
    last_esp_heartbeat: float = field(default_factory=time.monotonic)
    last_identify_request: float = 0.0
    next_heartbeat: float = 0.0
    next_sequence: int = 1

    def send(self, message: str):
        self.serial_port.write(
            (message + "\n").encode("utf-8")
        )
        self.serial_port.flush()
        log.info("[TX %s] %s", self.port, message)


class DeviceManager:
    def __init__(self):
        self.connections = {}
        self.last_discovery_scan = 0.0

    def discover_ports(self):
        ports = serial.tools.list_ports.comports()
        return sorted(
            port.device
            for port in ports
            if port.device
        )

    def open_new_ports(self):
        ports = self.discover_ports()

        for port in ports:
            if port in self.connections:
                continue

            try:
                ser = serial.Serial(
                    port=port,
                    baudrate=BAUDRATE,
                    timeout=0.05,
                    write_timeout=0.5,
                )

                connection = DeviceConnection(
                    port=port,
                    serial_port=ser,
                )

                self.connections[port] = connection

                log.info("DISCOVERED port=%s", port)

                self.send_identify(connection)

            except (SerialException, OSError) as exc:
                log.error(
                    "Could not open %s: %s",
                    port,
                    exc,
                )

    def close_connection(self, port: str, reason: str):
        connection = self.connections.pop(port, None)

        if connection is None:
            return

        try:
            connection.serial_port.close()
        except Exception:
            pass

        log.warning(
            "Connection closed: %s reason=%s",
            port,
            reason,
        )

    def reset_to_identifying(self, connection: DeviceConnection):
        connection.state = "IDENTIFYING"
        connection.session_id = None
        connection.next_sequence = 1
        connection.next_heartbeat = 0.0
        self.send_identify(connection)

    def send_identify(self, connection: DeviceConnection):
        connection.send(
            f"IDENTIFY {PROTOCOL_VERSION}"
        )
        connection.last_identify_request = time.monotonic()

    def poll_serial(self):
        for port in list(self.connections.keys()):
            connection = self.connections.get(port)

            if connection is None:
                continue

            try:
                while True:
                    line = (
                        connection.serial_port
                        .readline()
                        .decode(
                            "utf-8",
                            errors="replace",
                        )
                        .strip()
                    )

                    if not line:
                        break

                    log.info(
                        "[RX %s] %s",
                        port,
                        line,
                    )

                    self.handle_message(
                        connection,
                        line,
                    )

            except (SerialException, OSError) as exc:
                self.close_connection(
                    port,
                    f"serial error: {exc}",
                )

    def handle_message(
        self,
        connection: DeviceConnection,
        line: str,
    ):
        parts = line.split()

        if not parts:
            return

        msg_type = parts[0]

        if msg_type == "BOOT":
            if len(parts) != 5:
                return

            _, device_id, role, firmware, protocol = parts

            try:
                protocol = int(protocol)
            except ValueError:
                return

            connection.device_id = device_id
            connection.role = role
            connection.firmware = firmware
            connection.protocol = protocol

            connection.state = "IDENTIFYING"
            connection.session_id = None
            connection.next_sequence = 1

            log.info(
                "%s rebooted: ID=%s ROLE=%s",
                connection.port,
                device_id,
                role,
            )

            self.send_identify(connection)
            return

        if msg_type == "IDENTITY":
            if connection.state != "IDENTIFYING":
                return

            if len(parts) != 5:
                log.error(
                    "%s sent malformed IDENTITY",
                    connection.port,
                )
                return

            _, device_id, role, firmware, protocol = parts

            try:
                protocol = int(protocol)
            except ValueError:
                log.error(
                    "%s sent invalid protocol",
                    connection.port,
                )
                return

            connection.device_id = device_id
            connection.role = role
            connection.firmware = firmware
            connection.protocol = protocol

            log.info(
                "FOUND: port=%s ID=%s ROLE=%s FW=%s PROTO=%d",
                connection.port,
                device_id,
                role,
                firmware,
                protocol,
            )

            self.verify_device(connection)
            return

        if msg_type == "HB":
            if len(parts) != 4:
                return

            connection.last_esp_heartbeat = (
                time.monotonic()
            )
            return

        if msg_type == "READY":
            if len(parts) != 3:
                return

            _, device_id, session_id = parts

            if device_id != connection.device_id:
                log.error(
                    "%s READY has wrong device ID",
                    connection.port,
                )
                return

            if session_id != connection.session_id:
                log.error(
                    "%s READY has wrong session",
                    connection.port,
                )
                return

            connection.state = "READY"
            connection.last_esp_heartbeat = (
                time.monotonic()
            )
            connection.next_heartbeat = (
                time.monotonic()
            )

            log.info(
                "READY: role=%s port=%s ID=%s",
                connection.role,
                connection.port,
                connection.device_id,
            )
            return

        if msg_type == "CMD_OK":
            log.info(
                "Command accepted: %s",
                line,
            )
            return

        if msg_type == "CMD_REJECT":
            reason = " ".join(parts[1:])

            log.warning(
                "Command rejected by %s: %s",
                connection.port,
                reason,
            )

            if reason in (
                "NOT_READY",
                "BAD_SESSION",
            ):
                self.reset_to_identifying(
                    connection
                )

            return

        if msg_type == "ERR":
            reason = " ".join(parts[1:])

            log.warning(
                "Arduino error from %s: %s",
                connection.port,
                reason,
            )

            if reason in (
                "NOT_READY",
                "BAD_SESSION",
            ):
                self.reset_to_identifying(
                    connection
                )

            return

        if msg_type == "DISARMED":
            log.info(
                "%s is disarmed",
                connection.port,
            )
            return

        if msg_type == "SAFE_STOP":
            log.warning(
                "%s reported SAFE_STOP",
                connection.port,
            )
            return

        log.warning(
            "Unknown message from %s: %s",
            connection.port,
            line,
        )

    def verify_device(
        self,
        connection: DeviceConnection,
    ):
        device_id = connection.device_id
        role = connection.role
        protocol = connection.protocol

        if device_id is None:
            return

        expected_role = None

        for configured_role, configured_id in (
            EXPECTED_DEVICES.items()
        ):
            if (
                configured_id.upper()
                == device_id.upper()
            ):
                expected_role = configured_role
                break

        if expected_role is None:
            log.error(
                "REJECTED %s: unknown ID=%s",
                connection.port,
                device_id,
            )

            connection.state = "REJECTED"

            try:
                connection.send(
                    "DISARM UNKNOWN_DEVICE"
                )
            except Exception:
                pass

            self.close_connection(
                connection.port,
                "unknown hardware identity",
            )
            return

        if role != expected_role:
            log.error(
                "REJECTED %s: expected role=%s "
                "but device reports role=%s",
                connection.port,
                expected_role,
                role,
            )

            connection.state = "REJECTED"

            try:
                connection.send(
                    "DISARM ROLE_MISMATCH"
                )
            except Exception:
                pass

            self.close_connection(
                connection.port,
                "role mismatch",
            )
            return

        if protocol != PROTOCOL_VERSION:
            log.error(
                "REJECTED %s: unsupported protocol=%s",
                connection.port,
                protocol,
            )

            connection.state = "REJECTED"

            try:
                connection.send(
                    "DISARM PROTOCOL_MISMATCH"
                )
            except Exception:
                pass

            self.close_connection(
                connection.port,
                "protocol mismatch",
            )
            return

        connection.state = "VERIFYING"

        connection.session_id = (
            secrets.token_hex(8)
        )

        connection.next_sequence = 1

        connection.send(
            f"ARM {connection.session_id}"
        )

        log.info(
            "Identity verified: %s = %s",
            connection.role,
            connection.device_id,
        )

    def send_heartbeats(self):
        now = time.monotonic()

        for connection in list(
            self.connections.values()
        ):
            if connection.state != "READY":
                continue

            if now >= connection.next_heartbeat:
                try:
                    connection.send(
                        f"HB {connection.session_id}"
                    )

                    connection.next_heartbeat = (
                        now
                        + HOST_HEARTBEAT_PERIOD
                    )

                except (
                    SerialException,
                    OSError,
                ) as exc:
                    self.close_connection(
                        connection.port,
                        f"heartbeat send failed: {exc}",
                    )

    def check_heartbeats(self):
        now = time.monotonic()

        for connection in list(
            self.connections.values()
        ):
            if connection.state != "READY":
                continue

            elapsed = (
                now
                - connection.last_esp_heartbeat
            )

            if elapsed > ESP_HEARTBEAT_TIMEOUT:
                log.error(
                    "LOST: role=%s port=%s "
                    "no heartbeat for %.3f s",
                    connection.role,
                    connection.port,
                    elapsed,
                )

                connection.state = "LOST"

                self.close_connection(
                    connection.port,
                    "Arduino heartbeat timeout",
                )

    def retry_identification(self):
        now = time.monotonic()

        for connection in list(
            self.connections.values()
        ):
            if connection.state != "IDENTIFYING":
                continue

            if (
                now
                - connection.last_identify_request
                >= IDENTIFY_RETRY_INTERVAL
            ):
                self.send_identify(connection)

    def periodic_discovery(self):
        now = time.monotonic()

        if (
            now - self.last_discovery_scan
            >= DISCOVERY_INTERVAL
        ):
            self.open_new_ports()
            self.last_discovery_scan = now

    def send_command(
        self,
        role: str,
        value: int,
    ):
        role = role.upper()

        for connection in list(
            self.connections.values()
        ):
            if connection.role != role:
                continue

            if connection.state != "READY":
                log.warning(
                    "Cannot command %s: state=%s",
                    role,
                    connection.state,
                )
                return

            sequence = connection.next_sequence
            connection.next_sequence += 1

            message = (
                f"CMD "
                f"{connection.session_id} "
                f"{sequence} "
                f"{value}"
            )

            try:
                connection.send(message)

            except (
                SerialException,
                OSError,
            ) as exc:
                self.close_connection(
                    connection.port,
                    f"command send failed: {exc}",
                )

            return

        log.warning(
            "No READY device found for role=%s",
            role,
        )

    def stop_role(self, role: str):
        self.send_command(
            role,
            0,
        )

    def stop_all(self):
        for connection in list(
            self.connections.values()
        ):
            if (
                connection.state == "READY"
                and connection.session_id
            ):
                try:
                    connection.send(
                        f"DISARM "
                        f"{connection.session_id}"
                    )
                except Exception:
                    pass

    def print_status(self):
        if not self.connections:
            print("No devices discovered.")
            return

        for connection in self.connections.values():
            print(
                f"{connection.port:10} "
                f"{connection.state:12} "
                f"role={connection.role} "
                f"id={connection.device_id}"
            )

    def process_terminal_command(
        self,
        command: str,
    ):
        command = command.strip()

        if not command:
            return False

        parts = command.split()

        if parts[0].lower() == "status":
            self.print_status()
            return False

        if (
            parts[0].lower() == "set"
            and len(parts) == 3
        ):
            role = parts[1]

            try:
                value = int(parts[2])
            except ValueError:
                print("value must be an integer")
                return False

            self.send_command(
                role,
                value,
            )
            return False

        if (
            parts[0].lower() == "stop"
            and len(parts) == 2
        ):
            self.stop_role(parts[1])
            return False

        if parts[0].lower() == "stopall":
            self.stop_all()
            return False

        if parts[0].lower() in (
            "quit",
            "exit",
        ):
            self.stop_all()
            return True

        print(
            "Commands:\n"
            "  status\n"
            "  set LEFT_MOTOR 1\n"
            "  set LEFT_MOTOR 0\n"
            "  set RIGHT_MOTOR 1\n"
            "  set RIGHT_MOTOR 0\n"
            "  stop LEFT_MOTOR\n"
            "  stop RIGHT_MOTOR\n"
            "  stopall\n"
            "  quit"
        )

        return False

    def check_terminal(self):
        if not msvcrt.kbhit():
            return False

        try:
            command = input()
        except EOFError:
            return True

        return self.process_terminal_command(
            command
        )

    def run(self):
        log.info(
            "PS7 Windows device manager starting"
        )

        print()
        print("PS7 Windows Device Manager")
        print("---------------------------")
        print("Commands:")
        print("  status")
        print("  set LEFT_MOTOR 1")
        print("  set LEFT_MOTOR 0")
        print("  set RIGHT_MOTOR 1")
        print("  set RIGHT_MOTOR 0")
        print("  stop LEFT_MOTOR")
        print("  stop RIGHT_MOTOR")
        print("  stopall")
        print("  quit")
        print()

        while True:
            self.periodic_discovery()
            self.poll_serial()
            self.retry_identification()
            self.send_heartbeats()
            self.check_heartbeats()

            try:
                should_exit = self.check_terminal()
            except KeyboardInterrupt:
                print()
                self.stop_all()
                break

            if should_exit:
                break

            time.sleep(0.05)


if __name__ == "__main__":
    manager = DeviceManager()

    try:
        manager.run()
    except KeyboardInterrupt:
        manager.stop_all()
    finally:
        for port in list(
            manager.connections.keys()
        ):
            manager.close_connection(
                port,
                "program exit",
            )
