import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Get the urdf file
    TURTLEBOT3_MODEL = os.environ['TURTLEBOT3_MODEL']
    model_folder = 'turtlebot3_' + TURTLEBOT3_MODEL
    urdf_path = os.path.join(
        get_package_share_directory('turtlebot3_gazebo'),
        'models',
        model_folder,
        'model.sdf'
    )

    # Launch configuration variables specific to simulation
    x_pose = LaunchConfiguration('x_pose', default='0.0')
    y_pose = LaunchConfiguration('y_pose', default='0.0')

    # Declare the launch arguments
    declare_x_position_cmd = DeclareLaunchArgument(
        'x_pose', default_value='0.0',
        description='Specify namespace of the robot')

    declare_y_position_cmd = DeclareLaunchArgument(
        'y_pose', default_value='0.0',
        description='Specify namespace of the robot')

    start_gazebo_ros_spawner_cmd = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', TURTLEBOT3_MODEL,
            '-file', urdf_path,
            '-x', x_pose,
            '-y', y_pose,
            '-z', '0.01'
        ],
        output='screen',
    )

    # Bridge ROS topics and Gazebo messages for ROS 2 control and sensors
    bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist',
            *(
                ['/wheel/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry',
                 '/imu@sensor_msgs/msg/Imu[gz.msgs.IMU']
                if TURTLEBOT3_MODEL == 'burger' else
                ['/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry',
                 '/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V']
            ),
            '/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',
            '/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model',
            '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
            '/camera/image@sensor_msgs/msg/Image[gz.msgs.Image',
            '/camera/depth_image@sensor_msgs/msg/Image[gz.msgs.Image',
            '/camera/points@sensor_msgs/msg/PointCloud2[gz.msgs.PointCloudPacked',
            '/camera/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo'
        ],
        output='screen'
    )

    ld = LaunchDescription()

    # Declare the launch options
    ld.add_action(declare_x_position_cmd)
    ld.add_action(declare_y_position_cmd)

    # Add any conditioned actions
    ld.add_action(start_gazebo_ros_spawner_cmd)
    ld.add_action(bridge_node)

    # Use one odometry/TF source, corrected by the IMU during turns.
    # Wheel yaw rate is a fallback for worlds without IMU generation.
    if TURTLEBOT3_MODEL == 'burger':
        ld.add_action(Node(
            package='robot_localization', executable='ekf_node',
            name='ekf_filter_node', output='screen',
            parameters=[{
                'use_sim_time': True,
                'frequency': 30.0,
                'two_d_mode': True,
                'publish_tf': True,
                'map_frame': 'map',
                'odom_frame': 'odom',
                'base_link_frame': 'base_footprint',
                'world_frame': 'odom',
                'odom0': 'wheel/odom',
                'odom0_config': [False, False, False,
                                 False, False, False,
                                 True, True, False,
                                 False, False, True,
                                 False, False, False],
                'odom0_queue_size': 10,
                'imu0': 'imu',
                'imu0_config': [False, False, False,
                                False, False, True,
                                False, False, False,
                                False, False, True,
                                False, False, False],
                'imu0_relative': True,
                'imu0_queue_size': 10,
            }],
            remappings=[('odometry/filtered', 'odom')],
        ))

    return ld
