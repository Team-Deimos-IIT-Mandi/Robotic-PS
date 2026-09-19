# Inter IIT Tech Meet: Autonomous Vehicle Kinodynamic Simulator

This repository contains a C++ simulator designed to test motion planning and control algorithms for non-holonomic mobile robots (car-like Ackermann steering vehicles).

The simulator models vehicle dynamics in a $100\text{m} \times 100\text{m}$ grid environment and provides real-time state telemetry and occupancy maps over a TCP socket interface.

**Demo Video:** [https://youtu.be/oAvbw1vUkfA](https://youtu.be/oAvbw1vUkfA)

---

## Task Overview

Your objective is to write an autonomous path planning and control algorithm in C++ that connects to the simulator over TCP, receives map and pose data, plans a collision-free path to the goal pose, and streams control commands ($v, \delta$) back to navigate the vehicle safely.

### Constraints & Vehicle Model
1. **Non-Holonomic Constraints**: The car cannot move sideways. Motion is governed by the Ackermann kinematic bicycle model.
2. **Steering Bounds**: Maximum steering angle $\delta_{max} = 0.60\text{ rad} \approx 34.3^\circ$.
3. **Minimum Turning Radius**: $R_{min} = L_w / \tan(\delta_{max}) \approx 3.7\text{ meters}$ (Wheelbase $L_w = 2.5\text{m}$).
4. **Collision Detection**: The vehicle body size is $4.0\text{m} \times 1.8\text{m}$. Collisions are checked against oriented bounding boxes (OBB).

---

## Available Scenarios

| Scenario ID | Name | Description |
| :---: | :--- | :--- |
| **0** | **Street Parallel Parking** | Parallel park into a tight slot between two parked vehicles along a curb. |
| **1** | **Parking Lot Bay** | Park into a perpendicular bay in a parking lot with tight aisles. |
| **2** | **Slalom Track** | Navigate through an obstacle course track. |
| **3** | **Multi-Goal Navigation** | Navigate sequentially to multiple goal waypoints. |

---

## TCP Communication Protocol

The simulator runs a TCP server on port `8091`.

### 1. Request Configuration (`Client -> Server`)
Send string `Q\n` to receive initial pose, goal pose, vehicle parameters, and grid map:
- Response format:
  - `CONFIG <start_x> <start_y> <start_yaw> <goal_x> <goal_y> <goal_yaw> <len> <width> <wheelbase> <max_steer> <max_speed> <min_speed> <map_w> <map_h> <res> <orig_x> <orig_y> <cols> <rows>`
  - `WAYPOINTS <count> <x_0> <y_0> ... <x_N> <y_N>` (`count` is zero outside Scenario 3)
  - `GRID <num_cells> <val_0> <val_1> ... <val_N>` (0 = Free, 1 = Obstacle)

### 2. Stream Controls (`Client -> Server`)
Send control commands at 20 Hz:
- Format: `CTRL <target_speed_m_s> <target_steering_angle_rad>\n`
- Example: `CTRL 1.2 -0.25\n`

### 3. Upload Trajectory Visualization (`Client -> Server`)
- Format: `TRAJ <x1> <y1> <yaw1> <v1>;<x2> <y2> <yaw2> <v2>;...\n`
- TCP packets are not messages: the server buffers until the newline and then
  replaces the displayed path with the complete trajectory for the current leg.

### 4. Telemetry Stream (`Server -> Client`)
- Format: `TELEMETRY <step_count> <time_ms> <x> <y> <yaw> <v> <delta> <is_colliding> <is_goal_reached>`

### 5. Cancel a fully blocked intermediate waypoint (local extension)

- Request: `SKIP_WAYPOINT <1-based index>\n`.
- Reply: `WAYPOINT_SKIPPED <index>\n` or `WAYPOINT_SKIP_REJECTED <index>\n`.
- The car must be stopped, the requested waypoint must be the next unfinished
  waypoint, and its entire 1.2 m acceptance circle must contain no free map area.
  The final waypoint cannot be skipped. Both client and server check the map.
- Scenario 3 waypoint 7 at `(0, 0)` is inside a wall. After reaching waypoint 6,
  the client requests cancellation of 7, waits for confirmation, then plans to 8.
  The map and waypoint coordinates are unchanged. A skipped waypoint is drawn
  gray with a slash and is never reported as physically reached.
- Success requires all non-cancelled waypoints in order, plus the final position,
  heading and low-speed checks. Logs include the cancellation count. This is a
  user-requested local policy, not success under the original all-waypoints rule.

The client plans one complete leg at a time, stops at intermediate targets,
and sends zero-speed commands while planning the next leg. Rebuild **both**
executables together: the client now waits for `CONFIG`, `WAYPOINTS`, and `GRID`.

---

## Building and Running

### Prerequisites
- GCC / G++ 11+ (C++17)
- CMake 3.16+
- OpenCV 4 (`libopencv-dev`)

### Build Steps
```bash
cd ackermann_kinodynamic_sim
mkdir -p build && cd build
cmake ..
make -j4
```

### Running the Simulator
Launch the simulator with a chosen port, scenario ID, and optional time scale
(default `5`: five simulated seconds per real second):
```bash
./simulator_node 8091 0   # Scenario 0: Parallel Parking
./simulator_node 8091 1   # Scenario 1: Parking Lot Bay
./simulator_node 8091 2   # Scenario 2: Slalom Track
./simulator_node 8091 3 5 # Scenario 3: Multi-Goal Navigation at 5x speed
```

Use `./simulator_node 8091 3 1` for normal speed. The physics timestep stays
0.05 simulated seconds; only wall-clock pacing changes. At 5x the client must
keep up with approximately 100 telemetry/control updates per real second.
Requested speed is subject to the machine's rendering and processing capacity.

### Running the Client Template
In a separate terminal, run your client code:
```bash
./candidate_template 127.0.0.1 8091
```

Candidates should edit `apps/candidate_template.cpp` to implement their path planning and control logic.
