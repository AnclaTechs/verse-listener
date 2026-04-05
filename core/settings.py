"""
core/settings.py
Application settings with QSettings persistence.
"""

import os

from PyQt6.QtCore import QSettings
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AppSettings:
    # Audio
    audio_device: str = "default"
    audio_backend: str = "auto"

    # STT
    stt_backend: str = "auto"       # "auto" | "whisper" | "vosk" | "openai_realtime"
    whisper_model: str = "small.en"    # recommended English CPU model
    vosk_model: str = "en-us"

    # EasyWorship
    ew_window_title: str = "EasyWorship"
    ew_search_x: int = -1
    ew_search_y: int = -1
    ew_live_x: int = -1
    ew_live_y: int = -1
    ew_click_live: bool = False
    ew_translation: str = "NIV"
    ew_delay_focus: float = 0.5
    ew_delay_type: float = 0.05
    ew_delay_enter: float = 0.3

    # UI
    theme: str = "dark"
    font_size: int = 13
    preview_translation: str = "KJV"
    preview_max_height: int = 220
    preview_gradient_start: str = "#1d4ed8"
    preview_gradient_end: str = "#0f172a"
    context_detection_enabled: bool = True
    context_window_seconds: int = 8

    # ── Persistence ───────────────────────────────────────────────────────────

    def load(self):
        qs = QSettings()
        self.audio_device   = qs.value("audio/device",       self.audio_device)
        self.audio_backend  = qs.value("audio/backend",      self.audio_backend)
        self.stt_backend    = qs.value("stt/backend",        self.stt_backend)
        self.whisper_model  = qs.value("stt/whisper_model",  self.whisper_model)
        self.vosk_model     = qs.value("stt/vosk_model",     self.vosk_model)
        self.ew_window_title= qs.value("ew/window_title",    self.ew_window_title)
        self.ew_search_x    = int(qs.value("ew/search_x",    self.ew_search_x))
        self.ew_search_y    = int(qs.value("ew/search_y",    self.ew_search_y))
        self.ew_live_x      = int(qs.value("ew/live_x",      self.ew_live_x))
        self.ew_live_y      = int(qs.value("ew/live_y",      self.ew_live_y))
        self.ew_click_live  = qs.value("ew/click_live",      self.ew_click_live) in (True, "true")
        self.ew_translation = qs.value("ew/translation",     self.ew_translation)
        self.ew_delay_focus = float(qs.value("ew/delay_focus", self.ew_delay_focus))
        self.ew_delay_type  = float(qs.value("ew/delay_type",  self.ew_delay_type))
        self.ew_delay_enter = float(qs.value("ew/delay_enter", self.ew_delay_enter))
        self.theme          = qs.value("ui/theme",           self.theme)
        self.font_size      = int(qs.value("ui/font_size",   self.font_size))
        self.preview_translation = qs.value("preview/translation", self.preview_translation)
        self.preview_max_height = int(qs.value("preview/max_height", self.preview_max_height))
        self.preview_gradient_start = qs.value(
            "preview/gradient_start", self.preview_gradient_start
        )
        self.preview_gradient_end = qs.value(
            "preview/gradient_end", self.preview_gradient_end
        )
        self.context_detection_enabled = qs.value(
            "context/enabled", self.context_detection_enabled
        ) in (True, "true")
        self.context_window_seconds = int(
            qs.value("context/window_seconds", self.context_window_seconds)
        )
        self.audio_backend  = os.getenv("VERSE_LISTENER_AUDIO_BACKEND", self.audio_backend)
        self.stt_backend    = os.getenv("VERSE_LISTENER_STT_BACKEND", self.stt_backend)
        self.whisper_model  = os.getenv("VERSE_LISTENER_WHISPER_MODEL", self.whisper_model)
        self.vosk_model     = os.getenv("VERSE_LISTENER_VOSK_MODEL", self.vosk_model)

    def save(self):
        qs = QSettings()
        qs.setValue("audio/device",      self.audio_device)
        qs.setValue("audio/backend",     self.audio_backend)
        qs.setValue("stt/backend",       self.stt_backend)
        qs.setValue("stt/whisper_model", self.whisper_model)
        qs.setValue("stt/vosk_model",    self.vosk_model)
        qs.setValue("ew/window_title",   self.ew_window_title)
        qs.setValue("ew/search_x",       self.ew_search_x)
        qs.setValue("ew/search_y",       self.ew_search_y)
        qs.setValue("ew/live_x",         self.ew_live_x)
        qs.setValue("ew/live_y",         self.ew_live_y)
        qs.setValue("ew/click_live",     self.ew_click_live)
        qs.setValue("ew/translation",    self.ew_translation)
        qs.setValue("ew/delay_focus",    self.ew_delay_focus)
        qs.setValue("ew/delay_type",     self.ew_delay_type)
        qs.setValue("ew/delay_enter",    self.ew_delay_enter)
        qs.setValue("ui/theme",          self.theme)
        qs.setValue("ui/font_size",      self.font_size)
        qs.setValue("preview/translation", self.preview_translation)
        qs.setValue("preview/max_height", self.preview_max_height)
        qs.setValue("preview/gradient_start", self.preview_gradient_start)
        qs.setValue("preview/gradient_end", self.preview_gradient_end)
        qs.setValue("context/enabled", self.context_detection_enabled)
        qs.setValue("context/window_seconds", self.context_window_seconds)
        qs.sync()
