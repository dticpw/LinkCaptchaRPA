from __future__ import annotations

import sys
from dataclasses import dataclass

import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .automation import click_link, fill_captcha_and_submit, wait_browser
from .captcha_ocr import recognize_captcha, recognize_captcha_light
from .config import AppConfig, DEFAULT_PROFILE, PointConfig, RectConfig, load_config, save_config
from .link_detector import detect_blue_links, lowest_link_candidate
from .screen_capture import grab_screen


@dataclass(frozen=True)
class OverlayStyle:
    title: str
    color: QColor
    fill: QColor


class OverlayBox(QWidget):
    def __init__(self, key: str, style: OverlayStyle, geometry: QRect, on_changed):
        super().__init__()
        self.key = key
        self.style = style
        self.on_changed = on_changed
        self._drag_start: QPoint | None = None
        self._resize_start: QPoint | None = None
        self._start_geometry: QRect | None = None
        self._resizing = False

        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setMinimumSize(28, 28)
        self.setGeometry(geometry)
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        rect = self.rect().adjusted(1, 1, -2, -2)

        painter.fillRect(rect, self.style.fill)
        painter.setPen(QPen(self.style.color, 3))
        painter.drawRect(rect)

        label_rect = QRect(4, 4, min(120, self.width() - 8), 20)
        painter.fillRect(label_rect, QColor(0, 0, 0, 150))
        painter.setPen(Qt.white)
        painter.drawText(label_rect.adjusted(4, 0, 0, 0), Qt.AlignVCenter | Qt.AlignLeft, self.style.title)

        painter.setPen(QPen(self.style.color, 2))
        x = self.width() - 14
        y = self.height() - 14
        painter.drawLine(x, self.height() - 4, self.width() - 4, y)
        painter.drawLine(x + 5, self.height() - 4, self.width() - 4, y + 5)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        pos = event.position().toPoint()
        self._start_geometry = self.geometry()
        self._resizing = self._is_resize_area(pos)
        if self._resizing:
            self._resize_start = event.globalPosition().toPoint()
        else:
            self._drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        self.setCursor(Qt.SizeFDiagCursor if self._is_resize_area(pos) else Qt.SizeAllCursor)

        if self._resizing and self._resize_start and self._start_geometry:
            delta = event.globalPosition().toPoint() - self._resize_start
            new_w = max(self.minimumWidth(), self._start_geometry.width() + delta.x())
            new_h = max(self.minimumHeight(), self._start_geometry.height() + delta.y())
            self.setGeometry(self._start_geometry.x(), self._start_geometry.y(), new_w, new_h)
            self.on_changed()
            return

        if self._drag_start:
            self.move(event.globalPosition().toPoint() - self._drag_start)
            self.on_changed()

    def mouseReleaseEvent(self, event):
        self._drag_start = None
        self._resize_start = None
        self._start_geometry = None
        self._resizing = False
        self.on_changed()

    def _is_resize_area(self, pos: QPoint) -> bool:
        return pos.x() >= self.width() - 18 and pos.y() >= self.height() - 18

    def to_rect(self) -> RectConfig:
        geo = self.geometry()
        return RectConfig(geo.x(), geo.y(), geo.width(), geo.height())

    def to_point(self) -> PointConfig:
        geo = self.geometry()
        return PointConfig(geo.x() + geo.width() // 2, geo.y() + geo.height() // 2)

    def set_from_rect(self, rect: RectConfig) -> None:
        self.setGeometry(rect.x, rect.y, rect.w, rect.h)

    def set_from_point(self, point: PointConfig) -> None:
        size = max(34, min(self.width() or 42, 90))
        self.setGeometry(point.x - size // 2, point.y - size // 2, size, size)


class ControllerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("微信验证码 RPA 控制器")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.config = load_config()
        self.screen = None
        self.overlays_visible = True
        self._syncing = False

        self.overlays: dict[str, OverlayBox] = {}
        self.coord_labels: dict[str, QLabel] = {}
        self.spinboxes: dict[str, QSpinBox | QDoubleSpinBox] = {}
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(150)

        self._build_ui()
        self._create_overlays()
        self._sync_form_from_config()
        self.resize(430, 560)

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel("微信验证码 RPA 控制器")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        root.addWidget(title)

        btn_grid = QVBoxLayout()
        for row in [
            [("运行一次", self.run_once), ("测试链接", self.test_link)],
            [("测试验证码", self.test_captcha), ("点击链接", self.click_detected_link)],
            [("取样链接色", self.sample_link_color), ("显示/隐藏框", self.toggle_overlays)],
            [("保存配置", self.save_profile), ("加载配置", self.load_profile)],
        ]:
            line = QHBoxLayout()
            for text, handler in row:
                button = QPushButton(text)
                button.setMinimumHeight(34)
                button.clicked.connect(handler)
                line.addWidget(button)
            btn_grid.addLayout(line)
        root.addLayout(btn_grid)

        coords = QFormLayout()
        for key, label in [
            ("chat", "链接框"),
            ("captcha", "识别框"),
            ("input", "填写框"),
            ("submit", "提交框"),
        ]:
            value = QLabel("")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.coord_labels[key] = value
            coords.addRow(QLabel(label), value)
        root.addLayout(coords)

        advanced = QFormLayout()
        for key in ["h_lower", "s_lower", "v_lower", "h_upper", "s_upper", "v_upper"]:
            box = QSpinBox()
            box.setRange(0, 255)
            box.valueChanged.connect(self._sync_config_from_form)
            self.spinboxes[key] = box
            advanced.addRow(QLabel(key), box)

        wait_box = QDoubleSpinBox()
        wait_box.setRange(0.1, 30.0)
        wait_box.setSingleStep(0.1)
        wait_box.valueChanged.connect(self._sync_config_from_form)
        self.spinboxes["browser_wait_seconds"] = wait_box
        advanced.addRow(QLabel("等待网页秒数"), wait_box)
        root.addLayout(advanced)

        root.addWidget(QLabel("日志"))
        root.addWidget(self.log_box, 1)
        self.setCentralWidget(central)

    def _create_overlays(self) -> None:
        styles = {
            "chat": OverlayStyle("链接框", QColor(30, 120, 255), QColor(30, 120, 255, 36)),
            "captcha": OverlayStyle("识别框", QColor(35, 185, 90), QColor(35, 185, 90, 36)),
            "input": OverlayStyle("填写框", QColor(230, 175, 20), QColor(230, 175, 20, 42)),
            "submit": OverlayStyle("提交框", QColor(220, 60, 60), QColor(220, 60, 60, 42)),
        }
        self.overlays["chat"] = OverlayBox("chat", styles["chat"], self._physical_rect_to_logical_qrect(self.config.chat_link_region), self._overlay_changed)
        self.overlays["captcha"] = OverlayBox("captcha", styles["captcha"], self._physical_rect_to_logical_qrect(self.config.captcha_region), self._overlay_changed)
        self.overlays["input"] = OverlayBox("input", styles["input"], self._physical_point_to_logical_qrect(self.config.captcha_input_point, 52), self._overlay_changed)
        self.overlays["submit"] = OverlayBox("submit", styles["submit"], self._physical_point_to_logical_qrect(self.config.submit_button_point, 52), self._overlay_changed)

    def _overlay_changed(self) -> None:
        if self._syncing:
            return
        self.config.chat_link_region = self._logical_rect_to_physical(self.overlays["chat"].geometry())
        self.config.captcha_region = self._logical_rect_to_physical(self.overlays["captcha"].geometry())
        self.config.captcha_input_point = self._logical_point_to_physical(self.overlays["input"].geometry().center())
        self.config.submit_button_point = self._logical_point_to_physical(self.overlays["submit"].geometry().center())
        self._update_coord_labels()

    def _sync_config_from_form(self) -> None:
        if self._syncing:
            return
        self.config.link_color_hsv_lower = [
            self.spinboxes["h_lower"].value(),
            self.spinboxes["s_lower"].value(),
            self.spinboxes["v_lower"].value(),
        ]
        self.config.link_color_hsv_upper = [
            self.spinboxes["h_upper"].value(),
            self.spinboxes["s_upper"].value(),
            self.spinboxes["v_upper"].value(),
        ]
        self.config.browser_wait_seconds = float(self.spinboxes["browser_wait_seconds"].value())

    def _sync_form_from_config(self) -> None:
        self._syncing = True
        values = {
            "h_lower": self.config.link_color_hsv_lower[0],
            "s_lower": self.config.link_color_hsv_lower[1],
            "v_lower": self.config.link_color_hsv_lower[2],
            "h_upper": self.config.link_color_hsv_upper[0],
            "s_upper": self.config.link_color_hsv_upper[1],
            "v_upper": self.config.link_color_hsv_upper[2],
            "browser_wait_seconds": self.config.browser_wait_seconds,
        }
        for key, value in values.items():
            self.spinboxes[key].setValue(value)
        self._syncing = False
        self._update_coord_labels()

    def _sync_overlays_from_config(self) -> None:
        self._syncing = True
        self.overlays["chat"].setGeometry(self._physical_rect_to_logical_qrect(self.config.chat_link_region))
        self.overlays["captcha"].setGeometry(self._physical_rect_to_logical_qrect(self.config.captcha_region))
        self.overlays["input"].setGeometry(self._physical_point_to_logical_qrect(self.config.captcha_input_point, self.overlays["input"].width() or 52))
        self.overlays["submit"].setGeometry(self._physical_point_to_logical_qrect(self.config.submit_button_point, self.overlays["submit"].width() or 52))
        self._syncing = False
        self._update_coord_labels()

    def _update_coord_labels(self) -> None:
        c = self.config
        self.coord_labels["chat"].setText(self._fmt_rect(c.chat_link_region))
        self.coord_labels["captcha"].setText(self._fmt_rect(c.captcha_region))
        self.coord_labels["input"].setText(self._fmt_point(c.captcha_input_point))
        self.coord_labels["submit"].setText(self._fmt_point(c.submit_button_point))

    def toggle_overlays(self) -> None:
        self.overlays_visible = not self.overlays_visible
        for overlay in self.overlays.values():
            overlay.setVisible(self.overlays_visible)
        self.log("已显示校准框。" if self.overlays_visible else "已隐藏校准框。")

    def save_profile(self) -> None:
        self._overlay_changed()
        self._sync_config_from_form()
        save_config(self.config, DEFAULT_PROFILE)
        self.log(f"已保存配置：{DEFAULT_PROFILE}")

    def load_profile(self) -> None:
        self.config = load_config(DEFAULT_PROFILE)
        self._sync_overlays_from_config()
        self._sync_form_from_config()
        self.log(f"已加载配置：{DEFAULT_PROFILE}")

    def sample_link_color(self) -> None:
        self.log("请在 3 秒内把鼠标移动到微信蓝色链接文字上，程序会自动取样。")
        self._temporarily_hide_overlays()
        QTimer.singleShot(3000, self._sample_mouse_pixel)

    def _sample_mouse_pixel(self) -> None:
        pos = QApplication.primaryScreen().cursor().pos()
        physical_pos = self._logical_point_to_physical(pos)
        screen = grab_screen().convert("RGB")
        if physical_pos.x < 0 or physical_pos.y < 0 or physical_pos.x >= screen.width or physical_pos.y >= screen.height:
            self.log(f"取样失败：坐标超出屏幕 x={physical_pos.x}, y={physical_pos.y}")
            self._restore_overlays()
            return
        r, g, b = screen.getpixel((physical_pos.x, physical_pos.y))
        hsv = cv2.cvtColor(np.array([[[r, g, b]]], dtype=np.uint8), cv2.COLOR_RGB2HSV)[0][0]
        h, s, v = [int(value) for value in hsv]
        self.config.link_color_hsv_lower = [max(0, h - 12), max(0, s - 90), max(0, v - 100)]
        self.config.link_color_hsv_upper = [min(179, h + 12), min(255, s + 90), min(255, v + 100)]
        self._sync_form_from_config()
        self._restore_overlays()
        self.log(
            f"已取样链接颜色：RGB=({r},{g},{b}), HSV=({h},{s},{v}), "
            f"lower={self.config.link_color_hsv_lower}, upper={self.config.link_color_hsv_upper}"
        )

    def test_link(self):
        self._overlay_changed()
        self._sync_config_from_form()
        screen = self._grab_clean_screen()
        candidate = lowest_link_candidate(screen, self.config)
        candidates = detect_blue_links(screen, self.config)
        if not candidate:
            blue_pixels = self._count_link_color_pixels(screen)
            self.log(
                "未检测到蓝色链接候选。"
                f"链接框={self._fmt_rect(self.config.chat_link_region)}, "
                f"蓝色像素={blue_pixels}。请调整链接框或重新取样链接色。"
            )
            return None
        self.log(
            f"检测到 {len(candidates)} 个链接候选，选择最靠下："
            f"x={candidate.x}, y={candidate.y}, w={candidate.w}, h={candidate.h}"
        )
        return candidate

    def click_detected_link(self) -> None:
        candidate = self.test_link()
        if not candidate:
            return
        self._temporarily_hide_overlays()
        QTimer.singleShot(180, lambda: self._click_link_after_hide(candidate))

    def _click_link_after_hide(self, candidate) -> None:
        click_link(candidate, self.config)
        self._restore_overlays()
        self.log("已点击检测到的链接候选。")

    def test_captcha(self) -> None:
        self._overlay_changed()
        self._sync_config_from_form()
        screen = self._grab_clean_screen()
        light_result = recognize_captcha_light(screen, self.config)
        self.log(
            f"轻量 OCR：{light_result.code!r}, "
            f"confidence={light_result.confidence:.3f}, method={light_result.method}"
        )
        try:
            code = recognize_captcha(screen, self.config)
        except Exception as exc:
            self.log(f"验证码识别失败：{exc}")
            QMessageBox.warning(self, "验证码识别失败", str(exc))
            return
        self.log(f"验证码识别结果：{code}")

    def run_once(self) -> None:
        candidate = self.test_link()
        if not candidate:
            return
        self._temporarily_hide_overlays()
        QTimer.singleShot(180, lambda: self._run_once_after_hide(candidate))

    def _run_once_after_hide(self, candidate) -> None:
        click_link(candidate, self.config)
        self.log("已点击链接，等待微信浏览器加载。")
        QApplication.processEvents()
        wait_browser(self.config)
        screen = grab_screen()
        try:
            code = recognize_captcha(screen, self.config)
        except Exception as exc:
            self._restore_overlays()
            self.log(f"OCR 失败，等待手动输入验证码：{exc}")
            code, ok = QInputDialog.getText(self, "手动输入验证码", "请输入页面显示的四位数字验证码：")
            code = code.strip()
            if not ok or not code:
                self.log("运行中止：用户取消手动输入验证码。")
                return
            if not (code.isdigit() and len(code) == 4):
                self.log(f"运行中止：手动输入不是四位数字：{code!r}")
                QMessageBox.warning(self, "验证码格式错误", "验证码必须是四位数字。")
                return
            self._temporarily_hide_overlays()
        fill_captcha_and_submit(code, self.config)
        self._restore_overlays()
        self.log(f"已填写并提交验证码：{code}")

    def _grab_clean_screen(self):
        self._temporarily_hide_overlays()
        QApplication.processEvents()
        screen = grab_screen()
        self._restore_overlays()
        return screen

    def _temporarily_hide_overlays(self) -> None:
        for overlay in self.overlays.values():
            overlay.hide()
        QApplication.processEvents()

    def _restore_overlays(self) -> None:
        if self.overlays_visible:
            for overlay in self.overlays.values():
                overlay.show()
        QApplication.processEvents()

    def log(self, message: str) -> None:
        self.log_box.append(message)

    def closeEvent(self, event):
        for overlay in self.overlays.values():
            overlay.close()
        super().closeEvent(event)

    def _logical_rect_to_physical(self, rect: QRect) -> RectConfig:
        screen = QApplication.screenAt(rect.center()) or QApplication.primaryScreen()
        geo = screen.geometry()
        dpr = screen.devicePixelRatio()
        return RectConfig(
            int(round((rect.x() - geo.x()) * dpr + geo.x() * dpr)),
            int(round((rect.y() - geo.y()) * dpr + geo.y() * dpr)),
            max(1, int(round(rect.width() * dpr))),
            max(1, int(round(rect.height() * dpr))),
        )

    def _logical_point_to_physical(self, point: QPoint) -> PointConfig:
        screen = QApplication.screenAt(point) or QApplication.primaryScreen()
        geo = screen.geometry()
        dpr = screen.devicePixelRatio()
        return PointConfig(
            int(round((point.x() - geo.x()) * dpr + geo.x() * dpr)),
            int(round((point.y() - geo.y()) * dpr + geo.y() * dpr)),
        )

    def _physical_rect_to_logical_qrect(self, rect: RectConfig) -> QRect:
        screen = QApplication.primaryScreen()
        geo = screen.geometry()
        dpr = screen.devicePixelRatio()
        return QRect(
            int(round((rect.x - geo.x() * dpr) / dpr + geo.x())),
            int(round((rect.y - geo.y() * dpr) / dpr + geo.y())),
            max(28, int(round(rect.w / dpr))),
            max(28, int(round(rect.h / dpr))),
        )

    def _physical_point_to_logical_qrect(self, point: PointConfig, size: int) -> QRect:
        screen = QApplication.primaryScreen()
        geo = screen.geometry()
        dpr = screen.devicePixelRatio()
        x = int(round((point.x - geo.x() * dpr) / dpr + geo.x()))
        y = int(round((point.y - geo.y() * dpr) / dpr + geo.y()))
        return QRect(x - size // 2, y - size // 2, size, size)

    def _count_link_color_pixels(self, screen) -> int:
        rect = self.config.chat_link_region
        crop = screen.crop((rect.x, rect.y, rect.x + rect.w, rect.y + rect.h)).convert("RGB")
        rgb = np.array(crop)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        lower = np.array(self.config.link_color_hsv_lower, dtype=np.uint8)
        upper = np.array(self.config.link_color_hsv_upper, dtype=np.uint8)
        return int(cv2.inRange(hsv, lower, upper).sum() // 255)

    @staticmethod
    def _fmt_rect(rect: RectConfig) -> str:
        return f"x={rect.x}, y={rect.y}, w={rect.w}, h={rect.h}"

    @staticmethod
    def _fmt_point(point: PointConfig) -> str:
        return f"x={point.x}, y={point.y}"


def run_app() -> None:
    app = QApplication(sys.argv)
    window = ControllerWindow()
    window.show()
    sys.exit(app.exec())
