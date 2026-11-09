@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 패키지 읽어주기 데모

rem 파이썬 찾기 (python 또는 py)
set "PY="
python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY (
  echo [오류] 파이썬이 없어요. https://www.python.org/downloads/ 에서 설치할 때 Add python.exe to PATH 를 체크해 주세요.
  pause
  exit /b 1
)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo [오류] 파이썬 3.10 이상이 필요해요. 지금 버전:
  %PY% --version
  pause
  exit /b 1
)

rem 이 폴더 안에 가상환경 .venv 를 만든다 (처음 한 번, 몇 분 걸림)
if not exist .venv\Scripts\python.exe (
  echo 처음 실행이라 가상환경을 만들고 패키지를 설치해요. 몇 분 걸려요.
  %PY% -m venv .venv
  if errorlevel 1 goto :fail
)
set "VPY=.venv\Scripts\python.exe"
%VPY% -m pip install -q --disable-pip-version-check -r requirements.txt -r requirements-dev.txt -r requirements-tts.txt
if errorlevel 1 goto :fail

echo.
echo [1/2] 테스트
%VPY% -m pytest -q -p no:cacheprovider

echo.
echo [2/2] 웹 데모: 잠시 뒤 브라우저가 열려요. 샘플 사진을 눌러 보세요.
echo       끝내려면 이 창을 닫으면 돼요.
if not defined PACK_TTS set "PACK_TTS=edge,gtts"
start "" /min cmd /c "timeout /t 4 >nul & start http://localhost:8000"
%VPY% -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
exit /b 0

:fail
echo.
echo [오류] 설치에 실패했어요. 이 창의 메시지를 Claude 에게 알려 주세요.
pause
exit /b 1
