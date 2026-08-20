#!/usr/bin/env python3
"""Identify which ArUco dictionary a physical board belongs to.

aruco_ros exposes no `dictionary` parameter -- it is fixed at whatever the
vendored library defaults to. A marker from any other dictionary is never
detected, silently, with no warning of any kind. That is indistinguishable
from bad lighting or a bad angle if you only look at the detection rate, so
stop guessing and ask OpenCV directly.

This grabs frames off the live camera topic and runs EVERY predefined
dictionary against them. Exactly one should come back with hits.

    docker compose --profile calib run --rm \
        -v "$PWD/scripts:/scripts:ro" tracker \
        python3 /scripts/identify_dictionary.py

Point the camera at the board first. Fill a decent fraction of the frame,
reasonably square, reasonably lit -- you are testing the dictionary, not the
detector's tolerance for bad geometry.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image

try:
    import cv2
except ImportError:
    sys.exit("no python3 opencv in this image: apt-get install python3-opencv")


# Every predefined dictionary in cv2.aruco, resolved by name so this keeps
# working across OpenCV versions that add or drop families.
def predefined_dictionaries() -> list[str]:
    return sorted(n for n in dir(cv2.aruco) if n.startswith('DICT_'))


def get_dictionary(name: str):
    """OpenCV renamed this API in 4.7. Support both."""
    ident = getattr(cv2.aruco, name)
    if hasattr(cv2.aruco, 'getPredefinedDictionary'):
        return cv2.aruco.getPredefinedDictionary(ident)
    return cv2.aruco.Dictionary_get(ident)


def detect(gray, dictionary):
    """Returns the list of ids found. Handles the 4.7 ArucoDetector split."""
    if hasattr(cv2.aruco, 'ArucoDetector'):
        params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(dictionary, params)
        corners, ids, _ = detector.detectMarkers(gray)
    else:
        params = cv2.aruco.DetectorParameters_create()
        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, dictionary, parameters=params)
    if ids is None:
        return []
    return [int(i) for i in ids.flatten()]


def to_gray(msg: Image):
    """Decode without cv_bridge, which is not guaranteed present for python."""
    buf = np.frombuffer(msg.data, dtype=np.uint8)
    enc = msg.encoding.lower()
    if enc in ('rgb8', 'bgr8'):
        img = buf.reshape(msg.height, msg.width, 3)
        code = cv2.COLOR_RGB2GRAY if enc == 'rgb8' else cv2.COLOR_BGR2GRAY
        return cv2.cvtColor(img, code), img
    if enc in ('mono8', '8uc1'):
        img = buf.reshape(msg.height, msg.width)
        return img, cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    raise ValueError(f'unhandled encoding {msg.encoding!r}')


class Sweeper(Node):

    def __init__(self, topic: str, n_frames: int, save: str | None):
        super().__init__('identify_dictionary')
        self._want = n_frames
        self._save = save
        self._seen = 0
        # Match either publisher policy; the driver may be reliable or
        # sensor-data depending on CAMERA_QOS_ARGS.
        qos = QoSProfile(depth=5)
        qos.reliability = ReliabilityPolicy.BEST_EFFORT
        self._hits: dict[str, set[int]] = {}
        self._names = predefined_dictionaries()
        self.create_subscription(Image, topic, self._on_image, qos)
        self.get_logger().info(
            f'sweeping {len(self._names)} dictionaries over {n_frames} '
            f'frames from {topic}')

    def _on_image(self, msg: Image):
        if self._seen >= self._want:
            return
        try:
            gray, colour = to_gray(msg)
        except ValueError as exc:
            self.get_logger().error(str(exc))
            self._seen = self._want
            return

        if self._save and self._seen == 0:
            cv2.imwrite(self._save, colour[:, :, ::-1]
                        if msg.encoding.lower() == 'rgb8' else colour)
            self.get_logger().info(f'wrote {self._save}')

        for name in self._names:
            try:
                ids = detect(gray, get_dictionary(name))
            except cv2.error:
                continue
            if ids:
                self._hits.setdefault(name, set()).update(ids)

        self._seen += 1
        if self._seen % 5 == 0:
            self.get_logger().info(f'{self._seen}/{self._want} frames')

    @property
    def done(self) -> bool:
        return self._seen >= self._want

    def report(self) -> int:
        print()
        if not self._seen:
            print('NO FRAMES RECEIVED. The camera is not publishing on that '
                  'topic, or the QoS did not match.')
            return 1
        if not self._hits:
            print(f'{self._seen} frames, NO dictionary matched anything.')
            print()
            print('That is not a dictionary problem -- no family in OpenCV')
            print('saw a marker at all. Check the saved frame: is the board')
            print('actually in view, in focus, and not blown out? If it looks')
            print('fine, it may not be an ArUco/AprilTag board (ChArUco with')
            print('very small embedded markers, or a chequerboard).')
            return 1

        print(f'{self._seen} frames processed. Matches:')
        print()
        ranked = sorted(self._hits.items(), key=lambda kv: -len(kv[1]))
        for name, ids in ranked:
            shown = sorted(ids)[:12]
            more = '' if len(ids) <= 12 else f' (+{len(ids) - 12} more)'
            print(f'  {name:<28} {len(ids):>3} ids: {shown}{more}')

        print()
        best, ids = ranked[0]
        print(f'--> dictionary is almost certainly {best}')
        if len(ids) > 1:
            print(f'    {len(ids)} distinct ids: this is a BOARD, not a single')
            print(f'    marker. See the notes on aruco_opencv board support.')
        else:
            print(f'    single marker, id {sorted(ids)[0]}')
        print()
        print('A family that reports one or two stray ids while another')
        print('reports many is a false positive. Trust the one with the most.')
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--topic', default='/camera/camera/color/image_raw')
    ap.add_argument('--frames', type=int, default=20)
    ap.add_argument('--save', default='/ws/dict_sweep_frame.png',
                    help='write the first frame here for eyeballing')
    args = ap.parse_args()

    rclpy.init()
    node = Sweeper(args.topic, args.frames, args.save)
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=1.0)
    except KeyboardInterrupt:
        pass
    code = node.report()
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    sys.exit(code)


if __name__ == '__main__':
    main()
