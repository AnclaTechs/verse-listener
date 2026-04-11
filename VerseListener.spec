# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for lean Windows onedir builds.

This build intentionally ships the OpenAI-first app path and excludes heavier
offline engines from the base bundle. Users can install those later from the
app's Add-ons screen.
"""

from pathlib import Path


project_root = Path(SPECPATH).resolve()


def collect_dir(relative_dir: str, dest_dir: str) -> list[tuple[str, str]]:
    source_dir = project_root / relative_dir
    if not source_dir.is_dir():
        return []

    entries: list[tuple[str, str]] = []
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        relative_parent = path.relative_to(source_dir).parent
        target_dir = Path(dest_dir) / relative_parent
        entries.append((str(path), str(target_dir)))
    return entries


datas = []
datas += collect_dir("assets", "assets")
datas += collect_dir("canons", "canons")

for filename in (".env.example", "README.md", "LICENSE.md"):
    candidate = project_root / filename
    if candidate.is_file():
        datas.append((str(candidate), "."))


hiddenimports = [
    "dotenv",
    "sounddevice",
    "websocket",
    "pyautogui",
    "pygetwindow",
]


excludes = [
    # Optional/offline engines kept out of the base Windows bundle.
    "faster_whisper",
    "vosk",
    "sentence_transformers",
    "ctranslate2",
    "torch",
    "transformers",
    "tokenizers",
    "safetensors",
    "triton",
    "av",
    "onnxruntime",
    # Linux-only helpers.
    "jack",
    "Xlib",
    "pywinctl",
    "wmctrl",
]


a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VerseListener",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VerseListener",
)
