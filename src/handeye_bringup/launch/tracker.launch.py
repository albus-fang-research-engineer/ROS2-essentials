"""ArUco GRID BOARD tracker (aruco_opencv), wired to publish into TF.

WHY NOT aruco_ros

    aruco_ros vendors Rafael Munoz-Salinas' original `aruco` library, whose
    dictionary set (ARUCO_ORIGINAL, ARUCO_MIP_36h12, ARTag, ChiliTags, the
    AprilTag families) does NOT include OpenCV's NxN_M dictionaries. A board
    printed from cv2.aruco.DICT_5X5_50 is therefore invisible to it at any
    distance, any angle, with any min_marker_size -- silently, with no warning.
    aruco_opencv wraps cv2.aruco directly and takes the dictionary as a
    runtime parameter, so it is the only one of the two that can see this
    board. `make identify-dict` is what tells you which you have.

WHY A BOARD BEATS A SINGLE MARKER

    12 markers x 4 corners = 48 point correspondences per frame instead of 4,
    solved jointly against a known rigid geometry. Better conditioned, far less
    sensitive to the two-solution PnP ambiguity that makes single planar
    markers flip, and it degrades gracefully when part of the board is occluded
    or glared out. The cost is that the geometry must be described correctly:
    a wrong markers_x/markers_y or separation biases every corner constraint.

WHY output_frame IS camera_link AND NOT AN OPTICAL FRAME

    The camera driver already owns a subtree:
        camera_link -> camera_color_frame -> camera_color_optical_frame

    If the calibration solves base_link -> camera_color_optical_frame and you
    publish that, the optical frame gets a SECOND parent, tf2 stops being a
    tree, and lookups go non-deterministic. aruco_opencv's `output_frame` is
    the frame the board pose is REPORTED in -- it does the optical-frame
    lookup internally using the driver's own TF -- so pointing it at
    camera_link makes the solve target the root of the driver's subtree
    directly. scripts/promote_calibration.py refuses an optical-frame child
    for the same reason.

BOARD DESCRIPTION IS GENERATED, NOT COMMITTED

    aruco_opencv reads board geometry from a YAML file, not from parameters.
    Committing that file would mean the board dimensions live in two places --
    here and in cells/<host>.env -- and would drift. Instead the file is
    written at launch time from the launch arguments, so cells/<host>.env
    stays the single source of truth for what is physically on the bench.
"""

from __future__ import annotations

import os
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

ARGS = [
    ('marker_dict', '5X5_50',
     'OpenCV dictionary name WITHOUT the DICT_ prefix, e.g. 5X5_50. Run '
     '`make identify-dict` to determine this from the physical board rather '
     'than guessing -- a mismatch is undetectable except as 0%% detection.'),
    ('marker_size', '0.0575',
     'Black square edge of ONE marker, in METRES, measured with calipers. '
     'Measure across several markers and divide; printer scaling lies, and a '
     '2%% size error is a 2%% range bias no number of samples will average '
     'away.'),
    ('marker_separation', '0.006',
     'White gutter between adjacent markers, in METRES. Must be measured, '
     'not assumed: it sets the board geometry the joint solve relies on.'),
    ('markers_x', '3', 'Markers across, in the board frame.'),
    ('markers_y', '4', 'Markers down, in the board frame.'),
    ('first_id', '0',
     'Id of the top-left marker. OpenCV GridBoard numbers row-major from '
     'there, so first_id + markers_x*markers_y - 1 must be the last id that '
     '`make identify-dict` reported.'),
    ('board_name', 'handeye',
     'aruco_opencv publishes TF as board_<board_name>. Whatever you set here '
     'must match MARKER_FRAME in the cell file, or easy_handeye2 will sample '
     'a frame that does not exist and never say so.'),
    ('camera_ref_frame', 'camera_link',
     'Frame the board pose is REPORTED in, and therefore the frame the '
     'calibration solves for. The ROOT of the camera driver subtree, NOT an '
     'optical frame. See the module docstring.'),
    ('image_topic', '/camera/camera/color/image_raw',
     'Base topic. aruco_opencv derives camera_info as a sibling of this, so '
     '/camera/camera/color/image_raw implies /camera/camera/color/camera_info.'),
    ('image_is_rectified', 'false',
     'false = use the distortion coefficients from camera_info. Leave it '
     'false: if D is all zeros the flag is a no-op, and if D is non-zero, '
     'true would silently discard a real correction. Check with: ros2 topic '
     'echo --once <camera_info_topic> | grep -A2 "^d:"'),
    ('corner_refinement', '2',
     '0 None, 1 Subpix, 2 Contour. Subpixel corner accuracy is most of what '
     'determines the quality of the extrinsic; do not turn this off.'),
]


def _write_board_description(context, *_args, **_kwargs):
    """Materialise the board YAML aruco_opencv expects from launch args."""
    def arg(name):
        return LaunchConfiguration(name).perform(context)

    name = arg('board_name')
    board = (
        f"- name: '{name}'\n"
        f"  first_id: {int(arg('first_id'))}\n"
        f"  markers_x: {int(arg('markers_x'))}\n"
        f"  markers_y: {int(arg('markers_y'))}\n"
        f"  marker_size: {float(arg('marker_size'))}\n"
        f"  separation: {float(arg('marker_separation'))}\n"
        # Origin placement is arbitrary for hand-eye: AX = XB absorbs the
        # unknown board-to-flange transform, so only RIGIDITY matters.
        f"  frame_at_center: true\n"
    )

    fd, path = tempfile.mkstemp(prefix='board_', suffix='.yaml')
    with os.fdopen(fd, 'w') as handle:
        handle.write(board)

    # Load the package's own defaults first so every nested aruco.* parameter
    # exists, then override. Passing a parameter the node has not declared
    # makes it refuse to start, and the error does not name the parameter.
    defaults = os.path.join(
        get_package_share_directory('aruco_opencv'),
        'config', 'aruco_tracker.yaml')

    tracker = Node(
        package='aruco_opencv',
        executable='aruco_tracker_autostart',
        name='aruco_tracker',
        output='screen',
        parameters=[
            defaults,
            {
                'cam_base_topic': arg('image_topic'),
                'output_frame': arg('camera_ref_frame'),
                'marker_dict': arg('marker_dict'),
                'marker_size': float(arg('marker_size')),
                'image_is_rectified': arg('image_is_rectified') == 'true',
                'board_descriptions_path': path,
                'publish_tf': True,
                'aruco.cornerRefinementMethod': int(arg('corner_refinement')),
            },
        ],
    )
    return [tracker]


def generate_launch_description():
    declared = [
        DeclareLaunchArgument(name, default_value=default, description=desc)
        for name, default, desc in ARGS
    ]
    return LaunchDescription(declared + [OpaqueFunction(function=_write_board_description)])