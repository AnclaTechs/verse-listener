"""
ui/main_window.py
Main application window for VerseListener.
Orchestrates audio capture, transcription, verse detection, queue, and EasyWorship.
"""

import logging
import threading
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QToolBar, QStatusBar, QLabel, QMessageBox,
    QApplication,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QThread
from PyQt6.QtGui import QAction, QKeySequence, QShortcut, QFont

from core.settings import AppSettings
from core.bible_detector import BibleDetector
from core.transcription import AudioCaptureThread, TranscriptionThread
from core.easyworship import EasyWorshipController, EasyWorshipConfig
from ui.transcript_panel import TranscriptPanel
from ui.queue_panel import VerseQueuePanel
from ui.settings_dialog import SettingsDialog
from ui.styles import get_stylesheet

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = AppSettings()
        self.settings.load()

        self._detector = BibleDetector()
        self._ew_controller = self._build_ew_controller()
        self._audio_thread: Optional[AudioCaptureThread] = None
        self._transcription_thread: Optional[TranscriptionThread] = None
        self._listening = False

        self._build_ui()
        self._apply_theme()
        self._connect_shortcuts()
        self._start_ew_status_timer()

        self.setWindowTitle("VerseListener")
        self.resize(1100, 720)
        logger.info("Main window ready")

    # ── Builder helpers ───────────────────────────────────────────────────────

    def _build_ew_controller(self) -> EasyWorshipController:
        cfg = EasyWorshipConfig(
            window_title_fragment=self.settings.ew_window_title,
            translation=self.settings.ew_translation,
            delay_focus=self.settings.ew_delay_focus,
            delay_type=self.settings.ew_delay_type,
            delay_enter=self.settings.ew_delay_enter,
            click_live=self.settings.ew_click_live,
            search_x=self.settings.ew_search_x if self.settings.ew_search_x >= 0 else None,
            search_y=self.settings.ew_search_y if self.settings.ew_search_y >= 0 else None,
            live_x=self.settings.ew_live_x if self.settings.ew_live_x >= 0 else None,
            live_y=self.settings.ew_live_y if self.settings.ew_live_y >= 0 else None,
        )
        return EasyWorshipController(cfg)

    def _build_ui(self):
        # ── Toolbar ───────────────────────────────────────────────────────────
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        self._start_action = QAction("▶  Start Listening", self)
        self._start_action.setCheckable(True)
        self._start_action.setToolTip("Start / stop audio capture and transcription  [Ctrl+R]")
        self._start_action.setShortcut(QKeySequence("Ctrl+R"))
        self._start_action.triggered.connect(self._toggle_listening)
        toolbar.addAction(self._start_action)

        toolbar.addSeparator()

        calibrate_action = QAction("🎯  Calibrate EW", self)
        calibrate_action.setToolTip("Calibrate EasyWorship search field position")
        calibrate_action.triggered.connect(self._calibrate_easyworship)
        toolbar.addAction(calibrate_action)

        settings_action = QAction("⚙  Settings", self)
        settings_action.setToolTip("Open settings dialog")
        settings_action.triggered.connect(self._open_settings)
        toolbar.addAction(settings_action)

        toolbar.addSeparator()

        clear_action = QAction("🗑  Clear", self)
        clear_action.setToolTip("Clear transcript and verse queue")
        clear_action.triggered.connect(self._clear_all)
        toolbar.addAction(clear_action)

        toolbar.addSeparator()

        theme_action = QAction("◑  Toggle Theme", self)
        theme_action.triggered.connect(self._toggle_theme)
        toolbar.addAction(theme_action)

        # ── Central content ───────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        self._transcript_panel = TranscriptPanel()
        self._queue_panel = VerseQueuePanel(self.settings)

        splitter.addWidget(self._transcript_panel)
        splitter.addWidget(self._queue_panel)
        splitter.setSizes([660, 380])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # ── Connect queue signals ─────────────────────────────────────────────
        self._queue_panel.send_requested.connect(self._send_to_easyworship)
        self._queue_panel.verse_selected.connect(self._on_verse_selected_in_queue)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._sb_audio    = QLabel("Audio: idle")
        self._sb_model    = QLabel("Model: –")
        self._sb_ew       = QLabel("EW: unknown")
        self._sb_detected = QLabel("Verses detected: 0")

        for lbl in (self._sb_audio, self._sb_model, self._sb_ew, self._sb_detected):
            lbl.setObjectName("statusLabel")
            lbl.setStyleSheet("color: #8892b0; padding: 0 8px;")
            self._status_bar.addPermanentWidget(lbl)

    def _apply_theme(self):
        QApplication.instance().setStyleSheet(get_stylesheet(self.settings.theme))

    def _connect_shortcuts(self):
        # Ctrl+Shift+S → send top queued verse
        sc = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        sc.activated.connect(self._queue_panel.send_top_verse)

    def _start_ew_status_timer(self):
        self._ew_timer = QTimer(self)
        self._ew_timer.setInterval(5000)
        self._ew_timer.timeout.connect(self._refresh_ew_status)
        self._ew_timer.start()
        self._refresh_ew_status()

    # ── Listening control ─────────────────────────────────────────────────────

    @pyqtSlot(bool)
    def _toggle_listening(self, checked: bool):
        if checked:
            self._start_listening()
        else:
            self._stop_listening()

    def _start_listening(self):
        if self._listening:
            return
        logger.info("Starting audio capture and transcription")
        self._listening = True
        self._start_action.setText("⏹  Stop Listening")
        self._start_action.setChecked(True)
        self._detector.reset()
        self._detected_count = 0

        # Audio capture thread
        self._audio_thread = AudioCaptureThread(
            device_name=self.settings.audio_device,
            backend=self.settings.audio_backend,
        )
        self._audio_thread.status_changed.connect(self._on_audio_status)
        self._audio_thread.error_occurred.connect(self._on_error)
        self._audio_thread.audio_visual.connect(self._transcript_panel.update_audio_waveform)
        self._audio_thread.start()

        # Transcription thread
        self._transcription_thread = TranscriptionThread(
            audio_queue=self._audio_thread.audio_queue,
            whisper_model_name=self.settings.whisper_model,
            vosk_model_name=self.settings.vosk_model,
            backend=self.settings.stt_backend,
        )
        self._transcription_thread.partial_result.connect(self._on_partial)
        self._transcription_thread.final_result.connect(self._on_final)
        self._transcription_thread.status_changed.connect(self._on_status_msg)
        self._transcription_thread.error_occurred.connect(self._on_error)
        self._transcription_thread.model_loaded.connect(self._on_model_loaded)
        self._transcription_thread.start()

        self._transcript_panel.set_listening(True)
        self._sb_audio.setText("Audio: starting…")

    def _stop_listening(self):
        if not self._listening:
            return
        logger.info("Stopping audio capture and transcription")
        self._listening = False
        self._start_action.setText("▶  Start Listening")
        self._start_action.setChecked(False)

        if self._transcription_thread:
            self._transcription_thread.stop()
            self._transcription_thread.wait(3000)
            self._transcription_thread = None

        if self._audio_thread:
            self._audio_thread.stop()
            self._audio_thread.wait(3000)
            self._audio_thread = None

        self._transcript_panel.set_listening(False)
        self._sb_audio.setText("Audio: stopped")

    # ── Transcription signal handlers ─────────────────────────────────────────

    @pyqtSlot(str)
    def _on_partial(self, text: str):
        self._transcript_panel.show_partial(text)

    @pyqtSlot(str)
    def _on_final(self, text: str):
        """Process a committed transcription segment."""
        if not text.strip():
            return

        # Detect verses
        matches = self._detector.detect(text)

        # Display in transcript
        self._transcript_panel.append_segment(text, matches)

        # Add new detections to queue
        for vm in matches:
            self._queue_panel.add_verse(vm)
            self._detected_count = getattr(self, "_detected_count", 0) + 1
            self._sb_detected.setText(f"Verses detected: {self._detected_count}")

    @pyqtSlot(str)
    def _on_audio_status(self, msg: str):
        self._sb_audio.setText(f"Audio: {msg}")

    @pyqtSlot(str)
    def _on_status_msg(self, msg: str):
        self._status_bar.showMessage(msg, 4000)

    @pyqtSlot(str)
    def _on_model_loaded(self, model_name: str):
        self._sb_model.setText(f"Model: {model_name}")

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        logger.error("Error: %s", msg)
        self._status_bar.showMessage(f"⚠ {msg}", 6000)

    # ── EasyWorship ────────────────────────────────────────────────────────────

    @pyqtSlot(str)
    def _send_to_easyworship(self, reference: str):
        """Send verse reference to EasyWorship in a background thread."""
        def _do():
            success = self._ew_controller.send_verse(reference)
            if success:
                logger.info("Sent '%s' to EasyWorship", reference)
            else:
                logger.warning("Failed to send '%s' to EasyWorship", reference)

        t = threading.Thread(target=_do, daemon=True)
        t.start()
        self._status_bar.showMessage(f"Sending '{reference}' to EasyWorship…", 3000)

    @pyqtSlot(str)
    def _on_verse_selected_in_queue(self, reference: str):
        self._status_bar.showMessage(f"Selected: {reference}", 2000)

    def _refresh_ew_status(self):
        status = self._ew_controller.status_text()
        self._sb_ew.setText(status)
        if "connected" in status.lower():
            self._sb_ew.setStyleSheet("color: #4ade80; padding: 0 8px;")
        else:
            self._sb_ew.setStyleSheet("color: #f87171; padding: 0 8px;")

    def _calibrate_easyworship(self):
        QMessageBox.information(
            self,
            "Calibrate EasyWorship",
            "In 3 seconds, move your cursor to the <b>Bible search field</b> in EasyWorship "
            "and leave it there.\n\nThe coordinates will be saved automatically.",
        )
        def _do_calibrate():
            ok = self._ew_controller.calibrate_from_screenshot()
            if ok:
                cfg = self._ew_controller.config
                self.settings.ew_search_x = cfg.search_x
                self.settings.ew_search_y = cfg.search_y
                self.settings.save()
                logger.info(
                    "Calibrated search field to (%d, %d)",
                    cfg.search_x, cfg.search_y,
                )

        t = threading.Thread(target=_do_calibrate, daemon=True)
        t.start()

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            # Reload settings
            self.settings.load()
            self._ew_controller = self._build_ew_controller()
            self._queue_panel.apply_settings(self.settings)
            self._apply_theme()
            # Restart listening if active
            if self._listening:
                self._stop_listening()
                QTimer.singleShot(500, self._start_listening)

    def _toggle_theme(self):
        self.settings.theme = "light" if self.settings.theme == "dark" else "dark"
        self.settings.save()
        self._apply_theme()

    # ── Clear ─────────────────────────────────────────────────────────────────

    def _clear_all(self):
        self._transcript_panel.clear()
        self._queue_panel.clear()
        self._detector.reset()
        self._detected_count = 0
        self._sb_detected.setText("Verses detected: 0")

    # ── Window close ──────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._stop_listening()
        self.settings.save()
        event.accept()
