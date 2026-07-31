"""SKILL.md 전체 내용을 인앱에서 바로 보는 미리보기 다이얼로그.

스캐너의 400자 body_preview 캐시에 의존하지 않고, 열 때마다 파일을 새로
읽어 항상 최신 내용을 보여준다. Qt 기본 마크다운 렌더러(QTextEdit.setMarkdown)를
쓰므로 추가 의존성이 필요 없다.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QTextEdit, QVBoxLayout

from app.config import log
from app.core.skill_scanner import _parse_frontmatter
from app.models import Skill


class SkillPreviewDialog(QDialog):
    def __init__(self, skill: Skill, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{skill.name} — SKILL.md 미리보기")
        self.resize(640, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        view = QTextEdit()
        view.setReadOnly(True)
        view.setMarkdown(self._read(skill))
        layout.addWidget(view)

    def _read(self, skill: Skill) -> str:
        """이름/설명은 상세 패널에 이미 보이므로, frontmatter 는 걷어내고
        본문(실제 지시문)만 보여준다."""
        try:
            text = skill.path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            log.warning("SKILL.md 미리보기 읽기 실패 %s: %s", skill.path, exc)
            return f"파일을 읽을 수 없습니다: {skill.path}\n\n{exc}"
        _meta, body, _warning = _parse_frontmatter(text)
        return body.strip() or text
