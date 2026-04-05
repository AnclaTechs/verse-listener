"""
ui/settings_dialog.py
Settings dialog for VerseListener – audio, STT model, EasyWorship config, UI.
"""

import logging
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QPushButton, QDialogButtonBox,
    QFormLayout, QFrame,
)
from PyQt6.QtCore import Qt

from core.bible_preview import BiblePreviewLibrary
from core.settings import AppSettings

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._preview_library = BiblePreviewLibrary()
        self.setWindowTitle("VerseListener – Settings")
        self.setMinimumWidth(520)
        self.setModal(True)
        self._build_ui()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.addTab(self._audio_tab(),      "🎙  Audio")
        tabs.addTab(self._stt_tab(),        "🧠  Speech Model")
        tabs.addTab(self._ew_tab(),         "⛪  EasyWorship")
        tabs.addTab(self._ui_tab(),         "🎨  Interface")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _audio_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        grp = QGroupBox("Audio Input")
        form = QFormLayout(grp)

        self._audio_device = QLineEdit()
        self._audio_device.setPlaceholderText("default  (or JACK port name)")
        form.addRow("Device / Port:", self._audio_device)

        self._audio_backend = QComboBox()
        self._audio_backend.addItems(["auto", "jack", "sounddevice"])
        form.addRow("Backend:", self._audio_backend)

        layout.addWidget(grp)
        layout.addStretch()

        note = QLabel(
            "💡 On Linux with JACK running, 'auto' tries JACK first.\n"
            "   Set the backend to 'sounddevice' to use ALSA/PulseAudio.\n"
            "   For Windows builds, 'sounddevice' is the recommended backend."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8892b0; font-size: 11px;")
        layout.addWidget(note)
        return w

    def _stt_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        grp = QGroupBox("Speech-to-Text Engine")
        form = QFormLayout(grp)

        self._stt_backend = QComboBox()
        self._stt_backend.addItems(["auto", "whisper", "openai_realtime", "vosk"])
        form.addRow("Backend:", self._stt_backend)

        self._whisper_model = QComboBox()
        self._whisper_model.addItems(["tiny", "tiny.en", "base", "base.en",
                                       "small", "small.en", "medium", "medium.en",
                                       "large-v2", "large-v3"])
        form.addRow("Whisper Model:", self._whisper_model)

        self._vosk_model = QLineEdit()
        self._vosk_model.setPlaceholderText("en-us  (folder name under ~/.vosk/)")
        form.addRow("Vosk Model:", self._vosk_model)

        layout.addWidget(grp)

        context_grp = QGroupBox("Contextual Passage Guessing")
        context_form = QFormLayout(context_grp)

        self._context_detection_enabled = QCheckBox("Suggest likely passage from recent transcript context")
        context_form.addRow("", self._context_detection_enabled)

        self._context_window_seconds = QSpinBox()
        self._context_window_seconds.setRange(5, 60)
        self._context_window_seconds.setSingleStep(1)
        context_form.addRow("Context Window:", self._context_window_seconds)

        layout.addWidget(context_grp)
        layout.addStretch()

        note = QLabel(
            "💡 'auto' tries faster-whisper first, then Vosk.\n"
            "   Recommended for English sermons: backend 'whisper' with model 'small.en'.\n"
            "   Use 'base.en' on lower-end machines or 'medium.en' if you have CPU headroom.\n"
            "   For cloud realtime STT, use 'openai_realtime' and set OPENAI_API_KEY in .env.\n"
            "   Vosk requires a model folder at ~/.vosk/model-<name>.\n"
            "   Contextual guessing uses local Bible text first and upgrades automatically if sentence-transformers is installed."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8892b0; font-size: 11px;")
        layout.addWidget(note)
        return w

    def _ew_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        grp_gen = QGroupBox("EasyWorship General")
        form1 = QFormLayout(grp_gen)

        self._ew_title = QLineEdit()
        form1.addRow("Window Title Fragment:", self._ew_title)

        self._ew_translation = QLineEdit()
        form1.addRow("Bible Translation:", self._ew_translation)

        layout.addWidget(grp_gen)

        grp_coords = QGroupBox("Calibration Coordinates  (set via Calibrate button)")
        form2 = QFormLayout(grp_coords)

        self._ew_search_x = QSpinBox(); self._ew_search_x.setRange(-1, 9999)
        self._ew_search_y = QSpinBox(); self._ew_search_y.setRange(-1, 9999)
        form2.addRow("Search Field X:", self._ew_search_x)
        form2.addRow("Search Field Y:", self._ew_search_y)

        self._ew_live_x = QSpinBox(); self._ew_live_x.setRange(-1, 9999)
        self._ew_live_y = QSpinBox(); self._ew_live_y.setRange(-1, 9999)
        self._ew_click_live = QCheckBox("Click 'Live / Put on Screen' after loading")
        form2.addRow("Live Button X:", self._ew_live_x)
        form2.addRow("Live Button Y:", self._ew_live_y)
        form2.addRow("", self._ew_click_live)

        layout.addWidget(grp_coords)

        grp_delays = QGroupBox("Timing Delays (seconds)")
        form3 = QFormLayout(grp_delays)

        self._ew_delay_focus = QDoubleSpinBox()
        self._ew_delay_focus.setRange(0.0, 5.0); self._ew_delay_focus.setSingleStep(0.1)
        form3.addRow("Focus delay:", self._ew_delay_focus)

        self._ew_delay_type = QDoubleSpinBox()
        self._ew_delay_type.setRange(0.0, 0.5); self._ew_delay_type.setSingleStep(0.01)
        self._ew_delay_type.setDecimals(3)
        form3.addRow("Typing delay (per char):", self._ew_delay_type)

        self._ew_delay_enter = QDoubleSpinBox()
        self._ew_delay_enter.setRange(0.0, 3.0); self._ew_delay_enter.setSingleStep(0.1)
        form3.addRow("After-Enter delay:", self._ew_delay_enter)

        layout.addWidget(grp_delays)
        layout.addStretch()
        return w

    def _ui_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        grp = QGroupBox("Appearance")
        form = QFormLayout(grp)

        self._theme = QComboBox()
        self._theme.addItems(["dark", "light"])
        form.addRow("Theme:", self._theme)

        self._font_size = QSpinBox()
        self._font_size.setRange(9, 24)
        form.addRow("Font Size:", self._font_size)

        layout.addWidget(grp)

        preview_grp = QGroupBox("Verse Preview")
        preview_form = QFormLayout(preview_grp)

        self._preview_translation = QComboBox()
        self._preview_translation.setEditable(True)
        editions = self._preview_library.available_editions()
        if editions:
            self._preview_translation.addItems(editions)
        self._preview_translation.setEditText(self.settings.preview_translation)
        preview_form.addRow("Canon Edition:", self._preview_translation)

        self._preview_max_height = QSpinBox()
        self._preview_max_height.setRange(140, 500)
        self._preview_max_height.setSingleStep(10)
        preview_form.addRow("Preview Max Height:", self._preview_max_height)

        self._preview_gradient_start = QLineEdit()
        self._preview_gradient_start.setPlaceholderText("#1d4ed8")
        preview_form.addRow("Gradient Start:", self._preview_gradient_start)

        self._preview_gradient_end = QLineEdit()
        self._preview_gradient_end.setPlaceholderText("#0f172a")
        preview_form.addRow("Gradient End:", self._preview_gradient_end)

        layout.addWidget(preview_grp)

        note = QLabel(
            "💡 The preview uses local canon files from canons/<EDITION>/verses.json.\n"
            "   Pick the folder name as the edition, for example 'KJV'.\n"
            "   The preview card stays compact and becomes scrollable when the verse text is longer."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8892b0; font-size: 11px;")
        layout.addWidget(note)
        layout.addStretch()
        return w

    # ── Value management ──────────────────────────────────────────────────────

    def _load_values(self):
        s = self.settings
        self._audio_device.setText(s.audio_device)
        self._audio_backend.setCurrentText(s.audio_backend)
        self._stt_backend.setCurrentText(s.stt_backend)
        self._whisper_model.setCurrentText(s.whisper_model)
        self._vosk_model.setText(s.vosk_model)
        self._context_detection_enabled.setChecked(s.context_detection_enabled)
        self._context_window_seconds.setValue(s.context_window_seconds)
        self._ew_title.setText(s.ew_window_title)
        self._ew_translation.setText(s.ew_translation)
        self._ew_search_x.setValue(s.ew_search_x)
        self._ew_search_y.setValue(s.ew_search_y)
        self._ew_live_x.setValue(s.ew_live_x)
        self._ew_live_y.setValue(s.ew_live_y)
        self._ew_click_live.setChecked(s.ew_click_live)
        self._ew_delay_focus.setValue(s.ew_delay_focus)
        self._ew_delay_type.setValue(s.ew_delay_type)
        self._ew_delay_enter.setValue(s.ew_delay_enter)
        self._theme.setCurrentText(s.theme)
        self._font_size.setValue(s.font_size)
        self._preview_translation.setCurrentText(s.preview_translation)
        self._preview_max_height.setValue(s.preview_max_height)
        self._preview_gradient_start.setText(s.preview_gradient_start)
        self._preview_gradient_end.setText(s.preview_gradient_end)

    def _save_and_accept(self):
        s = self.settings
        s.audio_device      = self._audio_device.text().strip() or "default"
        s.audio_backend     = self._audio_backend.currentText()
        s.stt_backend       = self._stt_backend.currentText()
        s.whisper_model     = self._whisper_model.currentText()
        s.vosk_model        = self._vosk_model.text().strip() or "en-us"
        s.context_detection_enabled = self._context_detection_enabled.isChecked()
        s.context_window_seconds = self._context_window_seconds.value()
        s.ew_window_title   = self._ew_title.text().strip() or "EasyWorship"
        s.ew_translation    = self._ew_translation.text().strip() or "NIV"
        s.ew_search_x       = self._ew_search_x.value()
        s.ew_search_y       = self._ew_search_y.value()
        s.ew_live_x         = self._ew_live_x.value()
        s.ew_live_y         = self._ew_live_y.value()
        s.ew_click_live     = self._ew_click_live.isChecked()
        s.ew_delay_focus    = self._ew_delay_focus.value()
        s.ew_delay_type     = self._ew_delay_type.value()
        s.ew_delay_enter    = self._ew_delay_enter.value()
        s.theme             = self._theme.currentText()
        s.font_size         = self._font_size.value()
        s.preview_translation = self._preview_translation.currentText().strip() or "KJV"
        s.preview_max_height = self._preview_max_height.value()
        s.preview_gradient_start = (
            self._preview_gradient_start.text().strip() or "#1d4ed8"
        )
        s.preview_gradient_end = (
            self._preview_gradient_end.text().strip() or "#0f172a"
        )
        s.save()
        self.accept()
