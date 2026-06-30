# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


ENV_BIN = Path(r"D:/python/anaconda/envs/th123/Library/bin")
QT_DLLS = [
    "pyside6.cp310-win_amd64.dll",
    "shiboken6.cp310-win_amd64.dll",
    "Qt6Core.dll",
    "Qt6Gui.dll",
    "Qt6Widgets.dll",
    "Qt6Network.dll",
    "Qt6Svg.dll",
    "double-conversion.dll",
    "freetype.dll",
    "libpng16.dll",
    "pcre2-16.dll",
]

qt_binaries = [(str(ENV_BIN / name), ".") for name in QT_DLLS]


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=qt_binaries,
    datas=[("profiles", "profiles")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytesseract",
        "pandas",
        "torch",
        "torchvision",
        "torchaudio",
        "transformers",
        "scipy",
        "sklearn",
        "matplotlib",
        "gradio",
        "tensorflow",
        "sympy",
        "pytest",
        "IPython",
        "jupyter",
        "notebook",
        "lxml",
        "cryptography",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WeChatLinkCaptchaRPA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="WeChatLinkCaptchaRPA",
)
