"""대상 콘솔 창에 명령 문자열을 입력한다.

핵심 안전장치: 포커스 확보 후 GetForegroundWindow() 로 재확인하고, 대상이
아니면 아무것도 타이핑하지 않고 실패를 반환한다. 엉뚱한 창(예: 사용자의
에디터)에 명령이 들어가는 사고를 막기 위한 필수 가드다.
"""

from __future__ import annotations

import threading
import time

from app.config import Settings, log
from app.core import keyboard
from app.models import ConsoleTarget, InjectResult, InjectStrategy, Skill

try:
    import win32api
    import win32clipboard
    import win32con
    import win32gui
    import win32process

    WIN32_AVAILABLE = True
except ImportError:  # pragma: no cover
    WIN32_AVAILABLE = False

WM_CHAR = 0x0102


def build_command(skill: Skill, user_input: str, template: str) -> str:
    """스킬 + 사용자 추가 지시문으로 최종 전송 문자열을 만든다.

    기본 템플릿은 `/plugin:skill` 형태의 슬래시 커맨드(`{{invocation}}`)를 그대로
    전송한다 — "Use the X skill" 같은 자연어 문장은 모델이 스킬 호출을 알아서
    판단하게 맡기는 방식이라 disable-model-invocation 스킬 등에서 안 먹힐 수 있고,
    사용자가 클릭했을 때는 항상 확정적으로 그 스킬이 실행되길 기대하기 때문이다."""
    raw = skill.command_template or template
    text = raw.replace("{{invocation}}", skill.invocation)
    text = text.replace("{{name}}", skill.name)
    extra = (user_input or "").strip()
    text = text.replace("{{input}}", extra)

    if not extra:
        # "Use the pdf skill: " 처럼 남는 꼬리 구분자를 정리
        text = text.rstrip()
        while text and text[-1] in ":-,;":
            text = text[:-1].rstrip()

    # 개행은 조기 전송을 유발하므로 공백으로 치환
    return " ".join(text.split())


class Injector:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._lock = threading.Lock()

    def inject(self, target: ConsoleTarget, text: str) -> InjectResult:
        strategy = self.settings.strategy

        if not WIN32_AVAILABLE:
            return InjectResult(False, strategy, "pywin32 를 사용할 수 없습니다.")
        if not text.strip():
            return InjectResult(False, strategy, "전송할 명령이 비어 있습니다.")
        if not self._alive(target.hwnd):
            return InjectResult(False, strategy, "대상 콘솔 창이 닫혔습니다.")

        if not self._lock.acquire(blocking=False):
            return InjectResult(False, strategy, "이미 주입이 진행 중입니다.")
        try:
            return self._inject_locked(target, text, strategy)
        finally:
            self._lock.release()

    # ----------------------------------------------------------------- private

    def _inject_locked(
        self, target: ConsoleTarget, text: str, strategy: InjectStrategy
    ) -> InjectResult:
        if strategy is InjectStrategy.WM_CHAR:
            ok = self._send_wm_char(target.hwnd, text)
            return InjectResult(
                ok, strategy, "전송 완료" if ok else "WM_CHAR 전송 실패", text
            )

        if not self._focus(target.hwnd):
            return InjectResult(
                False,
                strategy,
                "콘솔 창에 포커스를 줄 수 없습니다. "
                "관리자 권한으로 실행된 콘솔이면 Launcher 도 관리자 권한이 필요합니다.",
            )

        time.sleep(self.settings.focus_delay_ms / 1000)

        # 필수 가드: 실제로 대상 창이 포그라운드인지 재확인
        if not self._is_foreground(target.hwnd):
            return InjectResult(
                False, strategy, "포커스 확인 실패로 전송을 취소했습니다."
            )

        if strategy is InjectStrategy.PASTE:
            ok = self._send_paste(text)
            failure = "클립보드 붙여넣기 실패"
        else:
            ok = keyboard.type_unicode(text)
            failure = "유니코드 타이핑 실패"

        if ok and self.settings.send_enter:
            time.sleep(0.04)
            keyboard.press_enter()

        return InjectResult(ok, strategy, "전송 완료" if ok else failure, text)

    def _alive(self, hwnd: int) -> bool:
        try:
            return bool(win32gui.IsWindow(hwnd))
        except Exception:
            return False

    def _is_foreground(self, hwnd: int) -> bool:
        try:
            return win32gui.GetForegroundWindow() == hwnd
        except Exception:
            return False

    def _focus(self, hwnd: int) -> bool:
        """SetForegroundWindow 는 자주 실패하므로 3단 우회를 시도한다."""
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        except Exception as exc:
            log.debug("ShowWindow 실패: %s", exc)

        if self._try_set_foreground(hwnd):
            return True

        keyboard.nudge_alt()
        time.sleep(0.03)
        if self._try_set_foreground(hwnd):
            return True

        return self._is_foreground(hwnd)

    def _try_set_foreground(self, hwnd: int) -> bool:
        our_tid = None
        target_tid = None
        attached = False
        try:
            our_tid = win32api.GetCurrentThreadId()
            target_tid, _ = win32process.GetWindowThreadProcessId(hwnd)
            if our_tid != target_tid:
                attached = bool(win32process.AttachThreadInput(our_tid, target_tid, True))
            win32gui.SetForegroundWindow(hwnd)
            return self._is_foreground(hwnd)
        except Exception as exc:
            log.debug("SetForegroundWindow 실패 hwnd=%s: %s", hwnd, exc)
            return False
        finally:
            if attached and our_tid is not None and target_tid is not None:
                try:
                    win32process.AttachThreadInput(our_tid, target_tid, False)
                except Exception:
                    pass

    def _send_paste(self, text: str) -> bool:
        backup = self._read_clipboard() if self.settings.restore_clipboard else None
        if not self._write_clipboard(text):
            return False
        ok = keyboard.paste()
        if backup is not None:
            threading.Timer(0.4, self._write_clipboard, args=(backup,)).start()
        return ok

    def _read_clipboard(self) -> str | None:
        for _ in range(5):  # 클립보드는 다른 앱이 잠글 수 있어 재시도
            try:
                win32clipboard.OpenClipboard()
                try:
                    if win32clipboard.IsClipboardFormatAvailable(
                        win32con.CF_UNICODETEXT
                    ):
                        return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    return ""
                finally:
                    win32clipboard.CloseClipboard()
            except Exception:
                time.sleep(0.03)
        return None

    def _write_clipboard(self, text: str) -> bool:
        for _ in range(5):
            try:
                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                    return True
                finally:
                    win32clipboard.CloseClipboard()
            except Exception:
                time.sleep(0.03)
        log.warning("클립보드 쓰기 실패")
        return False

    def _send_wm_char(self, hwnd: int, text: str) -> bool:
        """레거시 conhost 전용. 포커스 없이 문자 메시지를 직접 보낸다."""
        try:
            for char in text:
                win32gui.PostMessage(hwnd, WM_CHAR, ord(char), 0)
            if self.settings.send_enter:
                win32gui.PostMessage(hwnd, WM_CHAR, 0x0D, 0)
            return True
        except Exception as exc:
            log.warning("WM_CHAR 전송 실패: %s", exc)
            return False
