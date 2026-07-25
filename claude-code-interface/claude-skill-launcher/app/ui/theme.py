"""디자인 토큰과 QSS 생성.

토큰 dict 만 교체하면 라이트 테마를 추가할 수 있도록 문자열 치환 방식을 쓴다.
색은 총 5계열(배경 뉴트럴 3 + 텍스트 2 + 액센트 1 + 상태 2)로 제한한다.
그라디언트/보라색은 사용하지 않는다.
"""

from __future__ import annotations

DARK = {
    # ui-ux-pro-max --design-system 추천: Dark Mode (OLED), 개발자 도구용
    "bg": "#0F172A",
    "surface": "#1E293B",
    "surface_hi": "#334155",
    "border": "#475569",
    "fg": "#F8FAFC",
    "fg_muted": "#94A3B8",
    "accent": "#22C55E",
    "accent_hover": "#4ADE80",
    "accent_fg": "#0B1120",
    "success": "#22C55E",
    "danger": "#EF4444",
    "radius": "10px",
    "radius_sm": "6px",
    "font_ui": '"Inter", "Segoe UI Variable", "Segoe UI", "Malgun Gothic", sans-serif',
    "font_mono": '"Cascadia Mono", Consolas, "D2Coding", monospace',
}

_QSS = """
* {
    font-family: {font_ui};
    color: {fg};
    outline: none;
}

QWidget#Root {
    background-color: {bg};
}

QLabel[role="title"] {
    font-size: 15px;
    font-weight: 600;
    color: {fg};
}
QLabel[role="muted"] {
    font-size: 12.5px;
    color: {fg_muted};
    line-height: 1.5;
}
QLabel[role="mono"] {
    font-family: {font_mono};
    font-size: 12.5px;
    color: {fg_muted};
}

/* ---------- 콘솔 바 ---------- */
QFrame#ConsoleBar {
    background-color: {surface};
    border-bottom: 1px solid {border};
}
QComboBox {
    background-color: {surface_hi};
    border: 1px solid {border};
    border-radius: {radius_sm};
    padding: 6px 10px;
    min-height: 24px;
    font-family: {font_mono};
    font-size: 12.5px;
}
QComboBox:hover { border-color: {accent}; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background-color: {surface_hi};
    border: 1px solid {border};
    selection-background-color: {accent};
    selection-color: {accent_fg};
    padding: 4px;
}

/* ---------- 버튼 ---------- */
QPushButton {
    background-color: {surface_hi};
    border: 1px solid {border};
    border-radius: {radius_sm};
    padding: 7px 14px;
    font-size: 13px;
}
QPushButton:hover { background-color: {border}; }
QPushButton:pressed { background-color: {surface}; }
QPushButton:disabled { color: {fg_muted}; background-color: {surface}; }

QPushButton[variant="primary"] {
    background-color: {accent};
    color: {accent_fg};
    border: 1px solid {accent};
    font-weight: 600;
}
QPushButton[variant="primary"]:hover { background-color: {accent_hover}; }
QPushButton[variant="primary"]:disabled {
    background-color: {surface_hi};
    color: {fg_muted};
    border-color: {border};
}
QPushButton[variant="ghost"] {
    background-color: transparent;
    border: none;
    color: {fg_muted};
    padding: 6px 10px;
    text-align: left;
}
QPushButton[variant="ghost"]:hover { color: {fg}; background-color: {surface_hi}; }
QPushButton[variant="ghost"]:checked {
    color: {accent};
    background-color: {surface_hi};
    font-weight: 600;
}

/* ---------- 입력 ---------- */
QLineEdit {
    background-color: {surface_hi};
    border: 1px solid {border};
    border-radius: {radius_sm};
    padding: 8px 12px;
    font-size: 13px;
}
QLineEdit:focus { border-color: {accent}; }

/* ---------- 사이드바 / 패널 ---------- */
QFrame#Sidebar {
    background-color: {surface};
    border-right: 1px solid {border};
}
QFrame#DetailPanel {
    background-color: {surface};
    border-left: 1px solid {border};
}
QFrame#Divider {
    background-color: {border};
    max-height: 1px;
    border: none;
}

/* ---------- 스킬 카드 ---------- */
QFrame#SkillCard {
    background-color: {surface};
    border: 1px solid {border};
    border-radius: {radius};
}
QFrame#SkillCard:hover { border-color: {accent}; background-color: {surface_hi}; }
QFrame#SkillCard[selected="true"] {
    border-color: {accent};
    background-color: {surface_hi};
}

QLabel[role="badge"] {
    background-color: {surface_hi};
    color: {fg_muted};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 11px;
}
QLabel[role="badge"][tone="accent"] {
    background-color: {accent};
    color: {accent_fg};
    border-color: {accent};
}
QLabel[role="dot"][state="on"] { color: {success}; font-size: 14px; }
QLabel[role="dot"][state="off"] { color: {fg_muted}; font-size: 14px; }

/* ---------- 스크롤바 ---------- */
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: transparent; width: 10px; margin: 2px;
}
QScrollBar::handle:vertical {
    background: {border}; border-radius: 5px; min-height: 28px;
}
QScrollBar::handle:vertical:hover { background: {fg_muted}; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

/* ---------- 상태바 / 토스트 ---------- */
QFrame#StatusBar {
    background-color: {surface};
    border-top: 1px solid {border};
}
QFrame#Toast {
    background-color: {surface_hi};
    border: 1px solid {border};
    border-radius: {radius_sm};
}
QFrame#Toast[tone="error"] { border-color: {danger}; }
QFrame#Toast[tone="success"] { border-color: {success}; }
"""


def stylesheet(tokens: dict[str, str] | None = None) -> str:
    values = tokens or DARK
    css = _QSS
    for key, value in values.items():
        css = css.replace("{" + key + "}", value)
    return css


def color(name: str, tokens: dict[str, str] | None = None) -> str:
    return (tokens or DARK)[name]
