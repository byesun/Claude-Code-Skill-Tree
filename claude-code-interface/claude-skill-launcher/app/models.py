"""데이터 모델 정의. OS/UI 의존성이 없는 순수 모듈."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SkillSource(str, Enum):
    """스킬이 발견된 위치. 값이 클수록 우선순위가 높다."""

    PLUGIN = "plugin"
    USER = "user"
    PROJECT = "project"

    @property
    def priority(self) -> int:
        return {"plugin": 0, "user": 1, "project": 2}[self.value]

    @property
    def label(self) -> str:
        return {"plugin": "플러그인", "user": "전역", "project": "프로젝트"}[self.value]


class InjectStrategy(str, Enum):
    PASTE = "paste"
    TYPE = "type"
    WM_CHAR = "wm_char"


@dataclass(slots=True)
class Skill:
    name: str
    description: str
    path: Path
    root: Path
    source: SkillSource
    allowed_tools: list[str] = field(default_factory=list)
    body_preview: str = ""
    has_scripts: bool = False
    has_assets: bool = False
    command_template: str | None = None
    parse_warning: str | None = None
    shadowed_by: SkillSource | None = None
    marketplace: str | None = None
    user_added: bool = True
    """프로젝트/전역 스킬이거나, 사용자가 직접 설치한 마켓플레이스(플러그인 매니저로
    설치한 것)에서 온 스킬이면 True. claude-plugins-official 처럼 기본 번들로 딸려오는
    마켓플레이스의 스킬은 False (installed_plugins.json 에 없는 마켓플레이스)."""
    plugin_name: str | None = None
    """PLUGIN 소스일 때만 값이 있음. 마켓플레이스 폴더 이름이 아니라 해당 플러그인의
    plugin.json `name` 필드 값 — 슬래시 커맨드 접두사(`/{plugin_name}:{skill}`)로
    실제 쓰이는 값과 정확히 일치해야 한다 (예: karpathy-skills 마켓플레이스의 실제
    plugin_name은 "andrej-karpathy-skills")."""

    @property
    def key(self) -> str:
        """중복 판정과 사용 이력 저장에 쓰이는 안정적인 식별자."""
        return self.name.strip().lower()

    @property
    def invocation(self) -> str:
        """실제 cmd에 입력할 슬래시 커맨드. 플러그인 스킬은 `/plugin:skill`,
        프로젝트/전역 스킬은 `/skill`."""
        if self.plugin_name:
            return f"/{self.plugin_name}:{self.name}"
        return f"/{self.name}"

    def matches(self, query: str) -> bool:
        if not query:
            return True
        q = query.strip().lower()
        haystack = f"{self.name} {self.description} {' '.join(self.allowed_tools)}"
        return q in haystack.lower()


@dataclass(slots=True)
class ConsoleTarget:
    hwnd: int
    title: str
    class_name: str
    pid: int
    shell_name: str = ""
    cwd: Path | None = None
    claude_running: bool = False
    is_elevated: bool = False

    @property
    def short_cwd(self) -> str:
        """드라이브 + 마지막 2단계만 남긴 축약 경로. 콤보박스 폭 제약 대응."""
        if not self.cwd:
            return "경로 미확인"
        parts = self.cwd.parts
        if len(parts) <= 3:
            return str(self.cwd)
        return str(Path(*parts[:1], "...", *parts[-2:]))

    @property
    def display_name(self) -> str:
        """콘솔 창 구분용 표시 문자열. 창 제목(어떤 작업인지)을 우선 보여주고
        셸/경로를 뒤에 붙여, 같은 경로에서 열린 여러 창도 구분할 수 있게 한다."""
        shell = self.shell_name or self.class_name
        title = self.title.strip() or shell
        return f"{title}  ·  {shell} — {self.short_cwd}"

    @property
    def full_description(self) -> str:
        where = str(self.cwd) if self.cwd else "경로 미확인"
        shell = self.shell_name or self.class_name
        return f"{self.title}\n{shell} — {where}"


@dataclass(slots=True)
class InjectResult:
    ok: bool
    strategy: InjectStrategy
    message: str
    sent_text: str = ""
