import numpy as np
import time
class LocalObject:
    def __init__(self, object_id, class_name, points, feature, timestamp=None):
        self.id = object_id
        self.class_name = class_name
        self.points = points
        self.feature = feature
        self.observation_count = 1
        self.observations = [{
            "timestamp": timestamp if timestamp is not None else time.time(),
            "class_id": class_name,
            "feature": feature,
            "point_cloud": points
        }]
        
    @property
    def min_bound(self):
        return np.min(self.points, axis=0) if len(self.points) > 0 else np.zeros(3)

    @property
    def max_bound(self):
        return np.max(self.points, axis=0) if len(self.points) > 0 else np.zeros(3)
        
    @property
    def centroid(self):
        return np.mean(self.points, axis=0) if len(self.points) > 0 else np.zeros(3)

    def add_observation(self, points, feature, timestamp=None):
        self.points = np.vstack([
            self.points,
            points
        ])
        self.feature = (self.feature * self.observation_count + feature) / (self.observation_count + 1)
        if hasattr(self.feature, 'norm'):
            self.feature = self.feature / self.feature.norm(dim=-1, keepdim=True)
        else:
            norm = np.linalg.norm(self.feature)
            if norm > 0:
                self.feature = self.feature / norm
        self.observation_count += 1
        self.observations.append({
            "timestamp": timestamp if timestamp is not None else time.time(),
            "class_id": self.class_name,
            "feature": feature,
            "point_cloud": points
        })
