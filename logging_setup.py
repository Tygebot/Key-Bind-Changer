"""
logging_setup.py
-----------------
Configures Python's `logging` module so every module's logger.debug/info/
warning/error calls show up:

  * in the console, if one is attached (run `python main.py` from a
    terminal, not by double-clicking, to see this)
  * in a log file in the app's own folder (debug.log, next to config.json)
    -- this is written every run (overwritten each launch) so you always
    have a fresh log to look at or share after reproducing an issue.

Call configure() once, as early as possible. main.py does this before
importing anything else.
"""

import logging
import os
import sys

from profile_manager import CONFIG_DIR

LOG_PATH = os.path.join(CONFIG_DIR, "debug.log")


def configure(level=logging.DEBUG):
    os.makedirs(CONFIG_DIR, exist_ok=True)

    fmt = "%(asctime)s.%(msecs)03d [%(levelname)-7s] [%(name)s] %(message)s"
    datefmt = "%H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    # sys.stdout/sys.stderr are None (not just hidden) in a --windowed /
    # noconsole PyInstaller build -- StreamHandler(None) would crash on the
    # very first log call. Just skip the console handler in that case; the
    # file handler below still captures everything.
    if sys.stdout is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    file_handler = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.getLogger(__name__).info("Logging started (level=%s). Log file: %s",
                                       logging.getLevelName(level), LOG_PATH)
    return LOG_PATH
