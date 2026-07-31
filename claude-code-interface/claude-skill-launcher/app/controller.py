"""UI 와 core 를 중개하는 앱 상태 머신.

UI 는 Win32/파일시스템을 직접 만지지 않고 이 컨트롤러의 시그널만 구독한다.
스캔은 QThreadPool 워커에서 수행해 UI 프리즈를 막는다.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal, pyqtSlot

from app.config import Settings, log
from app.core.console_manager import ConsoleManager
from app.core.injector import Injector, build_command
from app.core.skill_scanner import SkillScanner
from app.core.usage_store import UsageStore
from app.core.watcher import SkillWatcher
from app.models import ConsoleTarget, InjectResult, Skill

CONSOLE_POLL_MS = 2000


class _ScanSignals(QObject):
    done = pyqtSignal(list)


class _ScanTask(QRunnable):
    def __init__(self, scanner: SkillScanner, cwd: Path | None, extra: list[Path]):
        super().__init__()
        self.signals = _ScanSignals()
        self._scanner = scanner
        self._cwd = cwd
        self._extra = extra

    @pyqtSlot()
    def run(self) -> None:
        try:
            skills = self._scanner.scan(project_cwd=self._cwd, extra_roots=self._extra)
        except Exception as exc:  # 워커에서 예외가 나도 앱을 죽이지 않는다
            log.exception("스킬 스캔 실패: %s", exc)
            skills = []
        self.signals.done.emit(skills)


class AppController(QObject):
    skills_changed = pyqtSignal(list)  # list[Skill]
    consoles_changed = pyqtSignal(list)  # list[ConsoleTarget]
    active_console_changed = pyqtSignal(object)  # ConsoleTarget | None
    inject_finished = pyqtSignal(object)  # InjectResult
    status_changed = pyqtSignal(str)
    broadcast_finished = pyqtSignal(int, int, list)  # ok_count, total, failure_messages

    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings()
        self.usage = UsageStore()
        self.scanner = SkillScanner()
        self.consoles = ConsoleManager()
        self.injector = Injector(self.settings)
        self.watcher = SkillWatcher(self)
        self.watcher.changed.connect(self.refresh_skills)

        self._skills: list[Skill] = []
        self._console_list: list[ConsoleTarget] = []
        self._active: ConsoleTarget | None = None
        self._manual_cwd: Path | None = None
        self._pool = QThreadPool.globalInstance()

        self._poll = QTimer(self)
        self._poll.setInterval(CONSOLE_POLL_MS)
        self._poll.timeout.connect(self.refresh_consoles)

    # ------------------------------------------------------------------ 수명주기

    def start(self) -> None:
        self.refresh_consoles()
        self.refresh_skills()
        self._poll.start()

    def stop(self) -> None:
        self._poll.stop()
        self.watcher.stop()

    # -------------------------------------------------------------------- 상태

    @property
    def skills(self) -> list[Skill]:
        return list(self._skills)

    @property
    def active_console(self) -> ConsoleTarget | None:
        return self._active

    @property
    def console_targets(self) -> list[ConsoleTarget]:
        return list(self._console_list)

    def set_active_console(self, target: ConsoleTarget | None) -> None:
        previous_cwd = self._active.cwd if self._active else None
        self._active = target
        self.active_console_changed.emit(target)
        new_cwd = target.cwd if target else None
        if new_cwd != previous_cwd:
            self.refresh_skills()

    def set_manual_cwd(self, cwd: Path | None) -> None:
        """콘솔 cwd 탐지가 실패했을 때 사용자가 프로젝트 폴더를 직접 지정."""
        self._manual_cwd = cwd
        self.refresh_skills()

    # -------------------------------------------------------------------- 스캔

    def refresh_consoles(self) -> None:
        targets = self.consoles.list_consoles()
        if self._hwnd_set(targets) != self._hwnd_set(self._console_list):
            self._console_list = targets
            self.consoles_changed.emit(targets)
            self._reconcile_active(targets)
        else:
            self._console_list = targets

    def refresh_skills(self) -> None:
        self.status_changed.emit("스킬을 스캔하는 중…")
        task = _ScanTask(self.scanner, self._effective_cwd(), self.settings.extra_roots)
        task.signals.done.connect(self._on_scan_done)
        self._pool.start(task)

    def watch_roots(self) -> list[Path]:
        return self.scanner.scan_roots(self._effective_cwd())

    # -------------------------------------------------------------------- 주입

    def run_skill(self, skill: Skill, user_input: str = "") -> InjectResult:
        if self._active is None:
            result = InjectResult(
                False, self.settings.strategy, "대상 콘솔을 먼저 선택하세요."
            )
            self.inject_finished.emit(result)
            return result

        if not self.consoles.is_window_alive(self._active.hwnd):
            self.refresh_consoles()
            result = InjectResult(
                False, self.settings.strategy, "대상 콘솔 창이 닫혔습니다."
            )
            self.inject_finished.emit(result)
            return result

        command = build_command(skill, user_input, self.settings.default_template)
        result = self.injector.inject(self._active, command)
        if result.ok:
            self.usage.record_use(skill.key, user_input)
            self.skills_changed.emit(self._skills)  # 사용 횟수 갱신 반영
        else:
            log.warning("주입 실패 [%s]: %s", skill.name, result.message)
        self.inject_finished.emit(result)
        return result

    def run_skill_broadcast(self, skill: Skill, user_input: str = "") -> None:
        """감지된 모든 콘솔에 순차적으로 같은 명령을 전송한다.

        Injector.inject() 는 호출마다 포커스 확보→전송까지 동기적으로 완전히
        끝나고 락을 반환하므로, 같은 스레드에서 순차 호출해도 안전하다(별도
        스레드 불필요). 사용 횟수는 콘솔별이 아니라 스킬 실행 1회로 집계한다."""
        targets = list(self._console_list)
        if not targets:
            self.broadcast_finished.emit(0, 0, ["감지된 콘솔이 없습니다."])
            return

        command = build_command(skill, user_input, self.settings.default_template)
        ok_count = 0
        failures: list[str] = []
        for target in targets:
            if not self.consoles.is_window_alive(target.hwnd):
                failures.append(f"{target.title}: 창이 닫혔습니다.")
                continue
            result = self.injector.inject(target, command)
            if result.ok:
                ok_count += 1
            else:
                failures.append(f"{target.title}: {result.message}")

        if ok_count:
            self.usage.record_use(skill.key, user_input)
            self.skills_changed.emit(self._skills)

        self.broadcast_finished.emit(ok_count, len(targets), failures)

    def preview_command(self, skill: Skill, user_input: str = "") -> str:
        return build_command(skill, user_input, self.settings.default_template)

    def toggle_favorite(self, skill: Skill) -> bool:
        state = self.usage.toggle_favorite(skill.key)
        self.skills_changed.emit(self._skills)
        return state

    def reset_usage(self) -> None:
        """전체 사용 기록(횟수/최근/입력 히스토리) 초기화. 즐겨찾기는 유지."""
        self.usage.reset_all()
        self.skills_changed.emit(self._skills)

    def reset_skill_usage(self, skill: Skill) -> None:
        """특정 스킬 하나의 사용 기록만 초기화."""
        self.usage.reset_skill(skill.key)
        self.skills_changed.emit(self._skills)

    # ----------------------------------------------------------------- private

    def _effective_cwd(self) -> Path | None:
        if self._active and self._active.cwd:
            return self._active.cwd
        return self._manual_cwd

    def _hwnd_set(self, targets: list[ConsoleTarget]) -> frozenset[int]:
        return frozenset(t.hwnd for t in targets)

    def _reconcile_active(self, targets: list[ConsoleTarget]) -> None:
        """폴링 결과에 맞춰 선택 상태를 유지하거나 자동 선택한다."""
        if self._active is not None:
            still = next((t for t in targets if t.hwnd == self._active.hwnd), None)
            if still is not None:
                self._active = still
                self.active_console_changed.emit(still)
                return

        auto = next((t for t in targets if t.claude_running), None) or (
            targets[0] if targets else None
        )
        self.set_active_console(auto)

    def _on_scan_done(self, skills: list[Skill]) -> None:
        self._skills = skills
        self.skills_changed.emit(skills)
        self.watcher.set_roots(self.watch_roots())
        stamp = datetime.now().strftime("%H:%M:%S")
        self.status_changed.emit(
            f"스킬 {len(skills)}개 · 콘솔 {len(self._console_list)}개 감지 · 마지막 스캔 {stamp}"
        )

    def sorted_skills(self, query: str = "", source_filter: str = "all") -> list[Skill]:
        items = [s for s in self._skills if s.matches(query)]
        if source_filter == "favorite":
            items = [s for s in items if self.usage.is_favorite(s.key)]
        elif source_filter == "recent":
            order = {k: i for i, k in enumerate(self.usage.recent)}
            items = [s for s in items if s.key in order]
            return sorted(items, key=lambda s: order[s.key])
        elif source_filter == "added":
            items = [s for s in items if s.user_added]
        elif source_filter == "builtin":
            items = [s for s in items if not s.user_added]
        elif source_filter != "all":
            items = [s for s in items if s.source.value == source_filter]

        mode = self.settings.sort_mode
        if mode == "count":
            return sorted(items, key=lambda s: (-self.usage.count(s.key), s.name.lower()))
        if mode == "recent":
            return sorted(items, key=lambda s: self.usage.last_used(s.key), reverse=True)
        if mode == "name":
            return sorted(items, key=lambda s: s.name.lower())
        # 기본: 즐겨찾기 우선 → 사용 횟수 → 이름
        return sorted(
            items,
            key=lambda s: (
                not self.usage.is_favorite(s.key),
                -self.usage.count(s.key),
                s.name.lower(),
            ),
        )
