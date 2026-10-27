#!/usr/bin/env python3
"""Regenerate the desktop icon source PNG (1024x1024, stdlib only).

Design: a dark rounded square, an orange core with smaller nodes around it
joined by lines -- the node shell around a core. No third-party packages, so
it runs on any machine with Python 3, including Linux, where no .icns can be
produced. The .icns itself is built on macOS by make-icon.sh, which the app
build script calls.

Usage: python3 make-icon-source.py [output-path]
Default output: Assets/ExoIcon-1024.png next to this script.
"""
import math
import struct
import sys
import zlib
from pathlib import Path

SIZE = 1024
RADIUS = 190  # rounded-corner radius


def chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    return out + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "Assets" / "ExoIcon-1024.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    bg = (18, 20, 38, 255)
    core = (255, 124, 26, 255)
    core_light = (255, 178, 92, 255)
    node = (235, 238, 255, 255)
    line = (120, 130, 190, 255)
    cx = cy = SIZE // 2
    nodes = []
    for i in range(8):
        angle = math.pi / 4 * i + math.pi / 8
        nodes.append((cx + int(330 * math.cos(angle)), cy + int(330 * math.sin(angle))))

    def inside_rounded(x, y):
        if RADIUS <= x < SIZE - RADIUS:
            return True
        if RADIUS <= y < SIZE - RADIUS:
            return True
        for ox, oy in ((RADIUS, RADIUS), (SIZE - RADIUS, RADIUS),
                       (RADIUS, SIZE - RADIUS), (SIZE - RADIUS, SIZE - RADIUS)):
            if (x - ox) ** 2 + (y - oy) ** 2 <= RADIUS * RADIUS:
                return True
        return False

    def dist_to_segment(x, y, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        t = 0 if length2 == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / length2))
        return math.hypot(x - (ax + t * dx), y - (ay + t * dy))

    raw = bytearray()
    for y in range(SIZE):
        raw.append(0)  # no filter
        for x in range(SIZE):
            if not inside_rounded(x, y):
                raw.extend((0, 0, 0, 0))
                continue
            pixel = bg
            if min(dist_to_segment(x, y, cx, cy, nx, ny) for nx, ny in nodes) <= 5:
                pixel = line
            if any((x - nx) ** 2 + (y - ny) ** 2 <= 34 * 34 for nx, ny in nodes):
                pixel = node
            if (x - cx) ** 2 + (y - cy) ** 2 <= 170 * 170:
                pixel = core
            if (x - cx + 40) ** 2 + (y - cy + 40) ** 2 <= 70 * 70:
                pixel = core_light
            raw.extend(pixel)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(raw), level=9))
        + chunk(b"IEND", b"")
    )
    out.write_bytes(png)
    print(f"Wrote {out} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
