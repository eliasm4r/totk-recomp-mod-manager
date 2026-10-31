"""TOTK Mod Manager v1.0.1 by Melio, for totk-pc-recomp: add mods (.zip), enable / disable them, apply, start the game.
Double-click to open. Uses install_mods.py and the art in mm_assets (same folder). Standard library only (tkinter)."""
import math
import os
import random
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox

FROZEN = getattr(sys, 'frozen', False)          # running as the .exe built by build_exe.bat
ROOT = Path(sys.executable if FROZEN else __file__).resolve().parent
ART = Path(getattr(sys, '_MEIPASS', ROOT)) / 'mm_assets'   # the .exe carries its art inside
sys.path.insert(0, str(ROOT))
try:
    import install_mods as im
except SystemExit as e:                     # no zstd: install_mods.py exits with a message
    tk.Tk().withdraw()
    messagebox.showerror('TOTK Mod Manager', str(e))
    raise

if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)                                   # crisp text
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('totk.modmanager')  # own taskbar icon
    except Exception:
        pass

VERSION, AUTHOR = 'v1.0.1', 'Melio'
DISCORD = 'konomelioda'      # contact for bug reports and requests

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


def mod_info(mod):
    """(file count, total bytes) for a mod folder."""
    romfs = next((p for p in sorted(mod.rglob('romfs'), key=lambda p: len(p.parts)) if p.is_dir()), None)
    files = [f for f in romfs.rglob('*') if f.is_file()] if romfs else []
    game = [f for f in files if 'ResourceSizeTable' not in f.name]
    return len(game), sum(f.stat().st_size for f in files)


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
    """One mod: rune badge, name, details, ACTIVE / DORMANT chip, Zonai switch, delete."""

    H = 78

    def __init__(self, app, mod, enabled):
        super().__init__(app.list, height=self.H, bg=PANEL, highlightthickness=0)
        self.app, self.mod, self.enabled, self.hover = app, mod, enabled, False
        self.pos = 1.0 if enabled else 0.0
        n, size = mod_info(mod)
        self.meta = f'{n} file{"s" if n != 1 else ""}  ·  {human(size)}'
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Enter>', lambda e: self.set_hover(True))
        self.bind('<Leave>', lambda e: self.set_hover(False))
        self.bind('<Motion>', self.motion)
        self.bind('<Button-1>', self.click)

    def zones(self):
        w = self.winfo_width()
        return (w - 128, w - 66), (w - 52, w - 14)    # switch x-range, delete x-range

    def draw(self):
        self.delete('all')
        a = self.app
        w, h = self.winfo_width(), self.H
        on = self.pos > 0.5
        edge = (TEAL if on else LINE_HI) if self.hover else (LINE_HI if on else LINE)
        self.create_polygon(chamfer(2, 3, w - 3, h - 4, 12), fill=CARD_HI if self.hover else CARD, outline=edge, width=1.2)
        if on:                                          # glowing spine on the left
            self.create_line(2, 16, 2, h - 17, fill=TEAL, width=3)
        badge = a.img_badge if on else a.img_badge_off
        if badge:
            self.create_image(38, h / 2, image=badge)
        self.create_text(70, h / 2 - 11, text=self.mod.name, anchor='w', fill=TEXT if on else MUTED, font=a.f_card)
        self.create_text(70, h / 2 + 13, text=self.meta, anchor='w', fill=MUTED if on else DIM, font=a.f_small)
        (sx0, sx1), (dx0, dx1) = self.zones()
        chip = 'ACTIVE' if on else 'DORMANT'           # status chip
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
        (sx0, sx1), (dx0, dx1) = self.zones()
        hot = 'del' if dx0 <= e.x <= dx1 else 'sw' if sx0 <= e.x <= sx1 else None
        self.configure(cursor='hand2' if hot else '')
        if hot != getattr(self, 'hot', None):
            self.hot = hot
            self.draw()

    def click(self, e):
        (sx0, sx1), (dx0, dx1) = self.zones()
        if dx0 <= e.x <= dx1:
            self.app.remove(self.mod)
        elif sx0 - 120 <= e.x <= sx1:                   # switch, or its status chip
            self.enabled = not self.enabled
            self.animate()
            self.app.mark_dirty()

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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'TOTK Mod Manager {VERSION}  ·  by {AUTHOR}')
        self.game_code, self.game_ver = im.game_version()
        self.geometry('1000x760')
        self.minsize(960, 640)
        self.configure(bg=BG)
        im.SOURCES.mkdir(exist_ok=True)
        self.cards, self.dirty, self.busy = [], False, False
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

    def dark_titlebar(self):
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
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
            c.create_text(146, 54, text='TOTK MOD MANAGER', anchor='w', fill=GOLD, font=self.f_title)
        spaced = lambda t: '   '.join(' '.join(word) for word in t.split())
        c.create_text(150, 96, text=f'{spaced("TEARS OF THE KINGDOM")}   ·   {spaced("PC RECOMP")}   ·   {spaced(VERSION)}',
                      anchor='w', fill=TEAL, font=self.f_sub)
        h = c.winfo_height()                       # credits along the bottom edge
        c.create_text(36, h - 12, text=f'Made by {AUTHOR}  ·  bugs & requests on Discord: {DISCORD}', anchor='w',
                      fill=DIM, font=self.f_small)
        c.create_text(w - 36, h - 12, text=f'TOTK Mod Manager {VERSION}', anchor='e', fill=GOLD_DARK, font=self.f_small)
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
        Button(bar, '＋   ADD MODS', self.add_zips, 'teal', font=self.f_btn).pack(side='left')
        Button(bar, 'OPEN FOLDER', lambda: os.startfile(im.SOURCES) if hasattr(os, 'startfile') else None,
               font=self.f_btn).pack(side='left', padx=10)
        Button(bar, '⟳   REFRESH', self.refresh, font=self.f_btn).pack(side='left')
        Button(bar, '◈   DESKTOP SHORTCUT', self.make_shortcut, font=self.f_btn).pack(side='left', padx=10)
        self.dirty_lbl = tk.Label(bar, text='', bg=bar['bg'], fg=AMBER, font=self.f_small)
        self.dirty_lbl.pack(side='right')

    def build_list(self):
        wrap = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        wrap.place(x=36, y=self.HEADER + 58, relwidth=1, width=-72, relheight=1, height=-(self.HEADER + 58 + 200))
        head = tk.Frame(wrap, bg=PANEL)
        head.pack(fill='x', padx=18, pady=(12, 8))
        tk.Label(head, text='◆  YOUR MODS', bg=PANEL, fg=GOLD, font=self.f_section).pack(side='left')
        tk.Label(head, text='on conflicts, the last mod in A→Z order wins', bg=PANEL, fg=DIM, font=self.f_small).pack(side='right')
        tk.Label(head, text=f'YOUR GAME: {self.game_ver}  ·  add mods made for this version', bg=PANEL, fg=TEAL,
                 font=self.f_chip).pack(side='left', padx=(18, 0))
        tk.Frame(wrap, bg=LINE, height=1).pack(fill='x', padx=18)
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
        self.dirty_lbl.configure(text='◆  unapplied changes' if dirty else '')
        self.draw_stage()

    def refresh(self):
        for w in self.list.winfo_children():
            w.destroy()
        off = im.disabled()
        self.cards = []
        mods = im.all_mods()
        if not mods:
            empty = tk.Frame(self.list, bg=PANEL)
            empty.pack(fill='x', pady=40)
            if self.img_emblem:
                tk.Label(empty, image=self.img_emblem, bg=PANEL).pack()
            tk.Label(empty, text='No mods yet', bg=PANEL, fg=TEXT, font=self.f_card).pack(pady=(8, 2))
            tk.Label(empty, text='Click "ADD MODS" to import your first mod (.zip).', bg=PANEL, fg=MUTED,
                     font=self.f_small).pack()
        for m in mods:
            card = ModCard(self, m, m.name not in off)
            card.pack(fill='x', pady=3)
            self.cards.append(card)
        self.mark_dirty(False)

    # ---------- actions
    def add_zips(self):
        paths = filedialog.askopenfilenames(title='Choose one or more mods', filetypes=[('Zip archives', '*.zip')])
        added, errors = [], []
        for p in paths:
            p = Path(p)
            dest = im.SOURCES / p.stem
            if dest.exists() and not messagebox.askyesno('Mod already exists', f'"{p.stem}" already exists. Replace it?'):
                continue
            tmp = im.SOURCES / f'_import_{p.stem}'
            shutil.rmtree(tmp, ignore_errors=True)
            try:
                tmp.mkdir()
                safe_extract(p, tmp)
                if not any(d.is_dir() for d in tmp.rglob('romfs')):
                    raise ValueError('no romfs folder inside (not a RomFS mod)')
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

    def remove(self, mod):
        if messagebox.askyesno('Delete mod', f'Permanently delete "{mod.name}"?'):
            shutil.rmtree(mod, ignore_errors=True)
            self.refresh()
            self.mark_dirty()
            self.log([('info', f'Deleted {mod.name}. Click APPLY to update the game.')])

    def make_shortcut(self):
        """Desktop shortcut with the rune icon that opens this window without a console."""
        if sys.platform != 'win32':
            self.log([('warn', 'Desktop shortcuts are only made on Windows.')])
            return
        exe = Path(sys.executable)
        if exe.name.lower() == 'python.exe' and (exe.parent / 'pythonw.exe').is_file():
            exe = exe.parent / 'pythonw.exe'
        args = '' if FROZEN else f'\"{Path(__file__).resolve()}\"'
        icon = exe if FROZEN else ART / 'icon.ico'
        q = lambda s: str(s).replace("'", "''")
        ps = ("$d=[Environment]::GetFolderPath('Desktop');"
              "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'TOTK Mod Manager.lnk'));"
              f"$s.TargetPath='{q(exe)}';$s.Arguments='{q(args)}';"
              f"$s.WorkingDirectory='{q(ROOT)}';$s.IconLocation='{q(icon)}';"
              "$s.Description='TOTK Mod Manager';$s.Save()")
        r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps],
                           capture_output=True, text=True, creationflags=0x08000000)
        if r.returncode == 0:
            self.log([('ok', 'Shortcut "TOTK Mod Manager" added to your desktop.')])
        else:
            self.log([('err', f'Could not make the shortcut: {(r.stderr or r.stdout).strip()[:200]}')])

    def apply(self, then=None):
        if self.busy:
            return
        self.busy = True
        off = {c.mod.name for c in self.cards if not c.enabled}
        im.set_disabled(off)
        mods = [m for m in im.all_mods() if m.name not in off]
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
        exe = im.ROOT / 'totk.exe'
        if exe.is_file():
            subprocess.Popen([str(exe)], cwd=im.ROOT)
            self.log([('ok', 'Game started. Have fun!')])
        else:
            self.log([('err', f'totk.exe not found in {im.ROOT}')])


if __name__ == '__main__':
    App().mainloop()
