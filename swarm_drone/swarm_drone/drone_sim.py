
"""
Minimal 2D visualization/environment for the Drone Fleet PS.

IMPORTANT:
This file intentionally contains NO fleet-management logic and NO autonomous
drone movement. The user's simulation/controller is expected to update the
drone states.

The environment only:
- stores/accepts drone state
- stores/accepts package/target state
- draws the world in OpenCV
- optionally draws routes supplied by the user's simulator
- provides a simple keyboard-controlled demo ONLY for testing the renderer

For the actual project, call env.update_state(...) from your own simulation.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


WIDTH = 1200
HEIGHT = 760
MAP_W = 820
MAP_H = 700
PANEL_X = MAP_W

BASE = (MAP_W // 2, MAP_H // 2)
PAD_POSITIONS = [
    (BASE[0] - 80, BASE[1] + 70),
    (BASE[0],      BASE[1] + 70),
    (BASE[0] + 80, BASE[1] + 70),
]


@dataclass
class DroneState:
    id: int
    x: float
    y: float
    battery: float = 100.0
    status: str = "IDLE"
    payload: float = 0.0
    target: Optional[Tuple[float, float]] = None
    current_package: Optional[int] = None
    total_distance: float = 0.0
    total_flight_time: float = 0.0
    battery_capacity: float = 100.0
    cycle_count: int = 0
    cycle_energy: float = 0.0
    charging_pad: Optional[int] = None
    charge_start_time: Optional[float] = None
    charge_remaining: float = 0.0
    total_charge_wait_time: float = 0.0
    wait_start_time: Optional[float] = None
    target_battery: float = 100.0
    preparation_package: Optional[int] = None
    charging_managed: bool = False
    low_battery_wait_since: Optional[float] = None
    recovery_charging: bool = False
    recovery_package: Optional[int] = None
    charging_basis: Optional[dict] = None


@dataclass
class PackageState:
    id: int
    x: float
    y: float
    weight: float = 0.0
    request_time: float = 0.0
    deadline: float = 0.0
    assigned_drone: Optional[int] = None
    delivered: bool = False
    status: str = "PENDING"
    delivered_at: Optional[float] = None
    outcome_reason: Optional[str] = None
    decision_history: list = None

    def __post_init__(self):
        if self.decision_history is None:
            self.decision_history = []


class Drone2DEnvironment:
    """
    Passive visualization environment.

    No physics, movement, assignment, charging, battery drain, deadlines,
    failure handling, or package generation is implemented here.
    """

    def __init__(self, num_drones: int = 10):
        self.num_drones = num_drones

        # Initial state only. Nothing moves unless update_state() is called.
        self.drones: Dict[int, DroneState] = {
            i: DroneState(
                id=i,
                x=float(BASE[0]),
                y=float(BASE[1]),
            )
            for i in range(1, num_drones + 1)
        }

        self.packages: Dict[int, PackageState] = {}
        self.pad_occupancy: List[Optional[int]] = [None] * len(PAD_POSITIONS)

        # Optional routes supplied by user's simulator:
        # {drone_id: [(x1,y1), (x2,y2), ...]}
        self.routes: Dict[int, List[Tuple[float, float]]] = {}

        self.message = "Waiting for external simulation state..."
        self.playback_info = {}

    def update_state(
        self,
        drones: Dict[int, DroneState],
        packages: Optional[Dict[int, PackageState]] = None,
        pad_occupancy: Optional[List[Optional[int]]] = None,
        routes: Optional[Dict[int, List[Tuple[float, float]]]] = None,
        message: Optional[str] = None,
        playback_info: Optional[dict] = None,
    ):
        """
        Replace the rendered state with state produced by YOUR simulator.

        This method does not calculate anything.
        """
        self.drones = drones

        if packages is not None:
            self.packages = packages

        if pad_occupancy is not None:
            self.pad_occupancy = pad_occupancy

        if routes is not None:
            self.routes = routes

        if message is not None:
            self.message = message
        if playback_info is not None:
            self.playback_info = playback_info

    def add_package(self, package: PackageState):
        """Convenience method for externally-created packages."""
        self.packages[package.id] = package

    def remove_package(self, package_id: int):
        self.packages.pop(package_id, None)

    def clear_routes(self):
        self.routes.clear()

    def draw(self) -> np.ndarray:
        frame = np.full((HEIGHT, WIDTH, 3), 245, dtype=np.uint8)

        # Map.
        cv2.rectangle(frame, (0, 0), (MAP_W, MAP_H), (235, 235, 235), -1)

        # Grid.
        for x in range(0, MAP_W, 50):
            cv2.line(frame, (x, 0), (x, MAP_H), (220, 220, 220), 1)
        for y in range(0, MAP_H, 50):
            cv2.line(frame, (0, y), (MAP_W, y), (220, 220, 220), 1)

        # Base.
        cv2.circle(frame, BASE, 26, (55, 55, 55), -1)
        cv2.putText(
            frame, "BASE",
            (BASE[0] - 25, BASE[1] - 36),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (30, 30, 30), 2
        )

        # Charging pads.
        for i, (x, y) in enumerate(PAD_POSITIONS):
            occupied = self.pad_occupancy[i] if i < len(self.pad_occupancy) else None
            cv2.rectangle(
                frame,
                (x - 20, y - 14),
                (x + 20, y + 14),
                (100, 100, 100) if occupied is None else (80, 160, 80),
                -1,
            )
            label = f"P{i + 1}"
            if occupied is not None:
                label += f":D{occupied}"
            cv2.putText(
                frame, label, (x - 18, y + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1
            )

        # Packages.
        for pkg in self.packages.values():
            if pkg.delivered or pkg.status in ("REJECTED", "EXPIRED"):
                continue

            x, y = int(pkg.x), int(pkg.y)
            cv2.drawMarker(
                frame, (x, y), (80, 80, 220),
                cv2.MARKER_DIAMOND, 18, 3
            )
            cv2.putText(
                frame,
                f"P{pkg.id} {pkg.weight:.1f}kg",
                (x + 8, y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (50, 50, 50), 1
            )

        # Routes supplied by external simulator.
        for drone_id, points in self.routes.items():
            if drone_id not in self.drones or len(points) < 2:
                continue

            pts = np.array(points, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], False, (170, 170, 170), 1)

        # Drones.
        for drone in self.drones.values():
            x, y = int(drone.x), int(drone.y)

            if drone.status == "IDLE":
                color = (70, 160, 70)
            elif drone.status in ("DELIVERY", "FLYING"):
                color = (220, 140, 40)
            elif drone.status in ("RETURNING", "RETURN"):
                color = (180, 100, 180)
            elif drone.status == "CHARGING":
                color = (80, 180, 200)
            elif drone.status in ("FAILED", "OFFLINE"):
                color = (50, 50, 220)
            else:
                color = (100, 100, 100)

            cv2.circle(frame, (x, y), 13, color, -1)
            cv2.circle(frame, (x, y), 13, (30, 30, 30), 1)

            cv2.putText(
                frame, f"D{drone.id}",
                (x - 10, y + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1
            )

            # Battery visualization is passive; the value comes from the caller.
            fill = max(0, min(34, int(34 * drone.battery / 100.0)))
            cv2.rectangle(
                frame, (x - 17, y + 17), (x + 17, y + 22),
                (150, 150, 150), -1
            )
            cv2.rectangle(
                frame, (x - 17, y + 17), (x - 17 + fill, y + 22),
                (70, 180, 70) if drone.battery > 30 else (70, 70, 220),
                -1
            )

        self._draw_panel(frame)
        return frame

    def _draw_panel(self, frame):
        x = MAP_W + 15
        y = 30

        cv2.putText(
            frame, "DRONE 2D ENVIRONMENT",
            (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (25, 25, 25), 2
        )
        y += 32

        cv2.putText(
            frame, self.message[:44],
            (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (90, 90, 90), 1
        )
        y += 28

        cv2.putText(
            frame, "DRONES",
            (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (30, 30, 30), 2
        )
        y += 24

        for drone in self.drones.values():
            line = (
                f"D{drone.id:02d} "
                f"{drone.status:<9} "
                f"{drone.battery:5.1f}%"
            )
            cv2.putText(
                frame, line, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (70, 70, 70), 1
            )
            y += 18

        y += 24
        for status in ("PENDING", "ASSIGNED", "REJECTED", "EXPIRED", "DELIVERED_ON_TIME", "DELIVERED_LATE"):
            count = sum(p.status == status for p in self.packages.values())
            cv2.putText(frame, f"{status}: {count}", (x, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (70, 70, 70), 1)
            y += 20

        for label, count in (
            ("REQUESTS RECEIVED", len(self.packages)),
            ("AIRBORNE", sum(d.status in ("DELIVERY", "RETURNING") for d in self.drones.values())),
            ("CHARGING", sum(d.status == "CHARGING" for d in self.drones.values())),
            ("CHARGING QUEUE", sum(d.status == "WAITING_FOR_CHARGE" for d in self.drones.values())),
        ):
            cv2.putText(frame, f"{label}: {count}", (x, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (70, 70, 70), 1)
            y += 20

        if self.playback_info:
            elapsed = int(self.playback_info["real_seconds"])
            lines = (f"REAL ELAPSED: {elapsed // 60:02d}:{elapsed % 60:02d}",
                     f"ACTUAL SPEED: {self.playback_info['actual_speed']:.2f}x")
            for line in lines:
                cv2.putText(frame, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.38, (70, 70, 70), 1)
                y += 20

        y = HEIGHT - 62
        cv2.putText(
            frame,
            "Q / ESC  quit",
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, (70, 70, 70), 1
        )
        cv2.putText(
            frame,
            "Clock and outcomes supplied by simulator",
            (x, y + 18),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, (70, 70, 70), 1
        )

    def run(self):
        """
        Renderer-only loop.

        It intentionally does not update drone positions.
        """
        cv2.namedWindow("Drone 2D Environment", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Drone 2D Environment", WIDTH, HEIGHT)

        while True:
            cv2.imshow("Drone 2D Environment", self.draw())
            key = cv2.waitKey(30) & 0xFF

            if key in (ord("q"), ord("Q"), 27):
                break

        cv2.destroyAllWindows()


def demo_renderer():
    """
    Small renderer test.

    All drones remain stationary. This is NOT a simulator/controller.
    Replace this function with your own simulation loop.
    """
    env = Drone2DEnvironment(num_drones=10)

    # Start all drones at the base.
    drones = {}

    for i in range(1, 11):
        drones[i] = DroneState(
            id=i,
            x=float(BASE[0]),
            y=float(BASE[1]),
            battery=100.0,
            status="IDLE",
            payload=0.0,
            target=None
        )

    env.update_state(
        drones=drones,
        message="All drones at base"
    )

    env.run()


if __name__ == "__main__":
    demo_renderer()
