# config.py

CONFIG = {
    # ROS Topics
    "rgb_topic": "/camera/image",
    "depth_topic": "/camera/depth_image",
    "odom_topic": "/odom",
    "camera_info_topic": "/camera/camera_info",
    
    # Synchronization Parameters
    "sync_queue_size": 10,
    "sync_slop": 0.05,
    
    # Camera Extrinsics (relative to base_footprint)
    "camera_translation": [0.04, 0.000, 0.120],
    
    # Model Paths
    "clip_checkpoint": "/home/deepak/InterIIT_practice/task_2/weights/mobileclip_s2.pt",
    "clip_model_name": "mobileclip_s2",
    "yolo_checkpoint": "weights/yolov8x-worldv2.pt",
    "sam_checkpoint": "weights/mobile_sam.pt",
    "sam_model_type": "vit_t",
    
    # Post-processing Thresholds
    "iou_threshold": 0.5,
    "color_threshold": 0.7,
    
    # YOLO Classes
    "yolo_classes": [
        "person", "chair", "bed", "nightstand", "table",
        "coffee table", "desk", "dining table", "door", "window",
        "cabinet", "kitchen cabinet", "refrigerator", "sofa", "trash bin",
        "tv", "tv cabinet", "vase", "wardrobe", "shoe rack",
        "air conditioner", "sink", "microwave", "oven", "toaster",
        "bottle", "cup", "bowl", "plate", "fork", "knife",
        "spoon", "book", "laptop", "computer", "keyboard",
        "mouse", "remote", "cell phone", "clock", "backpack",
        "handbag", "suitcase", "potted plant", "toilet", "mirror",
        "lamp", "fan", "picture frame", "washing machine"
    ]
}
