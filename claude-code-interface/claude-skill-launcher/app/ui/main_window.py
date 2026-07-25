"""메인 윈도우. 컨트롤러 시그널을 구독해 UI 를 갱신한다."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_TITLE, APP_VERSION, log, user_skills_root
from app.controller import AppController
from app.core.hotkey import GlobalHotkey
from app.models import ConsoleTarget, InjectResult, Skill
from app.ui.settings_dialog import SettingsDialog
from app.ui.theme import stylesheet
from app.ui.widgets.console_bar import ConsoleBar
from app.ui.widgets.detail_panel import DetailPanel
from app.ui.widgets.skill_grid import SkillGrid
from app.ui.widgets.toast import Toast

FILTERS = [
    ("favorite", "즐겨찾기"),
    ("recent", "최근"),
    ("all", "전체"),
    ("added", "내가 추가함"),
    ("builtin", "기본 제공"),
    ("project", "프로젝트"),
    ("user", "전역"),
    ("plugin", "플러그인"),
]


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController):
        super().__init__()
        self.controller = controller
        self.setWindowTitle(f"{APP_TITLE} {APP_VERSION}")
        self.resize(1100, 720)
        self.setMinimumSize(880, 560)
        self.setStyleSheet(stylesheet())
        if controller.settings.always_on_top:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self._filter = "all"
        self._selected: Skill | None = None

        self._build_ui()
        self._wire_controller()
        self._install_shortcuts()
        self._setup_hotkey()

    # -------------------------------------------------------------------- build

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.console_bar = ConsoleBar()
        outer.addWidget(self.console_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_center(), 1)

        self.detail = DetailPanel()
        body.addWidget(self.detail)
        outer.addLayout(body, 1)

        outer.addWidget(self._build_status_bar())
        self.setCentralWidget(root)

        self.toast = Toast(root)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(168)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(2)

        heading = QLabel("보기")
        heading.setProperty("role", "muted")
        layout.addWidget(heading)

        self._filter_group = QButtonGroup(self)
        self._filter_group.setExclusive(True)
        for key, label in FILTERS:
            button = QPushButton(label)
            button.setProperty("variant", "ghost")
            button.setCheckable(True)
            button.setChecked(key == self._filter)
            button.clicked.connect(lambda _c, k=key: self._set_filter(k))
            self._filter_group.addButton(button)
            layout.addWidget(button)

        layout.addStretch(1)

        open_root = QPushButton("스킬 폴더 열기")
        open_root.setProperty("variant", "ghost")
        open_root.clicked.connect(lambda: self._open_path(user_skills_root()))
        layout.addWidget(open_root)

        return sidebar

    def _build_center(self) -> QWidget:
        center = QWidget()
        layout = QVBoxLayout(center)
        layout.setContentsMargins(16, 14, 4, 0)
        layout.setSpacing(10)

        self.search = QLineEdit()
        self.search.setPlaceholderText("스킬 검색  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _t: self._render_skills())
        layout.addWidget(self.search)

        self.grid = SkillGrid()
        self.grid.skill_selected.connect(self._on_skill_selected)
        self.grid.skill_activated.connect(self._on_skill_activated)
        self.grid.favorite_toggled.connect(self._on_favorite_toggled)
        self.grid.context_requested.connect(self._on_context_menu)
        layout.addWidget(self.grid, 1)

        return center

    def _build_status_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(28)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)

        self.status = QLabel("준비 중…")
        self.status.setProperty("role", "muted")
        layout.addWidget(self.status, 1)
        return bar

    # --------------------------------------------------------------------- wire

    def _wire_controller(self) -> None:
        c = self.controller
        c.skills_changed.connect(lambda _s: self._render_skills())
        c.consoles_changed.connect(self._on_consoles_changed)
        c.active_console_changed.connect(self._on_active_console_changed)
        c.inject_finished.connect(self._on_inject_finished)
        c.status_changed.connect(self.status.setText)

        self.console_bar.console_chosen.connect(c.set_active_console)
        self.console_bar.refresh_requested.connect(self._refresh_all)
        self.console_bar.open_console_requested.connect(self._open_new_console)
        self.console_bar.settings_requested.connect(self._open_settings)

        self.detail.run_requested.connect(self._run_skill)
        self.detail.input_changed.connect(lambda _t: self._update_preview())
        self.detail.open_file_requested.connect(lambda s: self._open_path(s.path))
        self.detail.open_folder_requested.connect(lambda s: self._open_path(s.root))

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self.search.setFocus())
        QShortcut(QKeySequence("Ctrl+R"), self, self._refresh_all)
        QShortcut(QKeySequence("Ctrl+Return"), self, self._run_selected)
        QShortcut(QKeySequence("Escape"), self, self.search.clear)

    def _setup_hotkey(self) -> None:
        self._hotkey = GlobalHotkey(self)
        app = QApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self._hotkey)
        self._hotkey.triggered.connect(self._toggle_visibility)
        if self.controller.settings.hotkey_enabled:
            self._hotkey.register()

    # ------------------------------------------------------------------- render

    def _render_skills(self) -> None:
        skills = self.controller.sorted_skills(self.search.text(), self._filter)
        usage = self.controller.usage
        counts = {s.key: usage.count(s.key) for s in skills}
        favorites = {s.key for s in skills if usage.is_favorite(s.key)}
        self.grid.set_skills(skills, counts, favorites)

        if self._selected and all(s.key != self._selected.key for s in skills):
            self._on_skill_selected(None)
        else:
            self.grid.select_key(self._selected.key if self._selected else None)

    def _set_filter(self, key: str) -> None:
        self._filter = key
        self._render_skills()

    def _update_preview(self) -> None:
        if self._selected is None:
            self.detail.set_preview("-")
            return
        self.detail.set_preview(
            self.controller.preview_command(self._selected, self.detail.user_input())
        )

    # ------------------------------------------------------------------ handlers

    def _on_skill_selected(self, skill: Skill | None) -> None:
        self._selected = skill
        if skill is None:
            self.detail.set_skill(None)
        else:
            usage = self.controller.usage
            self.detail.set_skill(skill, usage.count(skill.key), usage.last_input(skill.key))
        self._update_preview()
        self.detail.set_run_enabled(self.controller.active_console is not None)

    def _on_skill_activated(self, skill: Skill) -> None:
        self._on_skill_selected(skill)
        self._run_skill(skill, self.detail.user_input())

    def _on_favorite_toggled(self, skill: Skill) -> None:
        state = self.controller.toggle_favorite(skill)
        self.toast.show_message(
            f"'{skill.name}' 즐겨찾기 {'추가' if state else '해제'}", "success", 1600
        )

    def _on_consoles_changed(self, targets: list[ConsoleTarget]) -> None:
        active = self.controller.active_console
        self.console_bar.set_targets(targets, active.hwnd if active else None)
        if not targets:
            self.detail.set_run_enabled(False)

    def _on_active_console_changed(self, target: ConsoleTarget | None) -> None:
        self.console_bar.set_active(target)
        self.detail.set_run_enabled(target is not None)
        if target is not None and target.cwd is None:
            self.status.setText(
                "콘솔 작업 폴더를 확인할 수 없습니다. 'CMD 열기'로 폴더를 지정하거나 프로젝트 폴더를 수동 선택하세요."
            )

    def _on_inject_finished(self, result: InjectResult) -> None:
        if result.ok:
            self.toast.show_message(f"전송 완료: {result.sent_text}", "success", 2600)
        else:
            self.toast.show_message(result.message, "error", 5000)
            self.status.setText(result.message)

    def _on_context_menu(self, skill: Skill, pos: QPoint) -> None:
        menu = QMenu(self)
        run = QAction("실행", menu)
        run.triggered.connect(lambda: self._run_skill(skill, self.detail.user_input()))
        menu.addAction(run)

        open_md = QAction("SKILL.md 열기", menu)
        open_md.triggered.connect(lambda: self._open_path(skill.path))
        menu.addAction(open_md)

        open_dir = QAction("폴더 열기", menu)
        open_dir.triggered.connect(lambda: self._open_path(skill.root))
        menu.addAction(open_dir)

        copy = QAction("명령 복사", menu)
        copy.triggered.connect(lambda: self._copy_command(skill))
        menu.addAction(copy)

        menu.exec(pos)

    # -------------------------------------------------------------------- 액션

    def _run_selected(self) -> None:
        if self._selected is not None:
            self._run_skill(self._selected, self.detail.user_input())

    def _run_skill(self, skill: Skill, user_input: str) -> None:
        self.controller.run_skill(skill, user_input)

    def _refresh_all(self) -> None:
        self.controller.refresh_consoles()
        self.controller.refresh_skills()

    def _open_new_console(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "프로젝트 폴더 선택", str(Path.home()))
        if not folder:
            return
        path = Path(folder)
        if self.controller.consoles.open_new_console(path):
            self.controller.set_manual_cwd(path)
            self.toast.show_message("새 CMD 창에서 claude 를 실행했습니다.", "success")
        else:
            self.toast.show_message("CMD 실행에 실패했습니다.", "error")

    def _copy_command(self, skill: Skill) -> None:
        from PyQt6.QtWidgets import QApplication

        text = self.controller.preview_command(skill, self.detail.user_input())
        QApplication.clipboard().setText(text)
        self.toast.show_message("명령을 클립보드에 복사했습니다.", "success", 1800)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.controller.settings, self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        dialog.apply()

        self.setWindowFlag(
            Qt.WindowType.WindowStaysOnTopHint, self.controller.settings.always_on_top
        )
        self.show()

        if self.controller.settings.hotkey_enabled:
            self._hotkey.register()
        else:
            self._hotkey.unregister()

        self._render_skills()
        self.controller.refresh_skills()
        self.toast.show_message("설정을 저장했습니다.", "success", 1800)

    def _toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()
            self.raise_()

    def _open_path(self, path: Path) -> None:
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except AttributeError:
            subprocess.Popen(["explorer", str(path)])
        except OSError as exc:
            log.warning("경로 열기 실패 %s: %s", path, exc)
            self.toast.show_message(f"열 수 없습니다: {path}", "error")

    # ------------------------------------------------------------------ 이벤트

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.toast.parent_resized()

    def closeEvent(self, event) -> None:
        self._hotkey.unregister()
        self.controller.stop()
        super().closeEvent(event)
