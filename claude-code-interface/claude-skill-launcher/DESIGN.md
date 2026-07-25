# Claude Skill Launcher — 설계 명세서

> Claude Code의 Skill을 GUI에서 클릭하면, 실행 중인 CMD 창에 해당 스킬 호출 명령을 자동으로 입력·실행해 주는 Windows 데스크톱 프로그램.

- **버전**: 0.1.0 (스켈레톤)
- **대상 OS**: Windows 10 / 11 (x64)
- **기술 스택**: Python 3.11+ / PyQt6 / pywin32 / psutil / PyYAML / watchdog
- **배포 형태**: PyInstaller 단일 `.exe` (windowed, onefile)

---

## 1. 제품 개요

### 1.1 해결하려는 문제
Claude Code는 `SKILL.md` 기반의 스킬을 자동으로 골라 쓰지만, 사용자는
1. 지금 내 환경에 **어떤 스킬이 있는지** 알기 어렵고
2. 스킬을 **명시적으로 호출하는 문구를 매번 타이핑**해야 하며
3. 스킬이 **실제로 사용됐는지** 추적하기 어렵다.

### 1.2 핵심 시나리오
1. 사용자가 CMD(또는 Windows Terminal)를 열고 `claude`를 실행한다.
2. Launcher를 실행하면 **열려 있는 콘솔 창을 자동 탐지**하여 상단 드롭다운에 나열한다.
3. Launcher는 탐지된 콘솔의 **작업 디렉터리(cwd)** 를 읽어, 그 프로젝트의 `.claude/skills` + 전역 `~/.claude/skills`를 스캔해 스킬 목록을 만든다.
4. 사용자가 스킬 카드를 클릭한다.
5. Launcher가 대상 콘솔 창을 포그라운드로 올리고, 스킬 호출 명령을 **자동 입력 + Enter** 한다.
6. 사용 이력(횟수/최근 사용/즐겨찾기)이 로컬에 기록된다.

### 1.3 비목표 (v0.1 범위 밖)
- Claude Code 응답 스트림 파싱 / 콘솔 출력 스크래핑
- 스킬 생성·편집 에디터
- macOS / Linux 지원

---

## 2. 아키텍처

### 2.1 레이어 구조

```
┌─────────────────────────────────────────────────────────┐
│  UI Layer (PyQt6)                                       │
│  MainWindow · ConsoleBar · SkillGrid · SkillCard         │
│  DetailPanel · SearchBar · StatusBar · theme.qss         │
└───────────────┬─────────────────────────────────────────┘
                │ Qt Signals / Slots
┌───────────────▼─────────────────────────────────────────┐
│  Controller (app/controller.py)                          │
│  - 스캔 트리거 / 필터·정렬 / 주입 오케스트레이션          │
└───┬───────────┬──────────────┬──────────────┬───────────┘
    │           │              │              │
┌───▼────┐ ┌────▼──────┐ ┌─────▼───────┐ ┌────▼────────┐
│Skill   │ │Console    │ │Injector     │ │UsageStore   │
│Scanner │ │Manager    │ │(SendInput)  │ │(JSON)       │
│(fs+yaml)│ │(win32gui) │ │             │ │             │
└────────┘ └───────────┘ └─────────────┘ └─────────────┘
      │           │              │
┌─────▼───────────▼──────────────▼────────────────────────┐
│  OS / FS  ·  ~/.claude/skills  ·  Win32 API  ·  %APPDATA%│
└─────────────────────────────────────────────────────────┘
```

**핵심 원칙**: UI는 Win32 API를 직접 호출하지 않는다. 모든 OS 상호작용은 `app/core/*`를 통과한다. 이렇게 하면 코어 모듈을 CLI/테스트에서 단독 실행할 수 있다.

### 2.2 파일 트리

```
claude-skill-launcher/
├── DESIGN.md                  ← 이 문서
├── README.md                  ← 실행/빌드 가이드
├── requirements.txt
├── build.bat                  ← PyInstaller 빌드 스크립트
├── launcher.spec              ← PyInstaller 스펙
├── main.py                    ← 엔트리포인트
└── app/
    ├── __init__.py
    ├── config.py              ← 경로/상수/QSettings 래퍼
    ├── models.py              ← Skill, ConsoleTarget, InjectResult 데이터클래스
    ├── controller.py          ← 앱 상태 머신 (UI ↔ core 중개)
    ├── core/
    │   ├── __init__.py
    │   ├── skill_scanner.py   ← SKILL.md 탐색 + frontmatter 파싱
    │   ├── console_manager.py ← 콘솔 창 열거/식별/cwd 추출
    │   ├── injector.py        ← 포커스 + 클립보드 붙여넣기/유니코드 타이핑
    │   ├── keyboard.py        ← ctypes SendInput 저수준 래퍼
    │   └── usage_store.py     ← 사용 이력/즐겨찾기 영속화
    └── ui/
        ├── __init__.py
        ├── theme.py           ← 디자인 토큰 + QSS 생성
        ├── main_window.py
        └── widgets/
            ├── __init__.py
            ├── console_bar.py
            ├── search_bar.py
            ├── skill_card.py
            ├── skill_grid.py
            ├── detail_panel.py
            └── toast.py
```

---

## 3. 데이터 모델

### 3.1 `Skill`

| 필드 | 타입 | 설명 |
|---|---|---|
| `name` | `str` | frontmatter `name`, 없으면 폴더명 |
| `description` | `str` | frontmatter `description` |
| `path` | `Path` | `SKILL.md` 절대 경로 |
| `root` | `Path` | 스킬 폴더 경로 |
| `source` | `SkillSource` | `USER` / `PROJECT` / `PLUGIN` |
| `allowed_tools` | `list[str]` | frontmatter `allowed-tools` |
| `body_preview` | `str` | 본문 앞 400자 (상세 패널 표시용) |
| `has_scripts` | `bool` | `scripts/` 하위 파일 존재 여부 |
| `has_assets` | `bool` | `assets/` 하위 파일 존재 여부 |
| `command_template` | `str \| None` | frontmatter `x-launcher-command` (커스텀 호출 문구) |

**중복 해소 규칙**: 같은 `name`이 여러 소스에 존재하면 `PROJECT` > `USER` > `PLUGIN` 우선. 밀린 항목은 목록에서 감추되 상세 패널에서 "shadowed by" 로 표기.

### 3.2 `ConsoleTarget`

| 필드 | 타입 | 설명 |
|---|---|---|
| `hwnd` | `int` | 창 핸들 |
| `title` | `str` | 창 제목 |
| `class_name` | `str` | `ConsoleWindowClass` / `CASCADIA_HOSTING_WINDOW_CLASS` 등 |
| `pid` | `int` | 창 소유 프로세스 |
| `shell_name` | `str` | `cmd.exe` / `powershell.exe` / `WindowsTerminal.exe` |
| `cwd` | `Path \| None` | 가장 깊은 자식 프로세스의 작업 디렉터리 |
| `claude_running` | `bool` | 자식 프로세스 트리에 `claude` 존재 여부 |

### 3.3 `InjectResult`
`ok: bool`, `strategy: InjectStrategy`, `message: str`, `sent_text: str`

---

## 4. 스킬 스캔 명세 (`skill_scanner.py`)

### 4.1 탐색 경로 (우선순위 낮음 → 높음)

| 소스 | glob 패턴 |
|---|---|
| `PLUGIN` | `%USERPROFILE%\.claude\plugins\*\skills\*\SKILL.md` |
| `USER` | `%USERPROFILE%\.claude\skills\**\SKILL.md` |
| `PROJECT` | `<cwd>\.claude\skills\**\SKILL.md` (콘솔 cwd 기준, 상위 디렉터리 최대 5단계까지 역탐색) |

`**` 은 최대 깊이 3으로 제한(대형 트리 방어). 심볼릭 링크는 따라가지 않음.

### 4.2 Frontmatter 파싱
`SKILL.md` 상단 `---` 블록을 YAML로 파싱. 파싱 실패 시 스킬을 버리지 않고 `name = 폴더명`, `description = 본문 첫 문장` 으로 폴백하고 `parse_warning` 을 남긴다.

```yaml
---
name: pdf
description: Fill PDF forms and extract text.
allowed-tools: Read, Bash
x-launcher-command: "Use the pdf skill to {{input}}"   # 선택 확장 필드
---
```

### 4.3 캐시 & 감시
- 스캔 결과는 `(path, mtime, size)` 키로 메모리 캐시. 변경 없으면 재파싱 생략.
- `watchdog.Observer` 로 스킬 루트를 감시하고, 변경 이벤트를 **500 ms 디바운스** 후 `scan_finished` 시그널로 재발행.
- 스캔은 `QThreadPool` 워커에서 수행 → UI 프리즈 방지.

---

## 5. 콘솔 창 탐지 명세 (`console_manager.py`)

### 5.1 창 열거
`win32gui.EnumWindows` → 아래 조건을 모두 만족하는 창만 채택.
1. `IsWindowVisible(hwnd)` 이 True
2. `GetClassName(hwnd)` 이 화이트리스트에 포함
   ```python
   CONSOLE_WINDOW_CLASSES = {
       "ConsoleWindowClass",                  # 레거시 conhost (cmd.exe, powershell.exe)
       "CASCADIA_HOSTING_WINDOW_CLASS",       # Windows Terminal
       "PseudoConsoleWindow",
       "mintty",                              # Git Bash
   }
   ```
3. 창 제목이 비어 있지 않음

### 5.2 PID → 프로세스 트리
`win32process.GetWindowThreadProcessId(hwnd)` 로 PID 획득 → `psutil.Process(pid)`.

Windows Terminal은 셸이 **별도 프로세스 트리**(`OpenConsole.exe` 자식)에 있어 창 PID의 자식만으로는 못 찾는 경우가 있다. 그래서 다음 순서로 셸을 찾는다.
1. `proc.children(recursive=True)` 중 이름이 셸 화이트리스트(`cmd.exe`, `powershell.exe`, `pwsh.exe`, `bash.exe`)인 가장 깊은 프로세스
2. 실패 시, 전체 프로세스를 훑어 `OpenConsole.exe` 의 부모가 대상 PID인 것을 찾아 그 자식 트리를 재탐색
3. 그래도 실패하면 `cwd = None` 으로 두고, UI에서 사용자가 프로젝트 폴더를 수동 지정할 수 있게 한다 (**중요: cwd 탐지 실패는 치명적 오류가 아니다**)

### 5.3 Claude Code 실행 여부
자식 프로세스 중 `name()` 이 `claude.exe` 이거나, `cmdline()` 에 `claude` 토큰이 포함된 `node.exe` 가 있으면 `claude_running = True`. UI에서 초록 점으로 표시하고, 아니면 회색 점 + "claude 미실행" 배지.

### 5.4 폴링
2초 간격 `QTimer` 로 재열거. 목록이 실제로 바뀔 때만(`hwnd` 집합 비교) 시그널 발행하여 UI 깜빡임 방지.

---

## 6. 입력 주입 명세 (`injector.py`)

### 6.1 전략 (설정에서 선택, 기본값 = `PASTE`)

| 전략 | 방식 | 장점 | 단점 |
|---|---|---|---|
| `PASTE` **(기본)** | 클립보드 저장 → `Ctrl+V` → `Enter` | 한글/유니코드/긴 문장 모두 안전, 즉각적 | 사용자 클립보드를 일시 점유 |
| `TYPE` | `SendInput` `KEYEVENTF_UNICODE` 로 문자 단위 전송 | 클립보드 안 건드림 | 느림, IME 간섭 가능 |
| `WM_CHAR` | `PostMessage(hwnd, WM_CHAR, ...)` | 포커스 불필요 | 레거시 conhost에서만 동작 |

`PASTE` 전략은 **원래 클립보드 내용을 백업 후 400 ms 뒤 복원**한다.

### 6.2 포커스 확보 절차
`SetForegroundWindow` 는 다른 프로세스 창에 대해 실패하는 경우가 있다. 다음 순서로 시도한다.
1. `ShowWindow(hwnd, SW_RESTORE)` (최소화 해제)
2. `AttachThreadInput(our_tid, target_tid, True)` → `SetForegroundWindow` → `AttachThreadInput(..., False)`
3. 실패 시 `ALT` 키 down/up 을 한 번 보내 포그라운드 락을 풀고 재시도
4. 포커스 확정 후 **120 ms 대기** (터미널 렌더 안정화)
5. `GetForegroundWindow() != hwnd` 이면 `InjectResult.ok = False` 로 조기 실패 반환 (엉뚱한 창에 타이핑하는 사고 방지 — **필수 가드**)

### 6.3 명령 문자열 생성
```
1. skill.command_template 이 있으면 그것을 사용
2. 없으면 settings.default_template (기본: "Use the {{name}} skill: {{input}}")
3. {{name}} → skill.name, {{input}} → 사용자가 입력창에 넣은 추가 지시문
   {{input}} 이 비면 "Use the {{name}} skill" 까지만 남기고 뒤의 ": " 제거
4. 개행 문자는 공백으로 치환 (조기 전송 방지)
```

`send_enter` 옵션이 False면 Enter를 생략한다(설정에서 토글).

### 6.4 안전장치
- 주입 직전 3초간 `Esc` 를 누르면 취소되는 카운트다운 오버레이(옵션, 기본 off)
- 대상 창이 사라졌으면(`IsWindow(hwnd)` False) 즉시 실패 + 콘솔 목록 새로고침
- 주입 중 재클릭은 무시(뮤텍스)

---

## 7. 사용 이력 (`usage_store.py`)

저장 위치: `%APPDATA%\ClaudeSkillLauncher\usage.json`

```json
{
  "version": 1,
  "favorites": ["pdf", "charts"],
  "skills": {
    "pdf": { "count": 12, "last_used": "2026-07-26T10:03:11", "last_input": "이 파일 요약" }
  },
  "recent": ["pdf", "charts", "neon"]
}
```

- 원자적 쓰기(`.tmp` → `os.replace`)로 손상 방지
- `recent` 는 최대 12개 LRU
- 정렬 옵션: `이름` / `최근 사용` / `사용 횟수` / `즐겨찾기 우선(기본)`

---

## 8. UI 설계

### 8.1 레이아웃 (1100 × 720 기본, 최소 880 × 560)

```
┌──────────────────────────────────────────────────────────────────┐
│ ● Claude Skill Launcher                        ─  □  ✕           │ 40px  타이틀바
├──────────────────────────────────────────────────────────────────┤
│ 콘솔  [▼ cmd.exe — C:\work\my-app        ●claude]  [⟳]  [핀]     │ 56px  ConsoleBar
├────────────┬─────────────────────────────────┬───────────────────┤
│ SIDEBAR    │  SearchBar  [🔍 스킬 검색…]      │  DETAIL PANEL     │
│ 168px      │  [전체][프로젝트][전역][플러그인] │  320px            │
│            ├─────────────────────────────────┤                   │
│ ★ 즐겨찾기 │  ┌───────────┐ ┌───────────┐    │  pdf              │
│ 🕘 최근    │  │ pdf    ★  │ │ charts    │    │  PROJECT · 12회   │
│ 📁 프로젝트│  │ Fill PDF… │ │ Recharts… │    │  ─────────────    │
│ 🌐 전역    │  │ 12회      │ │ 3회       │    │  description…     │
│ 🧩 플러그인│  └───────────┘ └───────────┘    │                   │
│            │  ┌───────────┐ ┌───────────┐    │  allowed-tools    │
│ ─────────  │  │ neon      │ │ r3f       │    │  [Read][Bash]     │
│ ⚙ 설정     │  └───────────┘ └───────────┘    │  ─────────────    │
│            │                                 │  추가 지시문       │
│            │                                 │  [_____________]  │
│            │                                 │  [ ▶ 실행 ]       │
├────────────┴─────────────────────────────────┴───────────────────┤
│ 스킬 24개 · 콘솔 2개 감지 · 마지막 스캔 10:04:22                  │ 28px  StatusBar
└──────────────────────────────────────────────────────────────────┘
```

### 8.2 상호작용
| 액션 | 결과 |
|---|---|
| 카드 **1클릭** | 우측 상세 패널에 선택 표시 |
| 카드 **더블클릭** 또는 `Enter` | 즉시 주입 실행 |
| 카드 `★` 클릭 | 즐겨찾기 토글 |
| 카드 우클릭 | 컨텍스트 메뉴: 실행 / SKILL.md 열기 / 폴더 열기 / 명령 복사 |
| `Ctrl+F` | 검색창 포커스 |
| `Ctrl+R` | 스킬 재스캔 |
| `↑↓←→` | 그리드 내 이동 |
| 전역 핫키 `Ctrl+Alt+K` | 창 표시/숨김 토글 (옵션) |

### 8.3 상태 화면
- **콘솔 0개**: 중앙에 "열려 있는 CMD 창이 없습니다" + `CMD 새로 열기` 버튼(cwd 선택 후 `cmd /K claude` 실행)
- **스킬 0개**: "`~/.claude/skills` 에 스킬이 없습니다" + 폴더 열기 버튼
- **주입 실패**: 우하단 토스트(빨강, 4초) + 상태바 상세 메시지

### 8.4 디자인 토큰 (다크 기본 · ui-ux-pro-max `--design-system` 추천 반영, 2026-07-26)

개발자 도구/생산성 유틸리티에 맞춰 `ui-ux-pro-max` 스킬로 조회한 "Dark Mode (OLED)"
디자인 시스템으로 교체함 (기존 테라코타 팔레트 대체).

| 토큰 | 값 | 용도 |
|---|---|---|
| `--bg` | `#0F172A` | 앱 배경 |
| `--surface` | `#1E293B` | 카드/패널 |
| `--surface-hi` | `#334155` | hover / 보더 |
| `--fg` | `#F8FAFC` | 본문 텍스트 |
| `--fg-muted` | `#94A3B8` | 보조 텍스트 |
| `--accent` | `#22C55E` | 주 액션 / claude 실행 중 표시 (그린) |
| `--accent-hover` | `#4ADE80` | 주 액션 hover |
| `--danger` | `#EF4444` | 오류 토스트 |
| `--radius` | `10px` | 카드 라운딩 |

> 그라디언트 미사용. 배경 변경 시 텍스트 색도 항상 동시 지정.

**타이포그래피**
- UI: `Inter` → `Segoe UI Variable` → `Segoe UI` → `sans-serif` (개발자 도구에 적합한
  기술적·정밀한 인상을 위해 Inter를 1순위로; 미설치 시 자동 폴백)
- 코드/경로/명령: `Cascadia Mono` → `Consolas` → `D2Coding` → `monospace`
- 본문 `line-height: 1.5`, 최소 크기 `12.5px`

**QSS 는 `theme.py` 가 토큰 dict 를 문자열 치환해 생성** → 라이트 테마 추가 시 토큰만 교체.

---

## 9. 설정 (`QSettings`, 레지스트리 `HKCU\Software\ClaudeSkillLauncher`)

| 키 | 기본값 | 설명 |
|---|---|---|
| `inject/strategy` | `PASTE` | 주입 전략 |
| `inject/send_enter` | `true` | Enter 자동 전송 |
| `inject/restore_clipboard` | `true` | 클립보드 복원 |
| `inject/focus_delay_ms` | `120` | 포커스 후 대기 |
| `template/default` | `Use the {{name}} skill: {{input}}` | 기본 명령 템플릿 |
| `scan/extra_roots` | `[]` | 추가 스킬 폴더 |
| `ui/sort` | `favorite` | 정렬 기준 |
| `ui/always_on_top` | `false` | 항상 위 |
| `hotkey/toggle` | `Ctrl+Alt+K` | 전역 핫키 |

---

## 10. 에러 처리 규칙

1. **어떤 예외도 앱을 죽이지 않는다.** `sys.excepthook` 을 설치해 로그 + 토스트로 전환.
2. 로그: `%APPDATA%\ClaudeSkillLauncher\logs\app.log` (`RotatingFileHandler`, 1 MB × 3).
3. Win32 호출은 모두 `try/except pywintypes.error` 로 감싸고 실패 시 `False`/`None` 반환.
4. 권한 문제로 `psutil.AccessDenied` 가 나는 프로세스는 조용히 건너뛴다.
5. **관리자 권한으로 실행된 CMD 창에는 일반 권한 프로세스가 입력을 보낼 수 없다** (UIPI). 이 경우를 감지해 "관리자 권한으로 Launcher 재실행" 안내 토스트를 띄운다.

---

## 11. 빌드

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pyinstaller launcher.spec        :: 또는 build.bat
```

산출물: `dist\ClaudeSkillLauncher.exe`

- `--windowed` (콘솔 창 없음), `--onefile`
- `--icon assets\icon.ico`
- `--hidden-import win32timezone` (pywin32 필수)
- UPX 비활성 (오탐 방지)
- 서명 없으면 SmartScreen 경고가 뜨므로 README 에 안내

---

## 12. 구현 우선순위 (Claude 작업 순서 권장)

| 단계 | 산출물 | 완료 기준 |
|---|---|---|
| M1 | `models.py`, `config.py`, `skill_scanner.py` | `python -m app.core.skill_scanner` 로 스킬 목록이 콘솔에 출력됨 |
| M2 | `console_manager.py` | 열린 CMD 창 목록 + cwd + claude 실행 여부가 출력됨 |
| M3 | `keyboard.py`, `injector.py` | 메모장/CMD 에 문자열 + Enter 가 실제로 들어감 |
| M4 | `theme.py`, `main_window.py`, 위젯들 | GUI 에서 클릭 → CMD 주입까지 E2E 동작 |
| M5 | `usage_store.py`, 정렬/즐겨찾기/검색 | 재실행 후에도 이력 유지 |
| M6 | watchdog 감시, 설정 다이얼로그, 전역 핫키 | 파일 추가 시 자동 반영 |
| M7 | PyInstaller 빌드, 아이콘, 에러 로깅 | `.exe` 단독 실행 성공 |

---

## 13. 테스트 체크리스트

- [ ] 레거시 `cmd.exe` 창에 주입 성공
- [ ] Windows Terminal 탭에 주입 성공
- [ ] PowerShell 7 (`pwsh.exe`) 주입 성공
- [ ] 한글이 포함된 추가 지시문 주입 시 깨짐 없음
- [ ] 대상 창을 주입 도중 닫았을 때 크래시 없음
- [ ] 콘솔 0개 / 스킬 0개 빈 상태 화면 정상
- [ ] 관리자 CMD 대상일 때 안내 메시지 노출
- [ ] 클립보드 원본이 주입 후 복원됨
- [ ] 스킬 폴더에 새 스킬 추가 시 3초 내 목록 반영
- [ ] `.exe` 를 Python 없는 PC 에서 실행 성공
