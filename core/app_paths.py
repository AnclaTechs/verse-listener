"""
core/app_paths.py
Helpers for locating app resources in source mode and bundled builds.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def source_root() -> Path:
    return Path(__file__).resolve().parent.parent


def executable_dir() -> Path:
    return Path(sys.executable).resolve().parent


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        resolved = str(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def resource_roots() -> list[Path]:
    roots: list[Path] = []

    override = os.getenv("VERSE_LISTENER_HOME", "").strip()
    if override:
        roots.append(Path(override).expanduser())

    if getattr(sys, "frozen", False):
        roots.append(executable_dir())
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            roots.append(Path(meipass))

    roots.append(source_root())
    return _dedupe_paths(roots)


def resource_path(*parts: str) -> Path:
    for root in resource_roots():
        candidate = root.joinpath(*parts)
        if candidate.exists():
            return candidate
    return source_root().joinpath(*parts)


def find_config_file(filename: str) -> Path | None:
    candidates: list[Path] = []

    override = os.getenv("VERSE_LISTENER_HOME", "").strip()
    if override:
        candidates.append(Path(override).expanduser())

    if getattr(sys, "frozen", False):
        candidates.append(executable_dir())

    candidates.append(Path.cwd())
    candidates.append(source_root())

    for root in _dedupe_paths(candidates):
        candidate = root / filename
        if candidate.is_file():
            return candidate
    return None
