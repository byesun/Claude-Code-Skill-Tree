"""설정 다이얼로그 (DESIGN.md 9절). Settings 를 직접 읽고 쓴다."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config import DEFAULT_TEMPLATE, Settings
from app.core.usage_store import UsageStore
from app.models import InjectStrategy

STRATEGY_LABELS = {
    InjectStrategy.PASTE: "붙여넣기 (권장, 유니코드/긴 문장 안전)",
    InjectStrategy.TYPE: "직접 타이핑 (클립보드 미사용, 느림)",
    InjectStrategy.WM_CHAR: "WM_CHAR (레거시 conhost 전용)",
}

SORT_LABELS = {
    "favorite": "즐겨찾기 우선 (기본)",
    "count": "사용 횟수",
    "recent": "최근 사용",
    "name": "이름",
}

THEME_LABELS = {
    "dark": "다크 (기본)",
    "light": "라이트",
}


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, usage: UsageStore, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.usage = usage
        self.setWindowTitle("설정")
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)
        root.addLayout(form)

        self._strategy = QComboBox()
        for strategy, label in STRATEGY_LABELS.items():
            self._strategy.addItem(label, strategy)
        self._strategy.setCurrentIndex(self._strategy.findData(settings.strategy))
        form.addRow("입력 방식", self._strategy)

        self._send_enter = QCheckBox("전송 후 Enter 자동 입력")
        self._send_enter.setChecked(settings.send_enter)
        form.addRow("", self._send_enter)

        self._restore_clipboard = QCheckBox("붙여넣기 후 원래 클립보드 복원")
        self._restore_clipboard.setChecked(settings.restore_clipboard)
        form.addRow("", self._restore_clipboard)

        self._focus_delay = QSpinBox()
        self._focus_delay.setRange(0, 2000)
        self._focus_delay.setSingleStep(10)
        self._focus_delay.setSuffix(" ms")
        self._focus_delay.setValue(settings.focus_delay_ms)
        form.addRow("포커스 후 대기", self._focus_delay)

        self._template = QLineEdit(settings.default_template)
        self._template.setPlaceholderText(DEFAULT_TEMPLATE)
        self._template.setToolTip(
            "{{invocation}} = /plugin:skill 형태의 슬래시 커맨드, "
            "{{name}} = 스킬 이름, {{input}} = 추가 지시문"
        )
        form.addRow("기본 명령 템플릿", self._template)

        self._sort_mode = QComboBox()
        for key, label in SORT_LABELS.items():
            self._sort_mode.addItem(label, key)
        self._sort_mode.setCurrentIndex(self._sort_mode.findData(settings.sort_mode))
        form.addRow("정렬 기준", self._sort_mode)

        self._theme = QComboBox()
        for key, label in THEME_LABELS.items():
            self._theme.addItem(label, key)
        self._theme.setCurrentIndex(self._theme.findData(settings.theme))
        form.addRow("테마", self._theme)

        self._always_on_top = QCheckBox("창을 항상 위에 표시")
        self._always_on_top.setChecked(settings.always_on_top)
        form.addRow("", self._always_on_top)

        self._hotkey_enabled = QCheckBox(f"전역 핫키 사용 ({settings.hotkey_label})")
        self._hotkey_enabled.setChecked(settings.hotkey_enabled)
        form.addRow("", self._hotkey_enabled)

        root.addWidget(QLabel("추가 스킬 폴더"))
        self._roots_list = QListWidget()
        for path in settings.extra_roots:
            self._roots_list.addItem(str(path))
        root.addWidget(self._roots_list)

        roots_buttons = QHBoxLayout()
        add_btn = QPushButton("폴더 추가")
        add_btn.clicked.connect(self._add_root)
        remove_btn = QPushButton("선택 제거")
        remove_btn.clicked.connect(self._remove_selected_root)
        roots_buttons.addWidget(add_btn)
        roots_buttons.addWidget(remove_btn)
        roots_buttons.addStretch(1)
        root.addLayout(roots_buttons)

        reset_row = QHBoxLayout()
        reset_usage_btn = QPushButton("사용 기록 초기화")
        reset_usage_btn.setToolTip("사용 횟수·최근 사용·추가 지시문 히스토리를 모두 지웁니다 (즐겨찾기는 유지)")
        reset_usage_btn.clicked.connect(self._reset_usage)
        reset_row.addWidget(reset_usage_btn)
        reset_row.addStretch(1)
        root.addLayout(reset_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ------------------------------------------------------------------- private

    def _add_root(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "추가 스킬 폴더 선택", str(Path.home()))
        if folder:
            self._roots_list.addItem(folder)

    def _remove_selected_root(self) -> None:
        for item in self._roots_list.selectedItems():
            self._roots_list.takeItem(self._roots_list.row(item))

    def _reset_usage(self) -> None:
        confirm = QMessageBox.question(
            self,
            "사용 기록 초기화",
            "사용 횟수, 최근 사용, 추가 지시문 히스토리를 모두 지웁니다.\n"
            "즐겨찾기는 유지됩니다. 계속할까요?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.usage.reset_all()
        QMessageBox.information(self, "사용 기록 초기화", "초기화했습니다.")

    # -------------------------------------------------------------------- public

    def apply(self) -> None:
        """OK 로 닫혔을 때 호출: 폼 값을 Settings 에 반영한다."""
        s = self.settings
        s.strategy = self._strategy.currentData()
        s.send_enter = self._send_enter.isChecked()
        s.restore_clipboard = self._restore_clipboard.isChecked()
        s.focus_delay_ms = self._focus_delay.value()
        s.default_template = self._template.text()
        s.sort_mode = self._sort_mode.currentData()
        s.theme = self._theme.currentData()
        s.always_on_top = self._always_on_top.isChecked()
        s.hotkey_enabled = self._hotkey_enabled.isChecked()
        s.extra_roots = [
            Path(self._roots_list.item(i).text()) for i in range(self._roots_list.count())
        ]
