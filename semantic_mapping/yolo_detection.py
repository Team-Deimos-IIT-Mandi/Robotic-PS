import torch
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import Image,CameraInfo
from cv_bridge import CvBridge
from ultralytics import YOLO
from mobile_sam import sam_model_registry, SamPredictor
import numpy as np
import cv2
import mobileclip
from nav_msgs.msg import Odometry, OccupancyGrid
from PIL import Image as PILImage
from scipy.spatial.transform import Rotation
from message_filters import Subscriber, ApproximateTimeSynchronizer
from semantic_mapping.config import CONFIG
from semantic_mapping.local_object import LocalObject
from semantic_mapping.map_manager import MapManager
import tf2_ros
from tf2_ros import TransformException
from sklearn.cluster import DBSCAN
class YoloNode(Node):
    def __init__(self):
        super().__init__(
            'yolo_node',
            parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)]
        )
        self.map_manager = MapManager()
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.declare_parameter(
            'association_threshold',
            0.8
        )
        self.association_threshold = self.get_parameter(
            'association_threshold'
        ).value
        self.costmap=None
        self.costmap_resolution=None
        self.costmap_origin_x=None
        self.costmap_origin_y=None
        
        self.fx=None
        self.fy=None
        self.cx=None
        self.cy=None
        self.declare_parameter('global_frame', 'map')
        self.global_frame = self.get_parameter('global_frame').value
        self.declare_parameter('spawn_x', -2.0)
        self.declare_parameter('spawn_y', -0.5)
        self.spawn_x = self.get_parameter('spawn_x').value
        self.spawn_y = self.get_parameter('spawn_y').value
        self.rgb_sub = Subscriber(self, Image, CONFIG['rgb_topic'])
        self.depth_sub = Subscriber(self, Image, CONFIG['depth_topic'])
        self.odom_sub = Subscriber(self, Odometry, CONFIG['odom_topic'])
        self.sync = ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub, self.odom_sub],
            queue_size=CONFIG['sync_queue_size'],
            slop=CONFIG['sync_slop']
        )
        self.camera_translation = np.array(CONFIG['camera_translation'], dtype=np.float64)
        self.camera_rotation = np.array([
            [ 0.0,  0.0,  1.0],
            [-1.0,  0.0,  0.0],
            [ 0.0, -1.0,  0.0]
        ], dtype=np.float64)
        self.sync.registerCallback(self.synced_callback)
        self.costmap_sub = self.create_subscription(OccupancyGrid, '/global_costmap/costmap', self.costmap_callback, 10)
        self.occupancy_grid = None
        self.info_sub = self.create_subscription(CameraInfo, CONFIG['camera_info_topic'], self.info_callback, 10)
        self.merge_timer = self.create_timer(5.0, self.merge_timer_callback)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.clip_checkpoint = CONFIG['clip_checkpoint']
        self.clip_model, _, self.clip_preprocess = mobileclip.create_model_and_transforms(
            CONFIG['clip_model_name'],
            pretrained=self.clip_checkpoint,
            device=self.device
        )
        self.clip_model.eval()
        self.clip_tokenize = mobileclip.get_tokenizer(CONFIG['clip_model_name'])
        self.bridge = CvBridge()
        self.model = YOLO(CONFIG['yolo_checkpoint'])
        self.model.to(self.device)
        self.sam = sam_model_registry[CONFIG['sam_model_type']](checkpoint=CONFIG['sam_checkpoint'])
        self.sam.to(device=self.device)
        self.predictor = SamPredictor(self.sam)
        self.model.set_classes(CONFIG['yolo_classes'])
    def transform_points_from_odom(self, points_camera, odom_msg):
        translation=np.array([odom_msg.pose.pose.position.x,odom_msg.pose.pose.position.y,odom_msg.pose.pose.position.z],dtype=np.float64)
        quaternion=np.array([odom_msg.pose.pose.orientation.x,odom_msg.pose.pose.orientation.y,odom_msg.pose.pose.orientation.z,odom_msg.pose.pose.orientation.w],dtype=np.float64)
        rotation=Rotation.from_quat(quaternion)
        R_odom_base=rotation.as_matrix()
        R_base_camera=self.camera_rotation
        t_base_camera=self.camera_translation
        R_odom_camera=R_odom_base @ R_base_camera
        t_odom_camera=R_odom_base @ t_base_camera + translation
        points_odom = points_camera @ R_odom_camera.T + t_odom_camera
        return points_odom
    def apply_dbscan(self, points):
        if points is None or len(points) == 0:
            return None
        import open3d as o3d
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)

        labels = np.array(pcd.cluster_dbscan(eps=0.05, min_points=10, print_progress=False))
        
        valid_labels = labels[labels != -1]
        if len(valid_labels) == 0:
            return points
            
        largest_cluster = np.bincount(valid_labels).argmax()
        filtered_points = points[labels == largest_cluster]
        return filtered_points
        
    def merge_timer_callback(self):
        before = len(self.map_manager.objects)
        self.map_manager.merge_duplicates()
        after = len(self.map_manager.objects)
        if before != after:
            self.get_logger().info(f"[MapManager] Merged duplicates. Map size reduced from {before} to {after}")
    def costmap_callback(self, msg):
        self.costmap = msg
        self.costmap_resolution = msg.info.resolution
        self.costmap_origin_x = msg.info.origin.position.x
        self.costmap_origin_y = msg.info.origin.position.y
        width = msg.info.width
        height = msg.info.height
        self.costmap_data = np.array(msg.data).reshape((height, width))
        
    def get_safe_goal(self, obj_x, obj_y):
        if self.costmap is None:
            return None
            
        # Parentheses added to enforce correct order of operations!
        grid_x = int((obj_x - self.costmap_origin_x) / self.costmap_resolution)
        grid_y = int((obj_y - self.costmap_origin_y) / self.costmap_resolution)
        
        free_indices = np.argwhere(self.costmap_data == 0)
        if len(free_indices) == 0:
            return None
            
        target = np.array([grid_y, grid_x])
        distances = np.linalg.norm(free_indices - target, axis=1)
        nearest_idx = np.argmin(distances)
        nearest_cell = free_indices[nearest_idx]
        
        safe_x = (nearest_cell[1] * self.costmap_resolution) + self.costmap_origin_x + (self.costmap_resolution / 2.0)
        safe_y = (nearest_cell[0] * self.costmap_resolution) + self.costmap_origin_y + (self.costmap_resolution / 2.0)
        return (float(safe_x), float(safe_y))
    def mask_to_camera_points(self, mask, depth):
        if self.fx is None:
            return None
        ys,xs=np.where(mask)
        depth_value=depth[ys,xs]
        if depth.dtype == np.uint16:
            depth_value = depth_value.astype(np.float32) / 1000.0
        valid=(depth_value>0) & np.isfinite(depth_value)
        xs=xs[valid]
        ys=ys[valid]
        depth_value=depth_value[valid]
        z=depth_value
        x=(xs-self.cx)*z/self.fx
        y=(ys-self.cy)*z/self.fy
        return np.stack([x,y,z],axis=1)
    def info_callback(self,msg):
        self.fx=msg.k[0]
        self.fy=msg.k[4]
        self.cx=msg.k[2]
        self.cy=msg.k[5]
    def calculate_iou(self, box1, box2):
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        intersection_width = max(0, x2 - x1)
        intersection_height = max(0, y2 - y1)
        intersection_area = intersection_width * intersection_height
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union_area = area1 + area2 - intersection_area
        if union_area == 0:
            return 0
        return intersection_area / union_area
    def color_similarity(self, image, box1, box2):
        x1, y1, x2, y2 = map(int, box1[:4])
        crop1=image[y1:y2,x1:x2]
        x1, y1, x2, y2 = map(int, box2[:4])
        crop2 = image[y1:y2, x1:x2]
        if crop1.size==0 or crop2.size==0:
            return 0
        hist1=cv2.calcHist([crop1],[0,1,2],None,[8,8,8],[0,256,0,256,0,256])
        hist2=cv2.calcHist([crop2],[0,1,2],None,[8,8,8],[0,256,0,256,0,256])
        cv2.normalize(hist1,hist1)
        cv2.normalize(hist2,hist2)
        sim=cv2.compareHist(hist1,hist2,cv2.HISTCMP_CORREL)
        return sim
    def get_clip_features(self,image,box_xyxy,class_name):
        x1,y1,x2,y2=box_xyxy
        crop=image[int(y1):int(y2),int(x1):int(x2)]
        pil_image=PILImage.fromarray(cv2.cvtColor(crop,cv2.COLOR_BGR2RGB))
        processed_image=self.clip_preprocess(pil_image).unsqueeze(0).to(self.device)
        text=self.clip_tokenize([class_name]).to(self.device)
        with torch.no_grad():
            image_features=self.clip_model.encode_image(processed_image)
            text_features=self.clip_model.encode_text(text)
            image_features/=image_features.norm(dim=-1,keepdim=True)
            text_features/=text_features.norm(dim=-1,keepdim=True)
            final_feature=0.7*image_features+0.3*text_features
            final_feature=final_feature/final_feature.norm(dim=-1,keepdim=True)
            return final_feature
    def merge_boxes(self,image,boxes,iou_threshold=0.5,color_threshold=0.7):
        merged=True
        while merged:
            new_boxes=[]
            used=[False]*len(boxes)
            merged=False
            for i in range(len(boxes)):
                if used[i]:
                    continue
                current_box=boxes[i]
                used[i] = True
                for j in range(i+1,len(boxes)):
                    if used[j]:
                        continue
                    other_box=boxes[j]
                    iou=self.calculate_iou(current_box,other_box)
                    if iou>iou_threshold:
                        similarity=self.color_similarity(image,current_box,other_box)
                        if similarity>color_threshold:
                            best_class_id = other_box[4] if other_box[5] > current_box[5] else current_box[4]
                            best_conf = max(current_box[5], other_box[5])
                            current_box=[min(current_box[0],other_box[0]),min(current_box[1],other_box[1]),max(current_box[2],other_box[2]),max(current_box[3],other_box[3]), best_class_id, best_conf]
                            used[j]=True
                            merged=True
                new_boxes.append(current_box)
            boxes=new_boxes
        return boxes
    def synced_callback(self, rgb_msg, depth_msg,odom_msg):
        rgb_time = rgb_msg.header.stamp.sec + rgb_msg.header.stamp.nanosec * 1e-9
        depth_time = depth_msg.header.stamp.sec + depth_msg.header.stamp.nanosec * 1e-9
        odom_time = odom_msg.header.stamp.sec + odom_msg.header.stamp.nanosec * 1e-9
        frame = self.bridge.imgmsg_to_cv2(rgb_msg, desired_encoding='bgr8')
        depth = self.bridge.imgmsg_to_cv2(depth_msg, desired_encoding='passthrough')
        results = self.model(frame)
        boxes = []
        for box in results[0].boxes:
            confidence = float(box.conf[0])
            if confidence < 0.55:
                continue
            box_xyxy = box.xyxy[0].cpu().numpy()
            class_id = int(box.cls[0])
            boxes.append([
                float(box_xyxy[0]),
                float(box_xyxy[1]),
                float(box_xyxy[2]),
                float(box_xyxy[3]),
                class_id,
                confidence
            ])
        merged_boxes = self.merge_boxes(
            frame,
            boxes,
            iou_threshold=CONFIG['iou_threshold'],
            color_threshold=CONFIG['color_threshold']
        )
        visualization = frame.copy()
        if len(merged_boxes) > 0:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.predictor.set_image(rgb_frame)
            frame_objects = []
            for box_info in merged_boxes:
                points_odom = None
                box_xyxy = box_info[:4]
                class_id = int(box_info[4])
                confidence = float(box_info[5])
                masks, scores, logits = self.predictor.predict(
                    box=np.array(box_xyxy),
                    multimask_output=False
                )
                mask = masks[0]
                points_camera = self.mask_to_camera_points(mask, depth)
                class_name = self.model.names[class_id]
                if points_camera is not None and points_camera.shape[0] > 0:
                    points_odom = self.transform_points_from_odom(
                        points_camera,
                        odom_msg
                    )
                    points_map = None
                    if points_odom is not None:
                        try:
                            t = self.tf_buffer.lookup_transform(
                                self.global_frame,
                                'odom',
                                rclpy.time.Time()
                            )
                            translation = np.array([t.transform.translation.x, t.transform.translation.y, t.transform.translation.z])
                            rotation_quat = [t.transform.rotation.x, t.transform.rotation.y, t.transform.rotation.z, t.transform.rotation.w]
                            R_map_odom = Rotation.from_quat(rotation_quat).as_matrix()
                            points_map = points_odom @ R_map_odom.T + translation
                            points_map += np.array([self.spawn_x, self.spawn_y, 0.0])
                            points_map = self.apply_dbscan(points_map)
                            
                        except TransformException as ex:
                            self.get_logger().warn(f'Could not transform odom to {self.global_frame}: {ex}')
                            points_map = points_odom + np.array([self.spawn_x, self.spawn_y, 0.0])
                overlay = visualization.copy()
                overlay[mask] = (0, 255, 0)
                visualization = cv2.addWeighted(visualization, 0.7, overlay, 0.3, 0)
                x1, y1, x2, y2 = map(int, box_xyxy)
                cv2.rectangle(visualization, (x1, y1), (x2, y2), (255, 0, 0), 2)
                feature=self.get_clip_features(frame,box_xyxy,class_name)
                if points_map is not None:
                    matched_obj = self.map_manager.process_observation(class_name, points_map, feature)
                frame_objects.append({
                    'class_name': class_name,
                    'confidence': confidence,
                    'mask': mask,
                    'points_map': points_map,
                    'clip_feature': feature
                })
                label = f"{class_name} {confidence:.2f}"
                cv2.putText(visualization, label, (x1, max(y1 - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        cv2.imshow("YOLO + MobileSAM", visualization)
        cv2.waitKey(1)
def main(args=None):
    rclpy.init(args=args)
    node = YoloNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info("[EndProcess] Shutting down. Running final map-level merge...")
        before = len(node.map_manager.objects)
        node.map_manager.merge_duplicates()
        after = len(node.map_manager.objects)
        node.get_logger().info(f"[EndProcess] Final merge complete. Map size reduced from {before} to {after}")
        node.map_manager.save_map("json/final_map.json", snap_func=node.get_safe_goal)
        node.get_logger().info("[EndProcess] Final map saved to json/final_map.json")
        node.destroy_node()
        rclpy.shutdown()
if __name__ == '__main__':
    main()
