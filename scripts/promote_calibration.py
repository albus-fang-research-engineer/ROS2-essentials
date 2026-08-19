#!/usr/bin/env python3
"""Promote an easy_handeye2 result into a cell's extrinsics.yaml.

This is the seam between the calibration producer (runs twice a year, needs a
GUI and the whole rig powered up) and the consumer (runs on every boot, needs
seven numbers). Keeping it a discrete, auditable step -- rather than having the
runtime read .calib files directly -- means a bad calibration cannot silently
propagate into every stack the moment it is saved.

Usage:
    scripts/promote_calibration.py \\
        --calib ~/.ros2/easy_handeye2/calibrations/ur5e_d435_eob.calib \\
        --cell  purdue-ur5e-01

    # inspect without writing
    scripts/promote_calibration.py --calib ... --cell ... --dry-run

The previous extrinsics.yaml is archived alongside, timestamped, before being
replaced. Rolling back a calibration that turned out worse than the old one
should never require git archaeology.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit('pyyaml required: pip install pyyaml')

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_transform(doc):
    """Locate the transform in a .calib file without hard-coding its schema.

    easy_handeye2's on-disk format has moved between versions. Rather than
    pinning to one layout, walk the document for the first mapping that looks
    like a transform. If upstream renames its keys again, this keeps working.
    """
    stack = [doc]
    while stack:
        node = stack.pop(0)
        if isinstance(node, dict):
            keys = set(node)
            if {'translation', 'rotation'} <= keys:
                return node
            if {'x', 'y', 'z', 'qx', 'qy', 'qz', 'qw'} <= keys:
                return {
                    'translation': {k: node[k] for k in 'xyz'},
                    'rotation': {
                        'x': node['qx'], 'y': node['qy'],
                        'z': node['qz'], 'w': node['qw'],
                    },
                }
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return None


def find_frames(doc, calib_type_hint=None):
    """Pull parent/child frame names out of the .calib parameters block."""
    stack, params = [doc], {}
    while stack:
        node = stack.pop(0)
        if isinstance(node, dict):
            for key in ('calibration_type', 'robot_base_frame',
                        'robot_effector_frame', 'tracking_base_frame',
                        'tracking_marker_frame', 'name'):
                if key in node and isinstance(node[key], str):
                    params.setdefault(key, node[key])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)

    calib_type = calib_type_hint or params.get('calibration_type', '')
    tracking_base = params.get('tracking_base_frame', 'camera_optical_frame')

    # eye_on_base solves base -> camera; eye_in_hand solves flange -> camera.
    if 'in_hand' in calib_type:
        parent = params.get('robot_effector_frame', 'tool0')
    else:
        parent = params.get('robot_base_frame', 'base_link')

    return parent, tracking_base, params


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--calib', required=True, type=Path,
                    help='Path to the .calib produced by easy_handeye2.')
    ap.add_argument('--cell', required=True,
                    help='Cell name; writes calibrations/<cell>/extrinsics.yaml.')
    ap.add_argument('--calibrations-dir', type=Path,
                    default=REPO_ROOT / 'calibrations')
    ap.add_argument('--calibration-type', default=None,
                    help='Override if the .calib does not record it.')
    ap.add_argument('--allow-optical-child', action='store_true',
                    help='Promote even if the child is an optical frame. Only '
                         'correct if you composed out the driver extrinsics.')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if not args.calib.is_file():
        return err(f'no such file: {args.calib}')

    doc = yaml.safe_load(args.calib.read_text()) or {}
    transform = find_transform(doc)
    if transform is None:
        return err(f'could not find a transform in {args.calib}\n'
                   f'  parsed keys: {sorted(doc)}')

    parent, child, params = find_frames(doc, args.calibration_type)
    t = transform['translation']
    r = transform['rotation']

    qx, qy, qz, qw = (float(r[k]) for k in ('x', 'y', 'z', 'w'))
    norm = math.hypot(math.hypot(qx, qy), math.hypot(qz, qw))
    if abs(norm - 1.0) > 1e-3:
        print(f'  warn: quaternion norm {norm:.6f}, renormalising')
        qx, qy, qz, qw = (v / norm for v in (qx, qy, qz, qw))

    dist = math.sqrt(sum(float(t[k]) ** 2 for k in ('x', 'y', 'z')))
    print(f'  {parent} -> {child}')
    print(f'  translation  {float(t["x"]):+.4f} {float(t["y"]):+.4f} '
          f'{float(t["z"]):+.4f}   (|t| = {dist:.4f} m)')
    print(f'  rotation     {qx:+.5f} {qy:+.5f} {qz:+.5f} {qw:+.5f}')

    # Refuse to promote a result that would give the camera driver's optical
    # frame a second parent. TF is a tree; the driver already publishes
    # camera_link -> ... -> *_optical_frame, so attaching there makes lookups
    # non-deterministic and orphans the driver's subtree. Solve for the
    # driver's ROOT link instead (set CAMERA_TF_ROOT / camera_ref_frame).
    if child.endswith('_optical_frame'):
        return err(
            f'refusing to promote: child frame is {child}\n'
            f'  The camera driver already publishes a parent for that frame,\n'
            f'  and TF allows only one. Re-run the calibration with\n'
            f'  camera_ref_frame / CAMERA_TF_ROOT set to the driver\'s root\n'
            f'  link (camera_link for RealSense) so the solve targets that.\n'
            f'  Override with --allow-optical-child only if you have already\n'
            f'  composed out the driver\'s internal extrinsics yourself.'
        ) if not args.allow_optical_child else print(
            f'  WARN: promoting with child={child} as explicitly requested')

    # A camera 4 m from the robot base, or 2 cm from it, is almost always a
    # frame-convention mistake rather than a real measurement.
    if dist < 0.02 or dist > 4.0:
        print(f'  WARN: |t| = {dist:.3f} m is implausible for a bench cell. '
              f'Check that you did not mix base_link with base.')

    entry = {
        'parent': parent,
        'child': child,
        'translation': {k: round(float(t[k]), 6) for k in ('x', 'y', 'z')},
        'rotation': {'x': round(qx, 8), 'y': round(qy, 8),
                     'z': round(qz, 8), 'w': round(qw, 8)},
        'source': args.calib.name,
        'promoted_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'calibration_type': params.get('calibration_type', args.calibration_type or 'unknown'),
    }

    cell_dir = args.calibrations_dir / args.cell
    out = cell_dir / 'extrinsics.yaml'

    existing = {'extrinsics': []}
    if out.is_file():
        existing = yaml.safe_load(out.read_text()) or {'extrinsics': []}

    # Replace any existing entry for the same parent/child pair, keep the rest.
    kept = [e for e in existing.get('extrinsics', [])
            if not (e.get('parent') == parent and e.get('child') == child)]
    if len(kept) != len(existing.get('extrinsics', [])):
        print(f'  replacing existing {parent} -> {child} entry')
    merged = {'extrinsics': kept + [entry]}

    if args.dry_run:
        print('\n--- dry run, would write ---')
        print(yaml.safe_dump(merged, sort_keys=False))
        return 0

    cell_dir.mkdir(parents=True, exist_ok=True)

    # Archive the .calib itself, date-stamped. Calibration results are data:
    # commit them, never overwrite them.
    stamp = dt.datetime.now().strftime('%Y-%m-%d')
    shutil.copy2(args.calib, cell_dir / f'{stamp}_{args.calib.name}')

    if out.is_file():
        backup = cell_dir / f'extrinsics.{stamp}.bak.yaml'
        shutil.copy2(out, backup)
        print(f'  previous extrinsics archived -> {backup.name}')

    out.write_text(
        '# Generated by scripts/promote_calibration.py -- edit by hand only if\n'
        '# you are prepared to explain the numbers six months from now.\n'
        + yaml.safe_dump(merged, sort_keys=False)
    )
    print(f'\nwrote {out}')
    print('restart the cell profile to pick it up:')
    print(f'  docker compose --profile cell up -d --force-recreate cell')
    return 0


def err(msg: str) -> int:
    print(f'error: {msg}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
