from __future__ import annotations

import time

import pyautogui

from .config import AppConfig
from .link_detector import LinkCandidate


pyautogui.FAILSAFE = True


def click_point(x: int, y: int, duration: float = 0.05) -> None:
    pyautogui.moveTo(x, y, duration=duration)
    pyautogui.click()


def click_link(candidate: LinkCandidate, config: AppConfig) -> None:
    x, y = candidate.center
    click_point(x, y, config.click_duration_seconds)


def fill_captcha_and_submit(code: str, config: AppConfig) -> None:
    click_point(config.captcha_input_point.x, config.captcha_input_point.y, config.click_duration_seconds)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.write(code, interval=0.02)
    click_point(config.submit_button_point.x, config.submit_button_point.y, config.click_duration_seconds)


def wait_browser(config: AppConfig) -> None:
    time.sleep(config.browser_wait_seconds)

