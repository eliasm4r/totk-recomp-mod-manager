# Changelog

## v1.0.2

Renamed to **TOTK Recomp Mod Manager**.

**New**
- Linux support (Steam Deck and Steam Machine included), as an AppImage: `TOTKRecompModManager.AppImage`.
- Priority order: ▲ ▼ arrows or drag and drop. When two mods change the same file, the one lower in the list wins
  (it used to be A→Z order).
- Red **CONFLICTS** badge on mods that change the same files as another enabled mod. Click it to see which mod wins.
- `.7z` and `.rar` mods, and drag and drop of mod archives onto the window.
- **ENABLE ALL** / **DISABLE ALL** buttons, and a search field.
- **FIND MODS** button (Tears of the Kingdom mods on GameBanana).
- **ⓘ** button explaining which mods work with the recomp (RomFS mods: yes; exefs code mods: no).
- Notice when a new version of the Mod Manager is out.
- **SHORTCUT** button also works on Linux (app menu entry and desktop icon).

**Changed**
- Disabled mods show **DISABLED** instead of DORMANT.
- New title art, and the Windows file is now `TOTKRecompModManager.exe`.
- Toggles and order are saved right away, so they survive a refresh before APPLY.
- Clearer warnings for mods with an `exefs` folder.

**Fixed**
- Mods whose `romfs` folder uses another letter case (`RomFS`, `Romfs`) are found on every system.

## v1.0.1

**Fixed**
- Game version detection: the resource size table has a different name depending on the game version, which showed
  "YOUR GAME: unknown" and could cause a black screen. Both names are recognized now, and the version can also be
  read from `totk-install.json`.
- When the size table cannot be found, the install stops with an error instead of wrongly reporting
  "size table patched".
- Clearer error when `romfs-index.bin` is missing (the Mod Manager is not in the game folder).

**Changed**
- The Windows file is now `TOTKModManager.exe`.

## v1

First release.
- Import RomFS mods from `.zip` files.
- Enable or disable each mod, then **APPLY** (or **APPLY & PLAY** to start the game right after).
- Detects the game version and warns when a mod was made for another version.
- Writes the `manifest.tsv` the recomp requires, patches the resource size table and updates `totk.ini`.
- Never modifies `romfs.bin`.
- **DESKTOP SHORTCUT** button (Windows).
