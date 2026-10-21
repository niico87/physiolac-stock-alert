@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
if not exist ".venv\Scripts\python.exe" (
  echo Installation des composants necessaires...
  %PY% -m venv .venv
  if errorlevel 1 (echo Installe Python 3 depuis python.org et relance ce fichier. & pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (echo La connexion Internet est necessaire pour l'installation. & pause & exit /b 1)
".venv\Scripts\python.exe" server.py
pause
