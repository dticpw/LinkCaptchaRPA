from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

from .config import AppConfig, RectConfig


@dataclass
class LinkCandidate:
    x: int
    y: int
    w: int
    h: int
    area: int

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)


def detect_blue_links(screen: Image.Image, config: AppConfig) -> list[LinkCandidate]:
    rect = config.chat_link_region
    crop = screen.crop((rect.x, rect.y, rect.x + rect.w, rect.y + rect.h)).convert("RGB")
    rgb = np.array(crop)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    lower = np.array(config.link_color_hsv_lower, dtype=np.uint8)
    upper = np.array(config.link_color_hsv_upper, dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask = cv2.dilate(mask, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates: list[LinkCandidate] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = int(cv2.contourArea(contour))
        if w < 14 or h < 6 or area < 20:
            continue
        if w > rect.w * 0.95 or h > 80:
            continue
        candidates.append(LinkCandidate(rect.x + x, rect.y + y, w, h, area))

    candidates.sort(key=lambda item: (item.y + item.h, item.x), reverse=True)
    return candidates


def lowest_link_candidate(screen: Image.Image, config: AppConfig) -> LinkCandidate | None:
    candidates = detect_blue_links(screen, config)
    return candidates[0] if candidates else None


def candidate_to_rect(candidate: LinkCandidate) -> RectConfig:
    return RectConfig(candidate.x, candidate.y, candidate.w, candidate.h)

