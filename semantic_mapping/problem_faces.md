# Problems Faced & Solutions

## 1. TF Extrapolation Error into the Future
**Problem:** The perception pipeline experienced TF extrapolation errors (looking into the future) when transforming camera data.
**Solution:** Solved by strictly synchronizing the `rgb`, `depth`, and `odom` topics using `message_filters.ApproximateTimeSynchronizer`. By directly injecting the synchronized odometry pose into the callback, the need for asynchronous TF lookups was eliminated, completely resolving the extrapolation mismatch.

## 2. Map Over-Segmentation (Duplicate Objects)
**Problem:** The tracker spawns multiple versions of the same physical object (e.g., 14 chairs when there are only 2). This happens because as the robot moves, the visible 3D centroid shifts >0.5m, and the visual CLIP feature changes drastically from the first frame. Additionally, YOLO outputs low-confidence "ghost" detections (like false persons).
**Solution:** 
1. **Feature Averaging:** Update `LocalObject` to calculate a cumulative moving average of the CLIP feature so it smoothly morphs as the perspective changes.
2. **YOLO Confidence Threshold:** Extracted the threshold used by DualMap (`fastsam_confidence: 0.80`) from their config and applied it directly to our YOLO detections. This strict `conf >= 0.80` filter immediately eliminates hallucinated low-confidence objects from ever entering the map.
3. **Map-Level Merging (Centroid Shift Fix):** As the robot drives around large objects (like a bed), the visible center shifts, tricking the tracker into spawning duplicates. To fix this, we mimicked DualMap's `EndProcess` strategy. Instead of running an expensive $O(N^2)$ merge every frame, we implemented:
    * A background timer that periodically calls `merge_duplicates()` to fuse overlapping 3D point clouds.
    * A final `EndProcess` merge block that runs upon node shutdown (catching `KeyboardInterrupt`) to definitively compress the map before exporting it to `final_map.json`.
4. **False Positive Rationalization:** Some false positives (like people inside a picture frame) are physically valid visual detections by YOLO. Because they are spatially distant from the floor, the strict `point_cloud_distance` threshold (0.2m) correctly refuses to blindly merge them, preserving the physical layout of the room.
