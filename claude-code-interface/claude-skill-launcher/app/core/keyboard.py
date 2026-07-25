"""ctypes 기반 SendInput 래퍼.

`keybd_event` 대신 SendInput 을 쓰는 이유: KEYEVENTF_UNICODE 를 지원하므로
한글/이모지 등 비ASCII 문자를 IME 없이 직접 전송할 수 있다.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from app.config import log

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_MENU = 0x12  # ALT
VK_ESCAPE = 0x1B
VK_V = 0x56

_user32 = ctypes.WinDLL("user32", use_last_error=True) if hasattr(ctypes, "WinDLL") else None


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("padding", ctypes.c_byte * 32)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


def _make_input(vk: int = 0, scan: int = 0, flags: int = 0) -> _INPUT:
    item = _INPUT()
    item.type = INPUT_KEYBOARD
    item.union.ki = _KEYBDINPUT(
        wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=None
    )
    return item


def _send(inputs: list[_INPUT]) -> bool:
    if not inputs or _user32 is None:
        return False
    array = (_INPUT * len(inputs))(*inputs)
    sent = _user32.SendInput(len(inputs), array, ctypes.sizeof(_INPUT))
    if sent != len(inputs):
        log.warning(
            "SendInput 부분 실패: %s/%s (err=%s)",
            sent,
            len(inputs),
            ctypes.get_last_error(),
        )
        return False
    return True


def tap(vk: int) -> bool:
    """가상 키 한 번 누르고 뗀다."""
    return _send([_make_input(vk=vk), _make_input(vk=vk, flags=KEYEVENTF_KEYUP)])


def chord(modifier_vk: int, key_vk: int) -> bool:
    """Ctrl+V 같은 조합키 전송."""
    return _send(
        [
            _make_input(vk=modifier_vk),
            _make_input(vk=key_vk),
            _make_input(vk=key_vk, flags=KEYEVENTF_KEYUP),
            _make_input(vk=modifier_vk, flags=KEYEVENTF_KEYUP),
        ]
    )


def press_enter() -> bool:
    return tap(VK_RETURN)


def paste() -> bool:
    return chord(VK_CONTROL, VK_V)


def nudge_alt() -> None:
    """포그라운드 락 해제용. SetForegroundWindow 실패 시의 우회 트릭."""
    tap(VK_MENU)


def type_unicode(text: str, delay: float = 0.004) -> bool:
    """문자 단위 유니코드 전송. 서로게이트 페어(이모지)도 처리한다."""
    ok = True
    for char in text:
        for unit in _utf16_units(char):
            if not _send(
                [
                    _make_input(scan=unit, flags=KEYEVENTF_UNICODE),
                    _make_input(
                        scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
                    ),
                ]
            ):
                ok = False
        if delay:
            time.sleep(delay)
    return ok


def _utf16_units(char: str) -> list[int]:
    encoded = char.encode("utf-16-le")
    return [
        int.from_bytes(encoded[i : i + 2], "little") for i in range(0, len(encoded), 2)
    ]
