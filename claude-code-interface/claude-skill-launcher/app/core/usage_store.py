"""사용 횟수 / 최근 사용 / 즐겨찾기를 JSON 으로 영속화한다."""

from __future__ import annotations

import json
import os
from datetime import datetime

from app.config import log, usage_file

SCHEMA_VERSION = 1
RECENT_LIMIT = 12


class UsageStore:
    def __init__(self) -> None:
        self._data: dict = {
            "version": SCHEMA_VERSION,
            "favorites": [],
            "skills": {},
            "recent": [],
        }
        self.load()

    # -------------------------------------------------------------- 영속화

    def load(self) -> None:
        path = usage_file()
        if not path.is_file():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("usage.json 읽기 실패, 초기화합니다: %s", exc)
            return
        if not isinstance(raw, dict):
            return
        self._data.update(
            {
                "version": raw.get("version", SCHEMA_VERSION),
                "favorites": [str(x) for x in raw.get("favorites", []) or []],
                "skills": raw.get("skills", {}) or {},
                "recent": [str(x) for x in raw.get("recent", []) or []],
            }
        )

    def save(self) -> None:
        """.tmp 에 쓰고 os.replace 로 교체하여 손상을 방지한다."""
        path = usage_file()
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(tmp, path)
        except OSError as exc:
            log.warning("usage.json 저장 실패: %s", exc)

    # ---------------------------------------------------------------- 조회

    def count(self, key: str) -> int:
        entry = self._data["skills"].get(key) or {}
        try:
            return int(entry.get("count", 0))
        except (TypeError, ValueError):
            return 0

    def last_used(self, key: str) -> str:
        entry = self._data["skills"].get(key) or {}
        return str(entry.get("last_used", "") or "")

    def last_input(self, key: str) -> str:
        entry = self._data["skills"].get(key) or {}
        return str(entry.get("last_input", "") or "")

    def is_favorite(self, key: str) -> bool:
        return key in self._data["favorites"]

    @property
    def recent(self) -> list[str]:
        return list(self._data["recent"])

    # ---------------------------------------------------------------- 변경

    def record_use(self, key: str, user_input: str = "") -> None:
        skills = self._data["skills"]
        entry = skills.setdefault(key, {"count": 0})
        entry["count"] = self.count(key) + 1
        entry["last_used"] = datetime.now().isoformat(timespec="seconds")
        entry["last_input"] = user_input

        recent = self._data["recent"]
        if key in recent:
            recent.remove(key)
        recent.insert(0, key)
        del recent[RECENT_LIMIT:]
        self.save()

    def toggle_favorite(self, key: str) -> bool:
        favorites = self._data["favorites"]
        if key in favorites:
            favorites.remove(key)
            state = False
        else:
            favorites.append(key)
            state = True
        self.save()
        return state
