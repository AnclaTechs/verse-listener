"""
ui/optional_packages_panel.py
Settings UI for optional downloadable add-ons.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from core.optional_packages import (
    OptionalPackageInstaller,
    OptionalPackageSpec,
    all_optional_package_statuses,
    optional_package_specs,
)


class OptionalPackageInstallThread(QThread):
    progress = pyqtSignal(str, str)
    completed = pyqtSignal(str, bool, str)

    def __init__(self, package_key: str, parent=None):
        super().__init__(parent)
        self.package_key = package_key

    def run(self):
        installer = OptionalPackageInstaller()
        try:
            installer.install(
                self.package_key,
                progress_callback=lambda message: self.progress.emit(
                    self.package_key, message
                ),
            )
        except Exception as exc:
            self.completed.emit(self.package_key, False, str(exc))
            return
        self.completed.emit(
            self.package_key,
            True,
            "Install complete. Restart the app for the cleanest experience.",
        )


class _PackageCard(QFrame):
    install_requested = pyqtSignal(str)

    def __init__(self, spec: OptionalPackageSpec, parent=None):
        super().__init__(parent)
        self.spec = spec
        self.setObjectName("optionalPackageCard")
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)

        title = QLabel(self.spec.title)
        title.setStyleSheet("font-size: 15px; font-weight: 600; color: #e8eaf0;")
        header.addWidget(title)

        size = QLabel(self.spec.estimated_size)
        size.setStyleSheet(
            "background: rgba(37, 99, 235, 0.16);"
            "color: #93c5fd; border-radius: 11px; padding: 4px 10px;"
        )
        header.addWidget(size)
        header.addStretch()

        self._status = QLabel("Checking…")
        self._status.setStyleSheet(
            "background: rgba(100, 116, 139, 0.18);"
            "color: #cbd5e1; border-radius: 11px; padding: 4px 10px;"
        )
        header.addWidget(self._status)
        outer.addLayout(header)

        body = QLabel(self.spec.description)
        body.setWordWrap(True)
        body.setStyleSheet("color: #c0c4d6; line-height: 1.5;")
        outer.addWidget(body)

        if self.spec.note:
            note = QLabel(self.spec.note)
            note.setWordWrap(True)
            note.setStyleSheet("color: #8892b0; font-size: 11px;")
            outer.addWidget(note)

        actions = QHBoxLayout()
        actions.setSpacing(10)

        self._button = QPushButton("Install")
        self._button.clicked.connect(lambda: self.install_requested.emit(self.spec.key))
        actions.addWidget(self._button)

        self._message = QLabel("Ready")
        self._message.setWordWrap(True)
        self._message.setStyleSheet("color: #94a3b8;")
        actions.addWidget(self._message, 1)
        outer.addLayout(actions)

        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setMaximumHeight(10)
        self._progress.hide()
        outer.addWidget(self._progress)

        self.setStyleSheet(
            """
            QFrame#optionalPackageCard {
                background-color: #161924;
                border: 1px solid #2d3142;
                border-radius: 12px;
            }
            """
        )

    def set_installed(
        self, installed: bool, version: str = "", installer_available: bool = True
    ):
        if installed:
            label = f"Installed{f' ({version})' if version else ''}"
            self._status.setText(label)
            self._status.setStyleSheet(
                "background: rgba(34, 197, 94, 0.14);"
                "color: #86efac; border-radius: 11px; padding: 4px 10px;"
            )
            self._button.setText("Reinstall")
            self._button.setEnabled(installer_available)
            self._message.setText(
                "Available now. Restart is optional but recommended after updates."
            )
        else:
            self._status.setText("Not installed")
            self._status.setStyleSheet(
                "background: rgba(100, 116, 139, 0.18);"
                "color: #cbd5e1; border-radius: 11px; padding: 4px 10px;"
            )
            self._button.setText("Install")
            self._button.setEnabled(installer_available)
            if installer_available:
                self._message.setText("Download on demand from Settings.")
            else:
                self._message.setText("Installer runtime unavailable in this build.")

    def set_busy(self, busy: bool, message: str = ""):
        self._button.setEnabled(not busy)
        self._progress.setVisible(busy)
        if busy:
            self._progress.setRange(0, 0)
            self._message.setText(message or "Installing…")
        else:
            self._progress.hide()

    def set_message(self, message: str):
        self._message.setText(message)


class OptionalPackagesPanel(QWidget):
    restart_recommended = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._installer = OptionalPackageInstaller()
        self._threads: dict[str, OptionalPackageInstallThread] = {}
        self._cards: dict[str, _PackageCard] = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self._runtime_note = QLabel()
        self._runtime_note.setWordWrap(True)
        self._runtime_note.setStyleSheet("color: #94a3b8;")
        layout.addWidget(self._runtime_note)

        intro = QLabel(
            "Keep the bundled app lean by downloading offline tools only when you need them. "
            "These installs go into your local VerseListener add-ons folder."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #c0c4d6; line-height: 1.5;")
        layout.addWidget(intro)

        for spec in optional_package_specs():
            card = _PackageCard(spec)
            card.install_requested.connect(self._request_install)
            layout.addWidget(card)
            self._cards[spec.key] = card

        layout.addStretch()

    def refresh(self):
        installer_available, installer_message = self._installer.installer_ready()
        self._runtime_note.setText(
            f"Installer runtime: {'ready' if installer_available else 'unavailable'}."
            f" {installer_message}"
        )
        self._runtime_note.setStyleSheet(
            "color: #86efac;" if installer_available else "color: #fca5a5;"
        )

        for status in all_optional_package_statuses():
            card = self._cards[status.spec.key]
            card.set_installed(status.installed, status.version, installer_available)

    def _request_install(self, package_key: str):
        spec = next(
            spec for spec in optional_package_specs() if spec.key == package_key
        )
        ok = QMessageBox.question(
            self,
            f"Install {spec.title}",
            (
                f"Install {spec.title} now?\n\n"
                f"Estimated size: {spec.estimated_size}\n"
                "This requires internet access and may take a moment."
            ),
        )
        if ok != QMessageBox.StandardButton.Yes:
            return

        card = self._cards[package_key]
        card.set_busy(True, "Preparing install…")

        thread = OptionalPackageInstallThread(package_key, self)
        thread.progress.connect(self._on_install_progress)
        thread.completed.connect(self._on_install_completed)
        thread.finished.connect(lambda: self._threads.pop(package_key, None))
        self._threads[package_key] = thread
        thread.start()

    def _on_install_progress(self, package_key: str, message: str):
        card = self._cards.get(package_key)
        if card:
            card.set_message(message)

    def _on_install_completed(self, package_key: str, success: bool, message: str):
        card = self._cards.get(package_key)
        if card:
            card.set_busy(False)
            card.set_message(message)
        self.refresh()
        if success:
            self.restart_recommended.emit()
            QMessageBox.information(
                self,
                "Install Complete",
                "The add-on finished installing. Restart VerseListener for the cleanest reload.",
            )
        else:
            QMessageBox.warning(self, "Install Failed", message)
