"""
main.py
-------
Entry point. Run with:

    python main.py

Run this from a terminal (not by double-clicking) if you want to see the
debug output live -- everything is also written to
%APPDATA%\\KeyBindChanger\\debug.log regardless of how it's launched.
"""

import logging_setup
LOG_PATH = logging_setup.configure()

import ctypes
import logging
import sys
import tkinter as tk
import tkinter.messagebox as messagebox

import hook_manager
import process_watcher
import tray_icon
from gui import App

logger = logging.getLogger(__name__)

# ShellExecuteW's return value is a legacy overload: > 32 means success
# (an instance handle), <= 32 is an error code. Declaring this as c_void_p
# would convert a literal 0 result into Python None, which breaks a plain
# integer comparison -- c_ssize_t always comes back as a real int.
ctypes.windll.shell32.ShellExecuteW.restype = ctypes.c_ssize_t


def _is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        logger.exception("Couldn't determine elevation status")
        return None


def _relaunch_as_admin():
    """Attempts to relaunch this script elevated. Returns True if the
    relaunch was actually started (caller should exit), False if the user
    cancelled the UAC prompt or it failed for some other reason."""
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller .exe: sys.executable IS this program, so
        # only forward any *extra* args, not argv[0] (the exe's own path).
        args = sys.argv[1:]
    else:
        # Running as `python main.py`: sys.executable is python.exe, and
        # argv[0] (main.py) is the script it needs to be told to run.
        args = sys.argv
    params = " ".join(f'"{a}"' for a in args)
    logger.info("Requesting elevated relaunch: %s %s", sys.executable, params)
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    # > 32 means success (an instance handle); <= 32 means it failed or was
    # cancelled at the UAC prompt (e.g. error code 1223 = ERROR_CANCELLED).
    if result <= 32:
        logger.warning("Elevated relaunch did not start (ShellExecuteW returned %s) -- "
                        "likely cancelled at the UAC prompt.", result)
        return False
    logger.info("Elevated relaunch started successfully.")
    return True


def _maybe_relaunch_as_admin(parent):
    is_admin = _is_admin()
    logger.info("Running as Administrator: %s", is_admin)
    if is_admin:
        return False

    want_restart = messagebox.askyesno(
        "Not running as Administrator",
        "KeyBind Changer is not running as Administrator.\n\n"
        "Many games (and most anti-cheat systems) run elevated. If this app "
        "isn't elevated too, Windows will silently block its remapped keys "
        "from ever reaching the game -- this is one of the most common "
        "reasons remapping doesn't work in a specific game.\n\n"
        "Restart as Administrator now?",
        parent=parent,
    )
    if not want_restart:
        logger.info("User declined to restart as Administrator; continuing without elevation.")
        return False

    if _relaunch_as_admin():
        return True

    messagebox.showinfo(
        "Continuing without elevation",
        "Okay, continuing without Administrator rights. You can restart "
        "this app as Administrator later if remapping doesn't reach a game.",
        parent=parent,
    )
    return False


def main():
    logger.info("=== KeyBind Changer starting (debug log: %s) ===", LOG_PATH)

    if sys.platform != "win32":
        logger.error("Unsupported platform: %s. This app only runs on Windows.", sys.platform)
        if sys.stdout is not None:
            print("KeyBind Changer only runs on Windows (it uses the Win32 keyboard hook API).")
        sys.exit(1)

    temp_root = tk.Tk()
    temp_root.withdraw()
    relaunching = _maybe_relaunch_as_admin(temp_root)
    temp_root.destroy()
    if relaunching:
        logger.info("Exiting this (non-elevated) instance in favor of the elevated relaunch.")
        return

    logger.info("Starting keyboard hook...")
    hook_manager.start()
    status = hook_manager.get_status()
    logger.info("Hook status after start(): %s", status)
    if not status.get("hook_installed"):
        messagebox.showerror(
            "Keyboard hook failed to install",
            "KeyBind Changer couldn't install its keyboard hook, so remapping, "
            "typing mode, and key-capture dialogs will not work.\n\n"
            f"Windows reported: {status.get('last_error')}\n\n"
            "Try re-launching as Administrator, or check whether antivirus/"
            "security software is blocking low-level keyboard hooks.\n\n"
            f"Full details were written to:\n{LOG_PATH}",
        )

    logger.info("Building GUI...")
    app = App()

    logger.info("Starting system tray icon...")
    tray = tray_icon.TrayIcon(app)
    app.tray_icon = tray.start()  # may be None if pystray/Pillow aren't installed

    logger.info("Starting process watcher...")
    watcher = process_watcher.ProcessWatcher(app.queue_process_change)
    watcher.start()

    def full_shutdown():
        logger.info("=== Shutting down ===")
        watcher.stop()
        hook_manager.stop()
        tray.stop()
        app.destroy()

    app.full_shutdown = full_shutdown
    app.protocol("WM_DELETE_WINDOW", app.minimize_to_tray)
    logger.info("Entering Tkinter main loop.")
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Unhandled exception -- app is crashing")
        raise
