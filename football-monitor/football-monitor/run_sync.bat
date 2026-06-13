@echo off
cd /d "%~dp0"
echo ==============================================
echo  Sincronizando Partidas (Futebol IA)
echo ==============================================
python scripts/sync_recent.py
echo.
echo Processo finalizado!
pause
