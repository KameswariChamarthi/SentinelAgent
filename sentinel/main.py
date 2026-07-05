"""
main.py

Sentinel entry point. Initializes the local database, checks for admin
elevation (only requesting it if the user opts in via settings/dialog --
never silently), and launches the PySide6 GUI.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from models.database import init_db
from utils.logger import get_text_logger

log = get_text_logger("main")


def main() -> int:
    init_db()
    app = QApplication(sys.argv)
    app.setApplicationName("Sentinel")

    from gui.main_window import MainWindow

    window = MainWindow()
    window.show()
    log.info("Sentinel GUI started.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
