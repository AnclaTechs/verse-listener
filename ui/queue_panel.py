"""
ui/queue_panel.py
The detected verses queue panel – shows verse references with timestamps,
send-to-EasyWorship and remove buttons, and an editable reference field.
"""

import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QWidget, QLineEdit, QSizePolicy,
    QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor

from core.bible_preview import BiblePreview, BiblePreviewLibrary
from core.bible_detector import VerseMatch
from core.settings import AppSettings

logger = logging.getLogger(__name__)


@dataclass
class QueueEntry:
    verse: VerseMatch
    timestamp: datetime = field(default_factory=datetime.now)
    reference: str = ""          # editable reference override
    confidence: float = 1.0

    def __post_init__(self):
        if not self.reference:
            self.reference = self.verse.reference


class VerseQueuePanel(QFrame):
    """
    Right panel: detected verse queue with send/remove controls.
    """

    send_requested   = pyqtSignal(str)    # reference string → EasyWorship
    verse_selected   = pyqtSignal(str)    # reference highlighted in transcript

    def __init__(self, settings: Optional[AppSettings] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("queuePanel")
        self._settings = settings or AppSettings()
        self._entries: list[QueueEntry] = []
        self._preview_library = BiblePreviewLibrary()
        self._build_ui()
        self.apply_settings(self._settings)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(38)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 6, 12, 6)

        title = QLabel("DETECTED VERSES")
        title.setProperty("class", "panelTitle")
        title.setStyleSheet("color: #64748b; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self._count_label = QLabel("0")
        self._count_label.setStyleSheet(
            "background-color: #2d3142; color: #8892b0; border-radius: 9px;"
            "padding: 1px 7px; font-size: 11px;"
        )
        header_layout.addWidget(self._count_label)

        layout.addWidget(header)

        # Divider
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: #2d3142;")
        layout.addWidget(div)

        self._preview = _VersePreviewWidget(self._preview_library)
        layout.addWidget(self._preview)

        # List
        self._list = QListWidget()
        self._list.setObjectName("queueList")
        self._list.setSpacing(2)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, 1)

        # ── Edit / action area ─────────────────────────────────────────────
        action_container = QWidget()
        action_container.setStyleSheet("background-color: #12141a;")
        action_layout = QVBoxLayout(action_container)
        action_layout.setContentsMargins(10, 10, 10, 10)
        action_layout.setSpacing(8)

        edit_label = QLabel("Edit reference before sending:")
        edit_label.setStyleSheet("color: #64748b; font-size: 11px;")
        action_layout.addWidget(edit_label)

        self._edit_field = QLineEdit()
        self._edit_field.setPlaceholderText("Select a verse above…")
        self._edit_field.setEnabled(False)
        self._edit_field.textChanged.connect(self._on_edit_changed)
        action_layout.addWidget(self._edit_field)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._send_btn = QPushButton("⛪  Send to EasyWorship")
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.setEnabled(False)
        self._send_btn.clicked.connect(self._on_send)
        btn_row.addWidget(self._send_btn, 2)

        self._remove_btn = QPushButton("✕ Remove")
        self._remove_btn.setObjectName("removeBtn")
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._on_remove)
        btn_row.addWidget(self._remove_btn, 1)

        action_layout.addLayout(btn_row)

        # Hotkey hint
        hint = QLabel("Ctrl+Shift+S  →  send top verse")
        hint.setStyleSheet("color: #4a5073; font-size: 10px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        action_layout.addWidget(hint)

        layout.addWidget(action_container)

    # ── Public API ────────────────────────────────────────────────────────────

    def add_verse(self, vm: VerseMatch):
        """Add a detected verse to the queue."""
        entry = QueueEntry(verse=vm)
        self._entries.append(entry)
        self._add_list_item(entry)
        self._update_count()
        logger.info("Queued verse: %s", entry.reference)

    def send_top_verse(self):
        """Hotkey: send the first queued verse."""
        if self._entries:
            self._send_entry(self._entries[0])

    def clear(self):
        self._entries.clear()
        self._list.clear()
        self._update_count()
        self._preview.clear_preview()
        self._edit_field.clear()
        self._edit_field.setEnabled(False)
        self._send_btn.setEnabled(False)
        self._remove_btn.setEnabled(False)

    def apply_settings(self, settings: AppSettings):
        self._settings = settings
        self._preview.apply_settings(settings)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _add_list_item(self, entry: QueueEntry):
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, entry)

        # Build display widget
        widget = _VerseItemWidget(entry)

        self._list.addItem(item)
        self._list.setItemWidget(item, widget)
        self._refresh_item_size(item, widget)
        self._list.scrollToBottom()

    def _refresh_item_size(self, item: QListWidgetItem, widget: "_VerseItemWidget"):
        widget_size = widget.sizeHint()
        item.setSizeHint(QSize(widget_size.width(), max(widget_size.height(), 84)))

    def _update_count(self):
        n = len(self._entries)
        self._count_label.setText(str(n))
        if n == 0:
            self._count_label.setStyleSheet(
                "background-color: #2d3142; color: #8892b0; border-radius: 9px; padding: 1px 7px; font-size: 11px;"
            )
        else:
            self._count_label.setStyleSheet(
                "background-color: #1a4f2a; color: #4ade80; border-radius: 9px; padding: 1px 7px; font-size: 11px;"
            )

    def _selected_entry(self) -> Optional[QueueEntry]:
        items = self._list.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    def _on_selection_changed(self):
        entry = self._selected_entry()
        if entry:
            self._edit_field.setEnabled(True)
            self._edit_field.setText(entry.reference)
            self._send_btn.setEnabled(True)
            self._remove_btn.setEnabled(True)
            self._preview.show_reference(entry.reference)
            self.verse_selected.emit(entry.reference)
        else:
            self._edit_field.setEnabled(False)
            self._send_btn.setEnabled(False)
            self._remove_btn.setEnabled(False)
            self._preview.clear_preview()

    def _on_edit_changed(self, text: str):
        entry = self._selected_entry()
        if entry:
            entry.reference = text
            # Refresh widget label
            row = self._list.currentRow()
            if 0 <= row < self._list.count():
                item = self._list.item(row)
                widget = self._list.itemWidget(item)
                if isinstance(widget, _VerseItemWidget):
                    widget.update_reference(text)
                    self._refresh_item_size(item, widget)
            self._preview.show_reference(text)

    def _on_send(self):
        entry = self._selected_entry()
        if entry:
            self._send_entry(entry)

    def _send_entry(self, entry: QueueEntry):
        ref = entry.reference.strip()
        if ref:
            logger.info("Sending to EasyWorship: %s", ref)
            self.send_requested.emit(ref)

    def _on_remove(self):
        items = self._list.selectedItems()
        if not items:
            return
        row = self._list.currentRow()
        entry = items[0].data(Qt.ItemDataRole.UserRole)
        self._entries.remove(entry)
        self._list.takeItem(row)
        self._update_count()
        self._edit_field.clear()
        self._edit_field.setEnabled(False)
        self._send_btn.setEnabled(False)
        self._remove_btn.setEnabled(False)


class _VerseItemWidget(QWidget):
    """Custom list item widget displaying book, reference, timestamp, confidence."""

    def __init__(self, entry: QueueEntry, parent=None):
        super().__init__(parent)
        self._entry = entry
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.setMinimumHeight(76)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        top = QHBoxLayout()
        self._ref_label = QLabel(entry.reference)
        self._ref_label.setStyleSheet("font-weight: bold; color: #fbbf24; font-size: 14px;")
        self._ref_label.setWordWrap(True)
        top.addWidget(self._ref_label)
        top.addStretch()

        pct = int(entry.confidence * 100)
        self._confidence_label = QLabel(f"{pct}%")
        confidence_fg = "#dcfce7" if pct >= 80 else "#fef3c7"
        confidence_bg = "rgba(34, 197, 94, 0.16)" if pct >= 80 else "rgba(245, 158, 11, 0.16)"
        confidence_border = "rgba(74, 222, 128, 0.24)" if pct >= 80 else "rgba(251, 191, 36, 0.24)"
        self._confidence_label.setStyleSheet(
            "font-size: 11px; font-weight: 700; "
            f"color: {confidence_fg}; "
            f"background-color: {confidence_bg}; "
            f"border: 1px solid {confidence_border}; "
            "border-radius: 10px; padding: 3px 10px;"
        )
        self._confidence_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._confidence_label.setMinimumSize(58, 24)
        top.addWidget(self._confidence_label, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        ts = entry.timestamp.strftime("%H:%M:%S")
        self._timestamp_label = QLabel(ts)
        self._timestamp_label.setStyleSheet(
            "color: #cbd5e1; font-size: 10px; font-weight: 600; "
            "background-color: rgba(148, 163, 184, 0.12); "
            "border: 1px solid rgba(148, 163, 184, 0.18); "
            "border-radius: 10px; padding: 3px 10px;"
        )
        self._timestamp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timestamp_label.setMinimumSize(76, 24)
        bottom.addWidget(self._timestamp_label, 0, Qt.AlignmentFlag.AlignTop)

        self._raw_label = QLabel(f'"{entry.verse.raw_text}"')
        self._raw_label.setStyleSheet("color: #4a5073; font-size: 10px; font-style: italic;")
        self._raw_label.setWordWrap(True)
        self._raw_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._raw_label.setToolTip(entry.verse.raw_text)
        bottom.addWidget(self._raw_label, 1)
        layout.addLayout(bottom)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(hint.width(), max(hint.height(), 84))

    def update_reference(self, text: str):
        self._ref_label.setText(text)


class _VersePreviewWidget(QFrame):
    def __init__(self, library: BiblePreviewLibrary, parent=None):
        super().__init__(parent)
        self._library = library
        self._settings: Optional[AppSettings] = None
        self._requested_edition = "KJV"
        self._current_reference = ""
        self.setObjectName("versePreviewCard")
        self._build_ui()
        self.clear_preview()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self._header_card = QFrame()
        self._header_card.setObjectName("previewHeaderCard")
        header_layout = QHBoxLayout(self._header_card)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(8)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)

        eyebrow = QLabel("VERSE PREVIEW")
        eyebrow.setObjectName("previewEyebrow")
        title_col.addWidget(eyebrow)

        self._reference_label = QLabel("No verse selected")
        self._reference_label.setObjectName("previewReference")
        self._reference_label.setWordWrap(True)
        title_col.addWidget(self._reference_label)
        header_layout.addLayout(title_col, 1)

        self._edition_label = QLabel("—")
        self._edition_label.setObjectName("previewEdition")
        self._edition_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self._edition_label, 0, Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self._header_card)

        self._body_card = QFrame()
        self._body_card.setObjectName("previewBodyCard")
        body_card_layout = QVBoxLayout(self._body_card)
        body_card_layout.setContentsMargins(12, 12, 12, 12)
        body_card_layout.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background: transparent;")

        scroll_body = QWidget()
        body_layout = QVBoxLayout(scroll_body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)

        self._body_label = QLabel()
        self._body_label.setObjectName("previewBody")
        self._body_label.setWordWrap(True)
        self._body_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._body_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body_layout.addWidget(self._body_label)

        self._note_label = QLabel()
        self._note_label.setObjectName("previewNote")
        self._note_label.setWordWrap(True)
        body_layout.addWidget(self._note_label)

        body_layout.addStretch()
        self._scroll.setWidget(scroll_body)
        body_card_layout.addWidget(self._scroll, 1)
        layout.addWidget(self._body_card, 1)

    def apply_settings(self, settings: AppSettings):
        self._settings = settings
        self._requested_edition = (
            settings.preview_translation.strip()
            or settings.ew_translation.strip()
            or "KJV"
        )
        max_height = max(140, min(500, settings.preview_max_height))
        self.setMaximumHeight(max_height)
        self.setMinimumHeight(min(180, max_height))
        self._apply_gradient_style(
            settings.preview_gradient_start,
            settings.preview_gradient_end,
        )
        self._refresh()

    def show_reference(self, reference: str):
        self._current_reference = reference.strip()
        if not self._current_reference:
            self.clear_preview()
            return
        preview = self._library.get_preview(self._current_reference, self._requested_edition)
        self._render_preview(preview)

    def clear_preview(self):
        self._current_reference = ""
        edition = self._requested_edition or "—"
        self._reference_label.setText("No verse selected")
        self._edition_label.setText(edition)
        self._body_label.setText("Select a verse from the queue to preview the local canon text here.")
        self._note_label.setText("Local preview")
        self._note_label.setStyleSheet("color: rgba(255, 255, 255, 0.72); font-size: 11px;")
        self._scroll.verticalScrollBar().setValue(0)

    def _refresh(self):
        if self._current_reference:
            self.show_reference(self._current_reference)
        else:
            self.clear_preview()

    def _render_preview(self, preview: BiblePreview):
        self._reference_label.setText(preview.reference)
        self._edition_label.setText(preview.edition)
        self._body_label.setText(preview.body)
        if preview.note:
            self._note_label.setText(preview.note)
        else:
            self._note_label.setText("Local canon preview")
        if preview.found:
            self._note_label.setStyleSheet("color: rgba(255, 255, 255, 0.72); font-size: 11px;")
        else:
            self._note_label.setStyleSheet("color: #fde68a; font-size: 11px;")
        self._scroll.verticalScrollBar().setValue(0)

    def _apply_gradient_style(self, start: str, end: str):
        start_color = self._valid_color(start, "#1d4ed8")
        end_color = self._valid_color(end, "#0f172a")
        self.setStyleSheet(
            f"""
            QFrame#versePreviewCard {{
                border: 1px solid rgba(148, 163, 184, 0.28);
                border-radius: 12px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 {start_color},
                    stop: 1 {end_color}
                );
            }}
            QFrame#previewHeaderCard {{
                background-color: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 12px;
            }}
            QFrame#previewBodyCard {{
                background-color: rgba(15, 23, 42, 0.18);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 14px;
            }}
            QLabel#previewEyebrow {{
                color: rgba(255, 255, 255, 0.72);
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QLabel#previewReference {{
                color: #ffffff;
                font-size: 18px;
                font-weight: 700;
            }}
            QLabel#previewEdition {{
                color: #eff6ff;
                background-color: rgba(15, 23, 42, 0.3);
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 10px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            }}
            QLabel#previewBody {{
                color: rgba(255, 255, 255, 0.96);
                font-size: 13px;
                line-height: 1.45;
            }}
            QLabel#previewNote {{
                color: rgba(255, 255, 255, 0.72);
                font-size: 11px;
            }}
            QScrollArea {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: rgba(15, 23, 42, 0.22);
                width: 10px;
                margin: 2px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 255, 255, 0.28);
                min-height: 24px;
                border-radius: 5px;
            }}
            """
        )

    def _valid_color(self, value: str, fallback: str) -> str:
        color = QColor(value.strip())
        return value.strip() if color.isValid() else fallback
