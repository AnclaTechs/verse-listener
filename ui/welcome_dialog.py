"""
ui/welcome_dialog.py
First-run onboarding dialog for VerseListener.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.app_paths import resource_path


class LayeredHeroArt(QFrame):
    OUTER_RADIUS = 28
    INNER_RADIUS = 22

    def __init__(self, background: QPixmap | None, banner: QPixmap | None, parent=None):
        super().__init__(parent)
        self._background = background
        self._banner = banner
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet(
            "background: transparent;" f"border-radius: {self.OUTER_RADIUS}px;"
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        pixel_rect = self.rect().adjusted(4, 4, -4, -4)
        rect = QRectF(pixel_rect)
        clip = QPainterPath()
        clip.addRoundedRect(rect, self.OUTER_RADIUS, self.OUTER_RADIUS)
        painter.setClipPath(clip)

        painter.fillPath(clip, QColor("#0f172a"))

        if self._background and not self._background.isNull():
            bg = self._background.scaled(
                pixel_rect.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = rect.x() + (rect.width() - bg.width()) / 2
            y = rect.y() + (rect.height() - bg.height()) / 2
            painter.drawPixmap(int(x), int(y), bg)

        painter.fillRect(rect, QColor(7, 18, 34, 92))

        overlay_rect = rect.adjusted(26, 26, -26, -26)
        overlay = QPainterPath()
        overlay.addRoundedRect(overlay_rect, self.INNER_RADIUS, self.INNER_RADIUS)
        painter.fillPath(overlay, QColor(255, 255, 255, 65))
        painter.strokePath(overlay, QPen(QColor(255, 255, 255, 75), 1))

        if self._banner and not self._banner.isNull():
            banner_rect = overlay_rect.adjusted(20, 20, -20, -20)
            banner = self._banner.scaled(
                banner_rect.toRect().size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = banner_rect.x() + (banner_rect.width() - banner.width()) / 2
            y = banner_rect.y() + (banner_rect.height() - banner.height()) / 2
            painter.drawPixmap(int(x), int(y), banner)

        painter.setClipping(False)
        painter.setPen(QPen(QColor(148, 163, 184, 76), 1))
        painter.drawRoundedRect(rect, self.OUTER_RADIUS, self.OUTER_RADIUS)


class WelcomeDialog(QDialog):
    QUICK_SETUP = "quick_setup"
    INSTALL_OFFLINE = "install_offline"
    DEVELOPER_MODE = "developer_mode"
    SKIP = "skip"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.choice = self.SKIP
        self.setModal(True)
        self.setWindowTitle("Welcome to VerseListener")
        self.setMinimumSize(860, 560)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("welcomeHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 22, 22, 22)
        hero_layout.setSpacing(22)

        artwork = LayeredHeroArt(
            self._load_pixmap("worship.jpg"),
            self._load_pixmap("verseListener_banner.png"),
        )
        hero_layout.addWidget(artwork, 1)

        right = QVBoxLayout()
        right.setSpacing(12)
        right.setContentsMargins(8, 4, 8, 4)

        logo = QLabel()
        logo_pixmap = self._load_pixmap("verseListener_logo.png")
        if logo_pixmap and not logo_pixmap.isNull():
            logo.setPixmap(
                logo_pixmap.scaledToHeight(
                    48,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            logo.setText("VerseListener")
        logo.setStyleSheet("color: #bfdbfe;" "font-size: 18px;" "font-weight: 700;")
        right.addWidget(logo, 0, Qt.AlignmentFlag.AlignLeft)

        title = QLabel("Welcome to VerseListener")
        title.setWordWrap(True)
        title.setStyleSheet(
            "background: rgba(255, 255, 255, 0.06);"
            "border-radius: 18px;"
            "padding: 14px 18px;"
            "font-size: 32px;"
            "font-weight: 700;"
            "color: white;"
        )
        right.addWidget(title)

        subtitle = QLabel("Smart Scripture presentation assistant.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            "background: rgba(59, 130, 246, 0.12);"
            "border: 1px solid rgba(147, 197, 253, 0.16);"
            "border-radius: 16px;"
            "padding: 10px 16px;"
            "font-size: 18px;"
            "font-weight: 600;"
            "color: #bfdbfe;"
        )
        right.addWidget(subtitle)

        body = QLabel(
            "VerseListener listens to your sermon in real time, identifies Bible verses as "
            "they're spoken — then sends them directly to any "
            "presentation software your media team already uses.\n\n"
            "No new workflow. No disruption. Just improved output."
        )
        body.setWordWrap(True)
        body.setStyleSheet(
            "background: rgba(15, 23, 42, 0.32);"
            "border: 1px solid rgba(148, 163, 184, 0.12);"
            "border-radius: 18px;"
            "padding: 18px;"
            "font-size: 14px;"
            "color: rgba(255, 255, 255, 0.88);"
            "line-height: 1.72;"
        )
        right.addWidget(body)
        right.addStretch()

        hero_layout.addLayout(right, 1)
        root.addWidget(hero)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        cards.addWidget(
            self._action_card(
                "Quick Setup",
                "Use OpenAI Realtime as your default engine and add your API key (requires Internet access).",
                "Lean start",
                lambda: self._choose(self.QUICK_SETUP),
                primary=True,
            )
        )
        cards.addWidget(
            self._action_card(
                "Install Offline",
                "Open add-ons manager and browse Vosk, faster-whisper, and semantic matching.",
                "Offline-ready",
                lambda: self._choose(self.INSTALL_OFFLINE),
            )
        )
        cards.addWidget(
            self._action_card(
                "Developer Mode",
                "Keep the advanced knobs visible and start with a more hands-on setup path.",
                "Advanced",
                lambda: self._choose(self.DEVELOPER_MODE),
            )
        )
        root.addLayout(cards)

        footer = QHBoxLayout()
        footer.addStretch()

        skip = QPushButton("Skip for now")
        skip.clicked.connect(lambda: self._choose(self.SKIP))
        footer.addWidget(skip)

        root.addLayout(footer)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #0f172a;
            }
            QFrame#welcomeHero {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #1d4ed8,
                    stop: 0.55 #0f766e,
                    stop: 1 #0f172a
                );
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 20px;
            }
            """
        )

    def _action_card(
        self,
        title: str,
        description: str,
        badge: str,
        callback,
        *,
        primary: bool = False,
    ) -> QWidget:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #111827; border: 1px solid #243041; border-radius: 16px; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        badge_label = QLabel(badge)
        badge_label.setStyleSheet(
            "background: rgba(59, 130, 246, 0.14); color: #93c5fd; border-radius: 11px; padding: 4px 10px;"
        )
        layout.addWidget(badge_label, 0, Qt.AlignmentFlag.AlignLeft)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #f8fafc; border: none;"
        )
        layout.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setStyleSheet(
            "background: rgba(255, 255, 255, 0.04);"
            "border-radius: 12px;"
            "padding: 12px 14px;"
            "color: #cbd5e1;"
            "line-height: 1.6;"
        )
        layout.addWidget(description_label, 1)

        button = QPushButton(title)
        if primary:
            button.setStyleSheet(
                "QPushButton { background: #2563eb; border: 1px solid #3b82f6; color: white; border-radius: 10px; padding: 10px 18px; }"
                "QPushButton:hover { background: #3b82f6; }"
            )
        button.clicked.connect(callback)
        layout.addWidget(button)
        return card

    def _load_pixmap(self, name: str) -> QPixmap | None:
        candidate = resource_path("assets", name)
        if not candidate.is_file():
            return None
        pixmap = QPixmap(str(candidate))
        if pixmap.isNull():
            return None
        return pixmap

    def _choose(self, choice: str):
        self.choice = choice
        self.accept()
