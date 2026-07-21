@echo off
setlocal
cd /d "%~dp0"

set "CODEX_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%CODEX_PYTHON%" (
  "%CODEX_PYTHON%" -c "import customtkinter" >nul 2>&1
  if errorlevel 1 "%CODEX_PYTHON%" -m pip install -r requirements.txt
  "%CODEX_PYTHON%" app.py
  goto :finished
)

where py.exe >nul 2>&1
if not errorlevel 1 (
  py -3 -c "import customtkinter" >nul 2>&1
  if errorlevel 1 py -3 -m pip install -r requirements.txt
  py -3 app.py
  goto :finished
)

where python.exe >nul 2>&1
if not errorlevel 1 (
  python -c "import customtkinter" >nul 2>&1
  if errorlevel 1 python -m pip install -r requirements.txt
  python app.py
  goto :finished
)

echo Khong tim thay Python de chay ung dung.
echo Hay cai Python 3.12 co Tkinter, sau do chay lai file nay.
pause
exit /b 1

:finished
if errorlevel 1 pause

