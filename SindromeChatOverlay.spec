from pathlib import Path

root = Path(SPECPATH)
icon = root / "assets" / "app.ico"
datas = [(str(root / "assets" / "icon.svg"), "assets")]
runtime_icon = root / "assets" / "icon.png"
if runtime_icon.exists():
    datas.append((str(runtime_icon), "assets"))
for notification_sound in sorted((root / "assets").glob("notification-*.wav")):
    datas.append((str(notification_sound), "assets"))

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "grpc",
        "grpc._cython.cygrpc",
        "google.protobuf",
        "sindrome_overlay.youtube_grpc.stream_list_pb2",
        "sindrome_overlay.youtube_grpc.stream_list_pb2_grpc",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pytest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SindromeChatOverlay",
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
    icon=str(icon) if icon.exists() else None,
)
