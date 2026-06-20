"""
profile_manager.py
-------------------
Reads/writes the JSON config file that stores:
  * One keybind profile per game .exe (only the keys that differ from
    "maps to itself" are stored, so a brand-new profile is an empty dict).
  * Typing-mode hotkeys, which can be set per-game (each profile gets its
    own start/end hotkeys, seeded from the Default when the profile is
    created) -- plus one top-level "Default" set used whenever no game
    profile is active (e.g. on the desktop), or as the starting point for
    new profiles.

Config lives in the app's own folder (next to main.py when run from
source, or next to the .exe when built with PyInstaller) -- not
%APPDATA% -- so the whole app, profiles included, is portable: copy the
folder anywhere (a USB drive, another PC) and it keeps working with the
same profiles. If that folder turns out not to be writable (e.g. the app
was placed in Program Files without admin rights), this falls back to
the old %APPDATA%\\KeyBindChanger location instead of crashing. Any config
already sitting at that old location (from before this app-folder
behavior existed) is migrated automatically the first time, so upgrading
doesn't lose existing profiles.
"""

import json
import logging
import os
import shutil
import sys

from keymap import VK_ESCAPE, VK_RETURN, VK_SCROLL

logger = logging.getLogger(__name__)


def _app_dir():
    if getattr(sys, "frozen", False):
        # Built with PyInstaller: store next to the actual .exe, not the
        # temporary extraction folder PyInstaller runs from.
        return os.path.dirname(sys.executable)
    # Running from source: store next to this file (i.e. next to main.py --
    # all our modules live in the same folder), regardless of the current
    # working directory the app happened to be launched from.
    return os.path.dirname(os.path.abspath(__file__))


def _old_appdata_dir():
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "KeyBindChanger")


def _pick_config_dir():
    candidate = _app_dir()
    try:
        os.makedirs(candidate, exist_ok=True)
        probe = os.path.join(candidate, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return candidate
    except OSError:
        # Can't print/log a fully-configured message yet (logging may not
        # be set up this early) -- the directory actually used is already
        # reported by load_config()'s own log lines below.
        return _old_appdata_dir()


CONFIG_DIR = _pick_config_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "typing_hotkeys": {
        "start": [VK_SCROLL],
        "end": [VK_ESCAPE, VK_RETURN],
    },
    "settings": {
        "ui_scale": 1.0,            # 1.0 = 100%, accessibility text/UI size
        "dark_mode": False,
        "show_game_icons": True,
        "show_window_hotkey": [],   # list of VKs forming a chord, e.g. [VK_LCONTROL, VK_LMENU, VK_K]
    },
    # profiles is keyed by the lowercase exe filename, e.g. "valorant-win64-shipping.exe"
    "profiles": {},
}


def _migrate_old_appdata_config():
    """One-time migration: if there's no config yet at the new (app-folder)
    location but there IS one at the old %APPDATA% location from a previous
    version of this app, copy it over so upgrading doesn't lose profiles."""
    old_path = os.path.join(_old_appdata_dir(), "config.json")
    if os.path.exists(CONFIG_PATH) or old_path == CONFIG_PATH or not os.path.exists(old_path):
        return
    try:
        shutil.copy2(old_path, CONFIG_PATH)
        logger.info("Migrated existing config from old location %s to %s", old_path, CONFIG_PATH)
    except OSError as exc:
        logger.warning("Found an old config at %s but couldn't migrate it (%s) -- starting fresh.", old_path, exc)


def load_config():
    _migrate_old_appdata_config()
    if not os.path.exists(CONFIG_PATH):
        logger.info("No existing config found -- creating a fresh one at %s", CONFIG_PATH)
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
        save_config(cfg)
        return cfg
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        logger.info("Loaded config from %s", CONFIG_PATH)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Couldn't read config (%s) -- starting from defaults.", exc)
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))

    cfg.setdefault("typing_hotkeys", json.loads(json.dumps(DEFAULT_CONFIG["typing_hotkeys"])))
    cfg["typing_hotkeys"].setdefault("start", [VK_SCROLL])
    cfg["typing_hotkeys"].setdefault("end", [VK_ESCAPE, VK_RETURN])
    cfg.setdefault("profiles", {})

    # Backward-compat: older config files have no "settings" section at all.
    cfg.setdefault("settings", json.loads(json.dumps(DEFAULT_CONFIG["settings"])))
    settings = cfg["settings"]
    settings.setdefault("ui_scale", 1.0)
    settings.setdefault("dark_mode", False)
    settings.setdefault("show_game_icons", True)
    settings.setdefault("show_window_hotkey", [])
    settings["ui_scale"] = float(settings["ui_scale"])
    settings["show_window_hotkey"] = [int(v) for v in settings["show_window_hotkey"]]

    # JSON object keys for "mappings" come back as strings -- normalize to int->int.
    for profile in cfg["profiles"].values():
        profile["mappings"] = {int(k): int(v) for k, v in profile.get("mappings", {}).items()}
        profile.setdefault("exe_path", None)

        # Backward-compat: older config files have no per-profile typing
        # hotkeys at all -- seed them from the Default so upgrades are
        # seamless, then each profile can be customized independently.
        th = profile.get("typing_hotkeys") or {}
        th.setdefault("start", list(cfg["typing_hotkeys"]["start"]))
        th.setdefault("end", list(cfg["typing_hotkeys"]["end"]))
        profile["typing_hotkeys"] = {
            "start": [int(v) for v in th["start"]],
            "end": [int(v) for v in th["end"]],
        }

    logger.info("Config has %d saved profile(s): %s", len(cfg["profiles"]),
                [p["display_name"] for p in cfg["profiles"].values()])
    return cfg


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    logger.debug("Config saved to %s", CONFIG_PATH)


def get_profile(cfg, exe_name):
    """Case-insensitive lookup. Returns the profile dict or None."""
    if not exe_name:
        return None
    profile = cfg["profiles"].get(exe_name.lower())
    if profile is None:
        logger.debug("get_profile('%s'): no saved profile for this process", exe_name)
    else:
        logger.debug("get_profile('%s'): matched profile '%s' (%d override(s))",
                     exe_name, profile["display_name"], len(profile.get("mappings", {})))
    return profile


def add_profile(cfg, exe_name, display_name, exe_path=None):
    key = exe_name.lower()
    cfg["profiles"][key] = {
        "exe_name": exe_name,
        "display_name": display_name,
        "exe_path": exe_path,  # best-effort, only used to show an icon -- process matching is by exe_name
        "mappings": {},
        "typing_hotkeys": {
            "start": list(cfg["typing_hotkeys"]["start"]),
            "end": list(cfg["typing_hotkeys"]["end"]),
        },
    }
    save_config(cfg)
    logger.info("Added profile '%s' for executable '%s'", display_name, exe_name)
    return key


def remove_profile(cfg, exe_key):
    removed = cfg["profiles"].pop(exe_key, None)
    save_config(cfg)
    logger.info("Removed profile '%s'", removed["display_name"] if removed else exe_key)


def set_mapping(cfg, exe_key, physical_vk, target_vk):
    profile = cfg["profiles"].get(exe_key)
    if profile is None:
        logger.warning("set_mapping called for unknown profile key '%s' -- ignoring", exe_key)
        return
    if target_vk == physical_vk:
        profile["mappings"].pop(physical_vk, None)
        logger.info("Profile '%s': key 0x%02X reset to default", profile["display_name"], physical_vk)
    else:
        profile["mappings"][physical_vk] = target_vk
        logger.info("Profile '%s': key 0x%02X -> 0x%02X", profile["display_name"], physical_vk, target_vk)
    save_config(cfg)


def reset_all_mappings(cfg, exe_key):
    profile = cfg["profiles"].get(exe_key)
    if profile is None:
        return
    profile["mappings"] = {}
    save_config(cfg)
    logger.info("Profile '%s': all keys reset to default", profile["display_name"])


def build_mapping_dict(profile):
    """Returns the physical_vk -> target_vk dict the hook should use."""
    if profile is None:
        return {}
    return dict(profile.get("mappings", {}))


def get_typing_hotkeys(cfg, exe_key):
    """Returns (start_vks, end_vks) for the given profile key. exe_key=None
    (or a key with no saved profile) returns the Default (no-game) set."""
    profile = cfg["profiles"].get(exe_key) if exe_key else None
    th = profile["typing_hotkeys"] if profile else cfg["typing_hotkeys"]
    return list(th.get("start", [])), list(th.get("end", []))


def get_settings(cfg):
    return cfg["settings"]


def set_setting(cfg, key, value):
    cfg["settings"][key] = value
    save_config(cfg)
    logger.info("Setting '%s' changed to %s", key, value)


def set_typing_hotkeys(cfg, exe_key, start_vks, end_vks):
    """exe_key=None edits the Default (no-game) hotkeys; otherwise edits
    that specific profile's own hotkeys."""
    if exe_key is None:
        cfg["typing_hotkeys"] = {"start": list(start_vks), "end": list(end_vks)}
        logger.info("Default typing hotkeys set -> start=%s end=%s", start_vks, end_vks)
    else:
        profile = cfg["profiles"].get(exe_key)
        if profile is None:
            logger.warning("set_typing_hotkeys called for unknown profile key '%s' -- ignoring", exe_key)
            return
        profile["typing_hotkeys"] = {"start": list(start_vks), "end": list(end_vks)}
        logger.info("Profile '%s': typing hotkeys set -> start=%s end=%s",
                    profile["display_name"], start_vks, end_vks)
    save_config(cfg)
