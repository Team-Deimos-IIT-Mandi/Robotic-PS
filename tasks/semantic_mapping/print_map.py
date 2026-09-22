#!/usr/bin/env python3
import sys
import json
import os

def find_semantic_map():
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        return sys.argv[1]

    candidates = [
        "/home/aarush/Robotic-PS/tasks/semantic_mapping/semantic_map.json",
        "/home/aarush/semantic_map.json",
        "/home/aarush/turtlebot3_ws/semantic_map.json",
        "semantic_map.json",
    ]
    existing = [c for c in candidates if os.path.exists(c)]
    if not existing:
        return "/home/aarush/Robotic-PS/tasks/semantic_mapping/semantic_map.json"
    
    # Pick the most recently modified file
    existing.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return existing[0]

def print_map():
    filepath = find_semantic_map()
    if not os.path.exists(filepath):
        print(f"Waiting for semantic_map.json to be created... (checked {filepath})")
        return
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Reading {filepath}... ({e})")
        return
    
    total = data.get("total_objects", 0)
    objects = data.get("objects", [])
    dist = data.get("robot_distance_traveled_m", 0.0)
    fps = data.get("fps", 0.0)
    
    obj_strs = [f"{obj['label']} ({obj['position'][0]:.1f}, {obj['position'][1]:.1f})" for obj in objects]
    summary_line = f"{total} objects — " + ", ".join(obj_strs) if obj_strs else "0 objects mapped."
    
    print("\n" + "="*65)
    print(f"        LIVE SEMANTIC MAP SUMMARY  [{filepath}]")
    print("="*65)
    print(f"Summary: {summary_line}")
    print(f"Distance Traveled: {dist:.2f} m | FPS: {fps:.1f} | Objects Confirmed: {total}")
    print("-" * 65)
    for obj in objects:
        print(f"  [ID {obj['id']:02d}] {obj['label']:<15} Base: [{obj['position'][0]:6.2f}, {obj['position'][1]:6.2f}, {obj['position'][2]:6.2f}]  Conf: {obj['confidence']:.2f}  Seen: {obj.get('observations', 1)}x")
    print("="*65 + "\n")

import time

if __name__ == "__main__":
    try:
        while True:
            os.system('clear')
            print_map()
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopped live updates.")
