"""Interactive marker picker: see every marker the camera detects, with its id.

There is no GUI picker in aruco_ros -- `single` is headless and takes an id you
must already know. But `marker_publisher` detects EVERY marker in view and
publishes an annotated image with each one outlined and its id drawn on it. So
the workflow you want does exist, it just looks like this:

    point the camera at the board -> read the ids off the screen -> pick one

That also settles the dictionary question for free. marker_publisher uses the
same dictionary as `single`, so anything it outlines is by definition
detectable by the calibration. Anything it ignores is not, no matter how good
the print looks.

The size passed here does NOT have to be correct to identify ids -- detection
is scale-free. It only affects the pose estimate, which you are ignoring at
this stage. Get the id first, then measure the square properly for MARKER_SIZE.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

ARGS = [
    ('marker_size', '0.05',
     'Only affects pose, not detection. A rough value is fine here.'),
    ('camera_ref_frame', 'camera_link', ''),
    ('camera_optical_frame', 'camera_color_optical_frame', ''),
    ('image_topic', '/camera/camera/color/image_raw', ''),
    ('camera_info_topic', '/camera/camera/color/camera_info', ''),
    ('open_viewer', 'true',
     'Open rqt_image_view on the annotated stream. Needs X11.'),
]


def generate_launch_description():
    declared = [
        DeclareLaunchArgument(n, default_value=d, description=desc)
        for n, d, desc in ARGS
    ]

    detector = Node(
        package='aruco_ros',
        executable='marker_publisher',
        name='aruco_marker_publisher',
        output='screen',
        parameters=[{
            'image_is_rectified': True,
            'marker_size': LaunchConfiguration('marker_size'),
            'reference_frame': LaunchConfiguration('camera_ref_frame'),
            'camera_frame': LaunchConfiguration('camera_optical_frame'),
        }],
        remappings=[
            ('/camera_info', LaunchConfiguration('camera_info_topic')),
            ('/image', LaunchConfiguration('image_topic')),
        ],
    )

    reporter = Node(
        package='handeye_bringup',
        executable='marker_report',
        name='marker_report',
        output='screen',
    )

    viewer = Node(
        package='rqt_image_view',
        executable='rqt_image_view',
        name='marker_view',
        arguments=['/aruco_marker_publisher/result'],
        condition=IfCondition(LaunchConfiguration('open_viewer')),
    )

    return LaunchDescription(declared + [detector, reporter, viewer])
