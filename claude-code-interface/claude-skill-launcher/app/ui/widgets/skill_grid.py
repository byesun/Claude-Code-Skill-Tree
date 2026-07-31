"""스킬 카드를 반응형 그리드로 배치한다.

너비에 따라 열 수를 1~3으로 조정한다(모바일 우선 사고를 데스크톱 창 폭에 적용).
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.models import Skill
from app.ui.widgets.skill_card import SkillCard

CARD_MIN_WIDTH = 260
CARD_MAX_WIDTH = 420
GRID_SPACING = 12


class SkillGrid(QScrollArea):
    skill_selected = pyqtSignal(object)
    skill_activated = pyqtSignal(object)
    favorite_toggled = pyqtSignal(object)
    context_requested = pyqtSignal(object, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._host = QWidget()
        self._host.setObjectName("GridHost")
        self._outer = QVBoxLayout(self._host)
        self._outer.setContentsMargins(16, 12, 12, 16)
        self._outer.setSpacing(12)

        self._grid = QGridLayout()
        self._grid.setSpacing(GRID_SPACING)
        self._outer.addLayout(self._grid)

        self._empty = QLabel()
        self._empty.setProperty("role", "muted")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.hide()
        self._outer.addWidget(self._empty)
        self._outer.addStretch(1)

        self.setWidget(self._host)

        self._cards: list[SkillCard] = []
        self._selected_key: str | None = None
        self._columns = 2

    # ------------------------------------------------------------------- public

    def set_skills(self, skills: list[Skill], counts: dict, favorites: set) -> None:
        self._clear()

        if not skills:
            self._empty.setText(
                "표시할 스킬이 없습니다.\n"
                "~/.claude/skills 또는 프로젝트의 .claude/skills 에 스킬을 추가해 보세요."
            )
            self._empty.show()
            return
        self._empty.hide()

        for skill in skills:
            card = SkillCard(skill, counts.get(skill.key, 0), skill.key in favorites)
            card.clicked.connect(self._on_card_clicked)
            card.activated.connect(self.skill_activated.emit)
            card.favorite_toggled.connect(self.favorite_toggled.emit)
            card.context_requested.connect(self.context_requested.emit)
            if skill.key == self._selected_key:
                card.set_selected(True)
            self._cards.append(card)

        self._relayout()

    def select_key(self, key: str | None) -> None:
        self._selected_key = key
        for card in self._cards:
            card.set_selected(card.skill.key == key)

    def focus_first_or_selected(self) -> None:
        """검색창에서 아래 화살표로 넘어올 때 호출 — 선택된 카드가 없으면
        첫 카드를 선택하고, 그리드로 키보드 포커스를 옮겨 화살표 키가 바로
        먹히게 한다."""
        if not self._cards:
            return
        index = self._current_index()
        if index is None:
            index = 0
        self._select_index(index)
        self.setFocus()

    # ------------------------------------------------------------------ private

    def _on_card_clicked(self, skill: Skill) -> None:
        self.select_key(skill.key)
        self.skill_selected.emit(skill)
        self.setFocus()

    def _current_index(self) -> int | None:
        for i, card in enumerate(self._cards):
            if card.skill.key == self._selected_key:
                return i
        return None

    def _select_index(self, index: int) -> None:
        if not self._cards:
            return
        index = max(0, min(len(self._cards) - 1, index))
        card = self._cards[index]
        self.select_key(card.skill.key)
        self.ensureWidgetVisible(card)
        self.skill_selected.emit(card.skill)

    def keyPressEvent(self, event) -> None:
        if not self._cards:
            super().keyPressEvent(event)
            return

        key = event.key()
        current = self._current_index()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if current is not None:
                self.skill_activated.emit(self._cards[current].skill)
            return

        step = None
        if key == Qt.Key.Key_Left:
            step = -1
        elif key == Qt.Key.Key_Right:
            step = 1
        elif key == Qt.Key.Key_Up:
            step = -self._columns
        elif key == Qt.Key.Key_Down:
            step = self._columns

        if step is None:
            super().keyPressEvent(event)
            return

        base = current if current is not None else 0
        self._select_index(base + step if current is not None else base)

    def _clear(self) -> None:
        for card in self._cards:
            self._grid.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards = []

    def _compute_layout(self) -> tuple[int, int]:
        """뷰포트 폭에서 열 수와, 모든 카드가 공유할 고정 카드 폭을 계산한다.

        카드 폭을 각 카드의 내용(뱃지 개수 등)에서 자동 유추하게 두면 열마다
        내용이 달라 폭이 서로 달라지는 문제가 있었다 — 항상 이 값으로
        setFixedWidth 해서 모든 카드/열의 폭을 강제로 맞춘다.
        """
        available = max(self.viewport().width() - 28, CARD_MIN_WIDTH)
        columns = max(1, min(3, available // CARD_MIN_WIDTH))
        card_width = (available - GRID_SPACING * (columns - 1)) // columns
        card_width = max(CARD_MIN_WIDTH, min(CARD_MAX_WIDTH, card_width))
        return columns, int(card_width)

    def _relayout(self) -> None:
        self._columns, card_width = self._compute_layout()
        align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        for index, card in enumerate(self._cards):
            card.setFixedWidth(card_width)
            row, col = divmod(index, self._columns)
            self._grid.addWidget(card, row, col, align)
        for col in range(self._columns):
            self._grid.setColumnStretch(col, 0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._cards:
            return
        columns, card_width = self._compute_layout()
        if columns != self._columns:
            for card in self._cards:
                self._grid.removeWidget(card)
            self._relayout()
        elif card_width != self._cards[0].width():
            for card in self._cards:
                card.setFixedWidth(card_width)
