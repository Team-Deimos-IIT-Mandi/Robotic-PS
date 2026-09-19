import os
import json
import threading
from math import sqrt, isfinite, atan2, sin, cos
from pathlib import Path
from groq import Groq
import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.parameter import Parameter
from tf2_ros import Buffer, TransformListener, TransformException

JSON_FILE = Path(__file__).resolve().parent / 'json' / 'final_map.json'
MAX_CANDIDATES = 20
NEAR_THRESHOLD = 2.0
MODEL = 'openai/gpt-oss-20b'

client = None
objects = []
available_classes = []


def initialize_client():
    global client
    env_path = Path(__file__).resolve().parent / '.env'
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    api_key = os.environ.get('GROQ_API_KEY')
    if not api_key:
        raise RuntimeError('GROQ_API_KEY is not set in the environment or Task 2 .env.')
    client = Groq(api_key=api_key, timeout=30.0, max_retries=1)


def reload_map():
    global objects, available_classes
    with JSON_FILE.open() as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, list):
        raise ValueError(f'{JSON_FILE} must contain a list of objects.')
    objects = [obj for obj in loaded if isinstance(obj, dict)
               and obj.get('status', 'active') != 'inactive'
               and obj.get('frame_id', 'map') == 'map'
               and isinstance(obj.get('class_name'), str)
               and 'object_id' in obj and valid_position(obj.get('centroid'))]
    available_classes = sorted({obj['class_name'].lower() for obj in objects})


def valid_position(value):
    try:
        return isinstance(value, (list, tuple)) and len(value) >= 2 and all(
            isfinite(float(axis)) for axis in value[:2])
    except (TypeError, ValueError):
        return False


context = {'previous_target': None, 'previous_command': None, 'current_task': None}
robot_position = None

def set_robot_position(position):
    global robot_position
    if not isinstance(position, (list, tuple)):
        raise ValueError('Robot position must be a list or tuple.')
    if len(position) < 2:
        raise ValueError('Robot position must contain at least x and y.')
    robot_position = list(position)

def retrieve_objects(objects, class_name):
    results = []
    for obj in objects:
        if 'class_name' not in obj:
            continue
        if obj['class_name'].lower() == class_name.lower():
            results.append(obj)
    return results

def simplify_object(obj):
    result = {'object_id': obj['object_id'], 'class_name': obj['class_name'], 'centroid': obj['centroid']}
    if 'safe_nav_goal' in obj:
        result['safe_nav_goal'] = obj['safe_nav_goal']
    else:
        result['safe_nav_goal'] = None
    return result

def build_context(objects, relevant_classes):
    context_data = {}
    for class_name in relevant_classes:
        matches = retrieve_objects(objects, class_name)
        simplified_matches = []
        for obj in matches:
            simplified_matches.append(simplify_object(obj))
        context_data[class_name] = simplified_matches
    return context_data

def distance_between(obj_a, obj_b):
    a = obj_a['centroid']
    b = obj_b['centroid']
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    if len(a) >= 3 and len(b) >= 3:
        dz = a[2] - b[2]
    else:
        dz = 0.0
    return sqrt(dx ** 2 + dy ** 2 + dz ** 2)

def distance_from_robot(obj):
    if robot_position is None:
        return None
    centroid = obj['centroid']
    dx = centroid[0] - robot_position[0]
    dy = centroid[1] - robot_position[1]
    return sqrt(dx ** 2 + dy ** 2)

def find_near_objects(objects_a, objects_b, threshold):
    results = []
    for obj_a in objects_a:
        for obj_b in objects_b:
            distance = distance_between(obj_a, obj_b)
            if distance <= threshold:
                results.append({'object_a': obj_a, 'object_b': obj_b, 'distance': distance})
    return results

def filter_by_spatial_relation(objects, target_class, reference_class, relation, threshold):
    target_objects = retrieve_objects(objects, target_class)
    reference_objects = retrieve_objects(objects, reference_class)
    if relation == 'near':
        pairs = find_near_objects(target_objects, reference_objects, threshold)
        candidates = []
        for pair in pairs:
            target = simplify_object(pair['object_a'])
            reference = simplify_object(pair['object_b'])
            candidates.append({'target': target, 'reference': reference, 'distance': pair['distance']})
        candidates.sort(key=lambda x: x['distance'])
        return candidates
    return []

def find_classes_in_command(command, available_classes):
    command = command.lower()
    found_classes = []
    for class_name in available_classes:
        if class_name in command:
            found_classes.append(class_name)
    return found_classes

def parse_command(command):
    previous_target = context['previous_target']
    if previous_target is None:
        previous_target_data = None
    else:
        previous_target_data = get_object_by_id(objects, previous_target)
        if previous_target_data is not None:
            previous_target_data = simplify_object(previous_target_data)
            
    parser_schema = {
        'type': 'object',
        'properties': {
            'action': {'type': ['string', 'null'], 'enum': ['navigate_to', 'traverse', None]},
            'target_class': {'type': ['string', 'null']},
            'reference_class': {'type': ['string', 'null']},
            'relation': {'type': ['string', 'null'], 'enum': ['near', None]}
        },
        'required': ['action', 'target_class', 'reference_class', 'relation'],
        'additionalProperties': False
    }
    
    system_prompt = (
        "\nYou are the semantic command parser for a mobile robot.\n"
        "Your job is to identify the action, target object, and optional spatial reference.\n"
        f"Available object classes:\n{json.dumps(available_classes)}\n"
        f"Previous target:\n{json.dumps(previous_target_data) if previous_target_data is not None else 'null'}\n"
        "Rules:\n"
        "1. For commands such as 'go to', 'move to', 'navigate to', 'approach', set action = 'navigate_to'.\n"
        "2. For commands such as 'go through', 'pass through', 'traverse', set action = 'traverse'.\n"
        "3. target_class must be one of the available object classes, unless no target can be identified, in which case use null.\n"
        "4. reference_class must be one of the available object classes, or null.\n"
        "5. If the command expresses proximity ('near', 'beside', 'next to', 'close to', 'by'), set relation to 'near'.\n"
        "6. If the user uses a pronoun ('it', 'that', 'this object') and a previous target exists, resolve the target to the previous target's class.\n"
        "7. If you cannot determine the target object, set action, target_class, reference_class, and relation all to null.\n"
        "8. Do not invent classes.\n"
        "Return only the requested JSON structure.\n"
    )
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': command}],
        temperature=0,
        response_format={'type': 'json_schema', 'json_schema': {'name': 'command_query', 'strict': True, 'schema': parser_schema}}
    )
    content = response.choices[0].message.content
    query = json.loads(content)
    return query

def get_object_by_id(objects, object_id):
    for obj in objects:
        if obj.get('object_id') == object_id:
            return obj
    return None

def generate_candidates(objects, query, near_threshold=NEAR_THRESHOLD):
    target_class = query.get('target_class')
    reference_class = query.get('reference_class')
    relation = query.get('relation')
    if target_class is None:
        return []
    target_class = target_class.lower()
    if target_class not in available_classes:
        return []
        
    if reference_class is not None and relation is not None:
        reference_class = reference_class.lower()
        if reference_class not in available_classes:
            return []
            
        candidates = filter_by_spatial_relation(objects, target_class, reference_class, relation, near_threshold)
        
        if not candidates:
            return []
            
        unique_candidates = {}
        for candidate in candidates:
            object_id = candidate['target']['object_id']
            if object_id not in unique_candidates:
                unique_candidates[object_id] = candidate
                
        candidates = list(unique_candidates.values())
        
        if robot_position is not None:
            for candidate in candidates:
                target_obj = get_object_by_id(objects, candidate['target']['object_id'])
                candidate['robot_distance'] = distance_from_robot(target_obj)
                
            candidates.sort(
                key=lambda x: x['robot_distance'] if x['robot_distance'] is not None else float('inf')
            )
            
        return candidates[:MAX_CANDIDATES]
        
    target_objects = retrieve_objects(objects, target_class)
    candidates = []
    for obj in target_objects:
        simplified = simplify_object(obj)
        robot_distance = distance_from_robot(obj)
        candidates.append({'target': simplified, 'robot_distance': robot_distance})
        
    if robot_position is not None:
        candidates.sort(key=lambda x: x['robot_distance'] if x['robot_distance'] is not None else float('inf'))
        
    return candidates[:MAX_CANDIDATES]

def resolve_task(task, objects):
    object_id = task['object_id']
    obj = get_object_by_id(objects, object_id)
    if obj is None:
        raise RuntimeError(f'Object ID {object_id} no longer exists in the local world model.')
    result = {'action': task['action'], 'object_id': object_id, 'class_name': obj['class_name'], 'centroid': obj['centroid']}
    if 'safe_nav_goal' in obj:
        result['safe_nav_goal'] = obj['safe_nav_goal']
    else:
        result['safe_nav_goal'] = None
    if task['action'] == 'traverse':
        if 'min_bound' in obj:
            result['min_bound'] = obj['min_bound']
        else:
            result['min_bound'] = None
        if 'max_bound' in obj:
            result['max_bound'] = obj['max_bound']
        else:
            result['max_bound'] = None
    return result

def update_context(command, task):
    context['previous_command'] = command
    context['previous_target'] = task['object_id']
    context['current_task'] = task

def process_command(command):
    reload_map()
    if not available_classes:
        return {'success': False, 'error': 'No active objects in map coordinates are available.'}
    if robot_position is None:
        return {'success': False, 'error': 'Robot position in map is unavailable. Start Gazebo and Nav2/SLAM first.'}
    query = parse_command(command)
    
    if not query.get('action') or not query.get('target_class'):
        return {'success': False, 'error': 'I could not determine the target object or action.', 'query': query}
        
    candidates = generate_candidates(objects, query, NEAR_THRESHOLD)
    if not candidates:
        return {'success': False, 'error': 'No matching candidates found.', 'query': query}
        
    best_candidate = candidates[0]
    object_id = best_candidate['target']['object_id']
    
    task = {
        'action': query['action'],
        'object_id': object_id
    }
    
    resolved = resolve_task(task, objects)
    update_context(command, task)
    return {'success': True, 'command': command, 'query': query, 'candidates': candidates, 'task': task, 'resolved_object': resolved, 'context': context}

def make_goal(resolved, stamp):
    goal = resolved.get('safe_nav_goal')
    if not valid_position(goal):
        goal = resolved.get('centroid')
    if not valid_position(goal):
        raise ValueError('Target has no valid safe_nav_goal or centroid.')
    msg = PoseStamped()
    msg.header.frame_id = 'map'
    msg.header.stamp = stamp
    msg.pose.position.x, msg.pose.position.y = float(goal[0]), float(goal[1])
    heading = 0.0
    center = resolved.get('centroid')
    if valid_position(center):
        heading = atan2(float(center[1]) - msg.pose.position.y,
                        float(center[0]) - msg.pose.position.x)
    msg.pose.orientation.z = sin(heading / 2.0)
    msg.pose.orientation.w = cos(heading / 2.0)
    return msg


def main():
    try:
        initialize_client()
        reload_map()
    except Exception as exc:
        print(f'[Commander] {exc}')
        return 1
    print(f'Loaded {len(objects)} active objects. Available classes: {available_classes}')
    print("Direct navigation interface. Type 'go to the chair', or 'exit' to quit.")
    rclpy.init()
    node = rclpy.create_node('semantic_llm_direct_commander', parameter_overrides=[
        Parameter('use_sim_time', value=True)])
    goal_pub = node.create_publisher(PoseStamped, '/goal_pose', 10)
    tf_buffer = Buffer()
    tf_listener = TransformListener(tf_buffer, node)

    def update_robot_position():
        global robot_position
        try:
            transform = tf_buffer.lookup_transform('map', 'base_footprint', rclpy.time.Time())
            p = transform.transform.translation
            set_robot_position([p.x, p.y, p.z])
        except TransformException:
            robot_position = None

    pose_timer = node.create_timer(0.2, update_robot_position)
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()
    try:
        while rclpy.ok():
            try:
                command = input('Command > ').strip()
            except (EOFError, KeyboardInterrupt):
                break
            if command.lower() in {'exit', 'quit'}:
                break
            if not command:
                continue
            try:
                update_robot_position()
                result = process_command(command)
                if not result.get('success'):
                    print(f"[Navigator] {result.get('error')}")
                    continue
                task = result['task']
                if task['action'] != 'navigate_to':
                    print('[Navigator] This direct interface supports navigate_to commands only; no goal sent.')
                    continue
                if goal_pub.get_subscription_count() == 0:
                    print('[Navigator] Nav2 is not listening on /goal_pose. Start navigation first; no goal sent.')
                    continue
                pose = make_goal(result['resolved_object'], node.get_clock().now().to_msg())
                goal_pub.publish(pose)
                target = result['resolved_object']
                print(f"[Navigator] Sent {target['class_name']} (ID {target['object_id']}) "
                      f"to /goal_pose: x={pose.pose.position.x:.2f}, y={pose.pose.position.y:.2f}")
            except Exception as exc:
                print(f'[Navigator] {exc}')
    finally:
        executor.shutdown(timeout_sec=2.0)
        spin_thread.join(timeout=2.0)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
