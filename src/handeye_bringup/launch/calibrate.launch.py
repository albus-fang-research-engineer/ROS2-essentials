"""Tracker + easy_handeye2 in one launch, for when you don't want two terminals.

Assumes the robot driver and camera are already up (compose profiles `ur` and
`camera`). This launch deliberately does NOT start them: the calibration stack
consumes TF and images, and coupling it to a specific driver would defeat the
point of keeping it hardware-independent.

Sampling advice that actually determines whether the result is any good:

  Rotate the flange as far as joint limits allow about all three axes, in both
  directions, across ~15-20 poses. Translation-only samples leave the rotation
  estimate rank deficient and the solve will be confidently wrong. Keep the
  target as close to the camera as focus allows.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

ARGS = [
    ('calibration_type', 'eye_on_base',
     'eye_on_base: camera fixed to the world, marker on the flange. '
     'eye_in_hand: camera on the flange, marker fixed to the table.'),
    ('name', 'default_eob',
     'Identifier for this calibration. The same name must be used to publish it.'),
    ('robot_base_frame', 'base_link',
     'UR note: base_link is the URDF root; base is the ROS-Industrial rotated '
     'frame. Mixing them costs you a 180 degree yaw.'),
    ('robot_effector_frame', 'tool0', 'Flange frame.'),
    ('marker_id', '582', ''),
    ('marker_size', '0.05', 'Metres.'),
    ('marker_frame', 'aruco_marker_frame', ''),
    ('camera_optical_frame', 'camera_color_optical_frame', ''),
    ('image_topic', '/camera/camera/color/image_raw', ''),
    ('camera_info_topic', '/camera/camera/color/camera_info', ''),
    ('freehand_robot_movement', 'true',
     'true = you jog the arm yourself. false = easy_handeye2 drives it via '
     'MoveIt, which needs the moveit profile up.'),
]


def generate_launch_description():
    declared = [
        DeclareLaunchArgument(n, default_value=d, description=desc)
        for n, d, desc in ARGS
    ]

    tracker = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('handeye_bringup'),
            'launch', 'tracker.launch.py')),
        launch_arguments={
            'marker_id': LaunchConfiguration('marker_id'),
            'marker_size': LaunchConfiguration('marker_size'),
            'marker_frame': LaunchConfiguration('marker_frame'),
            'camera_optical_frame': LaunchConfiguration('camera_optical_frame'),
            'image_topic': LaunchConfiguration('image_topic'),
            'camera_info_topic': LaunchConfiguration('camera_info_topic'),
        }.items(),
    )

    handeye = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('easy_handeye2'),
            'launch', 'calibrate.launch.py')),
        launch_arguments={
            'calibration_type': LaunchConfiguration('calibration_type'),
            'name': LaunchConfiguration('name'),
            'robot_base_frame': LaunchConfiguration('robot_base_frame'),
            'robot_effector_frame': LaunchConfiguration('robot_effector_frame'),
            'tracking_base_frame': LaunchConfiguration('camera_optical_frame'),
            'tracking_marker_frame': LaunchConfiguration('marker_frame'),
            'freehand_robot_movement': LaunchConfiguration('freehand_robot_movement'),
        }.items(),
    )

    return LaunchDescription(declared + [tracker, handeye])
