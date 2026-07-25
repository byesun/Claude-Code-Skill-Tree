"""우하단 토스트 알림. 부모 위젯 내부에 떠 있는 프레임."""

from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

MARGIN = 16


class Toast(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setProperty("tone", "success")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(360)
        layout.addWidget(self._label)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, tone: str = "success", duration_ms: int = 3000) -> None:
        self._label.setText(text)
        self.setProperty("tone", tone)
        self.style().unpolish(self)
        self.style().polish(self)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._timer.start(duration_ms)

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        x = parent.width() - self.width() - MARGIN
        y = parent.height() - self.height() - MARGIN - 28  # 상태바 위
        self.move(max(MARGIN, x), max(MARGIN, y))

    def parent_resized(self) -> None:
        if self.isVisible():
            self._reposition()
