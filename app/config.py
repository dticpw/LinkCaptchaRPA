from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
PROFILES_DIR = ROOT_DIR / "profiles"
DEFAULT_PROFILE = PROFILES_DIR / "default.json"


@dataclass
class RectConfig:
    x: int
    y: int
    w: int
    h: int


@dataclass
class PointConfig:
    x: int
    y: int


@dataclass
class AppConfig:
    profile_name: str = "default"
    chat_link_region: RectConfig = field(default_factory=lambda: RectConfig(600, 220, 620, 560))
    captcha_region: RectConfig = field(default_factory=lambda: RectConfig(900, 340, 180, 80))
    captcha_input_point: PointConfig = field(default_factory=lambda: PointConfig(980, 470))
    submit_button_point: PointConfig = field(default_factory=lambda: PointConfig(1040, 530))
    link_color_hsv_lower: list[int] = field(default_factory=lambda: [90, 45, 80])
    link_color_hsv_upper: list[int] = field(default_factory=lambda: [130, 255, 255])
    browser_wait_seconds: float = 2.5
    click_duration_seconds: float = 0.05

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        return cls(
            profile_name=data.get("profile_name", "default"),
            chat_link_region=RectConfig(**data.get("chat_link_region", {})),
            captcha_region=RectConfig(**data.get("captcha_region", {})),
            captcha_input_point=PointConfig(**data.get("captcha_input_point", {})),
            submit_button_point=PointConfig(**data.get("submit_button_point", {})),
            link_color_hsv_lower=list(data.get("link_color_hsv_lower", [90, 45, 80])),
            link_color_hsv_upper=list(data.get("link_color_hsv_upper", [130, 255, 255])),
            browser_wait_seconds=float(data.get("browser_wait_seconds", 2.5)),
            click_duration_seconds=float(data.get("click_duration_seconds", 0.05)),
        )


def ensure_dirs() -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def load_config(path: Path = DEFAULT_PROFILE) -> AppConfig:
    ensure_dirs()
    if not path.exists():
        cfg = AppConfig()
        save_config(cfg, path)
        return cfg
    return AppConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_config(config: AppConfig, path: Path = DEFAULT_PROFILE) -> None:
    ensure_dirs()
    path.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")

