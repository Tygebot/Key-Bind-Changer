"""
hook_manager.py
----------------
Installs a Windows low-level keyboard hook (WH_KEYBOARD_LL) and injects
remapped keys with SendInput.

  * Normal mode: every physical key listed in the active profile's
    mapping is swallowed and replaced with its mapped key. Keys not
    in the mapping pass through untouched.
  * Typing mode: ALL remapping is suspended (full passthrough) until
    one of the configured "end typing" keys is pressed.
  * Capture mode: used by the GUI to ask "press the key you want this
    bound to" -- the next physical key press is intercepted, reported
    back to the GUI, and swallowed so it doesn't leak through.

Two correctness notes, because both have caused real, hard-to-spot bugs:

1. LRESULT is pointer-sized (64 bits on 64-bit Windows), not a plain C
   "long" (always 32 bits). If the hook callback's declared return type is
   too small, the high bits Windows reads back are garbage and the hook
   silently misbehaves -- it looks installed, but key events stop doing
   anything sensible. Every Win32 prototype below is declared explicitly
   with correctly pointer-sized types.

2. Synthetic input can be sent two ways: by virtual-key code (wVk), or by
   raw hardware scan code (wScan + KEYEVENTF_SCANCODE). Many games --
   especially ones using DirectInput or reading WM_INPUT raw input
   directly -- only recognize scan codes, since that's what a real
   keyboard actually sends. We inject by scan code (using MapVirtualKeyW
   to translate from the target VK), which is the more universally
   compatible method and is what most other key-remapping tools do.
"""

import ctypes
import logging
import threading
from ctypes import wintypes

from keymap import (
    EXTENDED_VKS, label_for,
    VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU,
    VK_LWIN, VK_RWIN, VK_SHIFT, VK_CONTROL, VK_MENU,
)

logger = logging.getLogger(__name__)

# Keys that act as "held" modifiers for the global show-window hotkey combo
# capture -- a combo finalizes on the first non-modifier keydown, recording
# whatever's held alongside it.
MODIFIER_VKS = {
    VK_LSHIFT, VK_RSHIFT, VK_SHIFT,
    VK_LCONTROL, VK_RCONTROL, VK_CONTROL,
    VK_LMENU, VK_RMENU, VK_MENU,
    VK_LWIN, VK_RWIN,
}

# If True, every single key event (including ones with no mapping) is logged
# at DEBUG level -- the most useful setting while diagnosing an issue, but
# noisy over a long play session. Flip to False to only log the interesting
# events (remaps performed, typing-mode toggles, hook install/failure).
LOG_EVERY_KEY_EVENT = True

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
LLKHF_INJECTED = 0x00000010
HC_ACTION = 0

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

MAPVK_VK_TO_VSC_EX = 4

# LRESULT = LONG_PTR: pointer-sized, NOT ctypes.c_long. See module docstring.
LRESULT = ctypes.c_ssize_t


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTunion(ctypes.Union):
    # IMPORTANT: this union must include all three real members (keyboard,
    # mouse, hardware), not just the keyboard one we actually use. Windows'
    # real INPUT struct is sized by its LARGEST member -- which is
    # MOUSEINPUT (32 bytes), not KEYBDINPUT (24 bytes). Leaving mi/hi out
    # makes ctypes compute too small a struct size, and SendInput silently
    # rejects every call with ERROR_INVALID_PARAMETER (87) because the
    # cbSize we pass doesn't match what it expects sizeof(INPUT) to be.
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTunion)]


LOWLEVELKEYBOARDPROC = ctypes.WINFUNCTYPE(
    LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

# Explicit prototypes for every Win32 call we use. HHOOK/HMODULE/WPARAM/LPARAM
# are all pointer-sized on 64-bit Windows -- leaving these unset makes ctypes
# assume a 32-bit "int", which truncates/corrupts them.
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, LOWLEVELKEYBOARDPROC, wintypes.HMODULE, wintypes.DWORD
]

user32.CallNextHookEx.restype = LRESULT
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]

user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]

user32.PostThreadMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

user32.GetMessageW.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]

user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]

user32.SendInput.restype = wintypes.UINT
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]

user32.MapVirtualKeyW.restype = wintypes.UINT
user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]


def _send_key(vk, key_up):
    """Injects a key event for virtual-key `vk`. Prefers scan-code-based
    injection (KEYEVENTF_SCANCODE) since that's what most games -- anything
    using DirectInput or reading WM_INPUT raw input -- actually listen for.
    Falls back to VK-based injection if Windows can't translate the VK to a
    scan code (rare)."""
    flags = KEYEVENTF_KEYUP if key_up else 0
    scan_ex = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC_EX)

    if scan_ex:
        scan_code = scan_ex & 0xFF
        extended = (scan_ex >> 8) in (0xE0, 0xE1)
        flags |= KEYEVENTF_SCANCODE
        if extended:
            flags |= KEYEVENTF_EXTENDEDKEY
        ki = KEYBDINPUT(wVk=0, wScan=scan_code, dwFlags=flags, time=0, dwExtraInfo=None)
        logger.debug(
            "  send_key: %s (vk=0x%02X) -> scancode 0x%02X (extended=%s) %s [scan-code injection]",
            label_for(vk), vk, scan_code, extended, "UP" if key_up else "DOWN",
        )
    else:
        if vk in EXTENDED_VKS:
            flags |= KEYEVENTF_EXTENDEDKEY
        ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=None)
        logger.debug(
            "  send_key: %s (vk=0x%02X) has no scancode mapping -> falling back to VK injection %s",
            label_for(vk), vk, "UP" if key_up else "DOWN",
        )

    inp = INPUT(type=INPUT_KEYBOARD, union=_INPUTunion(ki=ki))
    sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
    if sent != 1:
        logger.warning(
            "  send_key: SendInput FAILED for %s (vk=0x%02X, %s) -- returned %s, %s",
            label_for(vk), vk, "UP" if key_up else "DOWN", sent, ctypes.WinError(),
        )
    else:
        logger.debug("  send_key: SendInput OK for %s (vk=0x%02X, %s)",
                      label_for(vk), vk, "UP" if key_up else "DOWN")
    return sent == 1


# ---------------------------------------------------------------------------
# Shared, thread-safe state
# ---------------------------------------------------------------------------
class _State:
    def __init__(self):
        self.lock = threading.RLock()
        self.mapping = {}                 # physical_vk -> target_vk
        self.typing_mode = False
        self.start_vks = set()            # keys that ENTER typing mode
        self.end_vks = set()              # keys that EXIT typing mode
        self.capture_callback = None      # set by GUI to capture the next key
        self.suppress_keyup_for = set()   # vks whose keyup we must also swallow
        self.hook_installed = False
        self.last_error = None

        self.held_keys = set()            # every physical vk currently held down
        self.combo_capture_callback = None    # set by GUI to capture a hotkey chord
        self.show_window_hotkey = frozenset()  # configured chord, e.g. {VK_LCONTROL, VK_K}
        self.show_window_callback = None      # called when that chord is pressed
        self.kill_callback = None             # called when Shift+<that chord> is pressed


_state = _State()
_hook_thread = None


def set_active_mapping(mapping):
    """mapping: dict[int,int]. Pass {} to disable remapping (passthrough)."""
    with _state.lock:
        _state.mapping = dict(mapping)
    if mapping:
        pretty = ", ".join(f"{label_for(k)}->{label_for(v)}" for k, v in mapping.items())
        logger.info("Active remap SET: %d key(s) overridden: %s", len(mapping), pretty)
    else:
        logger.info("Active remap CLEARED: passthrough (no matching profile, or profile has no overrides)")


def set_typing_hotkeys(start_vks, end_vks):
    with _state.lock:
        _state.start_vks = set(start_vks)
        _state.end_vks = set(end_vks)
    logger.info(
        "Typing-mode hotkeys set -> start=%s end=%s",
        [label_for(v) for v in start_vks], [label_for(v) for v in end_vks],
    )


def set_typing_mode(value):
    """Manually force typing mode on/off (used by the tray icon menu)."""
    with _state.lock:
        _state.typing_mode = bool(value)
    logger.info("Typing mode manually set to %s", _state.typing_mode)


def toggle_typing_mode():
    with _state.lock:
        _state.typing_mode = not _state.typing_mode
        new_value = _state.typing_mode
    logger.info("Typing mode toggled to %s (via tray icon)", new_value)
    return new_value


def capture_next_key(callback):
    """callback(vk) is called from the hook thread on the next non-injected
    key press anywhere on the system. That key press is swallowed."""
    with _state.lock:
        _state.capture_callback = callback
    logger.debug("Waiting to capture the next physical key press...")


def cancel_capture():
    with _state.lock:
        _state.capture_callback = None
    logger.debug("Key capture cancelled.")


def capture_next_combo(callback):
    """callback(frozenset_of_vks) is called from the hook thread once the
    user finishes pressing a key combo (a non-modifier keydown while other
    keys may also be held) -- used for the global 'show window' hotkey.
    Unlike capture_next_key, this does NOT swallow the keys involved, since
    it's meant for a chord the person might also use elsewhere."""
    with _state.lock:
        _state.combo_capture_callback = callback
    logger.debug("Waiting to capture the next key combo...")


def cancel_combo_capture():
    with _state.lock:
        _state.combo_capture_callback = None
    logger.debug("Combo capture cancelled.")


def set_show_window_hotkey(vks):
    """vks: an iterable of VKs forming the chord (e.g. {VK_LCONTROL, VK_K}).
    Pass an empty iterable to disable it."""
    with _state.lock:
        _state.show_window_hotkey = frozenset(vks)
    if vks:
        logger.info("Global show-window hotkey set to: %s", "+".join(label_for(v) for v in vks))
    else:
        logger.info("Global show-window hotkey disabled.")


def set_show_window_callback(callback):
    """callback() is called (from the hook thread) whenever the configured
    show-window chord is detected. The callback itself must be thread-safe
    -- it should just queue something for the GUI thread to pick up."""
    with _state.lock:
        _state.show_window_callback = callback


def set_kill_callback(callback):
    """callback() is called (from the hook thread) whenever the show-window
    chord is pressed together with Shift -- e.g. if the show-window hotkey
    is Ctrl+Alt+K, this fires on Ctrl+Alt+Shift+K. Meant for fully quitting
    the app from anywhere, including from inside a game. Thread-safety
    rules are the same as set_show_window_callback."""
    with _state.lock:
        _state.kill_callback = callback


def get_status():
    with _state.lock:
        return {
            "typing_mode": _state.typing_mode,
            "hook_installed": _state.hook_installed,
            "last_error": _state.last_error,
        }


# ---------------------------------------------------------------------------
# Hook thread
# ---------------------------------------------------------------------------
class HookThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.hook_id = None
        self.win_thread_id = None
        self._proc_ref = None  # keep a reference alive so it isn't GC'd
        self._ready = threading.Event()

    def run(self):
        self.win_thread_id = kernel32.GetCurrentThreadId()
        logger.debug("Hook thread running (Windows thread id=%s). Installing hook...", self.win_thread_id)
        self._proc_ref = LOWLEVELKEYBOARDPROC(self._callback)
        self.hook_id = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._proc_ref, kernel32.GetModuleHandleW(None), 0
        )

        with _state.lock:
            _state.hook_installed = bool(self.hook_id)
            if not self.hook_id:
                _state.last_error = str(ctypes.WinError())
                logger.error("SetWindowsHookExW FAILED: %s", _state.last_error)
            else:
                logger.info("Low-level keyboard hook installed successfully (handle=%s).", self.hook_id)
        self._ready.set()

        if not self.hook_id:
            return

        logger.debug("Entering hook thread's Win32 message loop.")
        msg = wintypes.MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                logger.info("Hook thread message loop exiting (GetMessageW returned %s).", ret)
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _callback(self, nCode, wParam, lParam):
        if nCode == HC_ACTION:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            injected = bool(kb.flags & LLKHF_INJECTED)
            is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_up = wParam in (WM_KEYUP, WM_SYSKEYUP)

            if not injected:
                if self._process(vk, is_down, is_up):
                    return 1
        return user32.CallNextHookEx(self.hook_id, nCode, wParam, lParam)

    def _process(self, vk, is_down, is_up):
        """Returns True if the original key event should be swallowed.

        IMPORTANT: `vk` here is always the RAW physical key Windows reports
        for real hardware input -- see _callback above, which only ever
        calls _process() for non-injected events, and never for events we
        ourselves generated via _send_key()/SendInput. That means every
        check below (typing-mode start/end hotkeys, the remap mapping
        lookup, capture, the global show-window combo) is always comparing
        against the key the person actually pressed, never against
        whatever a remap might turn it into. This matters specifically for
        the typing-mode hotkeys: they must fire based on the physical key,
        not on some other key that happens to be remapped to produce the
        same vk -- and they do, because remapped/injected output never
        re-enters this function at all.
        """
        label = label_for(vk)
        kind = "KeyDown" if is_down else "KeyUp" if is_up else "Key?"

        with _state.lock:
            # 0. Always keep an accurate "what's currently held" set, for the
            #    global show-window combo capture/match below.
            if is_down:
                _state.held_keys.add(vk)
            elif is_up:
                _state.held_keys.discard(vk)

            # 1. Finish swallowing the key-up half of an already-consumed key.
            if is_up and vk in _state.suppress_keyup_for:
                _state.suppress_keyup_for.discard(vk)
                logger.debug("%s %s (0x%02X): swallowing matching key-up for previously-consumed key", kind, label, vk)
                return True

            # 2. Settings is waiting to capture a new global hotkey combo.
            #    Finalizes on the first non-modifier keydown; everything
            #    else (modifier presses/releases) just passes through
            #    untouched while a capture is pending.
            if _state.combo_capture_callback is not None:
                if is_down and vk not in MODIFIER_VKS:
                    combo = frozenset(_state.held_keys)
                    cb = _state.combo_capture_callback
                    _state.combo_capture_callback = None
                    logger.info("Combo captured: %s", "+".join(label_for(v) for v in combo))
                    cb(combo)
                    return True
                return False

            # 3. GUI is waiting to capture the next single key press.
            if _state.capture_callback is not None and is_down:
                cb = _state.capture_callback
                _state.capture_callback = None
                _state.suppress_keyup_for.add(vk)
                logger.info("%s %s (0x%02X): captured for GUI 'press a key' dialog", kind, label, vk)
                cb(vk)
                return True

            # 4. Global hotkeys -- checked regardless of typing mode/profile,
            #    and NOT suppressed (the key still reaches whatever else is
            #    listening too, in case it's also bound to something there;
            #    only our own action is added on top).
            #    - The configured chord alone shows the window.
            #    - The same chord PLUS Shift fully quits the app instead --
            #      e.g. if the chord is Ctrl+Alt+K, Ctrl+Alt+Shift+K quits.
            if is_down and vk not in MODIFIER_VKS and _state.show_window_hotkey:
                extra = _state.held_keys - _state.show_window_hotkey
                if extra == set():
                    logger.info("Global show-window hotkey triggered.")
                    cb = _state.show_window_callback
                    if cb is not None:
                        try:
                            cb()
                        except Exception:
                            logger.exception("show_window_callback raised an exception")
                elif extra in ({VK_LSHIFT}, {VK_RSHIFT}, {VK_SHIFT}):
                    logger.info("Global KILL hotkey (Shift+show-window chord) triggered.")
                    cb = _state.kill_callback
                    if cb is not None:
                        try:
                            cb()
                        except Exception:
                            logger.exception("kill_callback raised an exception")

            # 5. Typing mode: full passthrough, watch for an exit key. `vk`
            #    is the physical key (see docstring), so this only ever
            #    fires for the actual key the person pressed.
            if _state.typing_mode:
                if is_down and vk in _state.end_vks:
                    _state.typing_mode = False
                    logger.info("%s %s (0x%02X): END-typing hotkey -> typing mode now OFF", kind, label, vk)
                elif LOG_EVERY_KEY_EVENT:
                    logger.debug("%s %s (0x%02X): typing mode is ON -> passthrough", kind, label, vk)
                return False

            # 6. Normal mode: watch for the "enter typing mode" key (again,
            #    the physical key -- this check runs before any remap
            #    lookup below, so a remap can never stand in for it).
            if is_down and vk in _state.start_vks:
                _state.typing_mode = True
                _state.suppress_keyup_for.add(vk)
                logger.info("%s %s (0x%02X): START-typing hotkey -> typing mode now ON (swallowing this key)", kind, label, vk)
                return True

            # 7. Normal remap lookup.
            target = _state.mapping.get(vk)
            if target is None or target == vk:
                if LOG_EVERY_KEY_EVENT:
                    logger.debug("%s %s (0x%02X): no remap configured -> passthrough", kind, label, vk)
                return False

            target_label = label_for(target)
            if is_down:
                logger.info("%s %s (0x%02X): REMAPPING -> %s (0x%02X)", kind, label, vk, target_label, target)
                _send_key(target, key_up=False)
                return True
            if is_up:
                logger.info("%s %s (0x%02X): REMAPPING -> %s (0x%02X)", kind, label, vk, target_label, target)
                _send_key(target, key_up=True)
                return True
            return False

    def stop(self):
        if self.hook_id:
            user32.UnhookWindowsHookEx(self.hook_id)
            logger.info("Keyboard hook uninstalled.")
            self.hook_id = None
        if self.win_thread_id:
            user32.PostThreadMessageW(self.win_thread_id, WM_QUIT, 0, 0)


def start():
    global _hook_thread
    if _hook_thread is not None:
        logger.debug("start() called but hook thread is already running.")
        return
    _hook_thread = HookThread()
    _hook_thread.start()
    _hook_thread._ready.wait(timeout=2)


def stop():
    global _hook_thread
    if _hook_thread is not None:
        _hook_thread.stop()
        _hook_thread = None
