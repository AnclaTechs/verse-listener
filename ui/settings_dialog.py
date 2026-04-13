"""
ui/settings_dialog.py
Settings dialog for VerseListener – audio, STT model, add-ons, EasyWorship config, UI.
"""

import logging

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.bible_preview import BiblePreviewLibrary
from core.settings import AppSettings
from ui.optional_packages_panel import OptionalPackagesPanel

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    reopen_welcome_requested = pyqtSignal()

    def __init__(
        self,
        settings: AppSettings,
        parent=None,
        *,
        initial_section: str = "audio",
        focus_target: str = "",
    ):
        super().__init__(parent)
        self.settings = settings
        self._preview_library = BiblePreviewLibrary()
        self._initial_section = initial_section
        self._focus_target = focus_target
        self._tab_indices: dict[str, int] = {}
        self.setWindowTitle("VerseListener – Settings")
        self.setMinimumWidth(720)
        self.setModal(True)
        self._build_ui()
        self._load_values()
        QTimer.singleShot(0, self._apply_initial_focus)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._tabs = QTabWidget()
        self._tab_indices["audio"] = self._tabs.addTab(self._audio_tab(), "🎙  Audio")
        self._tab_indices["speech"] = self._tabs.addTab(
            self._stt_tab(), "🧠  Speech Model"
        )
        self._tab_indices["addons"] = self._tabs.addTab(
            self._addons_tab(), "⬇  Add-ons"
        )
        self._tab_indices["easyworship"] = self._tabs.addTab(
            self._ew_tab(), "⛪  EasyWorship"
        )
        self._tab_indices["interface"] = self._tabs.addTab(
            self._ui_tab(), "🎨  Interface"
        )
        layout.addWidget(self._tabs)

        self._session_note = QLabel("")
        self._session_note.hide()
        self._session_note.setWordWrap(True)
        self._session_note.setStyleSheet(
            "background: rgba(37, 99, 235, 0.12);"
            "border: 1px solid rgba(59, 130, 246, 0.25);"
            "border-radius: 10px;"
            "padding: 10px 12px;"
            "color: #bfdbfe;"
        )
        layout.addWidget(self._session_note)

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
        layout.setSpacing(12)

        openai_grp = QGroupBox("OpenAI Realtime")
        openai_form = QFormLayout(openai_grp)

        key_row = QHBoxLayout()
        key_row.setSpacing(8)

        self._openai_api_key = QLineEdit()
        self._openai_api_key.setPlaceholderText("sk-...")
        self._openai_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(self._openai_api_key, 1)

        self._show_api_key = QPushButton("Show")
        self._show_api_key.setCheckable(True)
        self._show_api_key.toggled.connect(self._toggle_api_key_visibility)
        key_row.addWidget(self._show_api_key)

        openai_form.addRow("API Key:", key_row)

        openai_note = QLabel(
            "VerseListener now defaults to OpenAI Realtime for the leanest bundled experience. "
            "Your key is stored locally on this machine and applied to the running app immediately."
        )
        openai_note.setWordWrap(True)
        openai_note.setStyleSheet("color: #8892b0; font-size: 11px;")
        openai_form.addRow("", openai_note)

        layout.addWidget(openai_grp)

        grp = QGroupBox("Speech-to-Text Engine")
        form = QFormLayout(grp)

        self._stt_backend = QComboBox()
        self._stt_backend.addItems(["openai_realtime", "auto", "whisper", "vosk"])
        form.addRow("Backend:", self._stt_backend)

        self._whisper_model = QComboBox()
        self._whisper_model.addItems(
            [
                "tiny",
                "tiny.en",
                "base",
                "base.en",
                "small",
                "small.en",
                "medium",
                "medium.en",
                "large-v2",
                "large-v3",
            ]
        )
        form.addRow("Whisper Model:", self._whisper_model)

        self._vosk_model = QLineEdit()
        self._vosk_model.setPlaceholderText("en-us  (folder name under ~/.vosk/)")
        form.addRow("Vosk Model:", self._vosk_model)

        layout.addWidget(grp)

        context_grp = QGroupBox("Contextual Passage Guessing")
        context_form = QFormLayout(context_grp)

        self._context_detection_enabled = QCheckBox(
            "Suggest likely passage from recent transcript context"
        )
        context_form.addRow("", self._context_detection_enabled)

        self._context_window_seconds = QSpinBox()
        self._context_window_seconds.setRange(5, 60)
        self._context_window_seconds.setSingleStep(1)
        context_form.addRow("Context Window:", self._context_window_seconds)

        layout.addWidget(context_grp)
        layout.addStretch()

        note = QLabel(
            "💡 OpenAI Realtime is the recommended default for live use.\n"
            "   Use the Add-ons tab to install Vosk, faster-whisper, or sentence-transformers later.\n"
            "   Contextual guessing starts with local keyword matching and upgrades automatically if sentence-transformers is installed."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8892b0; font-size: 11px;")
        layout.addWidget(note)
        return w

    def _addons_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        self._addons_panel = OptionalPackagesPanel(self)
        self._addons_panel.restart_recommended.connect(self._show_restart_recommended)
        layout.addWidget(self._addons_panel)
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

        self._ew_search_x = QSpinBox()
        self._ew_search_x.setRange(-1, 9999)
        self._ew_search_y = QSpinBox()
        self._ew_search_y.setRange(-1, 9999)
        form2.addRow("Search Field X:", self._ew_search_x)
        form2.addRow("Search Field Y:", self._ew_search_y)

        self._ew_live_x = QSpinBox()
        self._ew_live_x.setRange(-1, 9999)
        self._ew_live_y = QSpinBox()
        self._ew_live_y.setRange(-1, 9999)
        self._ew_click_live = QCheckBox("Click 'Live / Put on Screen' after loading")
        form2.addRow("Live Button X:", self._ew_live_x)
        form2.addRow("Live Button Y:", self._ew_live_y)
        form2.addRow("", self._ew_click_live)

        layout.addWidget(grp_coords)

        grp_delays = QGroupBox("Timing Delays (seconds)")
        form3 = QFormLayout(grp_delays)

        self._ew_delay_focus = QDoubleSpinBox()
        self._ew_delay_focus.setRange(0.0, 5.0)
        self._ew_delay_focus.setSingleStep(0.1)
        form3.addRow("Focus delay:", self._ew_delay_focus)

        self._ew_delay_type = QDoubleSpinBox()
        self._ew_delay_type.setRange(0.0, 0.5)
        self._ew_delay_type.setSingleStep(0.01)
        self._ew_delay_type.setDecimals(3)
        form3.addRow("Typing delay (per char):", self._ew_delay_type)

        self._ew_delay_enter = QDoubleSpinBox()
        self._ew_delay_enter.setRange(0.0, 3.0)
        self._ew_delay_enter.setSingleStep(0.1)
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

        experience_grp = QGroupBox("Experience")
        experience_form = QFormLayout(experience_grp)

        self._developer_mode = QCheckBox("Enable developer mode")
        experience_form.addRow("", self._developer_mode)

        self._reopen_welcome = QPushButton("Reopen Welcome")
        self._reopen_welcome.clicked.connect(self.reopen_welcome_requested.emit)
        experience_form.addRow("Onboarding:", self._reopen_welcome)

        layout.addWidget(experience_grp)

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
        self._openai_api_key.setText(s.openai_api_key)
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
        self._developer_mode.setChecked(s.developer_mode)
        self._preview_translation.setCurrentText(s.preview_translation)
        self._preview_max_height.setValue(s.preview_max_height)
        self._preview_gradient_start.setText(s.preview_gradient_start)
        self._preview_gradient_end.setText(s.preview_gradient_end)

    def _save_and_accept(self):
        s = self.settings
        s.audio_device = self._audio_device.text().strip() or "default"
        s.audio_backend = self._audio_backend.currentText()
        s.openai_api_key = self._openai_api_key.text().strip()
        s.stt_backend = self._stt_backend.currentText()
        s.whisper_model = self._whisper_model.currentText()
        s.vosk_model = self._vosk_model.text().strip() or "en-us"
        s.context_detection_enabled = self._context_detection_enabled.isChecked()
        s.context_window_seconds = self._context_window_seconds.value()
        s.ew_window_title = self._ew_title.text().strip() or "EasyWorship"
        s.ew_translation = self._ew_translation.text().strip() or "NIV"
        s.ew_search_x = self._ew_search_x.value()
        s.ew_search_y = self._ew_search_y.value()
        s.ew_live_x = self._ew_live_x.value()
        s.ew_live_y = self._ew_live_y.value()
        s.ew_click_live = self._ew_click_live.isChecked()
        s.ew_delay_focus = self._ew_delay_focus.value()
        s.ew_delay_type = self._ew_delay_type.value()
        s.ew_delay_enter = self._ew_delay_enter.value()
        s.theme = self._theme.currentText()
        s.font_size = self._font_size.value()
        s.developer_mode = self._developer_mode.isChecked()
        s.preview_translation = self._preview_translation.currentText().strip() or "KJV"
        s.preview_max_height = self._preview_max_height.value()
        s.preview_gradient_start = (
            self._preview_gradient_start.text().strip() or "#1d4ed8"
        )
        s.preview_gradient_end = self._preview_gradient_end.text().strip() or "#0f172a"
        s.save()
        self.accept()

    def _apply_initial_focus(self):
        if self._initial_section in self._tab_indices:
            self._tabs.setCurrentIndex(self._tab_indices[self._initial_section])
        if self._focus_target == "api_key":
            self._openai_api_key.setFocus()
            self._openai_api_key.selectAll()

    def _toggle_api_key_visibility(self, visible: bool):
        self._openai_api_key.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self._show_api_key.setText("Hide" if visible else "Show")

    def _show_restart_recommended(self):
        self._session_note.setText(
            "An optional add-on finished installing. Restart VerseListener for the cleanest reload."
        )
        self._session_note.show()
