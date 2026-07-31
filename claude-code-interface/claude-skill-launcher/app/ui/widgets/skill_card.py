"""스킬 하나를 표현하는 카드. 1클릭=선택, 더블클릭=실행."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from app.models import Skill

DESC_CHAR_LIMIT = 96
CARD_FIXED_HEIGHT = 150
DESC_FIXED_HEIGHT = 54  # 3줄 분량. 카드 높이를 내용과 무관하게 고정하기 위함.


def _truncate(text: str, limit: int = DESC_CHAR_LIMIT) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."

STAR_ON = "\u2605"  # ★
STAR_OFF = "\u2606"  # ☆


class SkillCard(QFrame):
    clicked = pyqtSignal(object)  # Skill
    activated = pyqtSignal(object)  # Skill (더블클릭 / Enter)
    favorite_toggled = pyqtSignal(object)  # Skill
    context_requested = pyqtSignal(object, object)  # Skill, QPoint

    def __init__(self, skill: Skill, use_count: int, is_favorite: bool, parent=None):
        super().__init__(parent)
        self.skill = skill
        self.setObjectName("SkillCard")
        self.setProperty("selected", "false")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(CARD_FIXED_HEIGHT)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.context_requested.emit(self.skill, self.mapToGlobal(pos))
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 12, 12)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel(skill.name)
        title.setProperty("role", "title")
        header.addWidget(title, 1)

        self._star = QPushButton(STAR_ON if is_favorite else STAR_OFF)
        self._star.setProperty("variant", "ghost")
        self._star.setFixedSize(28, 24)
        self._star.setToolTip("즐겨찾기")
        self._star.clicked.connect(lambda: self.favorite_toggled.emit(self.skill))
        header.addWidget(self._star, 0)
        root.addLayout(header)

        desc = QLabel(_truncate(skill.description) or "설명 없음")
        desc.setProperty("role", "muted")
        desc.setWordWrap(True)
        desc.setFixedHeight(DESC_FIXED_HEIGHT)
        desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        desc.setToolTip(skill.description or "설명 없음")
        root.addWidget(desc)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        footer.addWidget(self._badge(skill.source.label, tone="accent"))
        if skill.source.value == "plugin" and skill.user_added:
            footer.addWidget(self._badge("내가 추가함"))
        if use_count:
            footer.addWidget(self._badge(f"{use_count}회"))
        if skill.has_scripts:
            footer.addWidget(self._badge("scripts"))
        if skill.parse_warning:
            footer.addWidget(self._badge("메타 경고"))
        footer.addStretch(1)
        root.addLayout(footer)

    def _badge(self, text: str, tone: str = "") -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "badge")
        if tone:
            label.setProperty("tone", tone)
        return label

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        # 동적 프로퍼티 변경은 스타일 재적용이 필요하다
        self.style().unpolish(self)
        self.style().polish(self)

    def set_favorite(self, is_favorite: bool) -> None:
        self._star.setText(STAR_ON if is_favorite else STAR_OFF)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.skill)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.skill)
        super().mouseDoubleClickEvent(event)
