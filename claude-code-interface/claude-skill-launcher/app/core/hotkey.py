"""RegisterHotKey 기반 전역 핫키 (기본 Ctrl+Alt+K, 창 표시/숨김 토글).

QAbstractNativeEventFilter 로 Qt 이벤트 루프에 흐르는 WM_HOTKEY 메시지를 가로챈다.
등록 실패(다른 프로그램이 같은 조합을 선점)해도 앱이 죽지 않고 조용히 비활성화된다.

주의: GlobalHotkey(QObject, QAbstractNativeEventFilter) 처럼 다중 상속으로 만들면
이 PyQt6 빌드에서 nativeEventFilter 가 조용히 호출되지 않는 문제가 실측으로
확인됐다 (등록은 성공하지만 WM_HOTKEY 를 못 받음). 그래서 시그널은 내부에 감싼
QObject(_Emitter)로 위임하고, GlobalHotkey 자체는 QAbstractNativeEventFilter 만
상속한다.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PyQt6.QtCore import QAbstractNativeEventFilter, QObject, pyqtSignal

from app.config import log

WM_HOTKEY = 0x0312
MOD_CONTROL = 0x0002
MOD_ALT = 0x0001
VK_K = 0x4B
HOTKEY_ID = 0xC0DE

try:
    _user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    WIN32_AVAILABLE = True
except (AttributeError, OSError):  # pragma: no cover - non-Windows
    _user32 = None
    WIN32_AVAILABLE = False


class _Emitter(QObject):
    triggered = pyqtSignal()


class GlobalHotkey(QAbstractNativeEventFilter):
    def __init__(self, parent=None) -> None:
        super().__init__()
        self._emitter = _Emitter(parent)
        self.triggered = self._emitter.triggered
        self._registered = False

    def register(self) -> bool:
        if self._registered or not WIN32_AVAILABLE:
            return self._registered
        ok = _user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT, VK_K)
        self._registered = bool(ok)
        if not ok:
            log.warning("전역 핫키(Ctrl+Alt+K) 등록 실패 - 다른 프로그램이 선점 중일 수 있습니다.")
        return self._registered

    def unregister(self) -> None:
        if self._registered and WIN32_AVAILABLE:
            _user32.UnregisterHotKey(None, HOTKEY_ID)
        self._registered = False

    def is_registered(self) -> bool:
        return self._registered

    def nativeEventFilter(self, eventType, message):  # noqa: N802 (Qt override signature)
        if eventType == b"windows_generic_MSG" and message:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.triggered.emit()
        return False, 0
