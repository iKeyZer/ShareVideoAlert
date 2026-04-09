@echo off
echo ================================================
echo   Compilando Video Share Alert.exe
echo ================================================
echo.
echo Instalando dependencias...
pip install pyinstaller yt-dlp pillow -q
echo.
echo Convirtiendo icono a .ico...
python -c "from PIL import Image; img=Image.open('19-1.png').convert('RGBA'); sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]; imgs=[img.resize(s,Image.LANCZOS) for s in sizes]; imgs[0].save('19-1.ico',format='ICO',append_images=imgs[1:],sizes=sizes)"
echo.
echo Compilando (puede tardar 2-5 minutos)...
python -m PyInstaller ^
  --onefile ^
  --noconsole ^
  --name "VideoShareAlert" ^
  --icon "19-1.ico" ^
  --add-data "video-share-alert-v2.html;." ^
  --add-data "19-1.png;." ^
  --collect-all yt_dlp ^
  app.py

echo.
if exist dist\VideoShareAlert.exe (
    echo ================================================
    echo   LISTO! Ejecutable generado en:
    echo   dist\VideoShareAlert.exe
    echo ================================================
    echo.
    echo Limpiando cache de iconos de Windows...
    taskkill /f /im explorer.exe >nul 2>&1
    del /f "%localappdata%\IconCache.db" >nul 2>&1
    del /f /s /q "%localappdata%\Microsoft\Windows\Explorer\iconcache*" >nul 2>&1
    start explorer.exe
) else (
    echo ERROR: No se pudo generar el ejecutable.
    echo Revisa los mensajes de error arriba.
)
echo.
pause
