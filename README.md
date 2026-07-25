# Claude Code Skill Launcher

Claude Code 스킬을 GUI에서 클릭하면, 열려 있는 CMD/터미널 창에 해당 스킬을 실행하는
슬래시 커맨드(`/plugin:skill`)를 자동으로 입력·실행해 주는 Windows 데스크톱 앱입니다.

- 열려 있는 콘솔 창(cmd.exe / Windows Terminal / PowerShell / Git Bash)을 자동 탐지
- 프로젝트 스킬, 전역 스킬, 설치된 플러그인 스킬을 모두 스캔해서 목록으로 표시
- "기본 제공" 스킬과 "내가 직접 설치한" 스킬을 구분해서 필터링 가능
- 스킬 카드를 클릭하면 대상 콘솔에 포커스를 주고 명령을 자동 입력
- 사용 이력 / 즐겨찾기 / 검색, 설정 다이얼로그, 스킬 폴더 변경 자동 감지, 전역 단축키(`Ctrl+Alt+K`)

## 실행 방법

```bat
cd claude-code-interface/claude-skill-launcher
python -m pip install -r requirements.txt
python main.py
```

Python 3.11 이상, Windows 10/11이 필요합니다. 자세한 사용법, 단축키, 알려진 제약
사항은 [`claude-code-interface/claude-skill-launcher/README.md`](claude-code-interface/claude-skill-launcher/README.md)를,
아키텍처/설계 배경은 같은 폴더의 [`DESIGN.md`](claude-code-interface/claude-skill-launcher/DESIGN.md)를 참고하세요.

## 폴더 구조

```
claude-code-interface/
├── claude-skill-launcher/   ← 실제 동작하는 PyQt6 데스크톱 앱 (여기가 본체)
└── (그 외)                  ← 초기 UI 디자인을 시각적으로 잡아본 Next.js 목업
```

## 만든 과정

이 프로젝트는 [Claude Code](https://claude.com/claude-code)와 함께 설계, 구현,
디버깅, 실제 환경 검증까지 진행했습니다.
