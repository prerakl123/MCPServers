"""Generate tray icons via Pillow — idle (gray) and active (accent)."""
from __future__ import annotations

from PIL import Image, ImageDraw


def _make(rgb: tuple[int, int, int]) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # rounded square
    d.rounded_rectangle((4, 4, size - 4, size - 4), radius=12, fill=rgb)
    # stylised "?" mark
    d.text((22, 12), "?", fill=(255, 255, 255, 255))
    return img


def idle_icon() -> Image.Image:
    return _make((90, 100, 110))


def active_icon() -> Image.Image:
    return _make((46, 134, 222))
