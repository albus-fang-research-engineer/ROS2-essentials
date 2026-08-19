"""Bring up the ROS <-> ZMQ frame packet bridge."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

ARGS = [
    ('bind_address', 'tcp://0.0.0.0:5680', 'ZMQ REP bind address.'),
    ('color_topic', '/camera/camera/color/image_raw', ''),
    ('depth_topic', '/camera/camera/aligned_depth_to_color/image_raw',
     'Must be aligned to colour, or K will not apply to the depth image.'),
    ('camera_info_topic', '/camera/camera/color/camera_info', ''),
    ('camera_optical_frame', 'camera_color_optical_frame', ''),
    ('base_frame', 'base_link', ''),
    ('ee_frame', 'tool0', ''),
    ('depth_scale', '0.001', 'Raw depth unit -> metres. 0.001 for RealSense.'),
    ('sync_slop', '0.05', 'ApproximateTimeSynchronizer tolerance, seconds.'),
]


def generate_launch_description():
    declared = [
        DeclareLaunchArgument(n, default_value=d, description=desc)
        for n, d, desc in ARGS
    ]
    node = Node(
        package='ros_zmq_bridge',
        executable='bridge_node',
        name='ros_zmq_bridge',
        output='screen',
        parameters=[{n: LaunchConfiguration(n) for n, _, _ in ARGS}],
    )
    return LaunchDescription(declared + [node])
