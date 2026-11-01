"""TOTK Recomp Mod Manager v1.0.2 by Melio, for totk-pc-recomp: add mods (.zip), enable / disable them, apply, start the game.
Double-click to open. Uses install_mods.py and the art in mm_assets (same folder). tkinter, plus optional packages:
tkinterdnd2 (drag and drop), py7zr (.7z mods), certifi (update check on Linux). The .exe builds include them."""
import json
import math
import os
import random
import re
import ssl
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
import tkinter.font as tkfont
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:                          # running from source without it: no drag and drop
    TkinterDnD = None

FROZEN = getattr(sys, 'frozen', False)          # running as the .exe built by build_exe.bat
if FROZEN and sys.platform.startswith('linux'):   # give the game / file manager / browser the system libraries back
    if 'LD_LIBRARY_PATH_ORIG' in os.environ:
        os.environ['LD_LIBRARY_PATH'] = os.environ.pop('LD_LIBRARY_PATH_ORIG')
    else:
        os.environ.pop('LD_LIBRARY_PATH', None)
# the built app's own file: an AppImage runs from a temporary mount, its real file is in $APPIMAGE
EXE = Path(os.environ.get('APPIMAGE') or sys.executable) if FROZEN else Path(sys.executable)
ROOT = (EXE if FROZEN else Path(__file__)).resolve().parent
ART = Path(getattr(sys, '_MEIPASS', ROOT)) / 'mm_assets'   # the .exe carries its art inside
sys.path.insert(0, str(ROOT))
try:
    import install_mods as im
except SystemExit as e:                     # no zstd: install_mods.py exits with a message
    tk.Tk().withdraw()
    messagebox.showerror('TOTK Recomp Mod Manager', str(e))
    raise
for var in ('APPIMAGE', 'APPDIR', 'ARGV0', 'OWD'):      # read above; the game and other programs must not inherit them
    os.environ.pop(var, None)

if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)                                   # crisp text
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('totk.modmanager')  # own taskbar icon
    except Exception:
        pass

VERSION, AUTHOR = 'v1.0.2', 'Melio'
DISCORD = 'konomelioda'      # contact for bug reports and requests
REPO = 'eliasm4r/totk-recomp-mod-manager'     # update check: the tag of its latest release, like v1.0.3
MODS_SITE = 'https://gamebanana.com/games/7617'
ARCHIVES = ('.zip', '.7z', '.rar')
NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0   # no console flash for helper programs on Windows

# Zonai palette: stone black-green, glowing teal, aged gold
BG, PANEL, CARD, CARD_HI = '#060d0c', '#0a1513', '#0e1d1a', '#122823'
LINE, LINE_HI = '#1b3a33', '#2f6b5c'
TEXT, MUTED, DIM = '#e6f2ec', '#8aa89d', '#4a675d'
TEAL, TEAL_HI, TEAL_DARK, TEAL_DEEP = '#3be3ad', '#9bffe0', '#17604b', '#0c2b23'
GOLD, GOLD_HI, GOLD_DARK = '#d8b45c', '#f6dc96', '#5c4a1f'
RED, AMBER = '#ef6f61', '#f2b84b'


def safe_extract(zip_path, dest):
    """Extracts the zip into dest, refusing paths that would escape the folder."""
    with zipfile.ZipFile(zip_path) as z:
        for m in z.infolist():
            target = (dest / m.filename).resolve()
            if not str(target).startswith(str(dest.resolve()) + os.sep) and target != dest.resolve():
                raise ValueError(f'unsafe path in zip: {m.filename}')
        z.extractall(dest)


def extract(archive, dest):
    """Extracts a .zip / .7z / .rar mod into the empty folder dest, refusing anything that would land outside it."""
    ext = archive.suffix.lower()
    if ext == '.zip':
        safe_extract(archive, dest)
    elif ext == '.7z':
        try:
            import py7zr
        except ImportError:
            raise ValueError('.7z mods need the py7zr package (pip install py7zr), or extract it and zip it')
        with py7zr.SevenZipFile(archive) as z:
            for name in z.getnames():
                if not str((dest / name).resolve()).startswith(str(dest.resolve()) + os.sep):
                    raise ValueError(f'unsafe path in archive: {name}')
            z.extractall(dest)
    elif ext == '.rar':                      # no Python reader: the system's own tools (all refuse paths outside dest)
        if sys.platform == 'win32':
            pf = Path(os.environ.get('ProgramFiles', r'C:\Program Files'))
            tools = [[str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'tar.exe'), '-xf', archive, '-C', dest],
                     [str(pf / 'WinRAR' / 'UnRAR.exe'), 'x', '-o+', archive, f'{dest}{os.sep}'],
                     [str(pf / '7-Zip' / '7z.exe'), 'x', '-y', f'-o{dest}', archive]]
        else:
            tools = [['bsdtar', '-xf', archive, '-C', dest], ['unrar', 'x', '-o+', archive, f'{dest}{os.sep}'],
                     ['7z', 'x', '-y', f'-o{dest}', archive]]
        for cmd in tools:
            if shutil.which(cmd[0]) and subprocess.run([str(c) for c in cmd], capture_output=True,
                                                       creationflags=NO_WINDOW).returncode == 0:
                break
            for f in dest.iterdir():         # drop what a failed tool left behind before trying the next one
                shutil.rmtree(f) if f.is_dir() and not f.is_symlink() else f.unlink()
        else:
            raise ValueError('could not open the .rar' + ('' if sys.platform == 'win32' else
                             ' (install bsdtar, unrar or 7z)') + ': or extract it yourself and zip it')
    else:
        raise ValueError('not a .zip, .7z or .rar file')
    if any(f.is_symlink() for f in dest.rglob('*')):
        raise ValueError('the archive contains links, which mods never need')


def version_key(v):
    return tuple(int(n) for n in re.findall(r'\d+', v))


def latest_release():
    """Tag of the newest GitHub release of the Mod Manager, like 'v1.0.3'."""
    try:
        import certifi                       # the Linux build cannot know where each distribution keeps certificates
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    req = urllib.request.Request(f'https://api.github.com/repos/{REPO}/releases/latest',
                                 headers={'User-Agent': 'TOTK-Recomp-Mod-Manager', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
        return json.load(r)['tag_name']


def mod_files(mod):
    """({romfs path: file} of what the mod installs, total bytes of its romfs folder)."""
    romfs = im.find_romfs(mod)
    files = [f for f in romfs.rglob('*') if f.is_file()] if romfs else []
    game = {f.relative_to(romfs).as_posix(): f for f in files    # same files install_mods.py skips
            if 'ResourceSizeTable' not in f.name and f.suffix.lower() not in ('.exe', '.dll', '.bat', '.txt', '.md')}
    return game, sum(f.stat().st_size for f in files)


def human(n):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024 or unit == 'GB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024


def pick_font(root, *names):
    have = set(tkfont.families(root))
    return next((n for n in names if n in have), 'TkDefaultFont')


def chamfer(x0, y0, x1, y1, c):
    """Polygon points of a rectangle with cut corners (the Zonai panel shape)."""
    return [x0 + c, y0, x1 - c, y0, x1, y0 + c, x1, y1 - c, x1 - c, y1, x0 + c, y1, x0, y1 - c, x0, y0 + c]


def mix(a, b, t):
    a, b = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{int(x + (y - x) * t):02x}' for x, y in zip(a, b))


def image(name):
    try:
        return tk.PhotoImage(file=str(ART / name))
    except Exception:
        return None


class Button(tk.Canvas):
    """Chamfered Zonai button with a glow edge, hover and press states."""

    STYLES = {   # fill, edge, text, glow
        'teal': {'normal': (TEAL_DEEP, TEAL, TEAL_HI, TEAL_DARK), 'hover': (TEAL_DARK, TEAL_HI, '#ffffff', TEAL),
                 'press': ('#0a3a2e', TEAL, TEAL_HI, TEAL_DARK)},
        'gold': {'normal': ('#1c160a', GOLD, GOLD_HI, GOLD_DARK), 'hover': ('#2c2310', GOLD_HI, '#fff3cf', GOLD),
                 'press': ('#140f06', GOLD, GOLD_HI, GOLD_DARK)},
        'ghost': {'normal': (PANEL, LINE, MUTED, None), 'hover': (CARD, LINE_HI, TEAL_HI, None),
                  'press': (BG, TEAL, TEAL, None)},
    }

    def __init__(self, master, text, command, kind='ghost', width=None, height=40, font=None, bg=None):
        super().__init__(master, height=height, bg=bg or master['bg'], highlightthickness=0, cursor='hand2')
        self.text, self.command, self.kind, self.font = text, command, kind, font
        self.state, self.enabled = 'normal', True
        self.configure(width=width or (self.font.measure(text) + 48))
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Enter>', lambda e: self.set_state('hover'))
        self.bind('<Leave>', lambda e: self.set_state('normal'))
        self.bind('<ButtonPress-1>', lambda e: self.set_state('press'))
        self.bind('<ButtonRelease-1>', self._release)

    def draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        fill, edge, fg, glow = self.STYLES[self.kind][self.state] if self.enabled else (PANEL, LINE, DIM, None)
        c = min(10, h // 3)
        if glow:
            self.create_polygon(chamfer(1, 1, w - 2, h - 2, c), fill='', outline=glow, width=4)
        self.create_polygon(chamfer(3, 3, w - 4, h - 4, c - 1), fill=fill, outline=edge, width=1.5)
        if self.kind == 'gold' and self.enabled:     # inner filigree line
            self.create_polygon(chamfer(7, 7, w - 8, h - 8, c - 3), fill='', outline=GOLD_DARK, width=1)
        if self.kind != 'ghost' and self.enabled:    # small diamonds on the sides
            for x in (10, w - 11):
                self.create_polygon(x, h / 2 - 3, x + 3, h / 2, x, h / 2 + 3, x - 3, h / 2, fill=edge, outline='')
        self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=self.font)

    def set_state(self, s):
        self.state = s
        self.draw()

    def set_text(self, text, enabled=True):
        self.text, self.enabled = text, enabled
        self.configure(cursor='hand2' if enabled else 'watch')
        self.draw()

    def _release(self, e):
        inside = 0 <= e.x <= self.winfo_width() and 0 <= e.y <= self.winfo_height()
        self.set_state('hover' if inside else 'normal')
        if inside and self.enabled:
            self.command()


class ModCard(tk.Canvas):
    """One mod: rune badge, name, details, conflicts, priority arrows, ACTIVE / DISABLED chip, Zonai switch, delete.
    Drag it by its left part to change the order."""

    H = 78

    def __init__(self, app, mod, enabled):
        super().__init__(app.list, height=self.H, bg=PANEL, highlightthickness=0)
        self.app, self.mod, self.enabled, self.hover = app, mod, enabled, False
        self.pos = 1.0 if enabled else 0.0
        self.files, size = mod_files(mod)
        n = len(self.files)
        self.meta = f'{n} file{"s" if n != 1 else ""}  ·  {human(size)}'
        self.conflicts = {}                       # other card -> romfs paths both change differently
        self.conf_zone, self.drag_from, self.dragging = None, None, False
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Enter>', lambda e: self.set_hover(True))
        self.bind('<Leave>', lambda e: self.set_hover(False))
        self.bind('<Motion>', self.motion)
        self.bind('<Button-1>', self.click)
        self.bind('<B1-Motion>', self.drag)
        self.bind('<ButtonRelease-1>', self.release)

    def zones(self):
        w = self.winfo_width()
        return (w - 128, w - 66), (w - 52, w - 14), (w - 262, w - 236)   # switch, delete, arrows x-ranges

    def can_move(self, d):
        shown = self.app.shown()
        return self in shown and 0 <= shown.index(self) + d < len(shown)

    def draw(self):
        self.delete('all')
        a = self.app
        w, h = self.winfo_width(), self.H
        on = self.pos > 0.5
        edge = GOLD if self.dragging else (TEAL if on else LINE_HI) if self.hover else (LINE_HI if on else LINE)
        self.create_polygon(chamfer(2, 3, w - 3, h - 4, 12), fill=CARD_HI if self.hover else CARD, outline=edge, width=1.2)
        if on:                                          # glowing spine on the left
            self.create_line(2, 16, 2, h - 17, fill=TEAL, width=3)
        badge = a.img_badge if on else a.img_badge_off
        if badge:
            self.create_image(38, h / 2, image=badge)
        self.create_text(70, h / 2 - 11, text=self.mod.name, anchor='w', fill=TEXT if on else MUTED, font=a.f_card)
        self.create_text(70, h / 2 + 13, text=self.meta, anchor='w', fill=MUTED if on else DIM, font=a.f_small)
        (sx0, sx1), (dx0, dx1), (ax0, ax1) = self.zones()
        ax, cy, hot = (ax0 + ax1) / 2, h / 2, getattr(self, 'hot', None)   # priority arrows: up / down in the list
        for d, tip in ((-1, cy - 14), (1, cy + 14)):
            col = (TEAL_HI if hot == d else MUTED) if self.can_move(d) else LINE
            self.create_polygon(ax - 7, cy + 5 * d, ax + 7, cy + 5 * d, ax, tip, fill=col, outline='')
        self.conf_zone = None
        n = sum(len(v) for v in self.conflicts.values())
        if n:                                           # red conflict chip, left of the arrows (click: details in the log)
            text = f'⚠  {n} CONFLICT{"S" if n > 1 else ""}'
            x1 = ax0 - 16
            x0 = x1 - a.f_chip.measure(text) - 18
            self.conf_zone = (x0, x1)
            hotc = hot == 'conf'
            self.create_polygon(chamfer(x0, cy - 11, x1, cy + 11, 5), fill='#3a1512' if hotc else '#24100e',
                                outline=RED, width=1)
            self.create_text((x0 + x1) / 2, cy, text=text, fill='#ffb3aa' if hotc else RED, font=a.f_chip)
        chip = 'ACTIVE' if on else 'DISABLED'           # status chip
        cw = a.f_chip.measure(chip) + 18
        cx1 = sx0 - 14
        self.create_polygon(chamfer(cx1 - cw, h / 2 - 11, cx1, h / 2 + 11, 5), fill=TEAL_DEEP if on else BG,
                            outline=TEAL_DARK if on else LINE, width=1)
        self.create_text(cx1 - cw / 2, h / 2, text=chip, fill=TEAL if on else DIM, font=a.f_chip)
        # Zonai switch: track with a diamond knob that glows when on
        p, cy = self.pos, h / 2
        track = mix(BG, TEAL_DARK, p)
        self.create_polygon(chamfer(sx0, cy - 12, sx1, cy + 12, 8), fill=track, outline=mix(LINE_HI, TEAL, p), width=1.5)
        kx = sx0 + 16 + p * (sx1 - sx0 - 32)
        if p > 0.5:
            self.create_oval(kx - 13, cy - 13, kx + 13, cy + 13, outline=TEAL_DARK, width=2)
        self.create_polygon(kx, cy - 9, kx + 9, cy, kx, cy + 9, kx - 9, cy, fill=mix(MUTED, TEAL_HI, p), outline='')
        self.create_polygon(kx, cy - 4, kx + 4, cy, kx, cy + 4, kx - 4, cy, fill=mix(BG, '#ffffff', p), outline='')
        # delete
        hot = getattr(self, 'hot', None) == 'del'
        mx = (dx0 + dx1) / 2
        self.create_text(mx, cy, text='✕', fill=RED if hot else DIM, font=a.f_card)

    def motion(self, e):
        (sx0, sx1), (dx0, dx1), (ax0, ax1) = self.zones()
        hot = 'del' if dx0 <= e.x <= dx1 else 'sw' if sx0 <= e.x <= sx1 else None
        if ax0 - 6 <= e.x <= ax1 + 6:
            d = -1 if e.y < self.H / 2 else 1
            hot = d if self.can_move(d) else None
        if self.conf_zone and self.conf_zone[0] <= e.x <= self.conf_zone[1]:
            hot = 'conf'
        self.configure(cursor='hand2' if hot else 'fleur' if e.x < self.drag_limit() else '')
        if hot != getattr(self, 'hot', None):
            self.hot = hot
            self.draw()

    def drag_limit(self):
        """The card is dragged by everything left of its conflict chip / arrows."""
        return (self.conf_zone[0] if self.conf_zone else self.zones()[2][0]) - 10

    def click(self, e):
        (sx0, sx1), (dx0, dx1), (ax0, ax1) = self.zones()
        if e.x < self.drag_limit():
            self.drag_from = e.y_root
        elif self.conf_zone and self.conf_zone[0] <= e.x <= self.conf_zone[1]:
            self.app.show_conflicts(self)
        elif dx0 <= e.x <= dx1:
            self.app.remove(self.mod)
        elif ax0 - 6 <= e.x <= ax1 + 6:
            self.app.move(self, -1 if e.y < self.H / 2 else 1)
        elif sx0 - 100 <= e.x <= sx1:                   # switch, or its status chip
            self.enabled = not self.enabled
            self.animate()
            self.app.mark_dirty()

    def drag(self, e):
        if self.drag_from is None or (not self.dragging and abs(e.y_root - self.drag_from) < 6):
            return
        if not self.dragging:
            self.dragging = True
            self.draw()
        self.app.drag_to(self, e.y_root)

    def release(self, e):
        if self.dragging:
            self.dragging = False
            self.app.drop(self)
            self.draw()
        self.drag_from = None

    def set_hover(self, on):
        self.hover = on
        if not on:
            self.hot = None
        self.draw()

    def animate(self):
        target = 1.0 if self.enabled else 0.0
        self.pos += (target - self.pos) * 0.4
        if abs(target - self.pos) < 0.02:
            self.pos = target
        self.draw()
        if self.pos != target:
            self.after(14, self.animate)


class InfoButton(tk.Canvas):
    """Round "i" button."""

    def __init__(self, master, command, font):
        super().__init__(master, width=36, height=36, bg=master['bg'], highlightthickness=0, cursor='hand2')
        self.font, self.hover = font, False
        self.bind('<Enter>', lambda e: self.draw(True))
        self.bind('<Leave>', lambda e: self.draw(False))
        self.bind('<Button-1>', lambda e: command())
        self.draw(False)

    def draw(self, hover):
        self.delete('all')
        self.create_oval(3, 3, 33, 33, fill=TEAL_DARK if hover else TEAL_DEEP, outline=TEAL_HI if hover else TEAL, width=1.5)
        self.create_text(18, 18, text='i', fill='#ffffff' if hover else TEAL_HI, font=self.font)


# Text of the info window: (mark, colour, heading, paragraph); a None heading is a plain paragraph
INFO = [
    (None, None, None, 'For now, the Mod Manager only installs RomFS mods: mods that have a "romfs" folder inside their '
     'archive. Mods that change the game code (an "exefs" folder) cannot be loaded by the recomp.'),
    ('✓', TEAL, 'RomFS mods: they work',
     'The romfs folder holds game files: models, textures, text, maps, menus... The recomp reads them from the mod '
     'instead of the original files, so these mods work like on a Switch or an emulator.'),
    ('◐', AMBER, 'RomFS mods with a small patch: the romfs part works',
     'Some mods also have an "exefs" folder with only patch files (.ips) in it. The romfs part is installed, the patch '
     'is never applied. A patch changes bytes of the Switch game code, but the recomp has already rebuilt that code '
     'for PC when it was installed, and it only starts if the original game code is untouched. If the patch is a '
     'small extra, the rest of the mod works without it. A mod that is only a patch (no romfs folder) does nothing.'),
    ('✕', RED, 'Code mods: they do not work',
     'Some mods have an "exefs" folder with other files: extra code modules, and the settings that tell the console '
     'to load them. They add new Switch code that runs next to the game. The recomp does not run Switch code, only the '
     'game rebuilt for PC, and it loads no extra module, so that code never runs. Even if such a mod also has a romfs '
     'folder, it will not work properly: its files expect that code to be there.'),
    ('⚙', GOLD, 'Built into the recomp',
     'The most common code mods have an equivalent in the recomp itself, in totk.ini next to the game: frame rate '
     '(fps_limit), game resolution (output_res), and the interface for ultrawide screens. No mod is needed for them.'),
    (None, None, None, 'Not sure about a mod? Open its archive: if it has a romfs folder, and its exefs folder (if '
     'any) only holds .ips files, its romfs part will work.'),
]


class Spinner(tk.Canvas):
    """Rotating Zonai rings shown while mods are being applied."""

    def __init__(self, master):
        super().__init__(master, width=46, height=46, bg=master['bg'], highlightthickness=0)
        self.angle, self.running = 0, False

    def start(self):
        self.running = True
        self.tick()

    def stop(self):
        self.running = False
        self.delete('all')

    def tick(self):
        if not self.running:
            return
        self.delete('all')
        a = self.angle
        self.create_arc(4, 4, 42, 42, start=a, extent=110, style='arc', outline=TEAL, width=3)
        self.create_arc(4, 4, 42, 42, start=a + 180, extent=110, style='arc', outline=TEAL_DARK, width=3)
        self.create_arc(13, 13, 33, 33, start=-a * 1.6, extent=200, style='arc', outline=GOLD, width=2)
        self.create_oval(20, 20, 26, 26, fill=TEAL_HI, outline='')
        self.angle = (a + 9) % 360
        self.after(30, self.tick)


class App(TkinterDnD.Tk if TkinterDnD else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'TOTK Recomp Mod Manager {VERSION}  ·  by {AUTHOR}')
        self.game_code, self.game_ver = im.game_version()
        self.geometry('1000x760')
        self.minsize(1000, 640)   # narrower and the title art runs into the counters
        self.configure(bg=BG)
        im.SOURCES.mkdir(exist_ok=True)
        self.cards, self.dirty, self.busy, self.new_version = [], False, False, None
        self.search = tk.StringVar()
        self.set_icon()
        self.after(10, self.dark_titlebar)

        ui = pick_font(self, 'Bahnschrift', 'Segoe UI', 'DejaVu Sans')
        ui_semi = pick_font(self, 'Bahnschrift SemiBold', 'Segoe UI Semibold', 'Segoe UI', 'DejaVu Sans')
        serif = pick_font(self, 'Palatino Linotype', 'Constantia', 'Georgia', 'DejaVu Serif')
        mono = pick_font(self, 'Cascadia Mono', 'Consolas', 'DejaVu Sans Mono')
        self.f_title = tkfont.Font(family=serif, size=26, weight='bold')
        self.f_sub = tkfont.Font(family=ui, size=9)
        self.f_section = tkfont.Font(family=serif, size=11, weight='bold')
        self.f_card = tkfont.Font(family=ui_semi, size=12)
        self.f_small = tkfont.Font(family=ui, size=9)
        self.f_chip = tkfont.Font(family=ui_semi, size=8)
        self.f_btn = tkfont.Font(family=ui_semi, size=10)
        self.f_big = tkfont.Font(family=ui_semi, size=12)
        self.f_stat = tkfont.Font(family=serif, size=22, weight='bold')
        self.f_mono = tkfont.Font(family=mono, size=9)
        self.f_body = tkfont.Font(family=ui, size=10)
        self.f_info = tkfont.Font(family=serif, size=15, weight='bold')
        self.img_bg, self.img_title, self.img_emblem = image('bg.png'), image('title.png'), image('emblem.png')
        self.img_badge, self.img_badge_off = image('badge.png'), image('badge_off.png')

        self.stage = tk.Canvas(self, bg=BG, highlightthickness=0)   # background art, header, floating motes
        self.stage.place(x=0, y=0, relwidth=1, relheight=1)
        self.stage.bind('<Configure>', lambda e: self.draw_stage())
        self.motes = [[random.random(), random.random(), random.uniform(0.3, 1), random.uniform(1, 2.6)] for _ in range(34)]
        self.build_toolbar()
        self.build_list()
        self.build_footer()
        self.refresh()
        self.log([('info', f'Ready. Your game is {self.game_ver}: only add mods made for this version. Toggle mods, then click APPLY.')])
        self.after(40, self.float_motes)
        if TkinterDnD:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', lambda e: self.add_archives(self.tk.splitlist(e.data)))
        self.check_update()

    # ---------- window
    def set_icon(self):
        try:
            if sys.platform == 'win32':
                self.iconbitmap(default=str(ART / 'icon.ico'))
            else:
                self._icon = tk.PhotoImage(file=str(ART / 'icon64.png'))
                self.iconphoto(True, self._icon)
        except Exception:
            pass

    def dark_titlebar(self, win=None):
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent((win or self).winfo_id())
            val = ctypes.c_int(1)
            for attr in (20, 19):           # DWMWA_USE_IMMERSIVE_DARK_MODE (Win11 / older Win10)
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), 4) == 0:
                    break
            color = ctypes.c_int(0x00110e06)   # DWMWA_CAPTION_COLOR (Win11): BGR of the background
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), 4)
        except Exception:
            pass

    # ---------- stage: background, header, motes
    HEADER = 150

    def draw_stage(self):
        c = self.stage
        c.delete('all')
        w = c.winfo_width()
        if self.img_bg:
            c.create_image(0, 0, image=self.img_bg, anchor='nw')
        if self.img_emblem:
            c.create_image(84, 72, image=self.img_emblem)
        if self.img_title:
            c.create_image(146, 54, image=self.img_title, anchor='w')
        else:
            c.create_text(146, 54, text='TOTK Recomp Mod Manager', anchor='w', fill=GOLD, font=self.f_title)
        spaced = lambda t: '   '.join(' '.join(word) for word in t.split())
        c.create_text(150, 96, text=f'{spaced("TEARS OF THE KINGDOM")}   ·   {spaced("PC RECOMP")}   ·   {spaced(VERSION)}',
                      anchor='w', fill=TEAL, font=self.f_sub)
        if self.new_version:                       # clickable update notice
            c.create_text(150, 116, text=f'◆  Update {self.new_version} available: click to download',
                          anchor='w', fill=GOLD_HI, font=self.f_small, tags='update')
            c.tag_bind('update', '<Button-1>', lambda e: webbrowser.open(f'https://github.com/{REPO}/releases/latest'))
            c.tag_bind('update', '<Enter>', lambda e: c.configure(cursor='hand2'))
            c.tag_bind('update', '<Leave>', lambda e: c.configure(cursor=''))
        h = c.winfo_height()                       # credits along the bottom edge
        c.create_text(36, h - 12, text=f'Made by {AUTHOR}  ·  bugs & requests on Discord: {DISCORD}', anchor='w',
                      fill=DIM, font=self.f_small)
        c.create_text(w - 36, h - 12, text=f'TOTK Recomp Mod Manager {VERSION}', anchor='e', fill=GOLD_DARK, font=self.f_small)
        y = self.HEADER - 18                       # ornate divider: gold rule, diamonds, center rune ring
        c.create_line(36, y, w / 2 - 26, y, fill=GOLD_DARK, width=1)
        c.create_line(w / 2 + 26, y, w - 36, y, fill=GOLD_DARK, width=1)
        c.create_line(36, y + 4, w / 2 - 40, y + 4, fill=LINE, width=1)
        c.create_line(w / 2 + 40, y + 4, w - 36, y + 4, fill=LINE, width=1)
        for x in (36, w - 36):
            c.create_polygon(x, y - 5, x + 5, y, x, y + 5, x - 5, y, fill=GOLD, outline='')
        c.create_oval(w / 2 - 14, y - 14, w / 2 + 14, y + 14, outline=GOLD, width=1.5)
        c.create_oval(w / 2 - 8, y - 8, w / 2 + 8, y + 8, outline=TEAL, width=1.5)
        c.create_oval(w / 2 - 2, y - 2, w / 2 + 2, y + 2, fill=TEAL_HI, outline='')
        for dx in (-22, 22):
            c.create_polygon(w / 2 + dx, y - 3, w / 2 + dx + 3, y, w / 2 + dx, y + 3, w / 2 + dx - 3, y, fill=TEAL, outline='')
        on = sum(card.enabled for card in self.cards)
        for i, (num, label, col) in enumerate(((on, 'ACTIVE', TEAL), (len(self.cards), 'INSTALLED', GOLD_HI))):
            x1 = w - 36 - i * 128
            c.create_polygon(chamfer(x1 - 112, 30, x1, 104, 12), fill=PANEL, outline=GOLD_DARK if i else TEAL_DARK, width=1.2)
            c.create_text(x1 - 56, 58, text=str(num), fill=col, font=self.f_stat)
            c.create_text(x1 - 56, 88, text=label, fill=MUTED, font=self.f_chip)
        self.mote_ids = [c.create_oval(0, 0, 0, 0, fill=TEAL, outline='') for _ in self.motes]

    def float_motes(self):
        c = self.stage
        w, h = max(c.winfo_width(), 1), max(c.winfo_height(), 1)
        for m, mid in zip(self.motes, getattr(self, 'mote_ids', [])):
            m[1] -= 0.0007 * m[2]
            m[0] += 0.0004 * math.sin(time.time() * 0.7 + m[3] * 3)
            if m[1] < 0:
                m[1], m[0] = 1.0, random.random()
            r = m[3]
            x, y = m[0] * w, m[1] * h
            glow = 0.5 + 0.5 * math.sin(time.time() * 1.6 + m[3] * 5)
            c.coords(mid, x - r, y - r, x + r, y + r)
            c.itemconfigure(mid, fill=mix(TEAL_DEEP, TEAL_HI, glow * m[2]))
        self.after(40, self.float_motes)

    # ---------- panels
    def bg_at(self, y):
        """Colour of the background art at height y, so strips over it blend in."""
        try:
            r, g, b = self.img_bg.get(300, int(y))[:3]
            return f'#{r:02x}{g:02x}{b:02x}'
        except Exception:
            return BG

    def build_toolbar(self):
        bar = tk.Frame(self, bg=self.bg_at(self.HEADER + 23))
        bar.place(x=36, y=self.HEADER, relwidth=1, width=-72, height=46)
        Button(bar, '＋   ADD MODS', self.add_archives, 'teal', font=self.f_btn).pack(side='left')
        Button(bar, '↗   FIND MODS', lambda: webbrowser.open(MODS_SITE), font=self.f_btn).pack(side='left', padx=10)
        Button(bar, 'OPEN FOLDER', self.open_folder, font=self.f_btn).pack(side='left')
        Button(bar, '⟳   REFRESH', self.refresh, font=self.f_btn).pack(side='left', padx=10)
        Button(bar, '◈   SHORTCUT', self.make_shortcut, font=self.f_btn).pack(side='left')
        InfoButton(bar, self.show_info, self.f_info).pack(side='right')

    def build_list(self):
        wrap = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        wrap.place(x=36, y=self.HEADER + 58, relwidth=1, width=-72, relheight=1, height=-(self.HEADER + 58 + 200))
        head = tk.Frame(wrap, bg=PANEL)
        head.pack(fill='x', padx=18, pady=(12, 8))
        tk.Label(head, text='◆  YOUR MODS', bg=PANEL, fg=GOLD, font=self.f_section).pack(side='left')
        Button(head, 'DISABLE ALL', lambda: self.set_all(False), height=28, font=self.f_chip).pack(side='right')
        Button(head, 'ENABLE ALL', lambda: self.set_all(True), height=28, font=self.f_chip).pack(side='right', padx=(0, 6))
        box = tk.Entry(head, textvariable=self.search, width=16, bg=BG, fg=TEXT, insertbackground=TEAL, relief='flat',
                       font=self.f_small, highlightthickness=1, highlightbackground=LINE, highlightcolor=TEAL)
        box.pack(side='right', padx=(0, 14), ipady=4)
        hint = tk.Label(box, text='Search mods', bg=BG, fg=DIM, font=self.f_small, cursor='xterm')   # placeholder
        hint.bind('<Button-1>', lambda e: box.focus_set())
        place_hint = lambda *a: hint.place(x=3, rely=0.5, anchor='w') if not self.search.get() and \
            self.focus_get() is not box else hint.place_forget()
        box.bind('<FocusIn>', place_hint)
        box.bind('<FocusOut>', place_hint)
        self.search.trace_add('write', lambda *a: (place_hint(), self.show_cards()))
        self.after(50, place_hint)
        tk.Label(head, text=f'YOUR GAME: {self.game_ver}  ·  add mods made for this version', bg=PANEL, fg=TEAL,
                 font=self.f_chip).pack(side='left', padx=(18, 0))
        tk.Frame(wrap, bg=LINE, height=1).pack(fill='x', padx=18)
        tk.Label(wrap, text='When two mods change the same file, the one lower in the list wins. Use ▲ ▼ or drag a mod to change the order.', bg=PANEL, fg=DIM,
                 font=self.f_small).pack(side='bottom', anchor='w', padx=18, pady=(0, 8))
        self.canvas = tk.Canvas(wrap, bg=PANEL, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True, padx=(14, 6), pady=10)
        self.list = tk.Frame(self.canvas, bg=PANEL)
        self.list.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        win = self.canvas.create_window((0, 0), window=self.list, anchor='nw')
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(win, width=e.width - 8))
        self.bind_all('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-e.delta / 120), 'units'))
        self.bind_all('<Button-4>', lambda e: self.canvas.yview_scroll(-1, 'units'))
        self.bind_all('<Button-5>', lambda e: self.canvas.yview_scroll(1, 'units'))

    def build_footer(self):
        # shortcut: colour sampled for the default window height, close enough when resized
        foot = tk.Frame(self, bg=self.bg_at(760 - 155))
        foot.place(x=36, rely=1, y=-188, relwidth=1, width=-72, height=58)
        self.apply_btn = Button(foot, 'APPLY', self.apply, 'teal', width=170, height=52, font=self.f_big)
        self.apply_btn.pack(side='left')
        self.play_btn = Button(foot, '▶   APPLY & PLAY', self.apply_and_play, 'gold', width=230, height=52, font=self.f_big)
        self.play_btn.pack(side='left', padx=14)
        self.spinner = Spinner(foot)
        self.spinner.pack(side='left')
        self.dirty_lbl = tk.Label(foot, text='', bg=foot['bg'], fg=AMBER, font=self.f_small)
        self.dirty_lbl.pack(side='left', padx=(6, 0))
        con = tk.Frame(self, bg='#040a09', highlightthickness=1, highlightbackground=LINE)
        con.place(x=36, rely=1, y=-122, relwidth=1, width=-72, height=92)
        tk.Label(con, text='LOG', bg='#040a09', fg=GOLD_DARK, font=self.f_chip).pack(anchor='w', padx=14, pady=(6, 0))
        self.console = tk.Text(con, bg='#040a09', fg=MUTED, font=self.f_mono, relief='flat', wrap='word',
                               padx=14, pady=2, highlightthickness=0, state='disabled')
        self.console.pack(fill='both', expand=True)
        for tag, col in (('info', MUTED), ('ok', TEAL), ('warn', AMBER), ('err', RED), ('time', DIM)):
            self.console.tag_configure(tag, foreground=col)

    # ---------- state
    def log(self, lines):
        self.console.configure(state='normal')
        for kind, text in lines:
            self.console.insert('end', time.strftime('%H:%M:%S  '), 'time')
            self.console.insert('end', text + '\n', kind)
        self.console.see('end')
        self.console.configure(state='disabled')

    def mark_dirty(self, dirty=True):
        self.dirty = dirty
        self.dirty_lbl.configure(text='◆  unapplied changes: click APPLY' if dirty else '')
        self.update_conflicts()
        if dirty:                                  # keep toggles and order even if the list is reloaded before APPLY
            im.save_state({c.mod.name for c in self.cards if not c.enabled}, [c.mod.name for c in self.cards])
        self.draw_stage()

    def shown(self):
        q = self.search.get().strip().lower()
        return [c for c in self.cards if q in c.mod.name.lower()]

    def same_file(self, f, g):
        if (f, g) not in self.same_cache:
            self.same_cache[f, g] = f.stat().st_size == g.stat().st_size and f.read_bytes() == g.read_bytes()
        return self.same_cache[f, g]

    def update_conflicts(self):
        """Files two enabled mods both change with a different content (an identical copy is not a conflict)."""
        owners = {}
        for c in self.cards:
            c.conflicts = {}
            if c.enabled:
                for path in c.files:
                    owners.setdefault(path, []).append(c)
        for path, cs in owners.items():
            for i, a in enumerate(cs):
                for b in cs[i + 1:]:
                    if not self.same_file(a.files[path], b.files[path]):
                        a.conflicts.setdefault(b, []).append(path)
                        b.conflicts.setdefault(a, []).append(path)
        for c in self.cards:
            c.draw()

    def show_conflicts(self, card):
        lines = [('warn', f'{card.mod.name}: conflicts (the mod lower in the list wins, change it with ▲ ▼ or drag):')]
        for other, paths in sorted(card.conflicts.items(), key=lambda kv: self.cards.index(kv[0])):
            win = max(card, other, key=self.cards.index).mod.name
            lines.append(('warn', f'   with {other.mod.name}: {len(paths)} file{"s" if len(paths) > 1 else ""} '
                                  f'(e.g. {paths[0]}), {win} wins'))
        self.log(lines)

    def drag_to(self, card, y_root):
        """Shows where the dragged card will land, and scrolls near the edges of the list."""
        others = [c for c in self.shown() if c is not card]
        if not others:
            return
        self.drop_at = sum(c.winfo_rooty() + c.H / 2 < y_root for c in others)
        if not getattr(self, 'drop_line', None) or not self.drop_line.winfo_exists():
            self.drop_line = tk.Frame(self.list, bg=GOLD_HI, height=3)
        ref = others[min(self.drop_at, len(others) - 1)]
        y = ref.winfo_y() - 3 if self.drop_at < len(others) else ref.winfo_y() + ref.H + 1
        self.drop_line.place(x=10, y=y, relwidth=1, width=-20, height=3)
        self.drop_line.lift()
        top = self.canvas.winfo_rooty()
        if y_root < top + 30:
            self.canvas.yview_scroll(-1, 'units')
        elif y_root > top + self.canvas.winfo_height() - 30:
            self.canvas.yview_scroll(1, 'units')

    def drop(self, card):
        if getattr(self, 'drop_line', None) and self.drop_line.winfo_exists():
            self.drop_line.place_forget()
        shown = self.shown()
        others = [c for c in shown if c is not card]
        at = getattr(self, 'drop_at', None)
        if at is None or not others or at == shown.index(card):
            return
        self.place_card(card, *((others[at], False) if at < len(others) else (others[-1], True)))

    def place_card(self, card, ref, after):
        """Moves card just before / after ref in the list, without rebuilding it (the list keeps its scroll)."""
        self.cards.remove(card)
        self.cards.insert(self.cards.index(ref) + after, card)
        card.pack_configure(**({'after': ref} if after else {'before': ref}))
        self.mark_dirty()                          # redraws every card: arrows and conflict winners changed

    def show_cards(self):
        shown = self.shown()
        for c in self.cards:
            c.pack_forget()
        if getattr(self, 'no_match', None):
            self.no_match.destroy()
            self.no_match = None
        for c in shown:
            c.pack(fill='x', pady=3)
            c.draw()                               # its arrows depend on its place in the list
        if self.cards and not shown:
            self.no_match = tk.Label(self.list, text=f'No mod matches "{self.search.get().strip()}".', bg=PANEL,
                                     fg=MUTED, font=self.f_small)
            self.no_match.pack(pady=30)
        self.canvas.yview_moveto(0)

    def move(self, card, d):
        """Moves a card one place up (-1) or down (1) among the cards on screen."""
        if card.can_move(d):
            shown = self.shown()
            self.place_card(card, shown[shown.index(card) + d], after=d > 0)

    def refresh(self):
        for w in self.list.winfo_children():
            w.destroy()
        off = im.disabled()
        self.cards, self.same_cache = [], {}
        mods = im.all_mods()
        if not mods:
            empty = tk.Frame(self.list, bg=PANEL)
            empty.pack(fill='x', pady=40)
            if self.img_emblem:
                tk.Label(empty, image=self.img_emblem, bg=PANEL).pack()
            tk.Label(empty, text='No mods yet', bg=PANEL, fg=TEXT, font=self.f_card).pack(pady=(8, 2))
            tk.Label(empty, text='Click "ADD MODS" or drop a mod (.zip, .7z, .rar) on this window.', bg=PANEL, fg=MUTED,
                     font=self.f_small).pack()
        self.cards = [ModCard(self, m, m.name not in off) for m in mods]
        self.no_match = None
        self.show_cards()
        self.mark_dirty(False)

    # ---------- actions
    def add_archives(self, paths=None):
        if paths is None:
            paths = filedialog.askopenfilenames(title='Choose one or more mods', filetypes=[
                ('Mod archives', ' '.join('*' + e for e in ARCHIVES)), ('All files', '*')])
        added, errors = [], []
        for p in paths:
            p = Path(p)
            if p.suffix.lower() not in ARCHIVES:
                errors.append(f'{p.name}: not a .zip, .7z or .rar file')
                continue
            dest = im.SOURCES / p.stem
            if dest.exists() and not messagebox.askyesno('Mod already exists', f'"{p.stem}" already exists. Replace it?'):
                continue
            tmp = im.SOURCES / f'_import_{p.stem}'
            shutil.rmtree(tmp, ignore_errors=True)
            try:
                tmp.mkdir()
                extract(p, tmp)
                if not im.find_romfs(tmp):
                    raise ValueError('no romfs folder inside (not a RomFS mod: the "i" button explains why)')
                shutil.rmtree(dest, ignore_errors=True)
                tmp.rename(dest)
                added.append(p.stem)
            except Exception as e:
                shutil.rmtree(tmp, ignore_errors=True)
                errors.append(f'{p.name}: {e}')
        if paths:
            self.refresh()
        if added:
            self.mark_dirty()
            self.log([('ok', f'Added {", ".join(added)}. Click APPLY to install.')])
        self.log([('err', e) for e in errors])

    def show_info(self):
        if getattr(self, 'info_win', None) and self.info_win.winfo_exists():
            self.info_win.lift()
            return
        win = self.info_win = tk.Toplevel(self, bg=PANEL, padx=30, pady=22)
        win.title('Supported mods')
        win.resizable(False, False)
        win.transient(self)
        tk.Label(win, text='◆  SUPPORTED MODS', bg=PANEL, fg=GOLD, font=self.f_section).pack(anchor='w')
        tk.Frame(win, bg=LINE, height=1).pack(fill='x', pady=(8, 4))
        for mark, col, head, text in INFO:
            if head:
                row = tk.Frame(win, bg=PANEL)
                row.pack(fill='x', pady=(14, 3))
                tk.Label(row, text=mark, bg=PANEL, fg=col, font=self.f_card).pack(side='left')
                tk.Label(row, text=head, bg=PANEL, fg=TEXT, font=self.f_card).pack(side='left', padx=(8, 0))
            tk.Label(win, text=text, bg=PANEL, fg=MUTED, font=self.f_body, wraplength=560, justify='left',
                     anchor='w').pack(fill='x', pady=(0 if head else 10, 0))
        Button(win, 'CLOSE', win.destroy, font=self.f_btn).pack(anchor='e', pady=(20, 0))
        win.after(10, lambda: self.dark_titlebar(win))

    def check_update(self):
        """Asks GitHub for the latest release in the background; silent when offline."""
        result = {}

        def work():
            try:
                result['tag'] = latest_release()
            except Exception:
                result['tag'] = None

        def poll():
            if 'tag' not in result:
                self.after(500, poll)
            elif result['tag'] and version_key(result['tag']) > version_key(VERSION):
                self.new_version = result['tag']
                self.log([('ok', f'Version {self.new_version} is available: click the notice at the top to download it.')])
                self.draw_stage()

        threading.Thread(target=work, daemon=True).start()
        poll()

    def set_all(self, on):
        """Turns on / off every mod on screen (only the search results while searching)."""
        changed = [c for c in self.shown() if c.enabled != on]
        for c in changed:
            c.enabled = on
            c.animate()
        if changed:
            self.mark_dirty()

    def open_folder(self):
        if hasattr(os, 'startfile'):
            os.startfile(im.SOURCES)
        else:
            subprocess.Popen(['xdg-open', str(im.SOURCES)])

    def remove(self, mod):
        if messagebox.askyesno('Delete mod', f'Permanently delete "{mod.name}"?'):
            shutil.rmtree(mod, ignore_errors=True)
            self.refresh()
            self.mark_dirty()
            self.log([('info', f'Deleted {mod.name}. Click APPLY to update the game.')])

    def make_shortcut(self):
        """Desktop shortcut with the rune icon that opens this window without a console."""
        if sys.platform != 'win32':
            return self.make_linux_shortcut()
        exe = Path(sys.executable)
        if exe.name.lower() == 'python.exe' and (exe.parent / 'pythonw.exe').is_file():
            exe = exe.parent / 'pythonw.exe'
        args = '' if FROZEN else f'\"{Path(__file__).resolve()}\"'
        icon = exe if FROZEN else ART / 'icon.ico'
        q = lambda s: str(s).replace("'", "''")
        ps = ("$d=[Environment]::GetFolderPath('Desktop');"
              "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'TOTK Recomp Mod Manager.lnk'));"
              f"$s.TargetPath='{q(exe)}';$s.Arguments='{q(args)}';"
              f"$s.WorkingDirectory='{q(ROOT)}';$s.IconLocation='{q(icon)}';"
              "$s.Description='TOTK Recomp Mod Manager';$s.Save()")
        r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps],
                           capture_output=True, text=True, creationflags=0x08000000)
        if r.returncode == 0:
            self.log([('ok', 'Shortcut "TOTK Recomp Mod Manager" added to your desktop.')])
        else:
            self.log([('err', f'Could not make the shortcut: {(r.stderr or r.stdout).strip()[:200]}')])

    def make_linux_shortcut(self):
        """App menu entry (+ desktop icon if there is a Desktop folder), as a freedesktop .desktop file."""
        home = Path.home()
        q = lambda s: '"' + ''.join('\\' + ch if ch in '"`$\\' else ch for ch in str(s)).replace('%', '%%') + '"'
        cmd = q(EXE) + ('' if FROZEN else ' ' + q(Path(__file__).resolve()))
        try:
            icon = home / '.local/share/icons/totk-recomp-mod-manager.png'   # the .exe's own art folder is temporary
            icon.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ART / 'icon256.png', icon)
            entry = ('[Desktop Entry]\nType=Application\nName=TOTK Recomp Mod Manager\n'
                     f'Comment=Mod manager for totk-pc-recomp\nExec={cmd}\nPath={ROOT}\nIcon={icon}\n'
                     'Terminal=false\nCategories=Game;\n')
            targets = [home / '.local/share/applications/totk-recomp-mod-manager.desktop']
            if (home / 'Desktop').is_dir():
                targets.append(home / 'Desktop' / 'TOTK Recomp Mod Manager.desktop')
            for t in targets:
                t.parent.mkdir(parents=True, exist_ok=True)
                t.write_text(entry, encoding='utf-8')
                t.chmod(0o755)
            where = 'your app menu and desktop' if len(targets) > 1 else 'your app menu'
            self.log([('ok', f'Shortcut "TOTK Recomp Mod Manager" added to {where}.')])
        except OSError as e:
            self.log([('err', f'Could not make the shortcut: {e}')])

    def apply(self, then=None):
        if self.busy:
            return
        self.busy = True
        im.save_state({c.mod.name for c in self.cards if not c.enabled}, [c.mod.name for c in self.cards])
        mods = [c.mod for c in self.cards if c.enabled]          # list order: the lowest one wins
        result = {}

        def work():
            try:
                result['ok'] = im.install(mods)
            except Exception as e:
                result['err'] = e

        threading.Thread(target=work, daemon=True).start()
        self.apply_btn.set_text('APPLYING…', enabled=False)
        self.play_btn.set_text('▶   APPLY & PLAY', enabled=False)
        self.spinner.start()

        def poll():
            if 'ok' not in result and 'err' not in result:
                self.after(100, poll)
                return
            self.busy = False
            self.spinner.stop()
            self.apply_btn.set_text('APPLY')
            self.play_btn.set_text('▶   APPLY & PLAY')
            if 'err' in result:
                self.log([('err', f'Error: {result["err"]}')])
                return
            warn, summary = result['ok']
            self.log([('ok', summary)] + [('warn', w) for w in warn])
            self.mark_dirty(False)
            if then:
                then()

        poll()

    def apply_and_play(self):
        self.apply(then=self.launch)

    def launch(self):
        # shortcut: Linux game file name guessed (the recomp's Linux build is new), add it here if it differs
        names = ['totk.exe'] if sys.platform == 'win32' else ['totk', 'totk.x86_64', 'totk.AppImage']
        exe = next((im.ROOT / n for n in names if (im.ROOT / n).is_file()), None)
        if not exe:
            self.log([('err', f'{" or ".join(names)} not found in {im.ROOT}')])
            return
        try:
            subprocess.Popen([str(exe)], cwd=im.ROOT)
            self.log([('ok', 'Game started. Have fun!')])
        except OSError as e:
            self.log([('err', f'Could not start {exe.name}: {e}')])


if __name__ == '__main__':
    App().mainloop()
