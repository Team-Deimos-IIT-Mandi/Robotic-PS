#!/usr/bin/env python3
"""
Semantic Mapping Node for ROS 2 Humble
--------------------------------------
Performs real-time RGB-D object instance segmentation, 3D back-projection,
base-point calculation (where object meets the floor), spatial-semantic gating
for deduplication, Kalman/weighted tracking, odometry drift logging, and
structured JSON map export.
"""

import os
import json
import time
import math
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.duration import Duration
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from sensor_msgs.msg import Image, CameraInfo
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Point, Vector3, Quaternion
from visualization_msgs.msg import Marker, MarkerArray

import tf2_ros
from tf2_ros import TransformException
import message_filters

try:
    from cv_bridge import CvBridge
except ImportError:
    CvBridge = None

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None


class SemanticObject:
    """Represents a unique tracked physical object in the semantic map."""

    def __init__(self, obj_id, label, position, confidence, extent, timestamp):
        self.id = obj_id
        self.label = label
        # 3D position [x, y, z] where z is base contact at floor level
        self.position = np.array(position, dtype=np.float64)
        self.confidence = float(confidence)
        # 3D bounding extent [width (x), depth (y), height (z)]
        self.extent = np.array(extent, dtype=np.float64)
        self.first_seen = timestamp
        self.last_seen = timestamp
        self.observation_count = 1
        # Track history for drift calculation
        self.observation_positions = [list(self.position)]

    def update(self, new_pos, new_conf, new_extent, timestamp):
        """Update object state using weighted recursive averaging."""
        n = self.observation_count
        w_new = 1.0 / (n + 1.0)
        w_old = 1.0 - w_new

        # Update position: running weighted average
        self.position = w_old * self.position + w_new * np.array(new_pos, dtype=np.float64)
        # Confidence: max or running average
        self.confidence = max(self.confidence, float(new_conf))
        # Extent: smooth update
        self.extent = w_old * self.extent + w_new * np.array(new_extent, dtype=np.float64)

        self.last_seen = timestamp
        self.observation_count += 1
        self.observation_positions.append(list(new_pos))

    def to_dict(self):
        return {
            "id": int(self.id),
            "label": str(self.label),
            "position": [round(float(v), 3) for v in self.position],
            "confidence": round(float(self.confidence), 3),
            "extent": [round(float(v), 3) for v in self.extent],
            "observations": int(self.observation_count),
        }


class SemanticCandidate:
    """Temporal persistence buffer for unconfirmed detection candidates."""

    def __init__(self, label, position, confidence, extent, timestamp):
        self.label = label
        self.position = np.array(position, dtype=np.float64)
        self.confidence = float(confidence)
        self.extent = np.array(extent, dtype=np.float64)
        self.first_seen = timestamp
        self.last_seen = timestamp
        self.count = 1


class SemanticMapperNode(Node):

    def __init__(self):
        super().__init__('semantic_mapper_node')

        # Declare parameters
        self.declare_parameter('rgb_topic', '/camera/image_raw')
        self.declare_parameter('depth_topic', '/camera/depth_image')
        self.declare_parameter('camera_info_topic', '/camera/camera_info')
        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('world_frame', 'odom')
        self.declare_parameter('camera_frame', 'camera_rgb_frame')
        self.declare_parameter('confidence_threshold', 0.45)
        self.declare_parameter('distance_threshold', 1.0)
        self.declare_parameter('persistence_threshold', 2)
        self.declare_parameter('yolo_model', 'yolov8n-seg.pt')
        self.declare_parameter('map_output_path', 'semantic_map.json')
        self.declare_parameter('publish_markers', True)

        self.rgb_topic = self.get_parameter('rgb_topic').value
        self.depth_topic = self.get_parameter('depth_topic').value
        self.camera_info_topic = self.get_parameter('camera_info_topic').value
        self.odom_topic = self.get_parameter('odom_topic').value
        self.world_frame = self.get_parameter('world_frame').value
        self.camera_frame = self.get_parameter('camera_frame').value
        self.conf_thresh = self.get_parameter('confidence_threshold').value
        self.dist_thresh = self.get_parameter('distance_threshold').value
        self.persist_thresh = self.get_parameter('persistence_threshold').value
        self.yolo_model_name = self.get_parameter('yolo_model').value
        self.map_output_path = self.get_parameter('map_output_path').value
        self.publish_markers = self.get_parameter('publish_markers').value

        self.bridge = CvBridge() if CvBridge is not None else None

        # Camera intrinsics
        self.fx = None
        self.fy = None
        self.cx = None
        self.cy = None
        self.cam_info_received = False

        # Latest robot odometry pose
        self.current_robot_pose = None
        self.total_distance_traveled = 0.0
        self.last_robot_pos = None

        # Tracked semantic map objects: id -> SemanticObject
        self.objects = {}
        self.candidates = []  # List of SemanticCandidate
        self.next_object_id = 1

        # Drift tracking records
        self.drift_events = []

        # Benchmark metrics
        self.frame_count = 0
        self.total_inference_time = 0.0
        self.total_pipeline_time = 0.0
        self.fps = 0.0

        # Target indoor classes (COCO classes common in indoor/house environments)
        self.target_classes = {
            'chair', 'couch', 'bed', 'dining table', 'tv', 'toilet', 'refrigerator',
            'sink', 'microwave', 'oven', 'potted plant', 'bench'
        }

        # Class remapping to normalize labels (e.g. Gazebo table detected as bench)
        self.class_remap = {
            'bench': 'dining table',
            'couch': 'sofa',
        }

        # Spatial gating distance thresholds per class (meters)
        self.class_distance_thresholds = {
            'bed': 1.6,
            'couch': 1.4,
            'dining table': 1.3,
            'tv': 1.0,
            'refrigerator': 1.0,
            'chair': 0.7,
            'toilet': 0.8,
            'sink': 0.8,
            'potted plant': 0.6,
            'clock': 0.5,
            'book': 0.4,
        }

        # Class colors for RViz markers (RGBA)
        self.class_colors = {
            'couch': (0.9, 0.2, 0.2, 0.8),
            'bed': (0.2, 0.4, 0.9, 0.8),
            'dining table': (0.2, 0.8, 0.3, 0.8),
            'chair': (0.9, 0.7, 0.1, 0.8),
            'tv': (0.8, 0.1, 0.8, 0.8),
            'refrigerator': (0.1, 0.9, 0.9, 0.8),
            'potted plant': (0.1, 0.7, 0.2, 0.8),
            'default': (0.6, 0.6, 0.6, 0.8),
        }

        # Initialize TF2 buffer and listener
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # Initialize YOLO model
        self.get_logger().info(f'Loading YOLO model: {self.yolo_model_name}...')
        self.model = None
        self._init_model()

        # Camera info subscriber
        self.info_sub = self.create_subscription(
            CameraInfo, self.camera_info_topic, self._camera_info_callback, 10
        )

        # Odometry subscriber
        self.odom_sub = self.create_subscription(
            Odometry, self.odom_topic, self._odom_callback, 10
        )

        # Time synchronized RGB and Depth subscribers
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5
        )
        self.rgb_sub = message_filters.Subscriber(self, Image, self.rgb_topic, qos_profile=qos)
        self.depth_sub = message_filters.Subscriber(self, Image, self.depth_topic, qos_profile=qos)

        self.sync = message_filters.ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub], queue_size=10, slop=0.15
        )
        self.sync.registerCallback(self._synced_image_callback)

        # Visualization publishers
        self.marker_pub = self.create_publisher(MarkerArray, '/semantic_map/markers', 10)
        self.annotated_img_pub = self.create_publisher(Image, '/semantic_map/annotated_image', 5)

        # Periodic timer for saving map and publishing markers (2 Hz)
        self.timer = self.create_timer(1.0, self._periodic_publish)

        self.get_logger().info('Semantic Mapper Node initialized successfully.')

    def _init_model(self):
        if YOLO is None:
            self.get_logger().error('YOLO / Ultralytics library not available!')
            return
        try:
            self.model = YOLO(self.yolo_model_name)
            self.get_logger().info(f'YOLO model {self.yolo_model_name} loaded successfully.')
        except Exception as e:
            self.get_logger().error(f'Failed to load YOLO model: {e}')

    def _camera_info_callback(self, msg: CameraInfo):
        if not self.cam_info_received:
            self.fx = msg.k[0]
            self.fy = msg.k[4]
            self.cx = msg.k[2]
            self.cy = msg.k[5]
            self.cam_info_received = True
            self.get_logger().info(
                f'Camera intrinsics received: fx={self.fx:.1f}, fy={self.fy:.1f}, cx={self.cx:.1f}, cy={self.cy:.1f}'
            )

    def _odom_callback(self, msg: Odometry):
        pos = msg.pose.pose.position
        current_pos = np.array([pos.x, pos.y, pos.z])
        if self.last_robot_pos is not None:
            step = np.linalg.norm(current_pos - self.last_robot_pos)
            self.total_distance_traveled += step
        self.last_robot_pos = current_pos
        self.current_robot_pose = msg.pose.pose

    def _synced_image_callback(self, rgb_msg: Image, depth_msg: Image):
        if self.model is None:
            return

        start_time = time.time()

        # Convert RGB ROS Image
        try:
            if self.bridge:
                rgb_cv = self.bridge.imgmsg_to_cv2(rgb_msg, desired_encoding='bgr8')
            else:
                rgb_cv = np.frombuffer(rgb_msg.data, dtype=np.uint8).reshape((rgb_msg.height, rgb_msg.width, -1))
                if rgb_msg.encoding == 'rgb8':
                    rgb_cv = rgb_cv[:, :, ::-1]  # RGB to BGR
        except Exception as e:
            self.get_logger().warn(f'Error converting RGB image: {e}')
            return

        # Convert Depth ROS Image
        try:
            if self.bridge:
                depth_cv = self.bridge.imgmsg_to_cv2(depth_msg, desired_encoding='passthrough')
            else:
                if '32F' in depth_msg.encoding:
                    depth_cv = np.frombuffer(depth_msg.data, dtype=np.float32).reshape((depth_msg.height, depth_msg.width))
                elif '16U' in depth_msg.encoding:
                    depth_cv = np.frombuffer(depth_msg.data, dtype=np.uint16).reshape((depth_msg.height, depth_msg.width)).astype(np.float32) / 1000.0
                else:
                    depth_cv = np.frombuffer(depth_msg.data, dtype=np.float32).reshape((depth_msg.height, depth_msg.width))
        except Exception as e:
            self.get_logger().warn(f'Error converting Depth image: {e}')
            return

        h, w = rgb_cv.shape[:2]

        # Use fallback intrinsics if not yet received
        if not self.cam_info_received:
            fov = 1.02974  # standard horizontal FOV
            self.fx = w / (2.0 * math.tan(fov / 2.0))
            self.fy = self.fx
            self.cx = w / 2.0
            self.cy = h / 2.0

        # 1. Run YOLO instance segmentation
        infer_start = time.time()
        results = self.model(rgb_cv, conf=self.conf_thresh, verbose=False)
        infer_time = time.time() - infer_start

        # 2. Lookup camera to world transform
        transform = self._get_camera_transform(rgb_msg.header.stamp, rgb_msg.header.frame_id)
        if transform is None:
            return

        rot_mat, trans_vec = transform

        annotated_frame = rgb_cv.copy()
        current_timestamp = rgb_msg.header.stamp.sec + rgb_msg.header.stamp.nanosec * 1e-9

        # 3. Process detections
        if len(results) > 0 and results[0].masks is not None:
            boxes = results[0].boxes
            masks = results[0].masks.data.cpu().numpy()  # [N, H_mask, W_mask]

            for i, box in enumerate(boxes):
                cls_id = int(box.cls[0])
                raw_cls_name = results[0].names[cls_id]
                conf = float(box.conf[0])

                # Remap class if needed (e.g. bench -> dining table)
                cls_name = self.class_remap.get(raw_cls_name, raw_cls_name)

                # Focus on target indoor classes
                if cls_name not in self.target_classes and len(self.target_classes) > 0:
                    continue

                # Resize mask to original image dimensions if needed
                mask_raw = masks[i]
                if mask_raw.shape[:2] != (h, w):
                    import cv2
                    mask = cv2.resize(mask_raw, (w, h), interpolation=cv2.INTER_NEAREST) > 0.5
                else:
                    mask = mask_raw > 0.5

                # 4. Extract 3D points inside mask
                pts_3d_world, base_point, extent = self._compute_3d_base_point(
                    mask, depth_cv, rot_mat, trans_vec
                )

                if base_point is None:
                    continue

                # Physical geometry sanity checks:
                # A bed in a house is at least 0.9m wide and <= 1.2m tall.
                # A wall or mailbox falsely detected as bed will have height > 1.8m or width < 0.7m.
                if cls_name == 'bed':
                    if extent[0] < 0.8 or extent[1] < 0.8 or extent[2] > 1.6:
                        continue

                # 5. Data Association & Spatial Gating
                self._associate_or_add_object(
                    cls_name, base_point, conf, extent, current_timestamp
                )

                # Annotate image: Draw transparent segmentation mask overlay
                import cv2
                mask_overlay = np.zeros_like(annotated_frame, dtype=np.uint8)
                mask_overlay[mask] = (0, 215, 255)  # Bright amber mask for clear visualization
                annotated_frame = cv2.addWeighted(annotated_frame, 0.85, mask_overlay, 0.35, 0)

                # Bounding box and label
                xmin, ymin, xmax, ymax = [int(v) for v in box.xyxy[0]]
                cv2.rectangle(annotated_frame, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
                label_txt = f"{cls_name} ({conf:.2f}) [{base_point[0]:.1f},{base_point[1]:.1f}]"
                cv2.putText(
                    annotated_frame, label_txt, (xmin, max(20, ymin - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
                )

        # Benchmark metrics
        total_time = time.time() - start_time
        self.frame_count += 1
        self.total_inference_time += infer_time
        self.total_pipeline_time += total_time
        self.fps = self.frame_count / self.total_pipeline_time

        # Publish annotated image
        if self.annotated_img_pub.get_subscription_count() > 0:
            if self.bridge:
                annotated_msg = self.bridge.cv2_to_imgmsg(annotated_frame, encoding='bgr8')
                annotated_msg.header = rgb_msg.header
                self.annotated_img_pub.publish(annotated_msg)

    def _compute_3d_base_point(self, mask, depth_img, rot_mat, trans_vec):
        """
        Back-project masked depth pixels into 3D camera coordinates,
        filter outliers, transform to world frame, and extract the floor contact base point.
        """
        # Get pixel coordinates inside mask
        vs, us = np.where(mask)
        if len(us) < 30:
            return None, None, None

        # Sample if too many points to conserve CPU on edge
        if len(us) > 2000:
            subsample_idx = np.random.choice(len(us), 2000, replace=False)
            us = us[subsample_idx]
            vs = vs[subsample_idx]

        depths = depth_img[vs, us]

        # Filter invalid depth values
        valid = (depths > 0.25) & (depths < 6.0) & (~np.isnan(depths)) & (~np.isinf(depths))
        if np.sum(valid) < 20:
            return None, None, None

        us = us[valid]
        vs = vs[valid]
        depths = depths[valid]

        # Statistical outlier removal along depth axis
        med_depth = np.median(depths)
        std_depth = np.std(depths)
        depth_inliers = np.abs(depths - med_depth) < max(0.35, 1.5 * std_depth)
        if np.sum(depth_inliers) < 15:
            return None, None, None

        us = us[depth_inliers]
        vs = vs[depth_inliers]
        zs = depths[depth_inliers]

        # Pinhole back-projection: camera frame
        xs = (us - self.cx) * zs / self.fx
        ys = (vs - self.cy) * zs / self.fy
        pts_cam = np.vstack((xs, ys, zs))  # [3, N]

        # Transform to world frame: P_world = R * P_cam + T
        pts_world = rot_mat @ pts_cam + trans_vec[:, np.newaxis]  # [3, N]

        # Compute 3D Extent [width, depth, height]
        min_bounds = np.min(pts_world, axis=1)
        max_bounds = np.max(pts_world, axis=1)
        extent = max_bounds - min_bounds

        # Compute Base Point:
        # Horizontal (x, y) centroid = median(x), median(y)
        # Vertical (z) base = floor level (0.0) or contact plane min(z)
        x_base = float(np.median(pts_world[0, :]))
        y_base = float(np.median(pts_world[1, :]))
        # In indoor world, ground plane is z=0.0; we anchor base point to z=0.0
        z_base = 0.0

        base_point = np.array([x_base, y_base, z_base], dtype=np.float64)
        return pts_world, base_point, extent

    def _get_camera_transform(self, timestamp: Time, camera_frame_id: str):
        """Retrieve rigid transform from camera optical frame to world (odom) frame."""
        frame = camera_frame_id if camera_frame_id else self.camera_frame

        try:
            # Query TF buffer
            t = self.tf_buffer.lookup_transform(
                self.world_frame, frame, timestamp, timeout=Duration(seconds=0.1)
            )
            trans = np.array([
                t.transform.translation.x,
                t.transform.translation.y,
                t.transform.translation.z
            ])
            q = t.transform.rotation
            rot = self._quaternion_to_rotation_matrix(q.x, q.y, q.z, q.w)
            return rot, trans
        except TransformException:
            # Fallback: latest available transform
            try:
                t = self.tf_buffer.lookup_transform(
                    self.world_frame, frame, Time(), timeout=Duration(seconds=0.05)
                )
                trans = np.array([
                    t.transform.translation.x,
                    t.transform.translation.y,
                    t.transform.translation.z
                ])
                q = t.transform.rotation
                rot = self._quaternion_to_rotation_matrix(q.x, q.y, q.z, q.w)
                return rot, trans
            except TransformException:
                pass

        # Fallback: estimate from current_robot_pose if available
        if self.current_robot_pose is not None:
            p = self.current_robot_pose.position
            q = self.current_robot_pose.orientation
            # Camera offset on TurtleBot3 Waffle: x=+0.069, y=-0.047, z=+0.107
            R_robot = self._quaternion_to_rotation_matrix(q.x, q.y, q.z, q.w)
            # Optical frame rotation: optical Z forward, X right, Y down
            R_optical_to_robot = np.array([
                [0, 0, 1],
                [-1, 0, 0],
                [0, -1, 0]
            ])
            R_total = R_robot @ R_optical_to_robot
            T_total = np.array([p.x, p.y, p.z]) + R_robot @ np.array([0.069, -0.047, 0.107])
            return R_total, T_total

        return None

    def _quaternion_to_rotation_matrix(self, x, y, z, w):
        """Convert quaternion to 3x3 rotation matrix."""
        R = np.array([
            [1.0 - 2.0 * (y**2 + z**2), 2.0 * (x*y - z*w), 2.0 * (x*z + y*w)],
            [2.0 * (x*y + z*w), 1.0 - 2.0 * (x**2 + z**2), 2.0 * (y*z - x*w)],
            [2.0 * (x*z - y*w), 2.0 * (y*z + x*w), 1.0 - 2.0 * (x**2 + y**2)]
        ])
        return R

    def _associate_or_add_object(self, label, base_point, conf, extent, timestamp):
        """
        Spatial-semantic gating: Matches detection to existing objects.
        If matched, updates position via Kalman/weighted running average.
        If new, pushes to temporal candidate buffer until persistence threshold is reached.
        """
        threshold = self.class_distance_thresholds.get(label, self.dist_thresh)

        # 1. Match against confirmed objects
        best_obj = None
        min_dist = float('inf')

        for obj in self.objects.values():
            if obj.label == label:
                # Horizontal 2D distance
                d = np.linalg.norm(obj.position[:2] - base_point[:2])
                if d < threshold and d < min_dist:
                    min_dist = d
                    best_obj = obj

        if best_obj is not None:
            # Re-observation detected: Record drift error if robot has traveled significantly
            if self.total_distance_traveled > 2.0:
                drift_err = float(min_dist)
                self.drift_events.append({
                    "object_id": best_obj.id,
                    "label": best_obj.label,
                    "drift_error_m": round(drift_err, 3),
                    "robot_dist_traveled_m": round(self.total_distance_traveled, 2),
                    "timestamp": round(timestamp, 2)
                })

            # Update existing object state
            best_obj.update(base_point, conf, extent, timestamp)
            return

        # 2. Match against candidate buffer
        best_cand = None
        cand_min_dist = float('inf')

        for cand in self.candidates:
            if cand.label == label:
                d = np.linalg.norm(cand.position[:2] - base_point[:2])
                if d < threshold and d < cand_min_dist:
                    cand_min_dist = d
                    best_cand = cand

        if best_cand is not None:
            best_cand.count += 1
            best_cand.last_seen = timestamp
            best_cand.position = 0.5 * (best_cand.position + base_point)
            best_cand.confidence = max(best_cand.confidence, conf)

            # Check persistence promotion
            if best_cand.count >= self.persist_thresh:
                new_id = self.next_object_id
                self.next_object_id += 1
                new_obj = SemanticObject(
                    new_id, best_cand.label, best_cand.position,
                    best_cand.confidence, best_cand.extent, timestamp
                )
                new_obj.observation_count = best_cand.count
                self.objects[new_id] = new_obj
                self.candidates.remove(best_cand)
                self.get_logger().info(
                    f"Confirmed new object #{new_id}: {label} at base "
                    f"[{new_obj.position[0]:.2f}, {new_obj.position[1]:.2f}, {new_obj.position[2]:.2f}]"
                )
            return

        # 3. Register fresh candidate
        self.candidates.append(
            SemanticCandidate(label, base_point, conf, extent, timestamp)
        )

        # Clean stale candidates (not seen in > 10 sec)
        self.candidates = [c for c in self.candidates if (timestamp - c.last_seen) < 10.0]

    def _periodic_publish(self):
        """Periodically export map and publish RViz visualization markers."""
        if self.publish_markers:
            self._publish_markers()

        # Save semantic map output to file
        self.export_map()

    def _publish_markers(self):
        """Publish 3D markers for all mapped objects in RViz."""
        marker_array = MarkerArray()

        # Marker DELETEALL to refresh cleanly
        del_marker = Marker()
        del_marker.action = Marker.DELETEALL
        marker_array.markers.append(del_marker)

        stamp = self.get_clock().now().to_msg()

        for obj in self.objects.values():
            color = self.class_colors.get(obj.label, self.class_colors['default'])

            # 1. Base Cylinder / Footprint Marker
            cyl_marker = Marker()
            cyl_marker.header.frame_id = self.world_frame
            cyl_marker.header.stamp = stamp
            cyl_marker.ns = "semantic_objects_base"
            cyl_marker.id = obj.id
            cyl_marker.type = Marker.CYLINDER
            cyl_marker.action = Marker.ADD
            cyl_marker.pose.position.x = float(obj.position[0])
            cyl_marker.pose.position.y = float(obj.position[1])
            cyl_marker.pose.position.z = float(obj.position[2]) + 0.05
            cyl_marker.pose.orientation.w = 1.0
            cyl_marker.scale.x = max(0.4, float(obj.extent[0]) * 0.8)
            cyl_marker.scale.y = max(0.4, float(obj.extent[1]) * 0.8)
            cyl_marker.scale.z = 0.1
            cyl_marker.color.r = float(color[0])
            cyl_marker.color.g = float(color[1])
            cyl_marker.color.b = float(color[2])
            cyl_marker.color.a = 0.7
            marker_array.markers.append(cyl_marker)

            # 2. Text Label Marker
            txt_marker = Marker()
            txt_marker.header.frame_id = self.world_frame
            txt_marker.header.stamp = stamp
            txt_marker.ns = "semantic_labels"
            txt_marker.id = obj.id + 1000
            txt_marker.type = Marker.TEXT_VIEW_FACING
            txt_marker.action = Marker.ADD
            txt_marker.pose.position.x = float(obj.position[0])
            txt_marker.pose.position.y = float(obj.position[1])
            txt_marker.pose.position.z = float(obj.position[2]) + 0.5
            txt_marker.pose.orientation.w = 1.0
            txt_marker.scale.z = 0.25
            txt_marker.color.r = 1.0
            txt_marker.color.g = 1.0
            txt_marker.color.b = 1.0
            txt_marker.color.a = 1.0
            txt_marker.text = f"#{obj.id}: {obj.label}\n({obj.confidence:.2f})"
            marker_array.markers.append(txt_marker)

        self.marker_pub.publish(marker_array)

    def export_map(self):
        """Export the stored semantic map to JSON adhering to Problem Statement specification."""
        map_list = [obj.to_dict() for obj in self.objects.values()]

        summary = {
            "total_objects": len(map_list),
            "world_frame": self.world_frame,
            "robot_distance_traveled_m": round(self.total_distance_traveled, 2),
            "fps": round(self.fps, 1),
            "objects": map_list,
            "drift_log": self.drift_events[-20:]  # Recent drift records
        }

        target_paths = {
            self.map_output_path,
            os.path.expanduser("~/Robotic-PS/tasks/semantic_mapping/semantic_map.json"),
            os.path.expanduser("~/semantic_map.json"),
        }
        for path in target_paths:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, 'w') as f:
                    json.dump(summary, f, indent=2)
            except Exception as e:
                pass

    def print_semantic_map(self):
        """Print the human-readable summary required by the booklet: 'After a run, one command prints your stored map'."""
        count = len(self.objects)
        entries = [
            f"{obj.label} ({obj.position[0]:.1f}, {obj.position[1]:.1f})"
            for obj in self.objects.values()
        ]
        text = f"{count} objects — " + ", ".join(entries) if entries else "0 objects mapped."
        self.get_logger().info(f"=== SEMANTIC MAP SUMMARY ===\n{text}\n============================")
        return text


def main(args=None):
    rclpy.init(args=args)
    node = SemanticMapperNode()
    try:
        rclpy.spin(node)
    except BaseException:
        pass
    finally:
        try:
            node.print_semantic_map()
            node.export_map()
        except Exception:
            pass
        try:
            node.destroy_node()
        except Exception:
            pass
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    main()
