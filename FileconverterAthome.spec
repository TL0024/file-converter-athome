# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files


ffmpeg_datas = collect_data_files("imageio_ffmpeg", includes=["binaries/*"])

analysis = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[("templates", "templates"), ("static", "static"), *ffmpeg_datas],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "boto3",
        "keras",
        "matplotlib",
        "numpy",
        "pandas",
        "pygame",
        "pytest",
        "scipy",
        "tensorflow",
        "tkinter",
        "torch",
        "transformers",
    ],
    noarchive=False,
    optimize=1,
)
python_archive = PYZ(analysis.pure)

executable = EXE(
    python_archive,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="FileconverterAthome",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/FileconverterAthome.ico",
    version="packaging/windows-version-info.txt",
)
