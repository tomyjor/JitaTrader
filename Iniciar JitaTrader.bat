@echo off
echo ================================================
echo   JitaTrader v2 - Iniciando aplicacion
echo ================================================
echo.

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: No se encontro Python en el PATH. Instala Python 3.10+ y volve a intentar.
    pause
    exit /b 1
)

echo Instalando dependencias...
python -m pip install --upgrade pip --quiet
python -m pip install streamlit requests pydantic --quiet

set JITA_PORT=8501

echo.
echo Iniciando Streamlit en el puerto %JITA_PORT%...
echo Si el navegador no se abre solo en unos segundos, entra manualmente a:
echo   http://localhost:%JITA_PORT%
echo.

rem Lanzamos streamlit en segundo plano y forzamos apertura del navegador
rem como red de seguridad, por si --server.headless false no dispara el
rem browser por defecto (pasa en algunas configuraciones de Windows).
start "" /b python -m streamlit run src\presentation\streamlit_app\app.py --server.headless false --server.port %JITA_PORT%

timeout /t 4 /nobreak >nul
start "" http://localhost:%JITA_PORT%

echo.
echo La aplicacion esta corriendo. Cerra esta ventana para detenerla.
pause
