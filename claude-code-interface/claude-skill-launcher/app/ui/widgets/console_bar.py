"""상단 콘솔 선택 바. 감지된 CMD 창 목록 + claude 실행 표시 + 새로고침."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from app.models import ConsoleTarget

DOT = "\u25CF"  # ●


class ConsoleBar(QFrame):
    console_chosen = pyqtSignal(object)  # ConsoleTarget | None
    refresh_requested = pyqtSignal()
    open_console_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConsoleBar")
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        label = QLabel("콘솔")
        label.setProperty("role", "muted")
        layout.addWidget(label)

        self._combo = QComboBox()
        self._combo.setMinimumWidth(460)
        self._combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._combo.currentIndexChanged.connect(self._on_index_changed)
        layout.addWidget(self._combo, 1)

        self._dot = QLabel(DOT)
        self._dot.setProperty("role", "dot")
        self._dot.setProperty("state", "off")
        self._dot.setToolTip("claude 실행 여부")
        layout.addWidget(self._dot)

        self._state = QLabel("claude 미실행")
        self._state.setProperty("role", "muted")
        self._state.setMinimumWidth(88)
        layout.addWidget(self._state)

        refresh = QPushButton("새로고침")
        refresh.setToolTip("콘솔 및 스킬 다시 스캔 (Ctrl+R)")
        refresh.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(refresh)

        new_console = QPushButton("CMD 열기")
        new_console.setToolTip("폴더를 선택해 새 CMD 창에서 claude 실행")
        new_console.clicked.connect(self.open_console_requested.emit)
        layout.addWidget(new_console)

        gear = QPushButton("설정")
        gear.clicked.connect(self.settings_requested.emit)
        layout.addWidget(gear)

        self._targets: list[ConsoleTarget] = []
        self._suppress = False

    # ------------------------------------------------------------------- public

    def set_targets(self, targets: list[ConsoleTarget], active_hwnd: int | None) -> None:
        self._suppress = True
        self._targets = targets
        self._combo.clear()

        if not targets:
            self._combo.addItem("감지된 콘솔 창이 없습니다")
            self._combo.setEnabled(False)
        else:
            self._combo.setEnabled(True)
            for i, target in enumerate(targets):
                mark = "claude" if target.claude_running else "     "
                self._combo.addItem(f"[{mark}] {target.display_name}")
                self._combo.setItemData(i, target.full_description, Qt.ItemDataRole.ToolTipRole)
            index = next(
                (i for i, t in enumerate(targets) if t.hwnd == active_hwnd), 0
            )
            self._combo.setCurrentIndex(index)

        self._suppress = False
        self._sync_state()

    def set_active(self, target: ConsoleTarget | None) -> None:
        if target is None:
            self._apply_state(False)
            return
        index = next(
            (i for i, t in enumerate(self._targets) if t.hwnd == target.hwnd), None
        )
        if index is not None and index != self._combo.currentIndex():
            self._suppress = True
            self._combo.setCurrentIndex(index)
            self._suppress = False
        self._apply_state(target.claude_running)

    def current_target(self) -> ConsoleTarget | None:
        index = self._combo.currentIndex()
        if 0 <= index < len(self._targets):
            return self._targets[index]
        return None

    # ------------------------------------------------------------------ private

    def _on_index_changed(self, _index: int) -> None:
        if self._suppress:
            return
        self.console_chosen.emit(self.current_target())
        self._sync_state()

    def _sync_state(self) -> None:
        target = self.current_target()
        self._apply_state(bool(target and target.claude_running))

    def _apply_state(self, running: bool) -> None:
        self._dot.setProperty("state", "on" if running else "off")
        self._dot.style().unpolish(self._dot)
        self._dot.style().polish(self._dot)
        self._state.setText("claude 실행 중" if running else "claude 미실행")
