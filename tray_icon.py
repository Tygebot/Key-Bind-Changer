"""
tray_icon.py
------------
System tray icon, built with pystray + Pillow.

Runs on its own background thread (pystray's normal usage pattern alongside
another GUI framework's main loop). None of its callbacks touch Tkinter
directly -- Tkinter is only safe to call into from its own thread -- so
"show the window" and "exit" just push a command onto the App's tray
queue, which the App's existing background poller already drains on a
timer. Toggling typing mode calls hook_manager directly, since that's
already thread-safe (see hook_manager._State.lock).
"""

import logging
import threading

import hook_manager

logger = logging.getLogger(__name__)

try:
    import pystray
    from PIL import Image, ImageDraw
    AVAILABLE = True
except Exception:  # broad on purpose: pystray can fail at import time for reasons
    # other than a missing package too (e.g. no usable backend on this system)
    logger.debug("pystray/Pillow unavailable -- tray icon will be disabled", exc_info=True)
    AVAILABLE = False


def build_icon_image(size=64):
    """A simple flat 'keyboard' glyph: a rounded accent-blue square with a
    couple of pale keycap rectangles. Legible at typical 16-32px tray sizes."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = max(2, size // 16)
    draw.rounded_rectangle((pad, pad, size - pad, size - pad), radius=size // 5, fill=(47, 111, 237, 255))

    key_w = size * 0.22
    key_h = size * 0.18
    gap = size * 0.06
    top = size * 0.32
    left0 = size * 0.20
    for col in range(3):
        x0 = left0 + col * (key_w + gap)
        draw.rounded_rectangle((x0, top, x0 + key_w, top + key_h), radius=size // 16, fill=(255, 255, 255, 235))
    bar_top = top + key_h + gap
    bar_w = key_w * 3 + gap * 2
    draw.rounded_rectangle((left0, bar_top, left0 + bar_w, bar_top + key_h), radius=size // 16, fill=(255, 255, 255, 235))
    return img


class TrayIcon:
    def __init__(self, app):
        self.app = app
        self._icon = None
        self._thread = None

    # -- menu actions (run on the tray's own thread) -----------------------
    def _on_show(self, icon, item):
        logger.debug("Tray: 'Show' clicked")
        self.app.queue_tray_command("show")

    def _on_toggle_typing(self, icon, item):
        hook_manager.toggle_typing_mode()

    def _typing_mode_checked(self, item):
        return hook_manager.get_status().get("typing_mode", False)

    def _on_exit(self, icon, item):
        logger.info("Tray: 'Exit' clicked")
        self.app.queue_tray_command("exit")
        icon.stop()

    # -- lifecycle -----------------------------------------------------------
    def start(self):
        if not AVAILABLE:
            logger.warning(
                "pystray/Pillow aren't installed -- system tray icon disabled. "
                "Run: pip install pystray Pillow"
            )
            return None

        menu = pystray.Menu(
            pystray.MenuItem("Show KeyBind Changer", self._on_show, default=True),
            pystray.MenuItem("Typing Mode", self._on_toggle_typing, checked=self._typing_mode_checked),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._on_exit),
        )
        self._icon = pystray.Icon("KeyBindChanger", build_icon_image(), "KeyBind Changer", menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
        logger.info("System tray icon started.")
        return self._icon

    def stop(self):
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                logger.debug("Tray icon stop() raised (likely already stopped)", exc_info=True)
