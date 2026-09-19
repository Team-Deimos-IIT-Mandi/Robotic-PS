# Semantic Mapping of an Indoor Environment (PS 02)

This repository contains the complete autonomous vision and semantic mapping pipeline for **Problem Statement 02 (Perception - Semantic Mapping)**. The pipeline runs on TurtleBot3 in Gazebo Sim (`turtlebot3_house` world), processes RGB-D imagery, performs real-time instance segmentation, computes ground contact base points, eliminates duplicate object sightings via spatial-semantic gating, and exports structured semantic maps.

---

## Key Features

* **Strict Adherence to Contest Rules**: No pre-built maps, no reading coordinates from Gazebo world files. The map starts from zero on every run.
* **Edge-Deployable Architecture**: Designed for Jetson Nano / Raspberry Pi 4 compute constraints (Peak RAM $\approx 380\text{ MB}$, well under the 8 GB limit; throughput $> 18\text{ FPS}$ on ARM, $> 45\text{ FPS}$ on GPU).
* **Instance Segmentation vs. Boxes**: Uses **YOLOv8n-seg** pixel masks to extract only genuine object depth, eliminating background wall and floor contamination.
* **Floor-Contact Base Point Calculation**: Computes the exact 3D location where each object meets the floor $(X, Y, Z=0.0)$ for direct navigation stack readiness.
* **Robust Deduplication & Tracking**: Spatial-semantic gating ($D_{thresh}$) combined with weighted recursive position filtering and a temporal persistence buffer ($K \ge 3$) prevents duplicate entries when revisiting objects.
* **Live RViz Visualization**: Visualizes 3D bounding footprints, class-colored base cylinders, and interactive text labels in real time.

---

## Deliverables in this Directory

* [`design_note.md`](./design_note.md): Full technical defense of the 5 core coordinate questions and interview viva preparation.
* [`benchmark_report.md`](./benchmark_report.md): End-to-end FPS, per-stage latency breakdown, RAM measurements, and day-by-day optimization changelog.
* [`semantic_map.json`](./semantic_map.json): Output structured JSON semantic map from a live run.
* [`package.xml`](./package.xml) & [`setup.py`](./setup.py): ROS 2 Humble package definitions.
* [`semantic_mapping/semantic_mapper_node.py`](./semantic_mapping/semantic_mapper_node.py): Core perception and mapping node.
* [`launch/semantic_mapping.launch.py`](./launch/semantic_mapping.launch.py): One-command launch script.

---

## Quick Start & Reproduction

### 1. Prerequisites
* Ubuntu 22.04 with ROS 2 Humble
* Gazebo Sim (Ignition / gz-sim 8+)
* Python packages: `ultralytics`, `torch`, `torchvision`, `cv_bridge`, `numpy`

```bash
pip install ultralytics torch torchvision
```

### 2. Build the ROS 2 Workspace
```bash
cd ~/turtlebot3_ws
colcon build --symlink-install --packages-select semantic_mapping
source install/setup.bash
```

### 3. Launch Simulation & Pipeline

**Terminal 1 — Launch Gazebo Small House Simulation:**
```bash
export TURTLEBOT3_MODEL=waffle
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
ros2 launch turtlebot3_gazebo turtlebot3_house.launch.py
```

**Terminal 2 — Launch Semantic Mapping & RViz:**
```bash
source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
ros2 launch semantic_mapping semantic_mapping.launch.py
```

**Terminal 3 — Teleoperate TurtleBot3 to Explore the House:**
```bash
source /opt/ros/humble/setup.bash
ros2 run turtlebot3_teleop teleop_keyboard
```

### 4. Output Verification
When exploration is finished, the pipeline automatically writes `semantic_map.json` and prints the human-readable summary:
```text
=== SEMANTIC MAP SUMMARY ===
7 objects — sofa (1.2, 3.4), dining table (-0.5, 2.1), chair (-0.8, 1.9), bed (4.2, 0.8), tv (2.1, -1.5), refrigerator (3.1, -2.4), trash can (-1.8, 0.4)
============================
```
