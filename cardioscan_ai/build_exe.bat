@echo off
chcp 65001 >nul
echo.
echo ============================================================
echo   CardioScan AI - Generador de Ejecutable (.exe)
echo ============================================================
echo.

REM ── Verificar Python ─────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo Instala Python desde https://python.org y vuelve a intentar.
    pause
    exit /b 1
)

echo [1/5] Instalando dependencias del proyecto...
pip install flask numpy scipy matplotlib scikit-learn pillow --quiet
if errorlevel 1 (
    echo [ERROR] Fallo al instalar dependencias.
    pause
    exit /b 1
)

echo [2/5] Instalando PyInstaller...
pip install pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Fallo al instalar PyInstaller.
    pause
    exit /b 1
)

echo [3/5] Limpiando compilaciones anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [4/5] Generando el ejecutable (esto puede tardar 2-5 minutos)...
pyinstaller cardioscan.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] Fallo al generar el ejecutable. Revisa el log arriba.
    pause
    exit /b 1
)

echo [5/5] Listo.
echo.
echo ============================================================
echo   EJECUTABLE GENERADO CON EXITO
echo ============================================================
echo.
echo   Ubicacion: dist\CardioScanAI.exe
echo.
echo   Puedes mover ese archivo .exe a cualquier carpeta o PC con
echo   Windows (no necesita Python instalado) y abrirlo con doble clic.
echo.
pause
