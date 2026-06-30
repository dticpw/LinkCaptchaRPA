from __future__ import annotations

from PIL import Image, ImageGrab

from .config import RectConfig


def grab_screen() -> Image.Image:
    return ImageGrab.grab(all_screens=True)


def crop_region(image: Image.Image, rect: RectConfig) -> Image.Image:
    return image.crop((rect.x, rect.y, rect.x + rect.w, rect.y + rect.h))

