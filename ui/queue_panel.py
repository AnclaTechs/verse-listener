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
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QColor

from core.bible_detector import VerseMatch

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("queuePanel")
        self._entries: list[QueueEntry] = []
        self._build_ui()

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
        self._edit_field.clear()
        self._edit_field.setEnabled(False)
        self._send_btn.setEnabled(False)
        self._remove_btn.setEnabled(False)

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
            self.verse_selected.emit(entry.reference)
        else:
            self._edit_field.setEnabled(False)
            self._send_btn.setEnabled(False)
            self._remove_btn.setEnabled(False)

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
        conf_label = QLabel(f"{pct}%")
        conf_label.setStyleSheet(
            f"color: {'#4ade80' if pct >= 80 else '#fbbf24'}; font-size: 11px;"
        )
        conf_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        top.addWidget(conf_label)
        layout.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        ts = entry.timestamp.strftime("%H:%M:%S")
        ts_label = QLabel(ts)
        ts_label.setStyleSheet("color: #4a5073; font-size: 10px;")
        ts_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        bottom.addWidget(ts_label)

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
