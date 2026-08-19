#!/usr/bin/env python3
"""Generate a print-accurate ArUco marker sheet.

WHY A "CANDIDATES" SHEET

    aruco_ros as installed here exposes no `dictionary` parameter, so the
    dictionary is fixed at whatever the underlying ArUco library defaults to,
    and that default has changed between versions. A marker printed from the
    wrong dictionary does not degrade gracefully -- it simply never detects,
    with no error saying why.

    Rather than guess, print one sheet containing the same ID rendered from
    each plausible dictionary, hold it up, and let the detector tell you which
    one it recognises. That is one print instead of a guessing loop.

PRINT SCALING IS THE OTHER TRAP

    `marker_size` is the physical edge of the BLACK SQUARE in metres, border
    included. Printers apply their own scaling ("fit to page", margins), so the
    number you asked for is not necessarily the number you get. Every sheet
    carries a 100 mm reference line: measure it after printing. If it is not
    100 mm, everything on the page scaled by the same factor, and the honest
    fix is to measure the actual black square with calipers and use THAT.

Usage:
    scripts/make_marker.py --size 0.06                  # candidate sheet
    scripts/make_marker.py --size 0.06 --dict ARUCO_ORIGINAL --id 42
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import cv2
    import numpy as np
except ImportError:
    sys.exit('needs opencv + numpy:  pip install opencv-contrib-python numpy')

# Ordered by how likely each is to be the library default.
CANDIDATES = ['ARUCO_ORIGINAL', 'ARUCO_MIP_36h12', '6X6_250', '4X4_50']

MM_PER_M = 1000.0


def _dictionary(name: str):
    attr = f'DICT_{name}'
    if not hasattr(cv2.aruco, attr):
        raise SystemExit(f'unknown dictionary {name}; have: '
                         + ', '.join(sorted(n[5:] for n in dir(cv2.aruco)
                                            if n.startswith('DICT_'))))
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, attr))


def _render(dictionary, marker_id: int, px: int):
    """generateImageMarker (OpenCV >= 4.7) vs drawMarker (older)."""
    if hasattr(cv2.aruco, 'generateImageMarker'):
        return cv2.aruco.generateImageMarker(dictionary, marker_id, px)
    return cv2.aruco.drawMarker(dictionary, marker_id, px)


def _label(canvas, text, x, y, scale=0.6):
    cv2.putText(canvas, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
                (0, 0, 0), 1, cv2.LINE_AA)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--size', type=float, required=True,
                    help='Black square edge in METRES, e.g. 0.06.')
    ap.add_argument('--id', type=int, default=42, help='Marker id.')
    ap.add_argument('--dict', default=None,
                    help='Single dictionary. Omit for a candidate sheet.')
    ap.add_argument('--dpi', type=int, default=300)
    ap.add_argument('--out', type=Path, default=Path('marker_sheet.png'))
    args = ap.parse_args()

    px_per_m = args.dpi / 0.0254
    side = int(round(args.size * px_per_m))
    if side < 50:
        return err(f'{args.size} m at {args.dpi} dpi is only {side} px; '
                   f'raise --size or --dpi')

    quiet = max(side // 6, int(0.008 * px_per_m))   # >= 1 module, >= 8 mm
    names = [args.dict] if args.dict else CANDIDATES

    tiles = []
    for name in names:
        dictionary = _dictionary(name)
        n_markers = dictionary.bytesList.shape[0]
        if args.id >= n_markers:
            print(f'  skip {name}: only {n_markers} ids, {args.id} is out of range')
            continue
        marker = _render(dictionary, args.id, side)

        h = side + 2 * quiet + int(0.012 * px_per_m)
        tile = np.full((h, side + 2 * quiet), 255, dtype=np.uint8)
        tile[quiet:quiet + side, quiet:quiet + side] = marker
        _label(tile, f'{name}  id={args.id}',
               quiet, h - int(0.003 * px_per_m), scale=args.dpi / 500.0)
        tiles.append(tile)
        print(f'  {name}: id {args.id} of {n_markers}')

    if not tiles:
        return err('no dictionary contained that id')

    # Two columns, or the candidate sheet runs off the end of a page.
    pad = int(0.01 * px_per_m)
    cols = 1 if len(tiles) == 1 else 2
    rows = (len(tiles) + cols - 1) // cols
    tw = max(t.shape[1] for t in tiles)
    th = max(t.shape[0] for t in tiles)
    ruler_h = int(0.035 * px_per_m)

    width = max(cols * tw + (cols + 1) * pad, int(0.115 * px_per_m) + 2 * pad)
    height = rows * th + (rows + 1) * pad + ruler_h
    sheet = np.full((height, width), 255, dtype=np.uint8)

    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        y0 = pad + r * (th + pad)
        x0 = pad + c * (tw + pad)
        sheet[y0:y0 + tile.shape[0], x0:x0 + tile.shape[1]] = tile

    y = pad + rows * (th + pad)

    # Warn rather than silently emitting something unprintable.
    w_mm, h_mm = width / px_per_m * 1000, height / px_per_m * 1000
    for page, (pw, ph) in {'A4': (210, 297), 'Letter': (216, 279)}.items():
        if w_mm <= pw - 10 and h_mm <= ph - 10:
            print(f'  fits {page} with margins')
            break
    else:
        print(f'  NOTE: sheet is {w_mm:.0f}x{h_mm:.0f} mm and will not fit A4 '
              f'or Letter with margins. Reduce --size, or pass --dict to print '
              f'a single candidate per page.')

    # 100 mm reference line: the only way to catch printer scaling.
    ruler_px = int(0.100 * px_per_m)
    y0 = y + ruler_h // 2
    cv2.line(sheet, (pad, y0), (pad + ruler_px, y0), (0, 0, 0), 3)
    for x in (pad, pad + ruler_px):
        cv2.line(sheet, (x, y0 - 12), (x, y0 + 12), (0, 0, 0), 3)
    _label(sheet, 'this line must measure 100 mm after printing',
           pad, y0 + int(0.010 * px_per_m), scale=args.dpi / 500.0)

    cv2.imwrite(str(args.out), sheet)
    print(f'\nwrote {args.out}  ({sheet.shape[1]}x{sheet.shape[0]} px @ {args.dpi} dpi)')
    print(f'nominal black square edge: {args.size * MM_PER_M:.1f} mm')
    print('\nPrint at 100% scale (NOT "fit to page"). Then:')
    print('  1. measure the 100 mm line; if it is off, everything scaled')
    print('  2. measure the actual black square with calipers')
    print('  3. put THAT value, in metres, in MARKER_SIZE')
    print('  4. mount it rigidly -- a flexing marker is unrecoverable noise')
    return 0


def err(msg: str) -> int:
    print(f'error: {msg}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
