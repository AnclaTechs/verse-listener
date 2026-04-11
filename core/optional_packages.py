"""
core/optional_packages.py
Helpers for optional, user-installed add-ons such as Vosk and faster-whisper.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import shutil
import site
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from importlib import util as importlib_util
from pathlib import Path
from typing import Callable, Optional


@dataclass(frozen=True)
class OptionalPackageSpec:
    key: str
    title: str
    dist_name: str
    import_names: tuple[str, ...]
    install_args: tuple[str, ...]
    estimated_size: str
    description: str
    note: str = ""


@dataclass(frozen=True)
class OptionalPackageStatus:
    spec: OptionalPackageSpec
    installed: bool
    version: str = ""
    location: str = ""

    @property
    def status_text(self) -> str:
        if self.installed:
            return f"Installed{f' ({self.version})' if self.version else ''}"
        return "Not installed"


OPTIONAL_PACKAGE_SPECS: tuple[OptionalPackageSpec, ...] = (
    OptionalPackageSpec(
        key="vosk",
        title="Vosk",
        dist_name="vosk",
        import_names=("vosk",),
        install_args=("vosk>=0.3.45",),
        estimated_size="~50 MB",
        description="Offline speech-to-text backend for lower-latency local transcription.",
        note="Language models are downloaded separately after the package install.",
    ),
    OptionalPackageSpec(
        key="faster_whisper",
        title="faster-whisper",
        dist_name="faster-whisper",
        import_names=("faster_whisper",),
        install_args=("faster-whisper>=1.0.0",),
        estimated_size="~120 MB",
        description="Offline Whisper transcription engine for CPU-based fallback use.",
        note="Whisper model weights are downloaded the first time you use a model.",
    ),
    OptionalPackageSpec(
        key="sentence_transformers",
        title="sentence-transformers",
        dist_name="sentence-transformers",
        import_names=("sentence_transformers",),
        install_args=("sentence-transformers>=3.0.0",),
        estimated_size="~350 MB+",
        description="Semantic passage matching upgrade for contextual Bible reference suggestions.",
        note="This may pull in a large Torch runtime. Final size varies by platform and wheel selection.",
    ),
)

OPTIONAL_PACKAGE_MAP = {spec.key: spec for spec in OPTIONAL_PACKAGE_SPECS}


def _user_data_root() -> Path:
    if sys.platform == "win32":
        base = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "VerseListener"


def extras_site_packages_dir() -> Path:
    version_tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    return _user_data_root() / "extras" / version_tag


def _candidate_extras_dirs() -> list[Path]:
    version_tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    candidates: list[Path] = []

    override = os.getenv("VERSE_LISTENER_EXTRAS_DIR", "").strip()
    if override:
        candidates.append(Path(override))

    candidates.append(extras_site_packages_dir())
    candidates.append(
        Path(tempfile.gettempdir()) / "VerseListener" / "extras" / version_tag
    )
    return candidates


def bootstrap_optional_packages() -> Path:
    for extras_dir in _candidate_extras_dirs():
        try:
            extras_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        site.addsitedir(str(extras_dir))
        importlib.invalidate_caches()
        return extras_dir
    raise RuntimeError(
        "VerseListener could not find a writable folder for optional add-ons. "
        "Set VERSE_LISTENER_EXTRAS_DIR to a writable location."
    )


def optional_package_specs() -> tuple[OptionalPackageSpec, ...]:
    return OPTIONAL_PACKAGE_SPECS


def get_optional_package_spec(key: str) -> OptionalPackageSpec:
    return OPTIONAL_PACKAGE_MAP[key]


def get_optional_package_status(spec: OptionalPackageSpec) -> OptionalPackageStatus:
    bootstrap_optional_packages()
    module_origin = ""
    for import_name in spec.import_names:
        found = importlib_util.find_spec(import_name)
        if found is not None:
            module_origin = str(found.origin or "")
            break
    if not module_origin:
        return OptionalPackageStatus(spec=spec, installed=False)

    version = ""
    for candidate in (spec.dist_name, *spec.import_names):
        try:
            version = importlib_metadata.version(candidate)
            break
        except importlib_metadata.PackageNotFoundError:
            continue

    return OptionalPackageStatus(
        spec=spec,
        installed=True,
        version=version,
        location=module_origin,
    )


def all_optional_package_statuses() -> list[OptionalPackageStatus]:
    return [get_optional_package_status(spec) for spec in OPTIONAL_PACKAGE_SPECS]


class _ProgressStream:
    def __init__(self, callback: Optional[Callable[[str], None]]):
        self._callback = callback
        self._buffer = ""

    def write(self, text: str):
        if not text:
            return
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line and self._callback:
                self._callback(line)

    def flush(self):
        line = self._buffer.strip()
        self._buffer = ""
        if line and self._callback:
            self._callback(line)


class OptionalPackageInstaller:
    def __init__(self):
        self.extras_dir = bootstrap_optional_packages()

    def installer_ready(self) -> tuple[bool, str]:
        if self._find_pip_command():
            return True, "Using a Python pip runtime."
        if self._can_use_embedded_pip():
            return True, "Using the embedded pip runtime."
        return (
            False,
            "Optional installs need a pip-capable runtime. "
            "For bundled builds, include a helper Python runtime or bundle pip.",
        )

    def install(
        self,
        package_key: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        spec = get_optional_package_spec(package_key)
        command = self._find_pip_command()
        if command:
            self._install_with_subprocess(spec, command, progress_callback)
        elif self._can_use_embedded_pip():
            self._install_with_embedded_pip(spec, progress_callback)
        else:
            raise RuntimeError(self.installer_ready()[1])
        bootstrap_optional_packages()

    def _find_pip_command(self) -> list[str]:
        env_python = os.getenv("VERSE_LISTENER_INSTALL_PYTHON", "").strip()
        candidates: list[Path] = []
        if env_python:
            candidates.append(Path(env_python))

        executable = Path(sys.executable)
        if not getattr(sys, "frozen", False):
            candidates.append(executable)

        if sys.platform == "win32":
            candidates.extend(
                [
                    executable.parent / "runtime" / "python" / "python.exe",
                    executable.parent / "python.exe",
                ]
            )
            for launcher in ("py", "python"):
                launcher_path = shutil.which(launcher)
                if launcher_path:
                    candidates.append(Path(launcher_path))
        else:
            candidates.extend(
                [
                    executable.parent / "runtime" / "python" / "bin" / "python3",
                    executable.parent / "python3",
                ]
            )
            for launcher in ("python3", "python"):
                launcher_path = shutil.which(launcher)
                if launcher_path:
                    candidates.append(Path(launcher_path))

        seen: set[str] = set()
        for candidate in candidates:
            candidate_str = str(candidate)
            if not candidate_str or candidate_str in seen:
                continue
            seen.add(candidate_str)
            if candidate.is_file():
                return [candidate_str, "-m", "pip"]
        return []

    def _can_use_embedded_pip(self) -> bool:
        try:
            from pip._internal.cli.main import main as _  # noqa: F401

            return True
        except Exception:
            return False

    def _install_with_subprocess(
        self,
        spec: OptionalPackageSpec,
        command: list[str],
        progress_callback: Optional[Callable[[str], None]],
    ):
        cmd = [
            *command,
            "install",
            "--upgrade",
            "--disable-pip-version-check",
            "--no-warn-script-location",
            "--target",
            str(self.extras_dir),
            *spec.install_args,
        ]
        if progress_callback:
            progress_callback(f"Running: {' '.join(cmd[:4])} ...")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        output_lines: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            clean = line.rstrip()
            if not clean:
                continue
            output_lines.append(clean)
            if progress_callback:
                progress_callback(clean)
        code = proc.wait()
        if code != 0:
            tail = "\n".join(output_lines[-12:])
            raise RuntimeError(
                f"pip install failed for {spec.title} (exit code {code})."
                + (f"\n{tail}" if tail else "")
            )

    def _install_with_embedded_pip(
        self,
        spec: OptionalPackageSpec,
        progress_callback: Optional[Callable[[str], None]],
    ):
        from pip._internal.cli.main import main as pip_main

        if progress_callback:
            progress_callback("Using embedded pip runtime…")
        stream = _ProgressStream(progress_callback)
        argv = [
            "install",
            "--upgrade",
            "--disable-pip-version-check",
            "--no-warn-script-location",
            "--target",
            str(self.extras_dir),
            *spec.install_args,
        ]
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            code = pip_main(argv)
        stream.flush()
        if code != 0:
            raise RuntimeError(
                f"pip install failed for {spec.title} (exit code {code})."
            )
