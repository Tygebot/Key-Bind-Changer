"""
game_scanner.py
----------------
Two ways to bulk-discover games instead of adding them one at a time:

  * scan_steam_games()        -- finds Steam's install location (registry,
                                  falling back to common paths), reads
                                  libraryfolders.vdf to find every Steam
                                  library (including ones on other drives),
                                  and reads each game's .acf manifest for its
                                  real name and install folder.
  * scan_folder_for_games(p)  -- treats every immediate subfolder of `p` as
                                  one game (matches how Epic, GOG, and most
                                  custom game folders are laid out) and
                                  guesses each one's main executable.

Picking the "main" executable inside a game folder is inherently a
heuristic: most install folders contain several .exe files (launchers,
crash handlers, redistributable installers, dedicated servers, etc).
We exclude common non-game patterns and then pick the largest remaining
.exe, which works well in practice but isn't guaranteed -- the GUI always
shows the user what was found before anything is added, so it's easy to
skip or fix.

No GUI code here -- safe to call from a background thread.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

try:
    import winreg
except ImportError:  # not on Windows
    winreg = None

# Filename substrings that almost never belong to the actual game binary.
_DENY_SUBSTRINGS = [
    "unins", "crashpad", "crashreporter", "crash_report", "crashreport",
    "vc_redist", "vcredist", "dxsetup", "directx", "dotnetfx", "dotnet_",
    "easyanticheat", "eac_launcher", "eossdk", "battleye", "beservice",
    "redistributable", "redist", "prereqsetup", "prerequisites",
    "unitycrashhandler", "cefsubprocess", "cef_subprocess", "uninstall",
    "setup.exe", "installer.exe", "dependencies",
]


def _is_denied(filename_lower):
    return any(token in filename_lower for token in _DENY_SUBSTRINGS)


def guess_main_executable(folder, max_depth=6):
    """Walk `folder` (bounded depth) and return the path to the largest
    .exe that doesn't look like an installer/crash-handler/redistributable.
    Returns None if nothing plausible was found."""
    best_path, best_size = None, -1
    base_depth = os.path.normpath(folder).count(os.sep)

    for root, dirs, files in os.walk(folder):
        depth = os.path.normpath(root).count(os.sep) - base_depth
        if depth >= max_depth:
            dirs[:] = []  # don't descend further
        for fname in files:
            if not fname.lower().endswith(".exe"):
                continue
            if _is_denied(fname.lower()):
                logger.debug("  guess_main_executable: skipping '%s' (matches deny-list)", fname)
                continue
            full_path = os.path.join(root, fname)
            try:
                size = os.path.getsize(full_path)
            except OSError:
                continue
            if size > best_size:
                best_size, best_path = size, full_path

    if best_path:
        logger.debug("guess_main_executable('%s') -> %s (%d bytes)", folder, best_path, best_size)
    else:
        logger.debug("guess_main_executable('%s') -> no plausible .exe found", folder)
    return best_path


# ---------------------------------------------------------------------------
# Steam-specific discovery
# ---------------------------------------------------------------------------
def find_steam_install_path():
    """Returns Steam's install directory, or None if it can't be found."""
    candidates = []

    if winreg is not None:
        for hive, subkey, value in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        ):
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    path, _ = winreg.QueryValueEx(key, value)
                    candidates.append(path.replace("/", "\\"))
            except OSError:
                pass

    candidates += [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam"]

    for path in candidates:
        if path and os.path.isdir(path):
            logger.info("Found Steam install at: %s", path)
            return path
    logger.info("Couldn't locate a Steam installation (checked: %s)", candidates)
    return None


def find_steam_library_folders(steam_path):
    """Returns every Steam library root (the folder that directly contains
    a 'steamapps' subfolder), including steam_path itself."""
    libraries = [steam_path]
    vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
    if os.path.isfile(vdf_path):
        try:
            with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for match in re.finditer(r'"path"\s*"([^"]+)"', content):
                lib_path = match.group(1).replace("\\\\", "\\")
                if os.path.isdir(lib_path) and lib_path not in libraries:
                    libraries.append(lib_path)
        except OSError:
            pass
    logger.info("Steam library folders: %s", libraries)
    return libraries


def find_installed_steam_games(library_paths):
    """Reads each library's .acf manifests and returns
    [{"display_name", "exe_path", "exe_name"}, ...]."""
    games = []
    seen_appids = set()

    for library in library_paths:
        steamapps = os.path.join(library, "steamapps")
        if not os.path.isdir(steamapps):
            continue
        try:
            manifest_files = [f for f in os.listdir(steamapps) if f.lower().endswith(".acf")]
        except OSError:
            continue

        for manifest_name in manifest_files:
            manifest_path = os.path.join(steamapps, manifest_name)
            try:
                with open(manifest_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except OSError:
                continue

            name_match = re.search(r'"name"\s*"([^"]+)"', content)
            installdir_match = re.search(r'"installdir"\s*"([^"]+)"', content)
            appid_match = re.search(r'"appid"\s*"([^"]+)"', content)
            if not (name_match and installdir_match):
                continue

            appid = appid_match.group(1) if appid_match else manifest_name
            if appid in seen_appids:
                continue
            seen_appids.add(appid)

            game_dir = os.path.join(steamapps, "common", installdir_match.group(1))
            if not os.path.isdir(game_dir):
                logger.debug("Manifest '%s' points to missing folder %s -- skipping", manifest_name, game_dir)
                continue

            exe_path = guess_main_executable(game_dir)
            if exe_path:
                logger.info("Steam game found: '%s' -> %s", name_match.group(1), exe_path)
                games.append({
                    "display_name": name_match.group(1),
                    "exe_path": exe_path,
                    "exe_name": os.path.basename(exe_path),
                })
            else:
                logger.debug("Steam game '%s' has no plausible executable in %s -- skipping", name_match.group(1), game_dir)

    return games


def scan_steam_games():
    """Returns None if Steam couldn't be located, otherwise a (possibly
    empty) list of discovered games."""
    steam_path = find_steam_install_path()
    if not steam_path:
        return None
    libraries = find_steam_library_folders(steam_path)
    return find_installed_steam_games(libraries)


# ---------------------------------------------------------------------------
# Generic folder discovery
# ---------------------------------------------------------------------------
def scan_folder_for_games(root_path):
    """Treats each immediate subfolder of root_path as one game and guesses
    its main executable. Good fit for Epic/GOG/custom game library folders."""
    games = []
    try:
        subfolders = [
            name for name in os.listdir(root_path)
            if os.path.isdir(os.path.join(root_path, name))
        ]
    except OSError:
        return games

    for name in subfolders:
        folder = os.path.join(root_path, name)
        exe_path = guess_main_executable(folder)
        if exe_path:
            games.append({
                "display_name": name,
                "exe_path": exe_path,
                "exe_name": os.path.basename(exe_path),
            })

    return games

