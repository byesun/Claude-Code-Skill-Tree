"""watchdog 기반 스킬 폴더 변경 감시. 500ms 디바운스 후 changed 시그널 발행.

watchdog 콜백은 감시 스레드에서 호출되므로 QTimer 를 직접 만지지 않고
시그널을 emit 해서 메인 스레드로 안전하게 넘긴다.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.config import log

DEBOUNCE_MS = 500


class _Handler(FileSystemEventHandler):
    def __init__(self, emit_raw) -> None:
        super().__init__()
        self._emit_raw = emit_raw

    def on_any_event(self, event) -> None:  # noqa: ARG002
        self._emit_raw()


class SkillWatcher(QObject):
    changed = pyqtSignal()
    _raw_event = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._observer: Observer | None = None
        self._watched_roots: frozenset[Path] = frozenset()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self.changed.emit)
        self._raw_event.connect(self._debounce.start)

    def set_roots(self, roots: list[Path]) -> None:
        new_roots = frozenset(r for r in roots if r.is_dir())
        if new_roots == self._watched_roots:
            return
        self._watched_roots = new_roots
        self._restart()

    def stop(self) -> None:
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=2)
            except Exception as exc:  # pragma: no cover
                log.debug("watchdog observer 종료 중 예외: %s", exc)
            self._observer = None

    # ----------------------------------------------------------------- private

    def _restart(self) -> None:
        self.stop()
        if not self._watched_roots:
            return
        observer = Observer()
        handler = _Handler(self._raw_event.emit)
        registered = False
        for root in self._watched_roots:
            try:
                observer.schedule(handler, str(root), recursive=True)
                registered = True
            except OSError as exc:
                log.warning("watchdog 감시 등록 실패 %s: %s", root, exc)
        if not registered:
            return
        try:
            observer.start()
            self._observer = observer
        except Exception as exc:  # pragma: no cover
            log.warning("watchdog observer 시작 실패: %s", exc)
