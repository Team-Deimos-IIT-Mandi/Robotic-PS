import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    pkg_share = get_package_share_directory('semantic_mapping')
    rviz_config_file = os.path.join(pkg_share, 'config', 'semantic_mapping.rviz')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    map_output_path = LaunchConfiguration('map_output_path', default='semantic_map.json')
    confidence_threshold = LaunchConfiguration('confidence_threshold', default='0.30')
    distance_threshold = LaunchConfiguration('distance_threshold', default='1.0')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use simulation (Gazebo) clock if true'
    )
    declare_map_output = DeclareLaunchArgument(
        'map_output_path', default_value='semantic_map.json',
        description='Path where JSON semantic map will be exported'
    )
    declare_conf_thresh = DeclareLaunchArgument(
        'confidence_threshold', default_value='0.30',
        description='Minimum detection confidence threshold'
    )
    declare_dist_thresh = DeclareLaunchArgument(
        'distance_threshold', default_value='1.0',
        description='Spatial distance threshold for object deduplication (m)'
    )

    semantic_mapper_node = Node(
        package='semantic_mapping',
        executable='semantic_mapper_node',
        name='semantic_mapper_node',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
            'rgb_topic': '/camera/image_raw',
            'depth_topic': '/camera/depth_image',
            'camera_info_topic': '/camera/camera_info',
            'odom_topic': '/odom',
            'world_frame': 'odom',
            'camera_frame': 'camera_rgb_frame',
            'confidence_threshold': confidence_threshold,
            'distance_threshold': distance_threshold,
            'persistence_threshold': 3,
            'map_output_path': map_output_path,
            'publish_markers': True
        }]
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config_file] if os.path.exists(rviz_config_file) else [],
        parameters=[{'use_sim_time': use_sim_time}]
    )

    ld = LaunchDescription()
    ld.add_action(declare_use_sim_time)
    ld.add_action(declare_map_output)
    ld.add_action(declare_conf_thresh)
    ld.add_action(declare_dist_thresh)
    ld.add_action(semantic_mapper_node)
    ld.add_action(rviz_node)

    return ld
