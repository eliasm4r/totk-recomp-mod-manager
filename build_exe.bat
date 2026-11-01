@echo off
rem Builds "TOTKRecompModManager.exe" into the game folder (one level up). Close the Mod Manager first.
cd /d "%~dp0"
echo Building TOTKRecompModManager.exe, this takes about a minute...
set PY=py
where py
if errorlevel 1 set PY=python
%PY% -m pip install --upgrade pyinstaller zstandard tkinterdnd2 py7zr certifi
%PY% -m PyInstaller --noconfirm --onefile --windowed --collect-all tkinterdnd2 --name "TOTKRecompModManager" --icon "%~dp0mm_assets\icon.ico" --add-data "%~dp0mm_assets;mm_assets" --distpath "%~dp0.." --workpath "%TEMP%\totkmm-build" --specpath "%TEMP%\totkmm-build" "%~dp0TOTK Recomp Mod Manager.pyw"
echo.
if exist "..\TOTKRecompModManager.exe" (echo Done: TOTKRecompModManager.exe is ready in the game folder.) else (echo Build failed)
pause
