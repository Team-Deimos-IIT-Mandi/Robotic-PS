import numpy as np
class Tracker:
    def __init__(self, spatial_threshold=0.5, clip_threshold=0.7):
        self.spatial_threshold = spatial_threshold
        self.clip_threshold = clip_threshold
    def find_match(self, class_name, points, feature, objects):
        best_object = None
        best_score = -1.0
        for obj in objects:
            if obj.class_name != class_name:
                continue
            center1 = np.mean(points, axis=0)
            center2 = np.mean(obj.points, axis=0)
            distance = np.linalg.norm(center1 - center2)
            if distance > self.spatial_threshold:
                continue
            spatial_score = 1.0 - (distance / self.spatial_threshold)
            clip_score = self.cosine_similarity(feature, obj.feature)
            if clip_score < self.clip_threshold:
                continue
            total_score = 0.5 * spatial_score + 0.5 * clip_score
            if total_score > best_score:
                best_score = total_score
                best_object = obj
        return best_object
    @staticmethod
    def cosine_similarity(feature1, feature2):
        if hasattr(feature1, 'cpu'):
            feature1 = feature1.cpu().numpy()
        if hasattr(feature2, 'cpu'):
            feature2 = feature2.cpu().numpy()
        feature1 = np.asarray(feature1).flatten()
        feature2 = np.asarray(feature2).flatten()
        norm1 = np.linalg.norm(feature1)
        norm2 = np.linalg.norm(feature2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return np.dot(feature1, feature2) / (norm1 * norm2)
