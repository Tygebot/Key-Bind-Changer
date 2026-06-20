"""
keymap.py
---------
Windows Virtual-Key (VK) code constants and the full-keyboard layout
definition used by the GUI to draw the keyboard and by the hook to
translate physical key presses.

Reference: https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
"""

# ---------------------------------------------------------------------------
# Virtual-Key constants (subset covering a full US keyboard)
# ---------------------------------------------------------------------------
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12          # Alt
VK_PAUSE = 0x13
VK_CAPITAL = 0x14       # Caps Lock
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_PRIOR = 0x21         # Page Up
VK_NEXT = 0x22          # Page Down
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_SNAPSHOT = 0x2C      # Print Screen
VK_INSERT = 0x2D
VK_DELETE = 0x2E

VK_0, VK_1, VK_2, VK_3, VK_4 = 0x30, 0x31, 0x32, 0x33, 0x34
VK_5, VK_6, VK_7, VK_8, VK_9 = 0x35, 0x36, 0x37, 0x38, 0x39

VK_A, VK_B, VK_C, VK_D, VK_E, VK_F, VK_G = 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47
VK_H, VK_I, VK_J, VK_K, VK_L, VK_M, VK_N = 0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E
VK_O, VK_P, VK_Q, VK_R, VK_S, VK_T, VK_U = 0x4F, 0x50, 0x51, 0x52, 0x53, 0x54, 0x55
VK_V, VK_W, VK_X, VK_Y, VK_Z = 0x56, 0x57, 0x58, 0x59, 0x5A

VK_LWIN = 0x5B
VK_RWIN = 0x5C

VK_NUMPAD0, VK_NUMPAD1, VK_NUMPAD2, VK_NUMPAD3, VK_NUMPAD4 = 0x60, 0x61, 0x62, 0x63, 0x64
VK_NUMPAD5, VK_NUMPAD6, VK_NUMPAD7, VK_NUMPAD8, VK_NUMPAD9 = 0x65, 0x66, 0x67, 0x68, 0x69
VK_MULTIPLY = 0x6A
VK_ADD = 0x6B
VK_SUBTRACT = 0x6D
VK_DECIMAL = 0x6E
VK_DIVIDE = 0x6F

VK_F1, VK_F2, VK_F3, VK_F4 = 0x70, 0x71, 0x72, 0x73
VK_F5, VK_F6, VK_F7, VK_F8 = 0x74, 0x75, 0x76, 0x77
VK_F9, VK_F10, VK_F11, VK_F12 = 0x78, 0x79, 0x7A, 0x7B

VK_NUMLOCK = 0x90
VK_SCROLL = 0x91

VK_LSHIFT, VK_RSHIFT = 0xA0, 0xA1
VK_LCONTROL, VK_RCONTROL = 0xA2, 0xA3
VK_LMENU, VK_RMENU = 0xA4, 0xA5     # Left/Right Alt

VK_OEM_1 = 0xBA       # ; :
VK_OEM_PLUS = 0xBB    # = +
VK_OEM_COMMA = 0xBC   # , <
VK_OEM_MINUS = 0xBD   # - _
VK_OEM_PERIOD = 0xBE  # . >
VK_OEM_2 = 0xBF       # / ?
VK_OEM_3 = 0xC0       # ` ~
VK_OEM_4 = 0xDB       # [ {
VK_OEM_5 = 0xDC       # \ |
VK_OEM_6 = 0xDD       # ] }
VK_OEM_7 = 0xDE       # ' "

# Keys that require the KEYEVENTF_EXTENDEDKEY flag when injected with SendInput.
EXTENDED_VKS = {
    VK_RCONTROL, VK_RMENU, VK_INSERT, VK_DELETE, VK_HOME, VK_END,
    VK_PRIOR, VK_NEXT, VK_UP, VK_DOWN, VK_LEFT, VK_RIGHT,
    VK_NUMLOCK, VK_SNAPSHOT, VK_RWIN, VK_LWIN, VK_DIVIDE,
}

# ---------------------------------------------------------------------------
# Human-readable labels (also used as the "display name" for a VK code)
# ---------------------------------------------------------------------------
VK_TO_LABEL = {
    VK_BACK: "Backspace", VK_TAB: "Tab", VK_RETURN: "Enter", VK_SHIFT: "Shift",
    VK_CONTROL: "Ctrl", VK_MENU: "Alt", VK_PAUSE: "Pause", VK_CAPITAL: "Caps Lock",
    VK_ESCAPE: "Esc", VK_SPACE: "Space", VK_PRIOR: "Page Up", VK_NEXT: "Page Down",
    VK_END: "End", VK_HOME: "Home", VK_LEFT: "Left", VK_UP: "Up", VK_RIGHT: "Right",
    VK_DOWN: "Down", VK_SNAPSHOT: "Print Screen", VK_INSERT: "Insert", VK_DELETE: "Delete",
    VK_LWIN: "Win (L)", VK_RWIN: "Win (R)",
    VK_MULTIPLY: "Num *", VK_ADD: "Num +", VK_SUBTRACT: "Num -",
    VK_DECIMAL: "Num .", VK_DIVIDE: "Num /",
    VK_NUMLOCK: "Num Lock", VK_SCROLL: "Scroll Lock",
    VK_LSHIFT: "Shift (L)", VK_RSHIFT: "Shift (R)",
    VK_LCONTROL: "Ctrl (L)", VK_RCONTROL: "Ctrl (R)",
    VK_LMENU: "Alt (L)", VK_RMENU: "Alt (R)",
    VK_OEM_1: ";", VK_OEM_PLUS: "=", VK_OEM_COMMA: ",", VK_OEM_MINUS: "-",
    VK_OEM_PERIOD: ".", VK_OEM_2: "/", VK_OEM_3: "`", VK_OEM_4: "[",
    VK_OEM_5: "\\", VK_OEM_6: "]", VK_OEM_7: "'",
}
for _i in range(10):
    VK_TO_LABEL[VK_0 + _i] = str(_i)
    VK_TO_LABEL[VK_NUMPAD0 + _i] = f"Num {_i}"
for _i, _c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    VK_TO_LABEL[VK_A + _i] = _c
for _i in range(1, 13):
    VK_TO_LABEL[0x70 + _i - 1] = f"F{_i}"


def label_for(vk):
    return VK_TO_LABEL.get(vk, f"VK_{vk:#x}")


# ---------------------------------------------------------------------------
# Layout rows for the GUI.  Each entry is (label, vk, column_span).
# A (None, None, span) entry is a blank spacer of that width.
# ---------------------------------------------------------------------------
MAIN_ROWS = [
    [("Esc", VK_ESCAPE, 1), (None, None, 1),
     ("F1", VK_F1, 1), ("F2", VK_F2, 1), ("F3", VK_F3, 1), ("F4", VK_F4, 1), (None, None, 1),
     ("F5", VK_F5, 1), ("F6", VK_F6, 1), ("F7", VK_F7, 1), ("F8", VK_F8, 1), (None, None, 1),
     ("F9", VK_F9, 1), ("F10", VK_F10, 1), ("F11", VK_F11, 1), ("F12", VK_F12, 1)],

    [("`", VK_OEM_3, 1), ("1", VK_1, 1), ("2", VK_2, 1), ("3", VK_3, 1), ("4", VK_4, 1),
     ("5", VK_5, 1), ("6", VK_6, 1), ("7", VK_7, 1), ("8", VK_8, 1), ("9", VK_9, 1),
     ("0", VK_0, 1), ("-", VK_OEM_MINUS, 1), ("=", VK_OEM_PLUS, 1), ("Backspace", VK_BACK, 2)],

    [("Tab", VK_TAB, 2), ("Q", VK_Q, 1), ("W", VK_W, 1), ("E", VK_E, 1), ("R", VK_R, 1),
     ("T", VK_T, 1), ("Y", VK_Y, 1), ("U", VK_U, 1), ("I", VK_I, 1), ("O", VK_O, 1),
     ("P", VK_P, 1), ("[", VK_OEM_4, 1), ("]", VK_OEM_6, 1), ("\\", VK_OEM_5, 2)],

    [("Caps Lock", VK_CAPITAL, 2), ("A", VK_A, 1), ("S", VK_S, 1), ("D", VK_D, 1),
     ("F", VK_F, 1), ("G", VK_G, 1), ("H", VK_H, 1), ("J", VK_J, 1), ("K", VK_K, 1),
     ("L", VK_L, 1), (";", VK_OEM_1, 1), ("'", VK_OEM_7, 1), ("Enter", VK_RETURN, 2)],

    [("Shift", VK_LSHIFT, 2), ("Z", VK_Z, 1), ("X", VK_X, 1), ("C", VK_C, 1), ("V", VK_V, 1),
     ("B", VK_B, 1), ("N", VK_N, 1), ("M", VK_M, 1), (",", VK_OEM_COMMA, 1),
     (".", VK_OEM_PERIOD, 1), ("/", VK_OEM_2, 1), ("Shift", VK_RSHIFT, 2)],

    [("Ctrl", VK_LCONTROL, 1), ("Win", VK_LWIN, 1), ("Alt", VK_LMENU, 1),
     ("Space", VK_SPACE, 6), ("Alt", VK_RMENU, 1), ("Win", VK_RWIN, 1), ("Ctrl", VK_RCONTROL, 1)],
]

NAV_ROWS = [
    [("PrtSc", VK_SNAPSHOT, 1), ("ScrLk", VK_SCROLL, 1), ("Pause", VK_PAUSE, 1)],
    [("Ins", VK_INSERT, 1), ("Home", VK_HOME, 1), ("PgUp", VK_PRIOR, 1)],
    [("Del", VK_DELETE, 1), ("End", VK_END, 1), ("PgDn", VK_NEXT, 1)],
    [(None, None, 1), (None, None, 1), (None, None, 1)],
    [(None, None, 1), ("Up", VK_UP, 1), (None, None, 1)],
    [("Left", VK_LEFT, 1), ("Down", VK_DOWN, 1), ("Right", VK_RIGHT, 1)],
]

NUMPAD_ROWS = [
    [("NumLk", VK_NUMLOCK, 1), ("/", VK_DIVIDE, 1), ("*", VK_MULTIPLY, 1), ("-", VK_SUBTRACT, 1)],
    [("7", VK_NUMPAD7, 1), ("8", VK_NUMPAD8, 1), ("9", VK_NUMPAD9, 1), ("+", VK_ADD, 1)],
    [("4", VK_NUMPAD4, 1), ("5", VK_NUMPAD5, 1), ("6", VK_NUMPAD6, 1), (None, None, 1)],
    [("1", VK_NUMPAD1, 1), ("2", VK_NUMPAD2, 1), ("3", VK_NUMPAD3, 1), ("Enter", VK_RETURN, 1)],
    [("0", VK_NUMPAD0, 2), (".", VK_DECIMAL, 1), (None, None, 1)],
]

# All VKs that appear anywhere on the keyboard map (used to seed identity profiles).
ALL_LAYOUT_VKS = sorted({
    vk for rows in (MAIN_ROWS, NAV_ROWS, NUMPAD_ROWS) for row in rows
    for (_label, vk, _span) in row if vk is not None
})
