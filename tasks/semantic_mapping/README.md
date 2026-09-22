# Semantic Mapping of an Indoor Environment (PS 02)

This repository contains the complete autonomous vision and semantic mapping pipeline for **Problem Statement 02 (Perception - Semantic Mapping)**. The pipeline runs on TurtleBot3 in Gazebo Sim (`turtlebot3_house` world), processes RGB-D imagery, performs real-time instance segmentation, computes the ground contact base point for each object detected, eliminates duplicate object sightings via spatial-semantic gating, and exports structured semantic maps.

---

## Key Features

* **Strict Adherence to Contest Rules**: No pre-built maps were used, no reading coordinates from Gazebo world files. The map starts from zero on every run.
* **Edge-Deployable Architecture**: Designed keeping in mind the Jetson Nano / Raspberry Pi 4 compute constraints (Peak RAM $\approx 380\text{ MB}$, well under the 8 GB limit; throughput $> 18\text{ FPS}$ on ARM, $> 45\text{ FPS}$ on GPU).
* **Instance Segmentation vs. just boxes**: Uses **YOLOv8n-seg** pixel masks via the `ultralytics` framework (v8.0+) to extract only genuine object depth, eliminating background wall and floor contamination. 
* **3D Geometric Validation (Sensor Fusion)**: We do not blindly trust 2D AI predictions. The pipeline actively fuses YOLO's 2D semantic labels with deterministic 3D bounding-box geometry derived from the depth camera. If YOLO hallucinates a "chair" on a flat wall, the physical height/width constraint mathematically rejects it. If an object is misclassified due to dataset limitations, its 3D physical volume (height/width) is used to mathematically intercept and correct the label (e.g., distinguishing a tall Cupboard from a medium Mailbox).
* **Huge Mistake Acknowledgment (The COCO Dataset)**: We chose to use the pre-trained COCO dataset (80 real-world classes). This was a **huge mistake** because we did not cross-check the vocabulary against the actual objects in the Gazebo `turtlebot3_house` world. Crucial world objects like the `Mail box`, `dustbin`, and `Cupboard` literally do not exist in the COCO dataset, making it mathematically impossible for the neural network to detect them natively. We should have used a synthetic simulator dataset instead. While we successfully engineered a 3D Sensor Fusion workaround to correct these hallucinations dynamically, forcing explicit geometric bounds to compensate for missing AI vocabulary remains a major architectural drawback.
* **Floor-Contact Base Point Calculation**: Computes the exact 3D location where each object meets the floor $(X, Y, Z=0.0)$ for direct navigation stack readiness.
* **Robust Deduplication & Tracking**: Spatial-semantic gating ($D_{thresh}$) combined with weighted recursive position filtering and a temporal persistence buffer ($K \ge 3$) prevents duplicate entries when revisiting objects.
* **Live RViz Visualization**: Visualizes 3D bounding footprints, class-colored base cylinders, and interactive text labels in real time.

---

## The list of all deliverables in this Directory are as follows

* [`design_note.md`](./design_note.md): Full technical and logical answers of the 5 main coordinate questions as mentioned in the Software.pdf. 
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

**⚠️ CRITICAL STEP: Custom Waffle Model**
The default TurtleBot3 Waffle model lacks a proper RGBD camera and has a `cmd_vel` bridging bug in Gazebo. We have provided the fixed `model.sdf` in this repository. You **must** replace the default model before launching:
```bash
# Assuming turtlebot3_simulations is installed in your workspace's src folder:
cp models_backup/model.sdf ~/turtlebot3_ws/src/turtlebot3_simulations/turtlebot3_gazebo/models/turtlebot3_waffle/model.sdf
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
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

### 4. Output Verification
When exploration is finished, the pipeline automatically writes `semantic_map.json` and prints the human-readable summary, an example of the output generated is given below:
```text
=== SEMANTIC MAP SUMMARY ===
7 objects — sofa (1.2, 3.4), dining table (-0.5, 2.1), chair (-0.8, 1.9), bed (4.2, 0.8), tv (2.1, -1.5), refrigerator (3.1, -2.4), trash can (-1.8, 0.4)
============================
```

### 5. File by File Reference
Here is a simple breakdown of the main files in this project and what each one does. This acts as our architecture flow from start to finish:

1. **`turtlebot3_house.launch.py` (Gazebo Simulation):** This creates the virtual house and puts our TurtleBot3 Waffle robot inside it.
2. **`teleop_twist_keyboard` (Teleoperation Node):** This node allows you to drive the robot around using your keyboard while it explores the house.
3. **`/camera/image_raw` & `/camera/depth_image` (ROS Topics):** As the robot drives, the camera constantly broadcasts normal color pictures and depth (distance) pictures over these topics.
4. **`semantic_mapper_node.py` (Core AI & Mapping Script):** This is the brain of the project. 
   - It listens to the camera topics.
   - It feeds the color image into the **YOLOv8n-seg model**, which outlines and labels the objects.
   - It overlays the mask onto the depth image to get the exact 3D distance to the object (Pixel Masking).
   - It uses a Math Transform (TF Matrix) to convert that camera distance into a floor coordinate on the map.
   - It handles deduplication (if it sees the same sofa twice, it averages the position).
   - It writes the final list of objects to our JSON file.
5. **`print_map.py` (Map Viewer Script):** This script reads the `semantic_map.json` file and prints out a clean, one-line summary in your terminal.
6. **`semantic_map.json` (Data Storage):** The final output file containing the exact floor coordinates (Base Points) of every piece of furniture the robot found.

### 6. Video demonstration Link 
 https://youtu.be/1pqi_4Y6CrU

