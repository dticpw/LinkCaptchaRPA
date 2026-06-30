# LinkCaptcha RPA 项目说明

## 1. 项目背景

本项目用于验证一种低侵入的微信桌面端 RPA 流程：用户打开微信聊天窗口后，程序通过可视化校准区域识别聊天中的链接，点击链接，并在打开的网页中识别四位数字验证码完成提交。

项目目标是先实现可用原型，再逐步评估常驻监听、新链接去重和更强 OCR 的可行性。

## 2. 设计原则

- 不读取微信数据库。
- 不修改微信客户端。
- 不注入微信进程。
- 不依赖浏览器 DOM。
- 通过屏幕截图和模拟鼠标键盘完成操作。
- 所有关键区域由用户可视化校准。
- OCR 失败时必须允许人工兜底，不盲目提交。

## 3. 当前架构

```text
main.py
  -> app.gui.ControllerWindow
      -> app.screen_capture
      -> app.link_detector
      -> app.captcha_ocr
      -> app.automation
      -> app.config
```

### app.gui

PySide6 GUI。

包含：

- 控制器窗口。
- 四个桌面悬浮框。
- 配置保存/加载。
- 测试链接。
- 测试验证码。
- 运行一次。

悬浮框使用 Qt 逻辑坐标显示。截图和点击前会转换为真实屏幕像素坐标，以适配 Windows DPI 缩放。

### app.config

配置数据结构和 JSON 保存/加载。

主要配置：

- `chat_link_region`
- `captcha_region`
- `captcha_input_point`
- `submit_button_point`
- `link_color_hsv_lower`
- `link_color_hsv_upper`
- `browser_wait_seconds`

### app.screen_capture

使用 Pillow `ImageGrab.grab(all_screens=True)` 截屏。

### app.link_detector

使用 OpenCV 在链接框内查找蓝色链接候选：

1. 裁剪聊天链接区域。
2. RGB 转 HSV。
3. HSV 阈值生成 mask。
4. 形态学合并。
5. 查找轮廓。
6. 过滤小噪声和异常区域。
7. 选择最靠下的候选。

### app.captcha_ocr

轻量四位数字 OCR。

流程：

1. 裁剪识别框。
2. 前景提取。
3. 去除边框类干扰。
4. 分割四个数字区域。
5. 归一化。
6. 与内置字体模板匹配。
7. 输出四位数字和置信度。

如果轻量 OCR 置信度不足，会尝试 Tesseract 兜底；当前 PyInstaller 分发包为了控制体积排除了 `pytesseract`，因此实际分发版会进入人工输入兜底。

### app.automation

使用 `pyautogui` 完成：

- 鼠标移动。
- 点击。
- `Ctrl+A`。
- 输入验证码。
- 点击提交。

## 4. DPI 处理

Windows 高 DPI 下，Qt 窗口坐标和屏幕截图像素坐标可能不同。例如：

```text
Qt 坐标：1707 x 960
截图像素：2560 x 1440
DPI：1.5
```

项目在 GUI 层做了动态转换：

- 悬浮框显示：Qt 逻辑坐标。
- 截图裁剪：真实像素坐标。
- 鼠标取样：真实像素坐标。
- 点击点：真实像素坐标。

注意事项：

- 多显示器不同缩放比例需要实机验证。
- 不建议让单个悬浮框跨越多个显示器。
- 修改 Windows 缩放后应重启程序并重新校准。

## 5. 打包

使用 PyInstaller 目录版。

```powershell
D:/python/anaconda/envs/th123/python.exe -m PyInstaller --clean WeChatLinkCaptchaRPA.spec
```

`WeChatLinkCaptchaRPA.spec` 显式加入 conda PySide6 需要的 Qt DLL：

```text
pyside6.cp310-win_amd64.dll
shiboken6.cp310-win_amd64.dll
Qt6Core.dll
Qt6Gui.dll
Qt6Widgets.dll
Qt6Network.dll
Qt6Svg.dll
double-conversion.dll
freetype.dll
libpng16.dll
pcre2-16.dll
```

打包后必须做：

1. PE 依赖扫描。
2. 干净 PATH 启动验证。

这样可以避免开发机 conda 环境掩盖 DLL 缺失问题。

## 6. 当前限制

- 只实现“运行一次”，没有常驻监听。
- 没有新链接去重。
- 没有托盘模式。
- 没有多 Profile 管理界面。
- 对强干扰验证码准确率有限。
- 依赖微信窗口和网页窗口可见。
- 链接检测基于颜色和位置，不读取消息结构。

## 7. 后续计划

优先级建议：

1. 增加常驻监听开关。
2. 增加新链接图像指纹去重。
3. 增加托盘运行。
4. 增加多 Profile。
5. 收集真实验证码样本，训练小型四位数字识别模型。
6. 优化打包体积，移除不必要的 OpenCV 视频组件和 Qt 插件。

