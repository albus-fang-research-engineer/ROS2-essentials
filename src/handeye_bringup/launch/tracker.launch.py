"""ArUco marker tracker, wired to publish tracking_marker_frame into TF.

The aruco_ros `single` node is instantiated directly rather than via upstream's
single.launch.py, because the upstream launch argument names have drifted
between distros while the NODE parameter names have been stable. Fewer moving
parts to break on a distro bump.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

ARGS = [
    ('marker_id', '582', 'ArUco id printed on the target.'),
    ('marker_size', '0.05',
     'Black square edge length in METRES. Measure the printed sheet -- '
     'printer scaling lies, and a 2% size error is a 2% range bias.'),
    ('marker_frame', 'aruco_marker_frame', 'TF frame the detector publishes.'),
    ('camera_optical_frame', 'camera_color_optical_frame',
     'Optical frame of the camera. NOTE: no leading slash -- ROS 2 tf2 '
     'rejects them, and upstream docs still show the ROS 1 style.'),
    ('image_topic', '/camera/camera/color/image_raw', 'Rectified colour image.'),
    ('camera_info_topic', '/camera/camera/color/camera_info', 'Intrinsics.'),
    ('corner_refinement', 'LINES',
     'NONE | HARRIS | LINES | SUBPIX. LINES is a good default for calibration.'),
]


def generate_launch_description():
    declared = [
        DeclareLaunchArgument(name, default_value=default, description=desc)
        for name, default, desc in ARGS
    ]

    tracker = Node(
        package='aruco_ros',
        executable='single',
        name='aruco_single',
        output='screen',
        parameters=[{
            'image_is_rectified': True,
            'marker_size': LaunchConfiguration('marker_size'),
            'marker_id': LaunchConfiguration('marker_id'),
            'reference_frame': LaunchConfiguration('camera_optical_frame'),
            'camera_frame': LaunchConfiguration('camera_optical_frame'),
            'marker_frame': LaunchConfiguration('marker_frame'),
            'corner_refinement': LaunchConfiguration('corner_refinement'),
        }],
        remappings=[
            ('/camera_info', LaunchConfiguration('camera_info_topic')),
            ('/image', LaunchConfiguration('image_topic')),
        ],
    )

    return LaunchDescription(declared + [tracker])
