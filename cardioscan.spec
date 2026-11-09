# -*- mode: python ; coding: utf-8 -*-
"""
Archivo de configuración de PyInstaller para CardioScan AI.
Genera un único .exe que incluye Python, Flask, numpy, scipy,
matplotlib, scikit-learn y todos los archivos de la interfaz.

Uso:
    pyinstaller cardioscan.spec
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Modulos que PyInstaller no detecta automaticamente
hidden_imports = (
    collect_submodules('sklearn') +
    collect_submodules('scipy') +
    collect_submodules('matplotlib') +
    [
        'engineio.async_drivers.threading',
        'PIL._tkinter_finder',
    ]
)

# Archivos de datos a incluir (HTML, CSS embebido)
datas = [
    ('templates', 'templates'),
]
datas += collect_data_files('matplotlib')
datas += collect_data_files('sklearn')

a = Analysis(
    ['cardioscan_launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'PyQt5',
        'PySide2',
        'IPython',
        'jupyter',
        'pytest',
    ],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CardioScanAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
