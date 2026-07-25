# Claude Skill Launcher

Claude Code 스킬을 GUI에서 클릭하면, 실행 중인 CMD 창에 호출 명령을 자동 입력·실행해 주는 Windows 데스크톱 앱.

> 상세 설계는 [`DESIGN.md`](./DESIGN.md) 참조. Claude에게 개발을 맡길 때는 이 두 문서를 함께 전달하세요.

## 동작 방식

1. `win32gui.EnumWindows` 로 열려 있는 콘솔 창(cmd / Windows Terminal / PowerShell / Git Bash)을 탐지
2. 창 PID → `psutil` 프로세스 트리 → 셸의 **작업 디렉터리(cwd)** 와 `claude` 실행 여부 판정
3. `~/.claude/skills`, `~/.claude/plugins/*/skills`, `<cwd>/.claude/skills` 의 `SKILL.md` 를 스캔해 YAML frontmatter 파싱
4. 카드 클릭 → 대상 창 포커스 → **클립보드 붙여넣기 + Enter** 로 명령 주입

## 실행 (개발 모드)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Python 3.11 이상, Windows 10/11 필요.

## 빌드 (.exe)

```bat
build.bat
```

산출물: `dist\ClaudeSkillLauncher.exe` (단일 파일, 콘솔 창 없음)

아이콘을 넣으려면 `assets\icon.ico` 를 추가하세요. 없으면 기본 아이콘으로 빌드됩니다.

## 코어 모듈 단독 검증

GUI 없이 각 계층을 먼저 확인할 수 있습니다.

```bat
python -m app.core.skill_scanner     :: 스킬 목록 출력
python -m app.core.console_manager   :: 콘솔 창 + cwd + claude 실행 여부 출력
```

## 단축키

| 키 | 동작 |
|---|---|
| `Ctrl+F` | 검색창 포커스 |
| `Ctrl+R` | 콘솔·스킬 재스캔 |
| `Ctrl+Enter` | 선택된 스킬 실행 |
| `Esc` | 검색 초기화 |
| 카드 더블클릭 | 즉시 실행 |
| 카드 우클릭 | 실행 / SKILL.md 열기 / 폴더 열기 / 명령 복사 |
| 전역 `Ctrl+Alt+K` | 창 표시/숨김 토글 (설정에서 끄기 가능, 다른 앱이 창을 갖고 있어도 동작) |

## 명령 템플릿

기본값은 `{{invocation}} {{input}}` 입니다 — `{{invocation}}`은 `/plugin:skill`
형태의 슬래시 커맨드(플러그인 스킬은 `/ponytail:ponytail-review`처럼, 프로젝트/전역
스킬은 `/skill-name`처럼)로, 클릭하면 자연어 문장이 아니라 **이 슬래시 커맨드가
그대로 콘솔에 입력**됩니다. 자연어("Use the X skill")로는 모델이 스킬 호출 여부를
알아서 판단하기 때문에 `disable-model-invocation` 스킬 등에서 확실히 안 먹힐 수
있어, 클릭 시에는 항상 확정적으로 그 스킬이 실행되는 슬래시 커맨드를 기본값으로 씁니다.

스킬별로 재정의하려면 `SKILL.md` frontmatter에 확장 필드를 추가하세요.

```yaml
---
name: pdf
description: Fill PDF forms and extract text.
x-launcher-command: "{{invocation}} {{input}}"
---
```

## 알려진 제약

- **관리자 권한 콘솔**: UIPI 때문에 일반 권한 프로세스는 관리자 권한 CMD에 입력을 보낼 수 없습니다. 이 경우 Launcher도 관리자 권한으로 실행해야 합니다.
- **Windows Terminal 탭**: 창 단위로만 대상 지정이 가능합니다. 탭별 선택은 지원하지 않습니다.
- **cwd 탐지 실패**: Windows Terminal의 프로세스 트리 구조상 실패할 수 있습니다. 이때는 `CMD 열기`로 폴더를 지정하거나 프로젝트 폴더를 수동 선택하세요.
- **코드 서명 없음**: 최초 실행 시 SmartScreen 경고가 표시됩니다. `추가 정보 → 실행`을 선택하세요.

## 구현 진행 상태

| 단계 | 내용 | 상태 |
|---|---|---|
| M1 | 모델 / 설정 / 스킬 스캐너 | 완료 (실제 환경 검증 완료) |
| M2 | 콘솔 탐지 | 완료 (실제 환경 검증 완료) |
| M3 | 키보드 / 주입 | 완료 (Notepad 대상 라이브 검증 완료) |
| M4 | GUI (테마·메인윈도우·위젯) | 완료 |
| M5 | 사용 이력 / 즐겨찾기 / 검색 | 완료 |
| M6 | watchdog 자동 감시, 설정 다이얼로그, 전역 핫키 | 완료 |
| M7 | 아이콘 / 코드 서명 | 미구현 (아이콘 에셋 없음, 서명 비용 발생) |

로그 위치: `%APPDATA%\ClaudeSkillLauncher\logs\app.log`

## 기존 스킬 / 내가 추가한 스킬 구분

사이드바에 **"내가 추가함" / "기본 제공"** 필터가 추가되었습니다.

- **기본 제공**: `claude-plugins-official`처럼 Claude Code에 기본 번들로 딸려오는
  마켓플레이스의 스킬.
- **내가 추가함**: 프로젝트/전역 스킬이거나, `~/.claude/plugins/installed_plugins.json`
  에 등록된(플러그인 매니저로 직접 설치한) 마켓플레이스의 스킬 — 예: ponytail,
  ui-ux-pro-max, karpathy-skills.

플러그인 스킬 카드에는 해당 시 "내가 추가함" 배지가 함께 표시됩니다.

## 실제 환경 검증 중 발견/수정한 이슈

- `skill_scanner.py`: 플러그인 스캔 경로가 `~/.claude/plugins/<plugin>/skills` 플랫
  레이아웃만 가정하고 있어, 실제 마켓플레이스 레이아웃
  (`~/.claude/plugins/marketplaces/<market>/plugins/<plugin>/skills`,
  `<market>/skills`, `<market>/.claude/skills`)에서 스킬을 하나도 못 찾던 문제 수정.
- `skill_scanner.py`: `entry.name.upper() == SKILL_FILENAME` 비교가 항상 거짓이라
  SKILL.md 파일 자체를 인식하지 못하던 치명적 버그 수정.
- `models.py` / `console_bar.py`: 콘솔 드롭다운이 셸 이름+경로만 보여줘 같은
  경로에서 열린 여러 콘솔 창을 구분할 수 없던 문제 → 창 제목을 앞에 표시하고
  전체 정보는 툴팁으로 제공하도록 수정.
- `skill_card.py` / `skill_grid.py`: 설명 텍스트가 카드 높이 제한에 걸려 단어
  중간에서 잘리던 문제 → 말줄임표(...) 처리 + 전체 설명은 툴팁 제공. 넓은 창에서
  카드가 과도하게 늘어나 속이 빈 것처럼 보이던 문제 → 카드 최대폭 제한 + 좌측 정렬.
- `core/hotkey.py`: `GlobalHotkey(QObject, QAbstractNativeEventFilter)` 처럼
  다중 상속하면 이 PyQt6 빌드에서 `nativeEventFilter`가 등록은 성공해도 실제
  WM_HOTKEY 메시지를 못 받는 문제를 실측으로 확인 → 시그널을 내부 `QObject`로
  위임하는 합성(composition) 구조로 변경해 해결.
- `models.py` / `skill_scanner.py` / `injector.py`: 클릭 시 전송되던 명령이
  `Use the {{name}} skill: {{input}}` 같은 자연어 문장이었는데, 이러면 모델이
  스킬 호출 여부를 알아서 판단하는 방식이라 `disable-model-invocation` 스킬 등에서
  확실히 안 먹힐 수 있음. `/plugin:skill` 형태의 슬래시 커맨드(`Skill.invocation`)를
  기본으로 전송하도록 변경. 이때 마켓플레이스 폴더 이름과 실제 plugin.json `name`이
  다른 경우가 있어(예: `karpathy-skills` 마켓플레이스의 실제 plugin_name은
  `andrej-karpathy-skills`) 반드시 `plugin.json`을 읽어서 계산해야 정확한 슬래시
  커맨드가 나옴.
