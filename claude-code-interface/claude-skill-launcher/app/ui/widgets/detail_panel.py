"""우측 상세 패널. 선택된 스킬 정보 + 추가 지시문 입력 + 실행 버튼."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models import Skill


class DetailPanel(QFrame):
    run_requested = pyqtSignal(object, str)  # Skill, user_input
    input_changed = pyqtSignal(str)
    open_file_requested = pyqtSignal(object)
    open_folder_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DetailPanel")
        self.setFixedWidth(320)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        self._name = QLabel("스킬을 선택하세요")
        self._name.setProperty("role", "title")
        self._name.setWordWrap(True)
        root.addWidget(self._name)

        self._meta = QLabel("")
        self._meta.setProperty("role", "muted")
        root.addWidget(self._meta)

        root.addWidget(self._divider())

        self._desc = QLabel("")
        self._desc.setProperty("role", "muted")
        self._desc.setWordWrap(True)
        root.addWidget(self._desc)

        self._tools_label = QLabel("allowed-tools")
        self._tools_label.setProperty("role", "muted")
        self._tools_label.hide()
        root.addWidget(self._tools_label)

        self._tools_host = QWidget()
        self._tools_layout = QHBoxLayout(self._tools_host)
        self._tools_layout.setContentsMargins(0, 0, 0, 0)
        self._tools_layout.setSpacing(4)
        root.addWidget(self._tools_host)

        self._path = QLabel("")
        self._path.setProperty("role", "mono")
        self._path.setWordWrap(True)
        root.addWidget(self._path)

        root.addStretch(1)
        root.addWidget(self._divider())

        input_label = QLabel("추가 지시문 (선택)")
        input_label.setProperty("role", "muted")
        root.addWidget(input_label)

        self._input = QLineEdit()
        self._input.setPlaceholderText("예: 이 폴더의 PDF 를 표로 정리해줘")
        self._input.textChanged.connect(self.input_changed.emit)
        self._input.returnPressed.connect(self._emit_run)
        root.addWidget(self._input)

        preview_label = QLabel("전송될 명령")
        preview_label.setProperty("role", "muted")
        root.addWidget(preview_label)

        self._preview = QLabel("-")
        self._preview.setProperty("role", "mono")
        self._preview.setWordWrap(True)
        self._preview.setMinimumHeight(36)
        root.addWidget(self._preview)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        self._open_md = QPushButton("SKILL.md")
        self._open_md.setEnabled(False)
        self._open_md.clicked.connect(
            lambda: self._skill and self.open_file_requested.emit(self._skill)
        )
        buttons.addWidget(self._open_md)

        self._run = QPushButton("실행")
        self._run.setProperty("variant", "primary")
        self._run.setEnabled(False)
        self._run.clicked.connect(self._emit_run)
        buttons.addWidget(self._run, 1)
        root.addLayout(buttons)

        self._skill: Skill | None = None

    # ------------------------------------------------------------------- public

    def set_skill(self, skill: Skill | None, use_count: int = 0, last_input: str = "") -> None:
        self._skill = skill
        self._clear_tools()

        if skill is None:
            self._name.setText("스킬을 선택하세요")
            self._meta.setText("")
            self._desc.setText("")
            self._path.setText("")
            self._tools_label.hide()
            self._run.setEnabled(False)
            self._open_md.setEnabled(False)
            self._preview.setText("-")
            return

        self._name.setText(skill.name)
        parts = [skill.source.label]
        if use_count:
            parts.append(f"{use_count}회 사용")
        if skill.shadowed_by:
            parts.append(f"{skill.shadowed_by.label} 버전 가림")
        self._meta.setText(" · ".join(parts))

        self._desc.setText(skill.description or skill.body_preview or "설명 없음")
        self._path.setText(str(skill.path))

        if skill.allowed_tools:
            self._tools_label.show()
            for tool in skill.allowed_tools[:8]:
                badge = QLabel(tool)
                badge.setProperty("role", "badge")
                self._tools_layout.addWidget(badge)
            self._tools_layout.addStretch(1)
        else:
            self._tools_label.hide()

        self._input.setText(last_input)
        self._run.setEnabled(True)
        self._open_md.setEnabled(True)

    def set_preview(self, text: str) -> None:
        self._preview.setText(text or "-")

    def set_run_enabled(self, enabled: bool) -> None:
        self._run.setEnabled(enabled and self._skill is not None)

    def user_input(self) -> str:
        return self._input.text()

    def focus_input(self) -> None:
        self._input.setFocus()

    # ------------------------------------------------------------------ private

    def _emit_run(self) -> None:
        if self._skill is not None and self._run.isEnabled():
            self.run_requested.emit(self._skill, self._input.text())

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setObjectName("Divider")
        line.setFrameShape(QFrame.Shape.HLine)
        return line

    def _clear_tools(self) -> None:
        while self._tools_layout.count():
            item = self._tools_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
