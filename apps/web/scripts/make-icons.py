"""Generate the PWA icons (SPEC 15.6) without any imaging library.

    python3 scripts/make-icons.py

Writes public/icons/{icon-192,icon-512,maskable-512,apple-touch-icon}.png: a white "Q" ring on the
brand blue. The maskable variant keeps the glyph inside the 80% safe zone and is full-bleed.
"""

import math
import struct
import zlib
from pathlib import Path

BLUE = (29, 78, 216)
WHITE = (255, 255, 255)
SUPERSAMPLE = 3


def coverage(x: float, y: float, size: int, scale: float) -> float:
    """1.0 where the glyph is, 0.0 elsewhere (in a unit square scaled by `scale` around centre)."""
    u = ((x / size) - 0.5) / scale
    v = ((y / size) - 0.5) / scale
    r = math.hypot(u, v)
    ring = 0.27 <= r <= 0.40
    # tail of the Q: a short stroke towards the lower right
    t = (u + v) / math.sqrt(2)  # along the diagonal
    d = abs(u - v) / math.sqrt(2)  # distance from the diagonal
    tail = 0.18 <= t <= 0.46 and d <= 0.055
    return 1.0 if ring or tail else 0.0


def render(size: int, scale: float, rounded: bool) -> bytes:
    rows = bytearray()
    radius = size * 0.22
    for y in range(size):
        rows.append(0)  # PNG filter: none
        for x in range(size):
            if rounded:
                # transparent outside a rounded square
                cx = min(max(x, radius), size - 1 - radius)
                cy = min(max(y, radius), size - 1 - radius)
                if math.hypot(x - cx, y - cy) > radius:
                    rows += bytes((0, 0, 0, 0))
                    continue
            hits = 0.0
            for sy in range(SUPERSAMPLE):
                for sx in range(SUPERSAMPLE):
                    px = x + (sx + 0.5) / SUPERSAMPLE
                    py = y + (sy + 0.5) / SUPERSAMPLE
                    hits += coverage(px, py, size, scale)
            a = hits / (SUPERSAMPLE * SUPERSAMPLE)
            rgb = tuple(round(BLUE[i] * (1 - a) + WHITE[i] * a) for i in range(3))
            rows += bytes((*rgb, 255))
    return bytes(rows)


def png(size: int, scale: float, rounded: bool) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(render(size, scale, rounded), 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "public" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    targets = {
        "icon-192.png": (192, 1.0, True),
        "icon-512.png": (512, 1.0, True),
        "apple-touch-icon.png": (180, 1.0, False),  # iOS applies its own mask
        "maskable-512.png": (512, 0.8, False),  # glyph inside the 80% safe zone, full bleed
    }
    for name, (size, scale, rounded) in targets.items():
        (out / name).write_bytes(png(size, scale, rounded))
        print("wrote", out / name)


if __name__ == "__main__":
    main()
