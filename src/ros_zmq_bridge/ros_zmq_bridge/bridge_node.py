"""Snapshot ROS state into a frame packet and serve it over ZMQ.

THE POINT OF THIS FILE
    Heavy CUDA perception (pose estimation, segmentation, mesh reconstruction,
    collision-aware planning) has a dependency graph that fights with ROS's.
    Installing rclpy into each of those containers means every one of them
    inherits the ROS graph, and you end up debugging Docker builds instead of
    robotics.

    So: exactly one node speaks ROS. It gathers a synchronised colour + depth +
    intrinsics + TF snapshot and hands it over the wire. The sidecars stay pure
    compute -- they receive a packet and extrinsics as arguments and never
    import rclpy.

WIRE FORMAT (msgpack, REQ/REP)
    Request:  {"cmd": "capture"}  |  {"cmd": "ping"}
    Reply:    {
        "ok": bool, "error": str|null, "stamp_ns": int, "seq": int,
        "color":  {"h","w","encoding","data"},        # data = raw bytes
        "depth":  {"h","w","encoding","data","scale"},# scale -> metres
        "K": [9 floats, row-major], "D": [k1..],
        "frames": {"camera_optical": str, "base": str, "ee": str},
        "T_base_camera": [16 floats, row-major],      # extrinsic, from TF
        "T_base_ee":     [16 floats, row-major],      # FK, from TF
    }

ALIGN THIS WITH YOUR EXISTING SCHEMA. If your sim-side capture script already
emits frame packets, make this match it rather than the other way round -- the
whole value is that sim and hardware produce byte-identical packets so the
sidecars cannot tell which one they are talking to.
"""

from __future__ import annotations

import threading

import msgpack
import numpy as np
import rclpy
import zmq
from cv_bridge import CvBridge
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CameraInfo, Image
from tf2_ros import Buffer, TransformListener


def _matrix_from_tf(tf) -> list:
    """TransformStamped -> row-major 4x4 as a flat list."""
    t, q = tf.transform.translation, tf.transform.rotation
    x, y, z, w = q.x, q.y, q.z, q.w
    m = np.eye(4)
    m[:3, :3] = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])
    m[:3, 3] = (t.x, t.y, t.z)
    return m.flatten().tolist()


class ZmqBridge(Node):

    def __init__(self):
        super().__init__('ros_zmq_bridge')

        p = self.declare_parameters('', [
            ('bind_address', 'tcp://0.0.0.0:5680'),
            ('color_topic', '/camera/camera/color/image_raw'),
            ('depth_topic', '/camera/camera/aligned_depth_to_color/image_raw'),
            ('camera_info_topic', '/camera/camera/color/camera_info'),
            ('camera_optical_frame', 'camera_color_optical_frame'),
            ('base_frame', 'base_link'),
            ('ee_frame', 'tool0'),
            ('depth_scale', 0.001),
            ('sync_slop', 0.05),
        ])
        self.cfg = {param.name: param.value for param in p}

        self._bridge = CvBridge()
        self._lock = threading.Lock()
        self._latest = None
        self._seq = 0

        # Sensor data is best-effort by convention; matching it avoids the
        # silent no-messages-ever failure mode.
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)

        subs = [
            Subscriber(self, Image, self.cfg['color_topic'], qos_profile=qos),
            Subscriber(self, Image, self.cfg['depth_topic'], qos_profile=qos),
            Subscriber(self, CameraInfo, self.cfg['camera_info_topic'], qos_profile=qos),
        ]
        self._sync = ApproximateTimeSynchronizer(
            subs, queue_size=5, slop=float(self.cfg['sync_slop']))
        self._sync.registerCallback(self._on_frame)

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        ctx = zmq.Context.instance()
        self._sock = ctx.socket(zmq.REP)
        self._sock.bind(self.cfg['bind_address'])
        self.get_logger().info(f"serving frame packets on {self.cfg['bind_address']}")

        self._server = threading.Thread(target=self._serve, daemon=True)
        self._server.start()

    def _on_frame(self, color_msg, depth_msg, info_msg):
        with self._lock:
            self._latest = (color_msg, depth_msg, info_msg)

    def _lookup(self, target: str, source: str):
        """TF from source expressed in target. Returns None on failure."""
        try:
            return self._tf_buffer.lookup_transform(
                target, source, rclpy.time.Time())
        except Exception as exc:  # tf2 raises a family of exceptions
            self.get_logger().warn(f'TF {target} <- {source}: {exc}')
            return None

    def _build_packet(self) -> dict:
        with self._lock:
            latest = self._latest

        if latest is None:
            return {'ok': False, 'error': 'no synchronised frame received yet'}

        color_msg, depth_msg, info_msg = latest
        color = self._bridge.imgmsg_to_cv2(color_msg, desired_encoding='rgb8')
        depth = self._bridge.imgmsg_to_cv2(depth_msg, desired_encoding='passthrough')

        base = self.cfg['base_frame']
        cam = self.cfg['camera_optical_frame']
        ee = self.cfg['ee_frame']

        tf_cam = self._lookup(base, cam)
        tf_ee = self._lookup(base, ee)
        if tf_cam is None:
            return {'ok': False,
                    'error': f'no TF {base} <- {cam}. Is the cell profile up?'}

        self._seq += 1
        stamp = color_msg.header.stamp
        return {
            'ok': True,
            'error': None,
            'seq': self._seq,
            'stamp_ns': int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec),
            'color': {
                'h': color.shape[0], 'w': color.shape[1],
                'encoding': 'rgb8', 'data': color.tobytes(),
            },
            'depth': {
                'h': depth.shape[0], 'w': depth.shape[1],
                'encoding': str(depth.dtype), 'data': depth.tobytes(),
                'scale': float(self.cfg['depth_scale']),
            },
            'K': list(info_msg.k),
            'D': list(info_msg.d),
            'frames': {'camera_optical': cam, 'base': base, 'ee': ee},
            'T_base_camera': _matrix_from_tf(tf_cam),
            'T_base_ee': _matrix_from_tf(tf_ee) if tf_ee else None,
        }

    def _serve(self):
        while rclpy.ok():
            try:
                if not self._sock.poll(timeout=200):
                    continue
                req = msgpack.unpackb(self._sock.recv(), raw=False)
                cmd = req.get('cmd', 'capture')
                if cmd == 'ping':
                    reply = {'ok': True, 'error': None}
                elif cmd == 'capture':
                    reply = self._build_packet()
                else:
                    reply = {'ok': False, 'error': f'unknown cmd: {cmd}'}
                self._sock.send(msgpack.packb(reply, use_bin_type=True))
            except Exception as exc:
                self.get_logger().error(f'bridge error: {exc}')
                try:
                    self._sock.send(msgpack.packb(
                        {'ok': False, 'error': str(exc)}, use_bin_type=True))
                except zmq.ZMQError:
                    pass


def main(argv=None):
    rclpy.init(args=argv)
    node = ZmqBridge()
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
