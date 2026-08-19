"""ArUco marker tracker, wired to publish tracking_marker_frame into TF.

WHY reference_frame IS NOT THE OPTICAL FRAME

    The camera driver already owns a TF subtree:
        camera_link -> camera_color_frame -> camera_color_optical_frame

    If the calibration solves base_link -> camera_color_optical_frame and you
    publish that as a static transform, the optical frame acquires a SECOND
    parent. TF is a tree, not a graph -- the two publishers fight, lookups go
    non-deterministic, and the driver's subtree is effectively orphaned.

    aruco_ros separates `camera_frame` (which optical frame the intrinsics
    describe -- pure projection math) from `reference_frame` (which frame the
    resulting pose is expressed in). Pointing reference_frame at camera_link
    makes the calibration solve base_link -> camera_link directly, which
    attaches cleanly at the ROOT of the driver's subtree. No post-hoc
    composition with the driver's internal extrinsics, and nothing to redo when
    you switch between the colour and depth optical frames.

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
     'Optical frame the intrinsics belong to. Used for the projection math '
     'ONLY. No leading slash -- ROS 2 tf2 rejects them, and upstream docs '
     'still show the ROS 1 style.'),
    ('camera_ref_frame', 'camera_link',
     'Frame the marker pose is REPORTED in, and therefore the frame the '
     'calibration will solve for. Set this to the ROOT of the camera '
     'driver\'s own TF subtree (camera_link for RealSense), NOT the optical '
     'frame. See the note in the module docstring.'),
    ('image_topic', '/camera/camera/color/image_raw', 'Rectified colour image.'),
    ('camera_info_topic', '/camera/camera/color/camera_info', 'Intrinsics.'),
    ('detection_mode', '',
     'DM_NORMAL | DM_FAST | DM_VIDEO_FAST. Empty = the node default (normal). '
     'NOTE: this node declares detection_mode, NOT corner_refinement -- '
     'passing an undeclared parameter makes the node refuse to start.'),
    ('min_marker_size', '0.02',
     'Minimum marker area as a fraction of the image. Raise it to reject '
     'far-away false positives.'),
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
            'reference_frame': LaunchConfiguration('camera_ref_frame'),
            'camera_frame': LaunchConfiguration('camera_optical_frame'),
            'marker_frame': LaunchConfiguration('marker_frame'),
            'detection_mode': LaunchConfiguration('detection_mode'),
            'min_marker_size': LaunchConfiguration('min_marker_size'),
        }],
        remappings=[
            ('/camera_info', LaunchConfiguration('camera_info_topic')),
            ('/image', LaunchConfiguration('image_topic')),
        ],
    )

    return LaunchDescription(declared + [tracker])
