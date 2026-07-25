@echo off
setlocal

echo [1/4] 가상환경 확인
if not exist .venv (
    python -m venv .venv || goto :fail
)

echo [2/4] 의존성 설치
call .venv\Scripts\activate.bat || goto :fail
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt || goto :fail

echo [3/4] 이전 빌드 정리
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [4/4] PyInstaller 빌드
pyinstaller launcher.spec || goto :fail

echo.
echo 빌드 완료: dist\ClaudeSkillLauncher.exe
goto :eof

:fail
echo.
echo 빌드 실패. 위 로그를 확인하세요.
exit /b 1
