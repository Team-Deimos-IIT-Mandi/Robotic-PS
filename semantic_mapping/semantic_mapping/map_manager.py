import numpy as np
import json
from .local_object import LocalObject
from .tracker import Tracker
import time
class MapManager:
    def __init__(self):
        self.objects = []
        self.next_object_id = 0
        self.tracker = Tracker()
        self.log_file = "json/tracking_logs.json"
        with open(self.log_file, "w") as f:
            json.dump([], f)
    def _append_log(self, log_entry):
        try:
            with open(self.log_file, "r") as f:
                logs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logs = []
        logs.append(log_entry)
        with open(self.log_file, "w") as f:
            json.dump(logs, f, indent=4)
    def check_stability(self):
        min_observations = 3
        inactive_time = 2.0
        current_time = time.time()
        stable_objects = []
        for obj in self.objects:
            last_update_time = obj.observations[-1]["timestamp"]
            inactive_duration = current_time - last_update_time
            if inactive_duration < inactive_time:
                stable_objects.append(obj)
                continue
            if obj.observation_count < min_observations:
                continue
            class_counts = {}
            for obs in obj.observations:
                c_id = obs["class_id"]
                class_counts[c_id] = class_counts.get(c_id, 0) + 1
            if not class_counts:
                continue
            most_common_count = max(class_counts.values())
            if most_common_count <= (obj.observation_count / 3):
                continue
            stable_objects.append(obj)
        self.objects = stable_objects
    def refine_map(self):
        """
        Periodically called to clean and consolidate the concrete map.
        1. Prunes ghost/unstable objects.
        2. Merges fragmented objects that overlap.
        """
        self.check_stability()
        self.merge_duplicates()
    def merge_duplicates(self):
        spatial_threshold = 0.2
        clip_threshold = 0.85
        merged_objects = []
        for obj in self.objects:
            matched = False
            for m_obj in merged_objects:
                if obj.class_name != m_obj.class_name:
                    continue
                dist = self.point_cloud_distance(obj.points, m_obj.points)
                if dist > spatial_threshold:
                    continue
                clip_score = self.tracker.cosine_similarity(obj.feature, m_obj.feature)
                if clip_score < clip_threshold:
                    continue
                total_observations = m_obj.observation_count + obj.observation_count
                merged_feature = (m_obj.feature * m_obj.observation_count + obj.feature * obj.observation_count) / total_observations
                if hasattr(merged_feature, 'norm'):
                    merged_feature = merged_feature / merged_feature.norm(dim=-1, keepdim=True)
                else:
                    norm = np.linalg.norm(merged_feature)
                    if norm > 0:
                        merged_feature = merged_feature / norm
                m_obj.points = np.vstack([m_obj.points, obj.points])
                m_obj.feature = merged_feature
                m_obj.observation_count = total_observations
                m_obj.observations.extend(obj.observations)
                matched = True
                break
            if not matched:
                merged_objects.append(obj)
        self.objects = merged_objects
    def point_cloud_distance(self,points1,points2):
        min1=np.min(points1,axis=0)
        max1=np.max(points1,axis=0)
        min2=np.min(points2,axis=0)
        max2=np.max(points2,axis=0)
        gap=np.maximum(min2-max1,min1-max2)
        gap = np.maximum(gap, 0)
        return np.linalg.norm(gap)
    def save_map(self, filepath="final_map.json", snap_func=None):
        final_objects = []
        for obj in self.objects:
            # Thresholding: Delete ghost objects/hallucinations seen fewer than 3 times
            obs_count = getattr(obj, 'observation_count', 1)
            if obs_count < 3:
                continue
                
            obj_data = {
                "object_id": obj.id,
                "class_name": obj.class_name,
                "points_count": len(obj.points),
                "observations": obs_count,
                "centroid": obj.centroid.tolist() if len(obj.points) > 0 else None,
                "min_bound": obj.min_bound.tolist() if len(obj.points) > 0 else None,
                "max_bound": obj.max_bound.tolist() if len(obj.points) > 0 else None
            }
            if snap_func is not None and len(obj.points) > 0:
                obj_x, obj_y = obj.centroid[:2]
                safe_goal = snap_func(obj_x, obj_y)
                obj_data["safe_nav_goal"] = safe_goal
                
            final_objects.append(obj_data)
        with open(filepath, "w") as f:
            json.dump(final_objects, f, indent=4)
    def process_observation(self, class_name, points, feature, timestamp=None):
        log_entry = {
            "observation": {
                "class_name": class_name,
                "points_count": len(points),
                "feature_shape": list(feature.shape)
            }
        }
        matched_object = self.tracker.find_match(class_name, points, feature, self.objects)
        if matched_object:
            log_entry["action"] = "matched_existing"
            log_entry["object_id"] = matched_object.id
            log_entry["object_class"] = matched_object.class_name
            matched_object.add_observation(points, feature, timestamp=timestamp)
            self._append_log(log_entry)
            return matched_object
        else:
            log_entry["action"] = "created_new"
            log_entry["object_id"] = self.next_object_id
            log_entry["object_class"] = class_name
            new_object = LocalObject(self.next_object_id, class_name, points, feature, timestamp=timestamp)
            self.objects.append(new_object)
            self.next_object_id += 1
            self._append_log(log_entry)
            return new_object
