"""열려 있는 콘솔 창을 열거하고, 셸 프로세스/cwd/claude 실행 여부를 판정한다.

Win32 호출은 모두 방어적으로 감싼다. 실패는 None/False 로 축약되며 예외를
바깥으로 던지지 않는다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import psutil

from app.config import log
from app.models import ConsoleTarget

try:  # Windows 이외 환경에서도 import 가능하도록
    import win32con
    import win32gui
    import win32process

    WIN32_AVAILABLE = True
except ImportError:  # pragma: no cover
    WIN32_AVAILABLE = False

CONSOLE_WINDOW_CLASSES = {
    "ConsoleWindowClass",  # 레거시 conhost (cmd.exe, powershell.exe)
    "CASCADIA_HOSTING_WINDOW_CLASS",  # Windows Terminal
    "PseudoConsoleWindow",
    "mintty",  # Git Bash
}

SHELL_NAMES = {
    "cmd.exe",
    "powershell.exe",
    "pwsh.exe",
    "bash.exe",
    "sh.exe",
    "nu.exe",
}

CLAUDE_PROCESS_NAMES = {"claude.exe", "claude"}
CLAUDE_HOST_NAMES = {"node.exe", "bun.exe", "deno.exe"}


class ConsoleManager:
    def list_consoles(self) -> list[ConsoleTarget]:
        if not WIN32_AVAILABLE:
            log.warning("pywin32 를 사용할 수 없어 콘솔 열거를 건너뜁니다.")
            return []

        targets: list[ConsoleTarget] = []

        def callback(hwnd: int, _acc) -> bool:
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                class_name = win32gui.GetClassName(hwnd)
                if class_name not in CONSOLE_WINDOW_CLASSES:
                    return True
                title = win32gui.GetWindowText(hwnd) or ""
                if not title.strip():
                    return True
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception as exc:  # pywintypes.error 포함
                log.debug("창 정보 조회 실패 hwnd=%s: %s", hwnd, exc)
                return True

            target = ConsoleTarget(
                hwnd=hwnd, title=title, class_name=class_name, pid=pid
            )
            self._enrich(target)
            targets.append(target)
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception as exc:
            log.warning("EnumWindows 실패: %s", exc)

        targets.sort(key=lambda t: (not t.claude_running, t.title.lower()))
        return targets

    def is_window_alive(self, hwnd: int) -> bool:
        if not WIN32_AVAILABLE:
            return False
        try:
            return bool(win32gui.IsWindow(hwnd))
        except Exception:
            return False

    def open_new_console(self, cwd: Path, run_claude: bool = True) -> bool:
        """새 CMD 창을 띄운다. 콘솔이 하나도 없을 때의 탈출구."""
        try:
            command = "claude" if run_claude else ""
            args = ["cmd.exe", "/K", command] if command else ["cmd.exe"]
            subprocess.Popen(
                args,
                cwd=str(cwd),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
            return True
        except OSError as exc:
            log.warning("새 콘솔 실행 실패: %s", exc)
            return False

    # ----------------------------------------------------------------- private

    def _enrich(self, target: ConsoleTarget) -> None:
        """셸 프로세스를 찾아 shell_name / cwd / claude_running 을 채운다."""
        proc = self._safe_process(target.pid)
        if proc is None:
            return

        descendants = self._descendants(proc)
        # Windows Terminal 은 셸이 OpenConsole.exe 하위 별도 트리에 있을 수 있다.
        if not any(p.name().lower() in SHELL_NAMES for p in descendants):
            descendants += self._descendants_via_openconsole(target.pid)

        shell = self._deepest_shell(descendants)
        if shell is not None:
            target.shell_name = self._safe_name(shell)
            target.cwd = self._safe_cwd(shell)
        else:
            target.shell_name = self._safe_name(proc)
            target.cwd = self._safe_cwd(proc)

        target.claude_running = self._has_claude(descendants)

    def _safe_process(self, pid: int) -> psutil.Process | None:
        try:
            return psutil.Process(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
            return None

    def _descendants(self, proc: psutil.Process) -> list[psutil.Process]:
        try:
            return list(proc.children(recursive=True))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return []

    def _descendants_via_openconsole(self, host_pid: int) -> list[psutil.Process]:
        """OpenConsole.exe 의 부모가 host_pid 인 트리를 추가로 수집."""
        collected: list[psutil.Process] = []
        try:
            for proc in psutil.process_iter(["name", "ppid"]):
                info = proc.info
                if (info.get("name") or "").lower() != "openconsole.exe":
                    continue
                if info.get("ppid") != host_pid:
                    continue
                collected.append(proc)
                collected += self._descendants(proc)
        except psutil.Error:
            pass
        return collected

    def _deepest_shell(self, procs: list[psutil.Process]) -> psutil.Process | None:
        shells = [p for p in procs if self._safe_name(p).lower() in SHELL_NAMES]
        if not shells:
            return None
        return max(shells, key=self._depth)

    def _depth(self, proc: psutil.Process) -> int:
        depth = 0
        current = proc
        for _ in range(16):  # 순환 방어
            try:
                parent = current.parent()
            except psutil.Error:
                break
            if parent is None:
                break
            depth += 1
            current = parent
        return depth

    def _has_claude(self, procs: list[psutil.Process]) -> bool:
        for proc in procs:
            name = self._safe_name(proc).lower()
            if name in CLAUDE_PROCESS_NAMES:
                return True
            if name in CLAUDE_HOST_NAMES and self._cmdline_has_claude(proc):
                return True
        return False

    def _cmdline_has_claude(self, proc: psutil.Process) -> bool:
        try:
            return any("claude" in part.lower() for part in (proc.cmdline() or []))
        except psutil.Error:
            return False

    def _safe_name(self, proc: psutil.Process) -> str:
        try:
            return proc.name() or ""
        except psutil.Error:
            return ""

    def _safe_cwd(self, proc: psutil.Process) -> Path | None:
        try:
            cwd = proc.cwd()
        except psutil.Error:
            return None
        try:
            return Path(cwd) if cwd else None
        except (ValueError, OSError):
            return None


if __name__ == "__main__":  # 수동 검증용
    for t in ConsoleManager().list_consoles():
        mark = "claude" if t.claude_running else "-"
        print(f"[{mark:>6}] hwnd={t.hwnd} {t.shell_name:<16} {t.cwd} | {t.title}")
