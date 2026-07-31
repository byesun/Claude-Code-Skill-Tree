"""경로, 상수, 영속 설정 래퍼."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt6.QtCore import QSettings

from app.models import InjectStrategy

APP_NAME = "ClaudeSkillLauncher"
APP_TITLE = "Claude Skill Launcher"
APP_VERSION = "0.1.0"
ORG_NAME = "ClaudeSkillLauncher"

DEFAULT_TEMPLATE = "{{invocation}} {{input}}"

# 스캔 시 무시할 폴더명
IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}
MAX_SCAN_DEPTH = 3
# 콘솔 cwd 에서 .claude/skills 를 찾아 위로 올라가는 최대 단계
MAX_PARENT_LOOKUP = 5


def home_dir() -> Path:
    return Path(os.path.expanduser("~"))


def claude_home() -> Path:
    return home_dir() / ".claude"


def user_skills_root() -> Path:
    return claude_home() / "skills"


def plugins_root() -> Path:
    return claude_home() / "plugins"


def app_data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(home_dir())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def usage_file() -> Path:
    return app_data_dir() / "usage.json"


def log_file() -> Path:
    logs = app_data_dir() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs / "app.log"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger(APP_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler(
        log_file(), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    return logger


log = setup_logging()


class Settings:
    """QSettings 를 타입 안전하게 감싼 얇은 래퍼."""

    def __init__(self) -> None:
        self._s = QSettings(ORG_NAME, APP_NAME)

    # --- 주입 ---
    @property
    def strategy(self) -> InjectStrategy:
        raw = self._s.value("inject/strategy", InjectStrategy.PASTE.value, str)
        try:
            return InjectStrategy(raw)
        except ValueError:
            return InjectStrategy.PASTE

    @strategy.setter
    def strategy(self, value: InjectStrategy) -> None:
        self._s.setValue("inject/strategy", value.value)

    @property
    def send_enter(self) -> bool:
        return self._s.value("inject/send_enter", True, bool)

    @send_enter.setter
    def send_enter(self, value: bool) -> None:
        self._s.setValue("inject/send_enter", value)

    @property
    def restore_clipboard(self) -> bool:
        return self._s.value("inject/restore_clipboard", True, bool)

    @restore_clipboard.setter
    def restore_clipboard(self, value: bool) -> None:
        self._s.setValue("inject/restore_clipboard", value)

    @property
    def focus_delay_ms(self) -> int:
        return int(self._s.value("inject/focus_delay_ms", 120, int))

    @focus_delay_ms.setter
    def focus_delay_ms(self, value: int) -> None:
        self._s.setValue("inject/focus_delay_ms", int(value))

    # --- 템플릿 ---
    @property
    def default_template(self) -> str:
        return self._s.value("template/default", DEFAULT_TEMPLATE, str)

    @default_template.setter
    def default_template(self, value: str) -> None:
        self._s.setValue("template/default", value or DEFAULT_TEMPLATE)

    # --- 스캔 ---
    @property
    def extra_roots(self) -> list[Path]:
        raw = self._s.value("scan/extra_roots", [], list) or []
        return [Path(p) for p in raw if p]

    @extra_roots.setter
    def extra_roots(self, value: list[Path]) -> None:
        self._s.setValue("scan/extra_roots", [str(p) for p in value])

    # --- UI ---
    @property
    def theme(self) -> str:
        return self._s.value("ui/theme", "dark", str)

    @theme.setter
    def theme(self, value: str) -> None:
        self._s.setValue("ui/theme", value)

    @property
    def sort_mode(self) -> str:
        return self._s.value("ui/sort", "favorite", str)

    @sort_mode.setter
    def sort_mode(self, value: str) -> None:
        self._s.setValue("ui/sort", value)

    @property
    def always_on_top(self) -> bool:
        return self._s.value("ui/always_on_top", False, bool)

    @always_on_top.setter
    def always_on_top(self, value: bool) -> None:
        self._s.setValue("ui/always_on_top", value)

    # --- 전역 핫키 ---
    @property
    def hotkey_enabled(self) -> bool:
        return self._s.value("hotkey/enabled", True, bool)

    @hotkey_enabled.setter
    def hotkey_enabled(self, value: bool) -> None:
        self._s.setValue("hotkey/enabled", value)

    @property
    def hotkey_label(self) -> str:
        return self._s.value("hotkey/toggle", "Ctrl+Alt+K", str)
