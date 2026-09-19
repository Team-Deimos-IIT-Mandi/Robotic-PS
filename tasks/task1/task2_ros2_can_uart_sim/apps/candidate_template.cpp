/**
 * ============================================================================
 * INTER IIT TECH MEET - TASK 2 CANDIDATE STARTER TEMPLATE
 * ============================================================================
 * Problem Statement: Custom Hardware Abstraction Driver over CAN and UART
 * Objectives:
 * 1. Implement CAN Bus Actuation (vcan0): Pack target motor velocity (Float32 LE)
 *    and XOR checksum into 8-byte CAN frame. Write using Linux SocketCAN.
 * 2. Implement CAN Encoder Feedback (vcan0): Read incoming encoder frames, verify XOR
 *    checksum, update wheel state.
 * 3. Implement UART Serial Parser (/tmp/ttyV0): Configure termios (115200 8N1 Non-blocking),
 *    parse ASCII NMEA "$ROVER,IMU,accel_x,accel_y,yaw*CRC\n", verify 8-bit XOR CRC.
 * ============================================================================
 */

#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <iomanip>
#include <cstring>
#include <chrono>
#include <thread>
#include <cmath>
#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <linux/can.h>
#include <linux/can/raw.h>

struct MotorCommand {
    uint8_t motor_id = 1;      // 1..4
    float target_velocity = 0.0f;
};

struct MotorState {
    uint8_t motor_id = 0;
    float position = 0.0f;
};

struct ImuData {
    float accel_x = 0.0f;
    float accel_y = 0.0f;
    float yaw = 0.0f;
};

class CandidateHardwareDriver {
public:
    CandidateHardwareDriver() = default;
    ~CandidateHardwareDriver() { closeBuses(); }

    bool init(const std::string& can_if = "vcan0", const std::string& serial_port = "/tmp/ttyV0") {
        m_can_if = can_if;
        m_serial_port = serial_port;

        std::cout << "[Candidate HAL Driver] Initializing hardware interfaces..." << std::endl;

        // --------------------------------------------------------------------
        // TODO 1: Initialize SocketCAN (PF_CAN, SOCK_RAW, CAN_RAW) on m_can_if.
        // --------------------------------------------------------------------
        m_can_fd = socket(PF_CAN, SOCK_RAW, CAN_RAW);

        if (m_can_fd < 0) {
            std::cerr << "[CAN] Failed to create SocketCAN socket." << std::endl;
            return false;
        }

        // Set socket to non-blocking mode
        int flags = fcntl(m_can_fd, F_GETFL, 0);
        if (flags < 0 || fcntl(m_can_fd, F_SETFL, flags | O_NONBLOCK) < 0) {
            std::cerr << "[CAN] Failed to set non-blocking mode." << std::endl;
            close(m_can_fd);
            m_can_fd = -1;
            return false;
        }

        // Get interface index for vcan0
        struct ifreq ifr{};
        std::strncpy(ifr.ifr_name, m_can_if.c_str(), IFNAMSIZ - 1);

        if (ioctl(m_can_fd, SIOCGIFINDEX, &ifr) < 0) {
            std::cerr << "[CAN] Failed to get interface index for "
                      << m_can_if << std::endl;
            close(m_can_fd);
            m_can_fd = -1;
            return false;
        }

        // Bind the socket to the CAN interface
        struct sockaddr_can addr{};
        addr.can_family = AF_CAN;
        addr.can_ifindex = ifr.ifr_ifindex;

        if (bind(m_can_fd,
                 reinterpret_cast<struct sockaddr*>(&addr),
                 sizeof(addr)) < 0) {
            std::cerr << "[CAN] Failed to bind to "
                      << m_can_if << std::endl;
            close(m_can_fd);
            m_can_fd = -1;
            return false;
        }

        std::cout << "[CAN] Socket bound to " << m_can_if
                  << " (non-blocking)." << std::endl;

        // --------------------------------------------------------------------
        // TODO 2: Initialize POSIX Serial Port (m_serial_port) with termios.h.
        // --------------------------------------------------------------------
        m_serial_fd = open(m_serial_port.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
        if (m_serial_fd < 0) {
            std::cerr << "[UART] Failed to open " << m_serial_port << std::endl;
            return false;
        }

        struct termios tty{};
        if (tcgetattr(m_serial_fd, &tty) != 0) {
            std::cerr << "[UART] Failed to get termios settings." << std::endl;
            close(m_serial_fd);
            m_serial_fd = -1;
            return false;
        }

        // Set baud rate to 115200
        cfsetospeed(&tty, B115200);
        cfsetispeed(&tty, B115200);

        // 8N1 raw mode, no hardware flow control
        tty.c_cflag &= ~PARENB;
        tty.c_cflag &= ~CSTOPB;
        tty.c_cflag &= ~CSIZE;
        tty.c_cflag |= CS8;
        tty.c_cflag &= ~CRTSCTS;
        tty.c_cflag |= CREAD | CLOCAL;

        // Raw local mode
        tty.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);

        // Raw input/output
        tty.c_iflag &= ~(IXON | IXOFF | IXANY);
        tty.c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL);
        tty.c_oflag &= ~OPOST;

        // Non-blocking read settings
        tty.c_cc[VMIN] = 0;
        tty.c_cc[VTIME] = 0;

        if (tcsetattr(m_serial_fd, TCSANOW, &tty) != 0) {
            std::cerr << "[UART] Failed to set termios settings." << std::endl;
            close(m_serial_fd);
            m_serial_fd = -1;
            return false;
        }

        std::cout << "[UART] Serial port opened at 115200 8N1 (non-blocking)." << std::endl;

        return (m_can_fd >= 0 && m_serial_fd >= 0);
    }

    void closeBuses() {
        if (m_can_fd >= 0) { close(m_can_fd); m_can_fd = -1; }
        if (m_serial_fd >= 0) { close(m_serial_fd); m_serial_fd = -1; }
    }

    /**
     * TODO 3: Compute 8-bit XOR Checksum
     * Calculate: checksum = payload[0] ^ payload[1] ^ ... ^ payload[6]
     */
    uint8_t computeCanChecksum(const uint8_t* payload_7bytes) {
        uint8_t checksum = 0;
        for (int i = 0; i < 7; ++i) {
            checksum ^= payload_7bytes[i];
        }
        return checksum;
    }

    /**
     * TODO 4: Send Motor Actuation CAN Frame
     * - Construct an 8-byte struct can_frame for CAN ID (0x100 + motor_id).
     * - Byte 0: motor_id
     * - Bytes 1..4: target_velocity (Float32 Little-Endian)
     * - Bytes 5..6: Reserved (0x00)
     * - Byte 7: XOR Checksum of Bytes 0..6
     * - Write non-blocking frame using write(m_can_fd, &frame, sizeof(frame)).
     */
    bool sendMotorVelocity(uint8_t motor_id, float target_velocity) {
        if (m_can_fd < 0) return false;

        struct can_frame frame;
        std::memset(&frame, 0, sizeof(frame));
        
        frame.can_id = 0x100 + motor_id;
        frame.can_dlc = 8;
        
        frame.data[0] = motor_id;
        std::memcpy(&frame.data[1], &target_velocity, sizeof(float));
        frame.data[5] = 0x00;
        frame.data[6] = 0x00;
        
        frame.data[7] = computeCanChecksum(frame.data);

        ssize_t nbytes = write(m_can_fd, &frame, sizeof(struct can_frame));
        return (nbytes == sizeof(struct can_frame));
    }

    /**
     * TODO 5: Read Motor Encoder CAN Frame & Verify Checksum
     * - Perform a non-blocking read from m_can_fd into a struct can_frame.
     * - Verify DLC >= 8 and check Byte 7 against expected XOR checksum of Bytes 0..6.
     * - Unpack motor_id (Byte 0) and position float (Bytes 1..4).
     * - Return true if a valid frame was read, false otherwise.
     */
    bool readEncoderFeedback(MotorState& state) {
        if (m_can_fd < 0) return false;

        struct can_frame frame;
        ssize_t nbytes = read(m_can_fd, &frame, sizeof(struct can_frame));
        
        if (nbytes != sizeof(struct can_frame)) {
            return false; // No data available or read error
        }

        if (frame.can_dlc < 8) {
            return false; // Incomplete payload
        }

        uint8_t expected_checksum = computeCanChecksum(frame.data);
        if (frame.data[7] != expected_checksum) {
            return false; // Checksum mismatch
        }

        state.motor_id = frame.data[0];
        std::memcpy(&state.position, &frame.data[1], sizeof(float));

        return true;
    }

    /**
     * TODO 6: Read & Parse UART NMEA IMU Sentence ($ROVER,IMU,accel_x,accel_y,yaw*CRC\n)
     * - Perform non-blocking read from m_serial_fd into an internal string buffer.
     * - Look for complete lines delimited by '\n'.
     * - Verify string starts with '$' and contains '*' separator.
     * - Extract string body between '$' and '*' and calculate 8-bit XOR CRC.
     * - Verify calculated 2-digit HEX CRC matches the provided CRC string.
     * - Parse comma-separated float tokens for accel_x, accel_y, and yaw.
     * - Return true if a valid sentence was parsed, false otherwise.
     */
    bool readImuTelemetry(ImuData& imu) {
        if (m_serial_fd < 0) {
            return false;
        }

        char chunk[256];

        ssize_t bytes_read =
            read(m_serial_fd, chunk, sizeof(chunk));

        // No new UART data
        if (bytes_read <= 0) {
            return false;
        }

        // Add newly received bytes to persistent buffer
        m_rx_buf.append(chunk, bytes_read);

        bool found_valid = false;

        // Process every complete line currently in the buffer
        size_t newline_pos;

        while ((newline_pos = m_rx_buf.find('\n')) != std::string::npos) {

            std::string line =
                m_rx_buf.substr(0, newline_pos);

            // Remove the processed line from the buffer
            m_rx_buf.erase(0, newline_pos + 1);

            // Remove optional '\r'
            if (!line.empty() && line.back() == '\r') {
                line.pop_back();
            }

            // Must start with '$'
            if (line.empty() || line[0] != '$') {
                continue;
            }

            // Find '*'
            size_t star_pos = line.find('*');

            if (star_pos == std::string::npos) {
                continue;
            }

            // Extract message body
            std::string body =
                line.substr(1, star_pos - 1);

            // Extract CRC after '*'
            std::string provided_crc =
                line.substr(star_pos + 1);

            if (provided_crc.size() != 2) {
                continue;
            }

            // Calculate XOR CRC over message body
            uint8_t crc = 0;

            for (char c : body) {
                crc ^= static_cast<uint8_t>(c);
            }

            // Convert calculated CRC to 2-digit uppercase HEX
            std::ostringstream crc_stream;
            crc_stream << std::uppercase
                       << std::setfill('0')
                       << std::setw(2)
                       << std::hex
                       << static_cast<int>(crc);

            std::string expected_crc = crc_stream.str();

            // Reject corrupted message
            if (provided_crc != expected_crc) {
                continue;
            }

            // Split body using commas
            std::istringstream ss(body);
            std::string token;
            std::vector<std::string> tokens;

            while (std::getline(ss, token, ',')) {
                tokens.push_back(token);
            }

            // Expected:
            // ROVER, IMU, accel_x, accel_y, yaw
            if (tokens.size() < 5 ||
                tokens[0] != "ROVER" ||
                tokens[1] != "IMU") {
                continue;
            }

            try {
                imu.accel_x = std::stof(tokens[2]);
                imu.accel_y = std::stof(tokens[3]);
                imu.yaw     = std::stof(tokens[4]);

                found_valid = true;
            }
            catch (...) {
                continue;
            }
        }

        return found_valid;
    }

private:
    int m_can_fd = -1;
    int m_serial_fd = -1;
    std::string m_can_if;
    std::string m_serial_port;
    std::string m_rx_buf;
};

int main(int argc, char** argv) {
    std::string can_if = "vcan0";
    std::string serial_port = "/tmp/ttyV0";

    if (argc > 1) can_if = argv[1];
    if (argc > 2) serial_port = argv[2];

    std::cout << "==========================================================" << std::endl;
    std::cout << "  Inter IIT Tech Meet: Task 2 Candidate HAL Driver        " << std::endl;
    std::cout << "==========================================================" << std::endl;

    CandidateHardwareDriver driver;
    if (!driver.init(can_if, serial_port)) {
        std::cerr << "[HAL Driver] Driver initialization failed. Check bus setup and emulator!" << std::endl;
        return 1;
    }

    std::cout << "[HAL Driver] Driver initialized. Running control loop..." << std::endl;

    double t = 0.0;
    while (true) {
        // Actuation test
        float target_v = static_cast<float>(2.0 * std::sin(t));
        for (uint8_t id = 1; id <= 4; ++id) {
            driver.sendMotorVelocity(id, target_v);
        }

        // Read feedback
        MotorState m_st;
        while (driver.readEncoderFeedback(m_st)) {
            std::cout << "[HAL Driver] Encoder Feedback Motor " << (int)m_st.motor_id 
                      << " Pos: " << m_st.position << std::endl;
        }

        // Read IMU telemetry
        ImuData imu;
        if (driver.readImuTelemetry(imu)) {
            std::cout << "[HAL Driver] IMU Telemetry -> AccelX: " << imu.accel_x 
                      << ", AccelY: " << imu.accel_y << ", Yaw: " << imu.yaw << std::endl;
        }

        t += 0.01;
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    return 0;
}
