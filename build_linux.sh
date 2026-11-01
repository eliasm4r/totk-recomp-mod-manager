#!/bin/sh
# Builds "TOTKRecompModManager.AppImage" (Linux) into the game folder (one level up). Close the Mod Manager first.
# Needs python3 with tkinter and venv (Debian/Ubuntu: sudo apt install python3-tk python3-venv) and curl.
set -e
cd "$(dirname "$0")"
T="${TMPDIR:-/tmp}/totkmm-build"
echo "Building TOTKRecompModManager.AppImage, this takes about a minute..."
python3 -m venv "$T/venv"
"$T/venv/bin/pip" install --upgrade pyinstaller zstandard tkinterdnd2 py7zr certifi
"$T/venv/bin/python" -m PyInstaller --noconfirm --onedir --windowed --collect-all tkinterdnd2 --name "TOTKRecompModManager" \
    --add-data "$PWD/mm_assets:mm_assets" --distpath "$T/dist" --workpath "$T/work" --specpath "$T" \
    "$PWD/TOTK Recomp Mod Manager.pyw"

# AppImage = the app folder + its icon + its menu entry, in one file
A="$T/AppDir"
rm -rf "$A"
mkdir -p "$A/usr/lib"
cp -r "$T/dist/TOTKRecompModManager" "$A/usr/lib/"
cp mm_assets/icon256.png "$A/totk-recomp-mod-manager.png"
cp mm_assets/icon256.png "$A/.DirIcon"
printf '[Desktop Entry]\nType=Application\nName=TOTK Recomp Mod Manager\nComment=Mod manager for totk-pc-recomp\nExec=TOTKRecompModManager\nIcon=totk-recomp-mod-manager\nTerminal=false\nCategories=Game;\n' \
    > "$A/totk-recomp-mod-manager.desktop"
printf '#!/bin/sh\nexec "$(dirname "$(readlink -f "$0")")/usr/lib/TOTKRecompModManager/TOTKRecompModManager" "$@"\n' > "$A/AppRun"
chmod +x "$A/AppRun"
if [ ! -x "$T/appimagetool" ]; then
    curl -fL -o "$T/appimagetool" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$T/appimagetool"
fi
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$T/appimagetool" --no-appstream "$A" ../TOTKRecompModManager.AppImage
echo "Done: TOTKRecompModManager.AppImage is ready in the game folder."
