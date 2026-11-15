# -*- mode: python ; coding: utf-8 -*-

import imageio_ffmpeg

# Localiza o FFmpeg instalado no ambiente virtual
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

a = Analysis(
    ['captube.py'],
    pathex=[],
    binaries=[
        (ffmpeg_exe, 'imageio_ffmpeg/binaries'),
    ],
    datas=[
        ('icons/*', 'icons'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='CapTube',
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
    icon=['icons/icon.ico'],
)
