# LinkCaptcha RPA

LinkCaptcha RPA is a Windows desktop prototype for automating a narrow WeChat workflow:

1. Detect the newest visible blue link in a WeChat chat window.
2. Click the link.
3. Read a four-digit numeric captcha from the opened page.
4. Fill the captcha input.
5. Click the submit button.

The app uses screen capture, image recognition, and simulated mouse/keyboard input. It does not read WeChat databases, modify WeChat, inject into WeChat, or control the WeChat embedded browser DOM.

## Current State

This is a working prototype, not a production-grade unattended bot.

Implemented:

- Small controller window.
- Four draggable always-on-top calibration boxes:
  - blue link box;
  - green OCR box;
  - yellow input box;
  - red submit box.
- DPI-aware coordinate conversion for Windows display scaling.
- Link color sampling.
- Blue-link detection with OpenCV.
- Lightweight four-digit OCR based on image preprocessing and template matching.
- One-shot workflow.
- Manual captcha fallback when OCR fails.
- PyInstaller directory build for zero-Python Windows machines.

Not implemented yet:

- Always-on background monitoring.
- New-link de-duplication.
- Tray mode.
- Multi-profile UI.
- Robust OCR for heavily distorted captcha images.

## Test Page

The controlled test page is:

```text
https://koa-ol.com/captcha-test/
```

Fixed-code example:

```text
https://koa-ol.com/captcha-test/?code=1234
```

## Run From Source

Use the shared conda environment `th123`:

```powershell
cd E:\PG\linkcaptcha
D:/python/anaconda/envs/th123/python.exe main.py
```

## Build EXE

The build uses `WeChatLinkCaptchaRPA.spec`, which explicitly bundles required Qt/PySide6 DLLs from the `th123` conda environment.

```powershell
cd E:\PG\linkcaptcha
D:/python/anaconda/envs/th123/python.exe -m PyInstaller --clean WeChatLinkCaptchaRPA.spec
```

Output:

```text
dist/WeChatLinkCaptchaRPA/WeChatLinkCaptchaRPA.exe
```

Do not distribute the EXE alone. Distribute the whole `dist/WeChatLinkCaptchaRPA/` folder, or create a zip from it.

## Documentation

- [应用使用说明](./APP_GUIDE.md)
- [项目说明](./PROJECT.md)

