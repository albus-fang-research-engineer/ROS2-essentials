"""Publish every calibrated extrinsic in a cell as static TF.

Why this exists instead of easy_handeye2's publish.launch.py:

  Calibration has a producer/consumer split. The producer (easy_handeye2 GUI)
  runs a few times a year, interactively, with the arm and camera up. The
  consumer runs on every boot of every stack and needs nothing but the numbers.

  Coupling the consumer to the calibration package means every stack that wants
  to know where the camera is drags in a Qt GUI and the .calib file format.
  A flat YAML of named transforms is a better contract: MoveIt reads TF, rviz
  reads TF, and the ZMQ sidecars can parse the same YAML directly without ROS.

Expected file (see config/extrinsics.example.yaml):

    extrinsics:
      - parent: base_link
        child: camera_color_optical_frame
        translation: {x: 0.61, y: -0.19, z: 0.83}
        rotation: {x: 0.0, y: 0.7071, z: 0.0, w: 0.7071}   # quaternion, xyzw
        source: 2026-08-14_d435_eob.calib                   # provenance
"""

import math
import os
import sys

import rclpy
import yaml
from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from tf2_ros import StaticTransformBroadcaster

QUAT_TOL = 1e-3


def _quat_from_entry(entry: dict) -> tuple:
    """Accept either a quaternion or roll/pitch/yaw, return (x, y, z, w)."""
    if 'rotation' in entry:
        r = entry['rotation']
        return (float(r['x']), float(r['y']), float(r['z']), float(r['w']))

    if 'rpy' in entry:
        roll, pitch, yaw = (float(v) for v in entry['rpy'])
        cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
        cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
        cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
        return (
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
            cr * cp * cy + sr * sp * sy,
        )

    raise KeyError("entry needs either 'rotation' (quaternion) or 'rpy'")


class ExtrinsicsPublisher(Node):

    def __init__(self):
        super().__init__('extrinsics_publisher')

        self.declare_parameter('extrinsics_file', '')
        path = self.get_parameter('extrinsics_file').value

        if not path:
            self.get_logger().fatal('extrinsics_file parameter is empty')
            raise SystemExit(2)

        if not os.path.isfile(path):
            # Fail loudly. A cell running with no extrinsics looks fine in rviz
            # right up until something reaches for an object and misses.
            self.get_logger().fatal(
                f'no extrinsics at {path}. Run the calib profile and promote '
                f'the result with scripts/promote_calibration.py.'
            )
            raise SystemExit(2)

        with open(path, 'r') as handle:
            doc = yaml.safe_load(handle) or {}

        entries = doc.get('extrinsics', [])
        if not entries:
            self.get_logger().fatal(f'{path} contains no "extrinsics:" list')
            raise SystemExit(2)

        self._broadcaster = StaticTransformBroadcaster(self)
        stamp = self.get_clock().now().to_msg()
        transforms = []

        for entry in entries:
            qx, qy, qz, qw = _quat_from_entry(entry)
            norm = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
            if abs(norm - 1.0) > QUAT_TOL:
                # Silently renormalising hides upstream bugs; say so, then fix.
                self.get_logger().warn(
                    f"{entry['parent']} -> {entry['child']}: quaternion norm "
                    f'{norm:.6f}, renormalising'
                )
                qx, qy, qz, qw = (v / norm for v in (qx, qy, qz, qw))

            tf = TransformStamped()
            tf.header.stamp = stamp
            tf.header.frame_id = entry['parent']
            tf.child_frame_id = entry['child']
            t = entry['translation']
            tf.transform.translation.x = float(t['x'])
            tf.transform.translation.y = float(t['y'])
            tf.transform.translation.z = float(t['z'])
            tf.transform.rotation.x = qx
            tf.transform.rotation.y = qy
            tf.transform.rotation.z = qz
            tf.transform.rotation.w = qw
            transforms.append(tf)

            self.get_logger().info(
                f"{entry['parent']} -> {entry['child']}  "
                f"[{entry.get('source', 'no provenance recorded')}]"
            )

        self._broadcaster.sendTransform(transforms)
        self.get_logger().info(f'published {len(transforms)} static transforms')


def main(argv=None):
    rclpy.init(args=argv)
    try:
        node = ExtrinsicsPublisher()
    except SystemExit as exc:
        rclpy.shutdown()
        return int(exc.code or 1)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
