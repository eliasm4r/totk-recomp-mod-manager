@echo off
rem Builds "TOTK Mod Manager.exe" into the game folder (one level up). Close the Mod Manager first.
cd /d "%~dp0"
echo Building TOTK Mod Manager.exe, this takes about a minute...
set PY=py
where py
if errorlevel 1 set PY=python
%PY% -m pip install --upgrade pyinstaller zstandard
%PY% -m PyInstaller --noconfirm --onefile --windowed --name "TOTK Mod Manager" --icon "%~dp0mm_assets\icon.ico" --add-data "%~dp0mm_assets;mm_assets" --distpath "%~dp0.." --workpath "%TEMP%\totkmm-build" --specpath "%TEMP%\totkmm-build" "%~dp0TOTK Mod Manager.pyw"
echo.
if exist "..\TOTK Mod Manager.exe" (echo Done: TOTK Mod Manager.exe is ready in the game folder.) else (echo Build failed: copy the messages above to Claude.)
pause
