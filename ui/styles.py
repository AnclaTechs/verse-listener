"""
ui/styles.py
Theme stylesheets for VerseListener – dark (default) and light.
Designed to be church-presentation-friendly: calm, clean, minimal.
"""

DARK_STYLESHEET = """
/* ── Global ──────────────────────────────────────────────────── */
* {
    font-family: 'Segoe UI', 'Ubuntu', 'Helvetica Neue', sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #1a1d23;
    color: #e8eaf0;
}

QWidget {
    background-color: #1a1d23;
    color: #e8eaf0;
}

/* ── Toolbar ─────────────────────────────────────────────────── */
QToolBar {
    background-color: #12141a;
    border-bottom: 1px solid #2d3142;
    spacing: 6px;
    padding: 4px 8px;
}

QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 5px 10px;
    color: #c0c4d6;
}

QToolButton:hover {
    background-color: #2d3142;
    border-color: #4a5073;
    color: #ffffff;
}

QToolButton:pressed {
    background-color: #3d4466;
}

QToolButton:checked {
    background-color: #2563eb;
    border-color: #3b82f6;
    color: #ffffff;
}

/* ── Status bar ──────────────────────────────────────────────── */
QStatusBar {
    background-color: #12141a;
    border-top: 1px solid #2d3142;
    color: #8892b0;
    font-size: 11px;
}

QStatusBar::item {
    border: none;
}

QLabel#statusLabel {
    color: #8892b0;
    padding: 0 6px;
}

/* ── Panels / Frames ─────────────────────────────────────────── */
QFrame#transcriptPanel, QFrame#queuePanel {
    background-color: #1e2130;
    border: 1px solid #2d3142;
    border-radius: 8px;
}

QLabel.panelTitle {
    color: #64748b;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 8px 12px 4px 12px;
}

/* ── Transcript text area ────────────────────────────────────── */
QTextEdit#transcriptArea {
    background-color: #161924;
    color: #d4d8e8;
    border: none;
    border-radius: 6px;
    padding: 12px;
    line-height: 1.6;
    selection-background-color: #2563eb;
}

QTextEdit#transcriptArea:focus {
    outline: none;
}

/* ── Queue list ──────────────────────────────────────────────── */
QListWidget#queueList {
    background-color: #161924;
    border: none;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}

QListWidget#queueList::item {
    background-color: #1e2130;
    border: 1px solid #2a2f45;
    border-radius: 6px;
    padding: 8px 10px;
    margin: 3px 2px;
    color: #d4d8e8;
}

QListWidget#queueList::item:hover {
    background-color: #252b44;
    border-color: #3d4466;
}

QListWidget#queueList::item:selected {
    background-color: #1d3a6e;
    border-color: #2563eb;
    color: #ffffff;
}

/* ── Buttons ─────────────────────────────────────────────────── */
QPushButton {
    background-color: #2d3142;
    border: 1px solid #3d4466;
    border-radius: 5px;
    color: #c0c4d6;
    padding: 6px 16px;
    min-height: 28px;
}

QPushButton:hover {
    background-color: #3d4466;
    border-color: #5a6490;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #1d2035;
}

QPushButton#sendBtn {
    background-color: #1a4f2a;
    border-color: #2d7a42;
    color: #4ade80;
    font-weight: bold;
}

QPushButton#sendBtn:hover {
    background-color: #1f6033;
    border-color: #4ade80;
    color: #86efac;
}

QPushButton#sendBtn:disabled {
    background-color: #1a1d23;
    border-color: #2d3142;
    color: #4a5073;
}

QPushButton#removeBtn {
    background-color: #3a1a1a;
    border-color: #6b2a2a;
    color: #f87171;
}

QPushButton#removeBtn:hover {
    background-color: #4a2020;
    border-color: #f87171;
}

/* ── Splitter ─────────────────────────────────────────────────── */
QSplitter::handle {
    background-color: #2d3142;
    width: 2px;
    height: 2px;
}

QSplitter::handle:hover {
    background-color: #2563eb;
}

/* ── Scroll bars ──────────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #1a1d23;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background-color: #3d4466;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #5a6490;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background-color: #1a1d23;
    height: 8px;
}
QScrollBar::handle:horizontal {
    background-color: #3d4466;
    border-radius: 4px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Dialogs ─────────────────────────────────────────────────── */
QDialog {
    background-color: #1a1d23;
}

QTabWidget::pane {
    border: 1px solid #2d3142;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #12141a;
    border: 1px solid #2d3142;
    border-bottom: none;
    color: #8892b0;
    padding: 6px 16px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}

QTabBar::tab:selected {
    background-color: #1e2130;
    color: #e8eaf0;
    border-color: #2d3142;
}

QTabBar::tab:hover:!selected {
    background-color: #1a1d23;
    color: #c0c4d6;
}

QGroupBox {
    border: 1px solid #2d3142;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    color: #8892b0;
    font-size: 11px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #12141a;
    border: 1px solid #2d3142;
    border-radius: 4px;
    color: #e8eaf0;
    padding: 4px 8px;
    min-height: 24px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #2563eb;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8892b0;
    width: 0;
    height: 0;
}

QComboBox QAbstractItemView {
    background-color: #1e2130;
    border: 1px solid #2d3142;
    selection-background-color: #2563eb;
    color: #e8eaf0;
}

QCheckBox {
    color: #c0c4d6;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3d4466;
    border-radius: 3px;
    background-color: #12141a;
}

QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}

QLabel {
    color: #c0c4d6;
}

/* ── Verse highlight format (applied programmatically) ────────── */
/* highlight color: #fbbf24 on #1a1d23 */
"""


LIGHT_STYLESHEET = """
* {
    font-family: 'Segoe UI', 'Ubuntu', 'Helvetica Neue', sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog, QWidget {
    background-color: #f8f9fb;
    color: #1a1d23;
}

QToolBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e5ef;
    spacing: 6px;
    padding: 4px 8px;
}

QToolButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 5px 10px;
    color: #4a5073;
}

QToolButton:hover {
    background-color: #eef1f8;
    border-color: #c5cae2;
}

QToolButton:checked {
    background-color: #2563eb;
    color: #ffffff;
}

QStatusBar {
    background-color: #ffffff;
    border-top: 1px solid #e2e5ef;
    color: #8892b0;
    font-size: 11px;
}

QFrame#transcriptPanel, QFrame#queuePanel {
    background-color: #ffffff;
    border: 1px solid #e2e5ef;
    border-radius: 8px;
}

QTextEdit#transcriptArea {
    background-color: #fdfeff;
    color: #1a1d23;
    border: none;
    padding: 12px;
}

QListWidget#queueList {
    background-color: #fdfeff;
    border: none;
    padding: 4px;
}

QListWidget#queueList::item {
    background-color: #ffffff;
    border: 1px solid #e2e5ef;
    border-radius: 6px;
    padding: 8px 10px;
    margin: 3px 2px;
}

QListWidget#queueList::item:hover { background-color: #eef1f8; }
QListWidget#queueList::item:selected { background-color: #dbeafe; border-color: #2563eb; }

QPushButton {
    background-color: #eef1f8;
    border: 1px solid #c5cae2;
    border-radius: 5px;
    color: #1a1d23;
    padding: 6px 16px;
}

QPushButton:hover { background-color: #dde3f5; }

QPushButton#sendBtn {
    background-color: #dcfce7;
    border-color: #86efac;
    color: #15803d;
    font-weight: bold;
}

QPushButton#sendBtn:hover { background-color: #bbf7d0; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    border: 1px solid #c5cae2;
    border-radius: 4px;
    color: #1a1d23;
    padding: 4px 8px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #2563eb; }
"""


def get_stylesheet(theme: str) -> str:
    return DARK_STYLESHEET if theme == "dark" else LIGHT_STYLESHEET
