"""
theme.py
--------
Centralizes the color palette, fonts, and ttk styling. Supports a light and
dark palette plus a UI scale factor (accessibility: larger text/controls
for low-vision users).

apply(root, scale, dark) re-points every module-level color/font constant
(theme.TEXT, theme.FONT_NORMAL, etc.) at the new values and reconfigures
ttk.Style. Because ttk widgets look up their style by NAME at render time
(not by value at creation time), any existing ttk widget using a style
this function reconfigures updates live, automatically, with no rebuild
needed. The few plain tk widgets (Canvas, chip Frames/Labels) that read
theme.* constants directly still need an explicit redraw after calling
this -- gui.py's _apply_theme_live() handles that.
"""

import ctypes
import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)

FONT_FAMILY = "Segoe UI"

_LIGHT = dict(
    BG="#f4f5f7", PANEL="#ffffff", BORDER="#e1e4e8",
    TEXT="#1f2430", TEXT_MUTED="#6b7280",
    ACCENT="#2f6fed", ACCENT_LIGHT="#e8f0fe",
    KEY_FILL="#ffffff", KEY_BORDER="#d8dbe0", KEY_HOVER="#eef1f5",
    KEY_DISABLED_FILL="#f1f2f4",
    KEY_REMAP_FILL="#e8f0fe", KEY_REMAP_BORDER="#2f6fed",
    STATUS_BG="#eef0f3", STATUS_OK="#1f9d55", STATUS_WARN="#d97706", STATUS_BAD="#dc2626",
    CHIP_BG="#e8f0fe", CHIP_TEXT="#2f6fed", CHIP_CLOSE="#5b7bd1",
)

_DARK = dict(
    BG="#1b1d22", PANEL="#23262d", BORDER="#33363f",
    TEXT="#e7e9ee", TEXT_MUTED="#9aa0ad",
    ACCENT="#5b8dff", ACCENT_LIGHT="#293657",
    KEY_FILL="#2b2f38", KEY_BORDER="#3a3e48", KEY_HOVER="#343843",
    KEY_DISABLED_FILL="#26282e",
    KEY_REMAP_FILL="#293657", KEY_REMAP_BORDER="#5b8dff",
    STATUS_BG="#15171b", STATUS_OK="#2fbf71", STATUS_WARN="#e3a008", STATUS_BAD="#f0506e",
    CHIP_BG="#293657", CHIP_TEXT="#8fb4ff", CHIP_CLOSE="#6f88c2",
)

_BASE_FONT_SIZES = dict(NORMAL=10, SMALL=9, HEADING=15, CARD_HEADING=11, KEY=9, KEY_SMALL=8, SETTINGS_HEADING=12)

# Populated by apply() -- read these (theme.BG, theme.FONT_NORMAL, etc.) any
# time after the first apply() call, which main.py/gui.py do at startup.
BG = PANEL = BORDER = TEXT = TEXT_MUTED = ACCENT = ACCENT_LIGHT = None
KEY_FILL = KEY_BORDER = KEY_HOVER = KEY_DISABLED_FILL = None
KEY_REMAP_FILL = KEY_REMAP_BORDER = None
STATUS_BG = STATUS_OK = STATUS_WARN = STATUS_BAD = None
CHIP_BG = CHIP_TEXT = CHIP_CLOSE = None
FONT_NORMAL = FONT_SMALL = FONT_HEADING = FONT_CARD_HEADING = FONT_KEY = FONT_KEY_SMALL = None
FONT_KEY_BOLD = FONT_KEY_SMALL_BOLD = FONT_SETTINGS_HEADING = None

CURRENT_SCALE = 1.0
CURRENT_DARK = False

# Accessibility scale presets shown in Settings.
SCALE_OPTIONS = [1.0, 1.25, 1.5, 1.75, 2.0]


def _scaled(size, scale):
    return max(6, round(size * scale))


def apply(root, scale=1.0, dark=False):
    """Sets every theme.* constant for the given scale/dark settings,
    configures ttk.Style, and sets the root window's background."""
    global BG, PANEL, BORDER, TEXT, TEXT_MUTED, ACCENT, ACCENT_LIGHT
    global KEY_FILL, KEY_BORDER, KEY_HOVER, KEY_DISABLED_FILL
    global KEY_REMAP_FILL, KEY_REMAP_BORDER
    global STATUS_BG, STATUS_OK, STATUS_WARN, STATUS_BAD
    global CHIP_BG, CHIP_TEXT, CHIP_CLOSE
    global FONT_NORMAL, FONT_SMALL, FONT_HEADING, FONT_CARD_HEADING, FONT_KEY, FONT_KEY_SMALL
    global FONT_KEY_BOLD, FONT_KEY_SMALL_BOLD, FONT_SETTINGS_HEADING
    global CURRENT_SCALE, CURRENT_DARK

    CURRENT_SCALE = scale
    CURRENT_DARK = dark
    palette = _DARK if dark else _LIGHT

    BG, PANEL, BORDER = palette["BG"], palette["PANEL"], palette["BORDER"]
    TEXT, TEXT_MUTED = palette["TEXT"], palette["TEXT_MUTED"]
    ACCENT, ACCENT_LIGHT = palette["ACCENT"], palette["ACCENT_LIGHT"]
    KEY_FILL, KEY_BORDER, KEY_HOVER = palette["KEY_FILL"], palette["KEY_BORDER"], palette["KEY_HOVER"]
    KEY_DISABLED_FILL = palette["KEY_DISABLED_FILL"]
    KEY_REMAP_FILL, KEY_REMAP_BORDER = palette["KEY_REMAP_FILL"], palette["KEY_REMAP_BORDER"]
    STATUS_BG = palette["STATUS_BG"]
    STATUS_OK, STATUS_WARN, STATUS_BAD = palette["STATUS_OK"], palette["STATUS_WARN"], palette["STATUS_BAD"]
    CHIP_BG, CHIP_TEXT, CHIP_CLOSE = palette["CHIP_BG"], palette["CHIP_TEXT"], palette["CHIP_CLOSE"]

    FONT_NORMAL = (FONT_FAMILY, _scaled(_BASE_FONT_SIZES["NORMAL"], scale))
    FONT_SMALL = (FONT_FAMILY, _scaled(_BASE_FONT_SIZES["SMALL"], scale))
    FONT_HEADING = (FONT_FAMILY, _scaled(_BASE_FONT_SIZES["HEADING"], scale), "bold")
    FONT_CARD_HEADING = (FONT_FAMILY, _scaled(_BASE_FONT_SIZES["CARD_HEADING"], scale), "bold")
    FONT_KEY = (FONT_FAMILY, _scaled(_BASE_FONT_SIZES["KEY"], scale))
    FONT_KEY_SMALL = (FONT_FAMILY, _scaled(_BASE_FONT_SIZES["KEY_SMALL"], scale))
    FONT_KEY_BOLD = (FONT_FAMILY, _scaled(_BASE_FONT_SIZES["KEY"], scale), "bold")
    FONT_KEY_SMALL_BOLD = (FONT_FAMILY, _scaled(_BASE_FONT_SIZES["KEY_SMALL"], scale), "bold")
    FONT_SETTINGS_HEADING = (FONT_FAMILY, _scaled(_BASE_FONT_SIZES["SETTINGS_HEADING"], scale), "bold")

    root.configure(bg=BG)

    style = ttk.Style(root)
    # IMPORTANT: 'vista' renders buttons/checkboxes/comboboxes/scrollbars
    # natively through the OS theme engine and ignores style.configure()
    # color overrides almost entirely -- it only respects font changes.
    # That's fine (even nice) in light mode, but it means dark mode is
    # impossible under 'vista': those widgets would stay light no matter
    # what we configure. 'clam' is drawn entirely by Tk itself, so every
    # color below actually takes effect -- use it whenever dark is on.
    preferred = ("clam", "default") if dark else ("vista", "clam", "default")
    for theme_name in preferred:
        try:
            style.theme_use(theme_name)
            break
        except tk.TclError:
            continue

    # The ttk Combobox's dropdown POPUP is actually a plain Tk Listbox under
    # the hood, not a styleable ttk widget -- it has to go through Tk's
    # option database instead of style.configure().
    root.option_add("*TCombobox*Listbox.background", PANEL)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", "white")
    root.option_add("*TCombobox*Listbox.font", FONT_NORMAL)

    style.configure("TFrame", background=BG, relief="flat", borderwidth=0)
    style.configure("Card.TFrame", background=PANEL, relief="flat", borderwidth=0)

    style.configure("TLabel", background=BG, foreground=TEXT, font=FONT_NORMAL)
    style.configure("Muted.TLabel", background=BG, foreground=TEXT_MUTED, font=FONT_SMALL)
    style.configure("Heading.TLabel", background=BG, foreground=TEXT, font=FONT_HEADING)
    style.configure("SettingsHeading.TLabel", background=BG, foreground=TEXT, font=FONT_SETTINGS_HEADING)
    style.configure("CardHeading.TLabel", background=PANEL, foreground=TEXT, font=FONT_CARD_HEADING)
    style.configure("CardMuted.TLabel", background=PANEL, foreground=TEXT_MUTED, font=FONT_SMALL)
    style.configure("CardLabel.TLabel", background=PANEL, foreground=TEXT_MUTED, font=FONT_SMALL)

    style.configure("TButton", font=FONT_SMALL, padding=_scaled(6, scale),
                     background=PANEL, foreground=TEXT, bordercolor=BORDER, relief="flat")
    style.map("TButton",
              background=[("pressed", BORDER), ("active", KEY_HOVER)],
              foreground=[("disabled", TEXT_MUTED), ("active", TEXT), ("pressed", TEXT)])

    accent_font = (FONT_FAMILY, _scaled(9, scale), "bold")
    if dark:
        # clam (used in dark mode) actually draws the background we ask for,
        # so a real accent-colored button with white text looks right here.
        style.configure("Accent.TButton", font=accent_font, background=ACCENT, foreground="white", bordercolor=ACCENT)
        style.map("Accent.TButton",
                  background=[("pressed", ACCENT), ("active", ACCENT)],
                  foreground=[("pressed", "white"), ("active", "white")])
    else:
        # vista (light mode) renders the button face itself natively and
        # ignores our background color entirely -- it stays light no matter
        # what we configure. White text would be invisible against that, so
        # in light mode this is just a bold button with normal dark text
        # instead of a genuinely accent-colored one.
        style.configure("Accent.TButton", font=accent_font, foreground=TEXT)
        style.map("Accent.TButton", foreground=[("pressed", TEXT), ("active", TEXT)])

    style.configure("TEntry", font=FONT_NORMAL, padding=4,
                     fieldbackground=PANEL, foreground=TEXT, bordercolor=BORDER, insertcolor=TEXT)
    style.configure("TSeparator", background=BORDER)

    style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                     font=FONT_NORMAL, rowheight=_scaled(28, scale), borderwidth=0)
    style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
    style.configure("Treeview.Heading", font=FONT_SMALL)

    style.configure("TCheckbutton", background=BG, foreground=TEXT, font=FONT_NORMAL)
    style.configure("TRadiobutton", background=BG, foreground=TEXT, font=FONT_NORMAL)
    try:
        # clam-specific: the checkbox/radio indicator square has its own
        # fill/check-mark colors (indicatorbackground/indicatorforeground,
        # NOT "indicatorcolor" -- that name doesn't exist on this element),
        # separate from "foreground". Without this it stays white/light-grey
        # even once everything else is dark.
        #
        # The "active" (hover) state also needs its own background --
        # without it, hovering falls back to clam's own light default,
        # which makes the whole row flash white with the (still dark)
        # text/indicator becoming invisible against it.
        for cls in ("TCheckbutton", "TRadiobutton"):
            style.map(
                cls,
                background=[("active", BG)],
                indicatorbackground=[("selected", ACCENT), ("!selected", PANEL)],
                indicatorforeground=[("selected", "white"), ("!selected", TEXT)],
                upperbordercolor=[("!selected", BORDER)],
                lowerbordercolor=[("!selected", BORDER)],
            )
    except tk.TclError:
        pass

    style.configure("TCombobox", font=FONT_NORMAL, fieldbackground=PANEL,
                     background=PANEL, foreground=TEXT, arrowcolor=TEXT, bordercolor=BORDER)
    style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)])

    for orientation in ("Vertical", "Horizontal"):
        style.configure(f"{orientation}.TScrollbar", background=PANEL, troughcolor=BG,
                         bordercolor=BORDER, arrowcolor=TEXT)

    return style


# DWMWA_USE_IMMERSIVE_DARK_MODE: 20 on Windows 10 20H1+ / Windows 11, 19 on
# a couple of early Windows 10 dark-mode builds. Try both; harmless no-op
# everywhere else (older Windows, or if this somehow runs off-Windows).
_DWMWA_DARK_MODE_ATTRS = (20, 19)

try:
    ctypes.windll.user32.GetParent.restype = ctypes.c_void_p
    ctypes.windll.user32.GetParent.argtypes = [ctypes.c_void_p]
    ctypes.windll.dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long
    ctypes.windll.dwmapi.DwmSetWindowAttribute.argtypes = [
        ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint
    ]
except Exception:
    logger.debug("Couldn't declare DWM prototypes (non-Windows?)", exc_info=True)


def set_titlebar_dark(window, dark):
    """Best-effort: tells Windows' DWM to draw this specific window's
    native title bar (and surrounding chrome) in dark mode. ttk styling
    only reaches a window's CLIENT area -- the title bar itself is drawn
    by the OS and stays light by default no matter what we configure,
    which is most noticeable on dialogs (smaller windows = proportionally
    more title bar). Call this for the root window and every Toplevel.
    Silently does nothing if it's not supported (non-Windows, very old
    Windows, or the window isn't realized yet)."""
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        for attr in _DWMWA_DARK_MODE_ATTRS:
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result == 0:  # S_OK
                break
    except Exception:
        logger.debug("Couldn't set dark titlebar (non-fatal)", exc_info=True)
