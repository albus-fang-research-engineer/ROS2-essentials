"""Print a running summary of which marker ids the camera is detecting.

The annotated image tells you what is detected right now; this tells you what
has been detected at all, and how reliably. That second question is the one
that matters for calibration: a marker seen in 6% of frames will make sampling
miserable long before it makes the solve wrong.
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node

try:
    from aruco_msgs.msg import MarkerArray
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        'aruco_msgs not found -- run this inside the calibration image'
    ) from exc


class MarkerReport(Node):

    def __init__(self):
        super().__init__('marker_report')
        self.declare_parameter('topic', '/aruco_marker_publisher/markers')
        self.declare_parameter('report_period', 2.0)

        topic = self.get_parameter('topic').value
        self._counts: dict[int, int] = {}
        self._frames = 0

        self.create_subscription(MarkerArray, topic, self._on_markers, 10)
        self.create_timer(
            float(self.get_parameter('report_period').value), self._report)

        self.get_logger().info(f'watching {topic}')
        self.get_logger().info(
            'Move the board around the workspace. Ids seen in nearly every '
            'frame are good calibration targets; intermittent ones are not.')

    def _on_markers(self, msg):
        self._frames += 1
        for marker in msg.markers:
            self._counts[marker.id] = self._counts.get(marker.id, 0) + 1

    def _report(self):
        if not self._frames:
            self.get_logger().warn(
                'no marker messages yet -- is the camera publishing, and are '
                'the image/camera_info remappings right?')
            return
        if not self._counts:
            self.get_logger().warn(
                f'{self._frames} frames, no markers detected. Wrong '
                f'dictionary, marker too small in frame, or badly lit.')
            return

        ranked = sorted(self._counts.items(), key=lambda kv: -kv[1])
        summary = '  '.join(
            f'id {mid}: {100.0 * n / self._frames:.0f}%' for mid, n in ranked)
        self.get_logger().info(f'[{self._frames} frames]  {summary}')

        best, hits = ranked[0]
        if hits / self._frames > 0.9:
            self.get_logger().info(
                f'--> MARKER_ID={best} is a solid choice '
                f'({100.0 * hits / self._frames:.0f}% of frames)')


def main(argv=None):
    rclpy.init(args=argv)
    node = MarkerReport()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
