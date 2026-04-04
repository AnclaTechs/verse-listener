"""
ui/transcript_panel.py
Live transcription display panel with Bible verse highlighting.
"""

import logging
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QWidget
from PyQt6.QtCore import Qt, pyqtSlot, QPointF
from PyQt6.QtGui import (
    QTextCharFormat, QColor, QTextCursor, QFont, QPainter, QPainterPath, QPen,
)

from core.bible_detector import VerseMatch

logger = logging.getLogger(__name__)

# Maximum characters to keep in transcript (prevent memory growth)
MAX_TRANSCRIPT_CHARS = 50_000


class AudioWaveformWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._samples = [0.0] * 96
        self._level = 0.0
        self._active = False
        self.setMinimumHeight(58)

    def set_active(self, active: bool):
        self._active = active
        if not active:
            self.clear_waveform()
        else:
            self.update()

    def clear_waveform(self):
        self._samples = [0.0] * len(self._samples)
        self._level = 0.0
        self.update()

    def set_waveform(self, samples, level: float):
        if samples is None:
            return
        self._samples = [max(-1.0, min(float(sample), 1.0)) for sample in samples]
        self._level = max(0.0, min(float(level), 1.0))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.fillRect(rect, QColor("#121722" if self._active else "#13161d"))

        painter.setPen(QPen(QColor("#253047"), 1))
        center_y = rect.center().y()
        painter.drawLine(rect.left() + 10, center_y, rect.right() - 10, center_y)

        if not self._active:
            painter.setPen(QPen(QColor("#2d3748"), 1.5))
            painter.drawRoundedRect(rect, 8, 8)
            return

        glow_alpha = 40 + int(90 * self._level)
        painter.fillRect(
            rect.adjusted(1, 1, -1, -1),
            QColor(37, 99, 235, min(glow_alpha, 120)),
        )

        path = QPainterPath()
        left = rect.left() + 10
        right = rect.right() - 10
        amplitude = max(8.0, rect.height() * (0.18 + self._level * 0.22))
        count = max(1, len(self._samples) - 1)

        for idx, sample in enumerate(self._samples):
            x = left + (right - left) * idx / count
            y = center_y - sample * amplitude
            point = QPointF(x, y)
            if idx == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)

        painter.setPen(QPen(QColor("#6ea8ff"), 2))
        painter.drawPath(path)
        painter.setPen(QPen(QColor("#2d3748"), 1.5))
        painter.drawRoundedRect(rect, 8, 8)


class TranscriptPanel(QFrame):
    """
    Left panel: scrolling real-time transcription with verse highlighting.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("transcriptPanel")
        self._build_ui()
        self._full_text = ""

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(38)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 6, 12, 6)

        title = QLabel("LIVE TRANSCRIPTION")
        title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self._live_dot = QLabel("●")
        self._live_dot.setStyleSheet("color: #2d3142; font-size: 10px;")
        header_layout.addWidget(self._live_dot)

        self._mic_label = QLabel("NOT LISTENING")
        self._mic_label.setStyleSheet("color: #4a5073; font-size: 10px;")
        header_layout.addWidget(self._mic_label)

        layout.addWidget(header)

        # Divider
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: #2d3142;")
        layout.addWidget(div)

        monitor = QWidget()
        monitor_layout = QVBoxLayout(monitor)
        monitor_layout.setContentsMargins(12, 10, 12, 10)
        monitor_layout.setSpacing(6)

        monitor_head = QHBoxLayout()
        monitor_head.setContentsMargins(0, 0, 0, 0)

        monitor_title = QLabel("AUDIO MONITOR")
        monitor_title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        monitor_head.addWidget(monitor_title)
        monitor_head.addStretch()

        self._audio_level_label = QLabel("IDLE")
        self._audio_level_label.setStyleSheet("color: #4a5073; font-size: 10px;")
        monitor_head.addWidget(self._audio_level_label)

        monitor_layout.addLayout(monitor_head)

        self._waveform = AudioWaveformWidget()
        monitor_layout.addWidget(self._waveform)
        layout.addWidget(monitor)

        # Text area
        self._text_edit = QTextEdit()
        self._text_edit.setObjectName("transcriptArea")
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        f = self._text_edit.font()
        f.setPointSize(13)
        self._text_edit.setFont(f)
        layout.addWidget(self._text_edit, 1)

        # Partial / streaming preview at bottom
        partial_bar = QWidget()
        partial_bar.setFixedHeight(28)
        partial_bar.setStyleSheet("background-color: #12141a;")
        pb_layout = QHBoxLayout(partial_bar)
        pb_layout.setContentsMargins(12, 4, 12, 4)

        pb_icon = QLabel("〜")
        pb_icon.setStyleSheet("color: #4a5073; font-size: 11px;")
        pb_layout.addWidget(pb_icon)

        self._partial_label = QLabel("")
        self._partial_label.setStyleSheet("color: #6b7280; font-size: 11px; font-style: italic;")
        self._partial_label.setWordWrap(False)
        pb_layout.addWidget(self._partial_label, 1)

        layout.addWidget(partial_bar)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_listening(self, listening: bool):
        if listening:
            self._live_dot.setStyleSheet("color: #f87171; font-size: 10px;")
            self._mic_label.setText("LISTENING")
            self._mic_label.setStyleSheet("color: #4ade80; font-size: 10px;")
            self._audio_level_label.setText("WAITING FOR INPUT")
            self._audio_level_label.setStyleSheet("color: #64748b; font-size: 10px;")
            self._waveform.set_active(True)
        else:
            self._live_dot.setStyleSheet("color: #2d3142; font-size: 10px;")
            self._mic_label.setText("NOT LISTENING")
            self._mic_label.setStyleSheet("color: #4a5073; font-size: 10px;")
            self._audio_level_label.setText("IDLE")
            self._audio_level_label.setStyleSheet("color: #4a5073; font-size: 10px;")
            self._waveform.set_active(False)

    def append_segment(self, text: str, verse_matches: list[VerseMatch] = None):
        """
        Append a committed transcription segment to the panel.
        Highlights any detected verse references.
        """
        if not text:
            return

        # Trim if too long
        if len(self._full_text) > MAX_TRANSCRIPT_CHARS:
            self._full_text = self._full_text[-MAX_TRANSCRIPT_CHARS // 2:]
            self._text_edit.setPlainText(self._full_text)

        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Add spacing between segments
        if self._full_text:
            fmt_space = QTextCharFormat()
            fmt_space.setForeground(QColor("#4a5073"))
            cursor.insertText(" ", fmt_space)

        self._full_text += " " + text if self._full_text else text

        if verse_matches:
            self._insert_with_highlights(cursor, text, verse_matches)
        else:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#d4d8e8"))
            cursor.insertText(text, fmt)

        # Auto-scroll
        self._text_edit.setTextCursor(cursor)
        self._text_edit.ensureCursorVisible()
        self._partial_label.clear()

    def show_partial(self, text: str):
        """Display streaming partial result (not committed)."""
        max_len = 120
        display = text if len(text) <= max_len else "…" + text[-max_len:]
        self._partial_label.setText(display)

    @pyqtSlot(object, float)
    def update_audio_waveform(self, samples, level: float):
        self._waveform.set_waveform(samples, level)
        if level >= 0.22:
            text = f"SIGNAL {int(level * 100):d}%"
            color = "#4ade80"
        elif level >= 0.06:
            text = f"LOW {int(level * 100):d}%"
            color = "#fbbf24"
        else:
            text = "QUIET"
            color = "#64748b"
        self._audio_level_label.setText(text)
        self._audio_level_label.setStyleSheet(f"color: {color}; font-size: 10px;")

    def clear(self):
        self._full_text = ""
        self._text_edit.clear()
        self._partial_label.clear()
        self._waveform.clear_waveform()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _insert_with_highlights(
        self, cursor: QTextCursor, text: str, matches: list[VerseMatch]
    ):
        """
        Insert *text* character by character in runs, applying
        golden highlight format over verse reference spans.
        """
        normal_fmt = QTextCharFormat()
        normal_fmt.setForeground(QColor("#d4d8e8"))

        highlight_fmt = QTextCharFormat()
        highlight_fmt.setForeground(QColor("#1a1d23"))
        highlight_fmt.setBackground(QColor("#fbbf24"))
        highlight_fmt.setFontWeight(QFont.Weight.Bold)

        # Build a list of (start, end, format) spans
        spans = []
        for m in matches:
            spans.append((m.start_pos, m.end_pos, highlight_fmt))

        # Sort by start position
        spans.sort(key=lambda s: s[0])

        pos = 0
        for start, end, fmt in spans:
            if pos < start:
                cursor.insertText(text[pos:start], normal_fmt)
            cursor.insertText(text[start:end], fmt)
            pos = end
        if pos < len(text):
            cursor.insertText(text[pos:], normal_fmt)
