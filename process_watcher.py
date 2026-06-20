"""
process_watcher.py
-------------------
Polls the foreground window every `poll_interval` seconds and reports the
owning process's executable name whenever it changes. This is what triggers
the automatic profile switch when you alt-tab into a game (or out of it).

It also checks whether the foreground process is running elevated
(as Administrator) and compares that against whether THIS app is elevated.
If the game is elevated and we're not, Windows' UIPI security feature will
silently block our injected key events from ever reaching it -- this is one
of the two most common reasons "remapping doesn't work in this game", so
it's worth surfacing loudly in the log rather than failing silently.

Only needs `psutil` -- the foreground-window lookup and elevation check are
done with plain ctypes so we don't need the full pywin32 package.
"""

import ctypes
import logging
import threading
import time
from ctypes import wintypes

import psutil

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
advapi32 = ctypes.windll.advapi32

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TOKEN_ELEVATION_CLASS = 20  # TokenElevation, from the TOKEN_INFORMATION_CLASS enum

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

advapi32.OpenProcessToken.restype = wintypes.BOOL
advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
advapi32.GetTokenInformation.restype = wintypes.BOOL
advapi32.GetTokenInformation.argtypes = [
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)
]


class _TOKEN_ELEVATION(ctypes.Structure):
    _fields_ = [("TokenIsElevated", wintypes.DWORD)]


def is_current_process_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        logger.exception("Couldn't determine our own elevation status")
        return None


def _is_process_elevated(pid):
    """Returns True/False, or None if it couldn't be determined (e.g. the
    process is protected and refuses even a limited-info query)."""
    h_process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h_process:
        logger.debug("OpenProcess failed for pid %s: %s", pid, ctypes.WinError())
        return None
    try:
        h_token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(h_process, TOKEN_QUERY, ctypes.byref(h_token)):
            logger.debug("OpenProcessToken failed for pid %s: %s", pid, ctypes.WinError())
            return None
        try:
            elevation = _TOKEN_ELEVATION()
            returned = wintypes.DWORD()
            ok = advapi32.GetTokenInformation(
                h_token, TOKEN_ELEVATION_CLASS, ctypes.byref(elevation),
                ctypes.sizeof(elevation), ctypes.byref(returned),
            )
            if not ok:
                logger.debug("GetTokenInformation failed for pid %s: %s", pid, ctypes.WinError())
                return None
            return bool(elevation.TokenIsElevated)
        finally:
            kernel32.CloseHandle(h_token)
    finally:
        kernel32.CloseHandle(h_process)


def _get_foreground_process():
    """Returns (name, pid, exe_path). Any of the three can be None if it
    couldn't be determined."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, None, None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None, None, None
    try:
        proc = psutil.Process(pid.value)
        return proc.name(), pid.value, proc.exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
        logger.debug("Couldn't read process info for pid %s: %s", pid.value, exc)
        return None, pid.value, None


class ProcessWatcher(threading.Thread):
    def __init__(self, on_change, poll_interval=0.4):
        super().__init__(daemon=True)
        self.on_change = on_change
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._last_name = object()  # sentinel guarantees first tick always fires
        self._we_are_admin = is_current_process_admin()
        logger.info("This app is running elevated (Administrator): %s", self._we_are_admin)

    def run(self):
        logger.info("Process watcher started (polling every %.1fs).", self.poll_interval)
        while not self._stop_event.is_set():
            name, pid, exe_path = _get_foreground_process()
            if name != self._last_name:
                self._last_name = name
                if name and pid:
                    self._check_elevation(name, pid)
                try:
                    self.on_change(name, exe_path)
                except Exception:
                    logger.exception("on_change callback raised an exception")
            time.sleep(self.poll_interval)
        logger.info("Process watcher stopped.")

    def _check_elevation(self, name, pid):
        elevated = _is_process_elevated(pid)
        if elevated is None:
            logger.debug("Couldn't determine elevation status of %s -- if remapping doesn't reach "
                          "it, try running this app as Administrator just in case.", name)
        elif elevated and not self._we_are_admin:
            logger.warning(
                "*** %s IS RUNNING AS ADMINISTRATOR, BUT THIS APP IS NOT. ***  Windows will block "
                "this app's injected keys from reaching it (UIPI). This is the most common reason "
                "remapping silently doesn't work for a specific game. Restart KeyBind Changer as "
                "Administrator to fix this.", name,
            )
        else:
            logger.debug("%s elevated=%s, this app elevated=%s -- no UIPI conflict expected.",
                         name, elevated, self._we_are_admin)

    def stop(self):
        self._stop_event.set()
