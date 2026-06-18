@echo off
REM ============================================================
REM  AI Compliance Suite — Backend-Only Testumgebung (Windows)
REM  Startet nur den Python/Flask-Backend (kein Node.js nötig).
REM
REM  Zugang nach Start:
REM    API:      http://localhost:5000
REM    Swagger:  http://localhost:5000/api/docs/
REM    Health:   http://localhost:5000/health
REM
REM  Demo-Zugangsdaten:
REM    Admin:    admin@example.com  /  admin-password
REM    Editor:   editor@example.com /  editor-password
REM
REM  Beenden: Dieses Fenster schließen oder Strg+C drücken.
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║  AI Compliance Suite — Backend-Testumgebung (Windows)     ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM ── Python prüfen ───────────────────────────────────────────
where python >nul 2>nul
if errorlevel 1 (
    echo [FEHLER] Python nicht gefunden.
    echo          Bitte Python 3.10+ installieren: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%V in ('python --version 2^>^&1') do set PYVER=%%V
echo Python gefunden: %PYVER%

REM ── Virtuelles Environment ──────────────────────────────────
set VENV_DIR=.venv-test

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo.
    echo Erstelle virtuelle Umgebung in %VENV_DIR%...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [FEHLER] venv-Erstellung fehlgeschlagen.
        pause
        exit /b 1
    )
)

call "%VENV_DIR%\Scripts\activate.bat"

REM ── Abhängigkeiten installieren ─────────────────────────────
echo.
echo Prüfe / installiere Python-Abhängigkeiten...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo [FEHLER] pip install fehlgeschlagen. Bitte Ausgabe prüfen.
    pause
    exit /b 1
)
echo Abhängigkeiten OK.

REM ── Umgebungsvariablen setzen ───────────────────────────────
REM .env-Datei laden wenn vorhanden (Werte NICHT überschreiben)
if exist "test.env" (
    echo Lade test.env...
    for /f "usebackq eol=# tokens=1,* delims==" %%A in ("test.env") do (
        if not defined %%A set %%A=%%B
    )
)

REM JWT-Secret automatisch generieren wenn nicht gesetzt
if not defined JWT_SECRET_KEY (
    echo Generiere JWT_SECRET_KEY...
    for /f "delims=" %%S in ('python -c "import secrets; print(secrets.token_hex(32))"') do (
        set JWT_SECRET_KEY=%%S
    )
)

REM Test-Defaults (überschreibbar via test.env)
if not defined ENABLE_DEMO_USERS  set ENABLE_DEMO_USERS=true
if not defined FLASK_ENV           set FLASK_ENV=development
if not defined CORS_ORIGINS        set CORS_ORIGINS=http://localhost:5000,http://127.0.0.1:5000

REM ── Start-Info ──────────────────────────────────────────────
echo.
echo ════════════════════════════════════════════════════════════
echo  Backend startet (HTTP, kein SSL, nur für lokale Tests)
echo ════════════════════════════════════════════════════════════
echo.
echo  API:      http://localhost:5000
echo  Swagger:  http://localhost:5000/api/docs/
echo  Health:   http://localhost:5000/health
echo.
echo  Demo-Login:
echo    admin@example.com   /  admin-password
echo    editor@example.com  /  editor-password
echo.
echo  Beenden: Strg+C oder dieses Fenster schließen.
echo.

REM Browser nach kurzem Delay öffnen (im Hintergrund)
start "" /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:5000/api/docs/"

REM ── Flask starten ───────────────────────────────────────────
python run_dev.py --http

REM Beim Beenden venv deaktivieren
call "%VENV_DIR%\Scripts\deactivate.bat" 2>nul
endlocal
