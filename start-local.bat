@echo off
REM AI Compliance Suite - Lokale Testumgebung (Windows)
REM Startet Backend (Flask) + Frontend (Vue.js) aus dem main-Branch.
REM Funktioniert auf jedem Branch - nutzt git worktree.
REM
REM Voraussetzungen:
REM   Python 3.10+  https://www.python.org/downloads/
REM   Node.js 18+   https://nodejs.org/
REM   Git           https://git-scm.com/
REM
REM Zugang nach Start:
REM   Web-UI:   http://localhost:5173
REM   API:      http://localhost:5000
REM   Swagger:  http://localhost:5000/api/docs/
REM
REM Demo-Zugangsdaten:
REM   Admin:   admin@example.com  /  admin-password
REM   Editor:  editor@example.com /  editor-password

setlocal enabledelayedexpansion

cd /d "%~dp0"
set "REPODIR=%~dp0"
set "WORKTREE=%USERPROFILE%\aics-web-test"
set "VENV_DIR=%USERPROFILE%\aics-web-venv"

echo.
echo ====================================================================
echo   AI Compliance Suite - Lokale Testumgebung
echo ====================================================================
echo.

REM Python pruefen
where python >nul 2>nul
if errorlevel 1 ( echo [FEHLER] Python nicht gefunden: https://www.python.org/downloads/ & pause & exit /b 1 )
for /f "tokens=*" %%V in ('python --version 2^>^&1') do echo Python: %%V

REM Node.js pruefen
where npm >nul 2>nul
if errorlevel 1 ( echo [FEHLER] Node.js nicht gefunden: https://nodejs.org/ & pause & exit /b 1 )
for /f "tokens=*" %%V in ('node --version 2^>^&1') do echo Node.js: %%V

REM Git pruefen
where git >nul 2>nul
if errorlevel 1 ( echo [FEHLER] Git nicht gefunden: https://git-scm.com/ & pause & exit /b 1 )

REM Port 5000 pruefen (Produktivsystem stoppen falls noetig)
netstat -ano | findstr ":5000 " | findstr LISTENING >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [WARN] Port 5000 ist bereits belegt!
    echo        Bitte das Produktivsystem stoppen ^(z.B. Docker-Container^).
    echo        Danach diese Batch-Datei neu starten.
    echo.
    echo        Docker: docker compose down
    echo.
    pause
    exit /b 1
)

REM main-Branch als Worktree auschecken (einmalig)
if not exist "%WORKTREE%\run_dev.py" goto do_worktree
echo Worktree vorhanden: %WORKTREE%
goto worktree_done

:do_worktree
echo.
echo Bereite Testumgebung vor (git worktree aus main)...
git worktree remove "%WORKTREE%" --force >nul 2>nul
git worktree add "%WORKTREE%" origin/main 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [FEHLER] git worktree fehlgeschlagen. Bitte 'git fetch origin' ausfuehren.
    pause & exit /b 1
)
echo Worktree OK.

:worktree_done

REM Python venv erstellen
if exist "%VENV_DIR%\Scripts\activate.bat" goto venv_done
echo.
echo Erstelle Python-Umgebung in %VENV_DIR%...
python -m venv "%VENV_DIR%"
if %ERRORLEVEL% NEQ 0 ( echo [FEHLER] venv fehlgeschlagen. & pause & exit /b 1 )

:venv_done

REM venv aktivieren
call "%VENV_DIR%\Scripts\activate.bat"
cd /d "%WORKTREE%"

echo.
echo Pruefe Python-Abhaengigkeiten...
pip install -q -r requirements.txt
if %ERRORLEVEL% NEQ 0 ( echo [FEHLER] pip install fehlgeschlagen. & pause & exit /b 1 )
echo Python-Abhaengigkeiten OK.

REM npm install
if exist "%WORKTREE%\frontend\node_modules\.bin\vite.cmd" goto npm_done
echo.
echo Installiere Frontend-Abhaengigkeiten (einmalig, ca. 1-2 Min.)...
pushd "%WORKTREE%\frontend"
npm install
if %ERRORLEVEL% NEQ 0 ( popd & echo [FEHLER] npm install fehlgeschlagen. & pause & exit /b 1 )
popd
echo Frontend-Abhaengigkeiten OK.

:npm_done

REM Umgebungsvariablen
if exist "%REPODIR%test.env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%REPODIR%test.env") do (
        if not defined %%A set "%%A=%%B"
    )
)
if not defined ENABLE_DEMO_USERS set "ENABLE_DEMO_USERS=true"
if not defined FLASK_ENV set "FLASK_ENV=development"
if not defined CORS_ORIGINS set "CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5000"

REM JWT-Secret generieren
if not defined JWT_SECRET_KEY (
    echo Generiere JWT_SECRET_KEY...
    for /f "delims=" %%S in ('python -c "import secrets; print(secrets.token_hex(32))"') do set "JWT_SECRET_KEY=%%S"
)

REM Hilfsskripte erstellen
(
    echo @echo off
    echo cd /d "%WORKTREE%"
    echo call "%VENV_DIR%\Scripts\activate.bat"
    echo cd /d "%WORKTREE%"
    echo set "JWT_SECRET_KEY=%JWT_SECRET_KEY%"
    echo set "ENABLE_DEMO_USERS=%ENABLE_DEMO_USERS%"
    echo set "FLASK_ENV=%FLASK_ENV%"
    echo set "CORS_ORIGINS=%CORS_ORIGINS%"
    echo python run_dev.py
    echo pause
) > "%USERPROFILE%\aics_backend.bat"

(
    echo @echo off
    echo cd /d "%WORKTREE%\frontend"
    echo npm run dev
    echo pause
) > "%USERPROFILE%\aics_frontend.bat"

REM Backend starten
echo.
echo Starte Backend (Flask HTTP Port 5000)...
start "AICS Backend" cmd /k "%USERPROFILE%\aics_backend.bat"

REM Auf Backend warten (max. 60s)
echo Warte auf Backend...
set /a WAITED=0
:wait_backend
timeout /t 2 /nobreak >nul
curl -sf -k https://localhost:5000/health >nul 2>nul
if %ERRORLEVEL% EQU 0 goto backend_ready
set /a WAITED+=2
if %WAITED% LSS 60 goto wait_backend
echo [WARN] Backend antwortet noch nicht - trotzdem fortfahren.
:backend_ready
echo Backend bereit.

REM Frontend starten
echo Starte Frontend (Vite Port 5173)...
start "AICS Frontend" cmd /k "%USERPROFILE%\aics_frontend.bat"
timeout /t 3 /nobreak >nul
start http://localhost:5173

echo.
echo ====================================================================
echo   Server gestartet
echo ====================================================================
echo.
echo   Web-UI:   https://localhost:5173  ^(oder http:// falls keine Zertifikate^)
echo   API:      https://localhost:5000
echo   Swagger:  https://localhost:5000/api/docs/
echo.
echo   Beim ersten Start: Browser-Zertifikatswarnung mit "Weiter" bestaetigen.
echo.
echo   Login: admin@example.com / admin-password
echo.
echo   Beenden: Fenster Backend und Frontend schliessen.
echo.
pause
endlocal