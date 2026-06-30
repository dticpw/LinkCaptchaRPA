from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .config import AppConfig


TEMPLATE_SIZE = (32, 44)


@dataclass
class LightOcrResult:
    code: str
    confidence: float
    method: str


def recognize_captcha(screen: Image.Image, config: AppConfig) -> str:
    result = recognize_captcha_light(screen, config)
    if result.confidence >= 0.58 and re.fullmatch(r"\d{4}", result.code):
        return result.code

    try:
        return recognize_captcha_tesseract(screen, config)
    except Exception as exc:
        raise RuntimeError(
            f"轻量 OCR 置信度不足：{result.code!r}, confidence={result.confidence:.3f}；"
            f"Tesseract 兜底失败：{exc}"
        ) from exc


def recognize_captcha_light(screen: Image.Image, config: AppConfig) -> LightOcrResult:
    crop = _crop_captcha(screen, config)
    mask = _foreground_mask(crop)
    digit_cells = _split_digit_cells(mask, expected=4)
    if len(digit_cells) != 4:
        return LightOcrResult("", 0.0, "light-template")

    templates = _digit_templates()
    digits: list[str] = []
    scores: list[float] = []

    for cell in digit_cells:
        normalized = _normalize_digit(cell)
        digit, score = _match_digit(normalized, templates)
        digits.append(digit)
        scores.append(score)

    return LightOcrResult("".join(digits), float(min(scores) if scores else 0.0), "light-template")


def recognize_captcha_tesseract(screen: Image.Image, config: AppConfig) -> str:
    crop = _crop_captcha(screen, config)
    mask = _foreground_mask(crop)
    binary = cv2.resize(mask, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    binary = 255 - binary

    try:
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("未安装 pytesseract，当前只能测试区域，不能自动 OCR。") from exc

    text = pytesseract.image_to_string(
        Image.fromarray(binary),
        config="--psm 7 -c tessedit_char_whitelist=0123456789",
    )
    digits = "".join(re.findall(r"\d", text))
    if not re.fullmatch(r"\d{4}", digits):
        raise RuntimeError(f"OCR 未得到四位数字，原始结果：{text!r}")
    return digits


def _crop_captcha(screen: Image.Image, config: AppConfig) -> Image.Image:
    rect = config.captcha_region
    return screen.crop((rect.x, rect.y, rect.x + rect.w, rect.y + rect.h)).convert("RGB")


def _foreground_mask(crop: Image.Image) -> np.ndarray:
    rgb = np.array(crop)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    # Digits may be black, dark gray, blue, or purple. Keep saturated colored
    # pixels and low-value dark pixels, then clean small background texture.
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    dark_text = gray < 145
    colored_text = (saturation > 75) & (value < 225)
    mask = np.where(dark_text | colored_text, 255, 0).astype(np.uint8)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask = _remove_edge_components(mask)
    return mask


def _remove_edge_components(mask: np.ndarray) -> np.ndarray:
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    cleaned = mask.copy()
    h, w = mask.shape
    for label in range(1, num_labels):
        x, y, bw, bh, area = stats[label]
        touches_edge = x <= 1 or y <= 1 or (x + bw) >= (w - 1) or (y + bh) >= (h - 1)
        is_frame_like = bw > w * 0.55 or bh > h * 0.75
        if touches_edge and is_frame_like:
            cleaned[labels == label] = 0
    return cleaned


def _split_digit_cells(mask: np.ndarray, expected: int = 4) -> list[np.ndarray]:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0 or len(ys) == 0:
        return []

    x1, x2 = int(xs.min()), int(xs.max()) + 1
    y1, y2 = int(ys.min()), int(ys.max()) + 1
    x1 = max(0, x1 - 3)
    y1 = max(0, y1 - 3)
    x2 = min(mask.shape[1], x2 + 3)
    y2 = min(mask.shape[0], y2 + 3)
    text = mask[y1:y2, x1:x2]

    components = _component_cells(text)
    if len(components) == expected:
        return components

    # Four fixed digits are easier and safer to split by equal cells when
    # interference lines connect characters or font spacing is uneven.
    h, w = text.shape
    cells: list[np.ndarray] = []
    for index in range(expected):
        start = int(round(index * w / expected))
        end = int(round((index + 1) * w / expected))
        pad = max(2, int(w * 0.015))
        start = max(0, start - pad)
        end = min(w, end + pad)
        cells.append(text[:, start:end])
    return cells


def _component_cells(mask: np.ndarray) -> list[np.ndarray]:
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    boxes: list[tuple[int, int, int, int]] = []
    h, w = mask.shape
    for label in range(1, num_labels):
        x, y, bw, bh, area = stats[label]
        if area < max(8, h * w * 0.002):
            continue
        if bh < h * 0.22 or bw < 3:
            continue
        boxes.append((int(x), int(y), int(bw), int(bh)))

    boxes.sort(key=lambda item: item[0])
    if len(boxes) != 4:
        return []

    cells: list[np.ndarray] = []
    for x, y, bw, bh in boxes:
        x1 = max(0, x - 2)
        y1 = max(0, y - 2)
        x2 = min(w, x + bw + 2)
        y2 = min(h, y + bh + 2)
        cells.append(mask[y1:y2, x1:x2])
    return cells


def _normalize_digit(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.where(mask > 0)
    if len(xs) == 0 or len(ys) == 0:
        return np.zeros((TEMPLATE_SIZE[1], TEMPLATE_SIZE[0]), dtype=np.uint8)

    digit = mask[max(0, ys.min() - 2) : min(mask.shape[0], ys.max() + 3), max(0, xs.min() - 2) : min(mask.shape[1], xs.max() + 3)]
    target_w, target_h = TEMPLATE_SIZE
    scale = min((target_w - 6) / max(1, digit.shape[1]), (target_h - 6) / max(1, digit.shape[0]))
    resized_w = max(1, int(round(digit.shape[1] * scale)))
    resized_h = max(1, int(round(digit.shape[0] * scale)))
    resized = cv2.resize(digit, (resized_w, resized_h), interpolation=cv2.INTER_AREA)

    canvas = np.zeros((target_h, target_w), dtype=np.uint8)
    x = (target_w - resized_w) // 2
    y = (target_h - resized_h) // 2
    canvas[y : y + resized_h, x : x + resized_w] = resized
    return canvas


def _match_digit(mask: np.ndarray, templates: dict[str, list[np.ndarray]]) -> tuple[str, float]:
    best_digit = ""
    best_score = -1.0
    sample = (mask > 0).astype(np.uint8)
    sample_count = int(sample.sum())

    for digit, digit_templates in templates.items():
        for template in digit_templates:
            templ = (template > 0).astype(np.uint8)
            intersection = int(np.logical_and(sample, templ).sum())
            union = int(np.logical_or(sample, templ).sum())
            dice = (2 * intersection) / max(1, sample_count + int(templ.sum()))
            iou = intersection / max(1, union)
            score = 0.72 * dice + 0.28 * iou
            if score > best_score:
                best_digit = digit
                best_score = float(score)

    return best_digit, best_score


@functools.lru_cache(maxsize=1)
def _digit_templates() -> dict[str, list[np.ndarray]]:
    fonts = _candidate_fonts()
    templates: dict[str, list[np.ndarray]] = {str(i): [] for i in range(10)}
    for digit in templates:
        for font_path in fonts:
            for size in (38, 44, 52, 60, 70):
                try:
                    font = ImageFont.truetype(str(font_path), size)
                except OSError:
                    continue
                for angle in (-15, -8, 0, 8, 15):
                    templates[digit].append(_render_digit_template(digit, font, angle))

    # Last resort for machines with unusual font folders.
    if not any(templates.values()):
        font = ImageFont.load_default()
        for digit in templates:
            templates[digit].append(_render_digit_template(digit, font, 0))

    return templates


def _candidate_fonts() -> list[Path]:
    windir = Path("C:/Windows/Fonts")
    names = [
        "georgiab.ttf",
        "georgia.ttf",
        "timesbd.ttf",
        "times.ttf",
        "arialbd.ttf",
        "arial.ttf",
        "calibrib.ttf",
        "calibri.ttf",
    ]
    return [windir / name for name in names if (windir / name).exists()]


def _render_digit_template(digit: str, font: ImageFont.ImageFont, angle: int) -> np.ndarray:
    source = Image.new("L", (96, 96), 0)
    draw = ImageDraw.Draw(source)
    bbox = draw.textbbox((0, 0), digit, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(((96 - w) / 2 - bbox[0], (96 - h) / 2 - bbox[1]), digit, fill=255, font=font)
    if angle:
        source = source.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor=0)
    arr = np.array(source)
    _, arr = cv2.threshold(arr, 30, 255, cv2.THRESH_BINARY)
    return _normalize_digit(arr)
