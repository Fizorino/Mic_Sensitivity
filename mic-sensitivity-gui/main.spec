# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

block_cipher = None

repo_root = Path(__file__).resolve().parents[1]
entry = repo_root / 'mic-sensitivity-gui' / 'src' / 'main.py'

# Data files that should live next to the exe
datas = []
for name in ['settings.json', 'config.json', 'main_settings.json']:
    p = repo_root / name
    if p.exists():
        datas.append((str(p), '.'))

# Convenience: ship all top-level preset jsons next to the exe
for p in repo_root.glob('*.json'):
    datas.append((str(p), '.'))


a = Analysis(
    [str(entry)],
    pathex=[str(repo_root / 'mic-sensitivity-gui' / 'src')],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6', 'PyQt6', 'PyQt5'],
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
    name='MicSensitivityGUI',
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
