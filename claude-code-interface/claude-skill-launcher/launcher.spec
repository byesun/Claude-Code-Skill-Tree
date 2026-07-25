# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 스펙. 빌드: pyinstaller launcher.spec"""

import os

block_cipher = None

icon_path = os.path.join("assets", "icon.ico")
if not os.path.isfile(icon_path):
    icon_path = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    # pywin32 는 런타임에 win32timezone 을 동적으로 찾으므로 명시해야 한다
    hiddenimports=["win32timezone"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PyQt6.QtWebEngineCore"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ClaudeSkillLauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 안티바이러스 오탐을 줄이기 위해 비활성
    runtime_tmpdir=None,
    console=False,  # windowed: 콘솔 창이 뜨지 않게 한다
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
