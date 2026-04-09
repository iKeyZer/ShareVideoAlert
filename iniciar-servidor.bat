@echo off
echo Cerrando procesos anteriores en puerto 8765...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8765 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
echo Instalando/actualizando yt-dlp...
pip install -q --upgrade yt-dlp
echo.
echo URL para OBS: http://localhost:8765/video-share-alert-v2.html
echo.
python server.py
pause
