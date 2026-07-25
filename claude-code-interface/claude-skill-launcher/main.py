"""Claude Skill Launcher 엔트리포인트.

실행: python main.py
빌드: pyinstaller launcher.spec
"""

from __future__ import annotations

import sys
import traceback

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from app.config import APP_NAME, ORG_NAME, log
from app.controller import AppController
from app.ui.main_window import MainWindow


def _install_excepthook(window: MainWindow) -> None:
    """어떤 예외도 앱을 죽이지 않는다. 로그 + 토스트로 전환."""

    def hook(exc_type, exc_value, exc_tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.error("처리되지 않은 예외:\n%s", text)
        try:
            window.toast.show_message(
                f"오류가 발생했습니다: {exc_value}", "error", 6000
            )
        except Exception:
            pass

    sys.excepthook = hook


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)

    controller = AppController()
    window = MainWindow(controller)
    _install_excepthook(window)

    window.show()
    controller.start()

    log.info("애플리케이션 시작")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
