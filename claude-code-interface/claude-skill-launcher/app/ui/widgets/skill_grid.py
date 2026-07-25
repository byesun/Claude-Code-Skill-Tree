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


class SkillGrid(QScrollArea):
    skill_selected = pyqtSignal(object)
    skill_activated = pyqtSignal(object)
    favorite_toggled = pyqtSignal(object)
    context_requested = pyqtSignal(object, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._host = QWidget()
        self._host.setObjectName("GridHost")
        self._outer = QVBoxLayout(self._host)
        self._outer.setContentsMargins(16, 12, 12, 16)
        self._outer.setSpacing(12)

        self._grid = QGridLayout()
        self._grid.setSpacing(12)
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

    # ------------------------------------------------------------------ private

    def _on_card_clicked(self, skill: Skill) -> None:
        self.select_key(skill.key)
        self.skill_selected.emit(skill)

    def _clear(self) -> None:
        for card in self._cards:
            self._grid.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._cards = []

    def _relayout(self) -> None:
        align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        for index, card in enumerate(self._cards):
            row, col = divmod(index, self._columns)
            self._grid.addWidget(card, row, col, align)
        for col in range(self._columns):
            self._grid.setColumnStretch(col, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        available = max(self.viewport().width() - 28, CARD_MIN_WIDTH)
        columns = max(1, min(3, available // CARD_MIN_WIDTH))
        if columns != self._columns and self._cards:
            self._columns = columns
            for card in self._cards:
                self._grid.removeWidget(card)
            self._relayout()
        else:
            self._columns = columns
