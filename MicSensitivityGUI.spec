# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['mic-sensitivity-gui\\src\\main.py'],
    pathex=['mic-sensitivity-gui/src'],
    binaries=[],
    datas=[('settings.json', '.'), ('config.json', '.'), ('main_settings.json', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6', 'PyQt6', 'PyQt5'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MicSensitivityGUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='C:\\Users\\AU001A0W\\OneDrive - WSA\\Documents\\Mic_Sensitivity\\mic-sensitivity-gui\\version_info.txt',
    icon=['C:\\Users\\AU001A0W\\OneDrive - WSA\\Documents\\Mic_Sensitivity\\mic-sensitivity-gui\\assets\\app.ico'],
)
