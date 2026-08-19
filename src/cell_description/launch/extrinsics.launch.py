"""Publish the cell's calibrated extrinsics as static TF."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    extrinsics_file = LaunchConfiguration('extrinsics_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'extrinsics_file',
            description='Absolute path to the cell extrinsics YAML. '
                        'Conventionally /calibrations/<cell>/extrinsics.yaml.',
        ),
        Node(
            package='cell_description',
            executable='extrinsics_publisher',
            name='extrinsics_publisher',
            output='screen',
            parameters=[{'extrinsics_file': extrinsics_file}],
        ),
    ])
