# LinkCaptchaRPA 项目记忆

此文档用于在新的 Codex 会话中快速接续本项目。下次继续讨论时，优先阅读：

1. `PROJECT_MEMORY.md`
2. `README.md`
3. `PROJECT.md`
4. `APP_GUIDE.md`

## 项目入口

本地路径：

```text
E:\PG\linkcaptcha
```

GitHub：

```text
https://github.com/dticpw/LinkCaptchaRPA
```

测试验证码页：

```text
https://koa-ol.com/captcha-test/
https://koa-ol.com/captcha-test/?code=1234
```

相关网站项目：

```text
F:\bak\git_koa-ol
```

## Python 环境

按全局偏好，所有 Python / pip 操作默认使用 conda 环境 `th123`：

```powershell
D:/python/anaconda/envs/th123/python.exe main.py
D:/python/anaconda/envs/th123/python.exe -m pip install <pkg>
D:/python/anaconda/envs/th123/python.exe -m PyInstaller --clean WeChatLinkCaptchaRPA.spec
```

不要使用裸 `python`、`python3`、`pip`、`pip3`。

## 当前产品形态

这是一个 Windows 微信桌面版验证码 RPA 原型。

当前交互：

- 启动后显示一个小型控制器窗口。
- 桌面上有四个置顶悬浮框：
  - 蓝色：链接框，用于框住微信聊天里的链接区域。
  - 绿色：识别框，用于框住网页验证码数字。
  - 黄色：填写框，用于点击验证码输入框。
  - 红色：提交框，用于点击提交按钮。
- 用户可以拖动悬浮框，也可以拖右下角改变大小。
- 控制器按钮包括：
  - 运行一次
  - 测试链接
  - 测试验证码
  - 点击链接
  - 取样链接色
  - 显示/隐藏框
  - 保存配置
  - 加载配置

当前只做“运行一次”，还没有常驻监听。

## 核心实现

主要文件：

```text
main.py
app/gui.py
app/config.py
app/link_detector.py
app/captcha_ocr.py
app/automation.py
app/screen_capture.py
profiles/default.json
WeChatLinkCaptchaRPA.spec
```

模块职责：

- `app/gui.py`：PySide6 控制器和四个悬浮框。
- `app/config.py`：配置数据结构和 JSON 保存/加载。
- `app/link_detector.py`：OpenCV 蓝色链接检测。
- `app/captcha_ocr.py`：轻量四位数字 OCR。
- `app/automation.py`：pyautogui 鼠标键盘操作。
- `app/screen_capture.py`：Pillow 截屏。

## 关键技术决策

### 不做微信插件

避免使用微信插件、DLL 注入、Hook、读取微信数据库、控制微信内置浏览器 DOM。当前方案只做屏幕级 RPA。

### 使用悬浮框而不是大截图画布

最初版本是大截图画布，用户需要在截图上拖框。后来改为桌面悬浮框：

- 更符合甲方/非技术用户直觉。
- 用户可以直接把框拖到微信和验证码页面上。
- 控制器只负责按钮和日志。

### DPI 坐标转换

曾遇到问题：悬浮框肉眼框住链接，但程序检测不到。

原因：

```text
Qt/悬浮框逻辑坐标：1707 x 960
真实截图像素：2560 x 1440
DPI 比例：1.5
```

修复：

- 悬浮框显示使用 Qt 逻辑坐标。
- 截图裁剪、颜色取样、点击使用真实屏幕像素坐标。
- `app/gui.py` 中通过 `screen.devicePixelRatio()` 动态转换。

注意：

- 不要让单个悬浮框跨多个显示器。
- 更换显示器或 Windows 缩放比例后建议重新校准。

### 轻量 OCR

当前没有足够真实验证码训练数据，所以先实现轻量数字 OCR：

- 前景提取。
- 去边框干扰。
- 四位数字分割。
- 模板匹配。
- 低置信度时人工输入兜底。

对 `koa-ol.com/captcha-test/?code=1234` 这类清晰验证码有效。对强干扰、倾斜、粘连验证码不保证 90%+。

未来如果要提升真实验证码准确率，建议收集真实样本后训练小型四位数字识别模型，导出 ONNX，再用 `onnxruntime` 推理。

## 已遇到并修复的问题

### 1. `PIL.ImageQt` 打包导入失败

旧代码：

```python
from PIL.ImageQt import ImageQt
```

PyInstaller 后报错：

```text
cannot import name 'ImageQt' from 'PIL.ImageQt'
```

修复：

- 不再依赖 `ImageQt`。
- 直接把 PIL RGBA bytes 转成 `QImage`。

### 2. Shiboken / Qt DLL 缺失

打包后在无 conda 环境目录运行时报：

```text
DLL load failed while importing Shiboken
```

原因：

- conda 版 PySide6 的 Qt DLL 在 `D:\python\anaconda\envs\th123\Library\bin`。
- PyInstaller 没有自动全收进去。

修复：

`WeChatLinkCaptchaRPA.spec` 显式打包：

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

打包后必须验证：

```text
DEPENDENCY_SCAN_OK
CLEAN_PATH_EXE_RUNNING
```

### 3. DPI 缩放导致链接检测不到

见上文 DPI 坐标转换。

## 打包与发布

打包命令：

```powershell
cd E:\PG\linkcaptcha
D:/python/anaconda/envs/th123/python.exe -m PyInstaller --clean WeChatLinkCaptchaRPA.spec
```

输出：

```text
dist\WeChatLinkCaptchaRPA\WeChatLinkCaptchaRPA.exe
```

分发时不能只发单个 exe，必须发整个目录：

```text
dist\WeChatLinkCaptchaRPA\
```

或者压缩整个目录。

当前打包体积大致：

```text
目录版约 219 MB
zip 约 85 MB
```

主要体积来源：

- OpenCV
- PySide6 / Qt
- NumPy
- Pillow
- Python runtime

## Git 状态

仓库已初始化并成功推送：

```text
origin https://github.com/dticpw/LinkCaptchaRPA.git
branch main tracks origin/main
```

初始提交：

```text
64fae9a Initial LinkCaptcha RPA project
```

## 当前限制

- 还没有常驻监听模式。
- 没有新链接去重。
- 没有托盘运行。
- 没有多 Profile 管理。
- 点击微信链接偶尔可能因为焦点、候选点、微信状态导致未打开。
- 对强干扰验证码准确率有限。
- 依赖微信窗口和验证码网页可见。

## 后续建议

优先级建议：

1. 增加常驻监听开关。
2. 增加新链接图像指纹去重。
3. 优化点击链接位置，例如从候选框中心改为文字左中偏内侧。
4. 点击前后增加更稳的隐藏框和延迟策略。
5. 增加托盘模式。
6. 增加多 Profile 管理。
7. 收集真实验证码样本，训练小型 OCR 模型。
8. 优化打包体积，排除 OpenCV 视频组件和多余 Qt 插件。

