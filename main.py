#!/usr/bin/env python3
"""
VerseListener - Real-time Bible verse detection and EasyWorship integration
Entry point for the application.
"""

import sys
import os
import logging

# Load .env before app imports so settings/env-backed integrations can see it.
try:
    from dotenv import load_dotenv
    from core.app_paths import find_config_file

    env_path = find_config_file(".env")
    if env_path:
        load_dotenv(env_path)
    else:
        load_dotenv()
except Exception:
    pass

# Configure logging before any imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.expanduser("~/.verse_listener.log")),
    ],
)

logger = logging.getLogger("VerseListener")
import PyQt6

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow


def main():
    logger.info("Starting VerseListener")
    app = QApplication(sys.argv)
    app.setApplicationName("VerseListener")
    app.setOrganizationName("Church Tools")
    app.setApplicationVersion("1.0.0")

    # High DPI support
    if hasattr(Qt.ApplicationAttribute, "AA_UseHighDpiPixmaps"):
        app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    window = MainWindow()
    window.show()

    logger.info("Application started successfully")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
