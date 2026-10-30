# TOTK Mod Manager v1

A mod manager for **[totk-pc-recomp](https://github.com/valentderah/totk-pc-recomp)** (The Legend of Zelda: Tears of the Kingdom, PC recompilation).
Add mods from `.zip` files, switch them on and off, and apply them with one click. No command line needed.

Made by **Melio**. Bugs and requests: Discord **konomelioda**.

## Features

- Import RomFS mods from `.zip` files (a mod must contain a `romfs` folder).
- Enable or disable each mod with a switch, then click **APPLY** (or **APPLY & PLAY** to start the game right after).
- Detects your game version and warns when a mod was made for another version.
- Writes the `manifest.tsv` the recomp requires, patches the resource size table for the mods and updates `totk.ini`.
- Never modifies `romfs.bin`: disable every mod and click APPLY to go back to the vanilla game.

## Install

1. Download `TOTKModManager.exe` from the [Releases](../../releases) page.
2. Put it in your game folder, next to `totk.exe`.
3. Double-click it. Use **DESKTOP SHORTCUT** to get a shortcut with its icon.

> Windows Defender may flag the `.exe` (a known false positive with PyInstaller builds). You can run the Python version below instead.

## Important: use mods made for your game version

Mods replace game files. A mod made for another version of the game (for example 1.2.1 when your game is 1.4.3)
can ship outdated files and crash the game. The manager shows **YOUR GAME: x.y.z** at the top of the list:
only add mods made for that version. When two mods change the same file, the last one in A→Z order wins.

## Run from source

Needs Python 3.14, or an older Python 3 with `py -m pip install zstandard`.
Put `TOTK Mod Manager.pyw`, `install_mods.py` and the `mm_assets` folder next to `totk.exe`, then double-click the `.pyw`.

To build the `.exe` yourself, put this folder inside the game folder and run `build_exe.bat` (installs PyInstaller, writes the `.exe` one level up).

## Files

| File | Role |
|---|---|
| `TOTK Mod Manager.pyw` | The window (tkinter) |
| `install_mods.py` | Installs the enabled mods (also works on its own: `py install_mods.py`) |
| `mm_assets/` | Icon and artwork (original, no game assets) |
| `build_exe.bat` | Builds `TOTK Mod Manager.exe` |

The title font is [Cinzel](https://fonts.google.com/specimen/Cinzel) (SIL Open Font License), rendered into `mm_assets/title.png`.
Not affiliated with Nintendo. Tears of the Kingdom is a trademark of Nintendo.
