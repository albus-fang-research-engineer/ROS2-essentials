"""Print a running summary of which marker ids the camera is detecting.

The annotated image tells you what is detected right now; this tells you what
has been detected at all, and how reliably. That second question is the one
that matters for calibration: a marker seen in 6% of frames will make sampling
miserable long before it makes the solve wrong.

WHY markers_list AND NOT markers

    aruco_ros suppresses the MarkerArray when a frame produced no detections:

        // publish marker array
        if (marker_msg_->markers.size() > 0) {
          marker_pub_->publish(*marker_msg_);
        }

    So counting messages on `markers` gives a denominator of "frames in which
    something was detected", not "frames". A lone marker visible in 40% of
    frames then reports 100% -- exactly the case this node exists to catch.

    `markers_list` (std_msgs/UInt32MultiArray) is published on every processed
    frame, empty ones included, so a single subscription is both the id source
    and an honest frame counter. It also leaves the detector's pose/TF branch
    switched off, since that branch runs only when `markers` has a subscriber
    and nothing here wants a pose.
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import UInt32MultiArray


class MarkerReport(Node):

    def __init__(self):
        super().__init__('marker_report')
        self.declare_parameter('topic', '/aruco_marker_publisher/markers_list')
        self.declare_parameter('report_period', 2.0)

        topic = self.get_parameter('topic').value
        self._counts: dict[int, int] = {}
        self._frames = 0

        self.create_subscription(UInt32MultiArray, topic, self._on_frame, 10)
        self.create_timer(
            float(self.get_parameter('report_period').value), self._report)

        self.get_logger().info(f'watching {topic}')
        self.get_logger().info(
            'Move the board around the workspace. Ids seen in nearly every '
            'frame are good calibration targets; intermittent ones are not.')

    def _on_frame(self, msg):
        self._frames += 1
        # set(): two markers carrying the same id in one frame would otherwise
        # push that id's rate above 100%.
        for marker_id in set(msg.data):
            self._counts[marker_id] = self._counts.get(marker_id, 0) + 1

    def _report(self):
        # These two branches now mean genuinely different things, because the
        # frame counter ticks whether or not anything was detected.
        if not self._frames:
            self.get_logger().warn(
                'no frames processed yet -- the detector is not receiving '
                'images. Check that the camera is publishing and that the '
                'image/camera_info remappings are right.')
            return
        if not self._counts:
            self.get_logger().warn(
                f'{self._frames} frames processed, no markers in any of them. '
                f'Images are flowing, so this is the wrong dictionary, a '
                f'marker too small in frame, or bad lighting.')
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
