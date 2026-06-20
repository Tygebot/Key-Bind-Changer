# KeyBind Changer

A per-game keyboard remapper for Windows. Keep a different key-binding layout
for every game on your computer -- the layout switches automatically based on
whichever game window is currently focused.

## Features

- **Accessibility Settings** (gear icon, top right) -- adjustable text/UI
  scale (100-200%), a dark mode, and an optional global hotkey that brings
  the window to the front from anywhere, even while it's hidden in the
  tray. See "Accessibility & Settings" below.
- **Full keyboard map UI** -- every key on a standard keyboard is shown and
  clickable, drawn as a clean rounded-key board (not raw OS buttons). By
  default every key sends itself; remapped keys are highlighted in blue,
  with the key it now sends shown in **bold** under the original.
- **System tray icon** -- closing the window doesn't quit the app; it keeps
  running in the background (and remapping) and lives in the system tray.
  Right-click the tray icon for "Show KeyBind Changer", a "Typing Mode"
  toggle, and "Exit". Double-click (or its default action) reopens the
  window.
- **Per-game profiles** -- add a game's `.exe` once, then remap any key just
  for that game. Switching between games (or back to the desktop) swaps the
  active layout automatically, with no manual switching required. Optional
  per-game icons (shown next to each name, like Steam's library) -- toggle
  in Settings.
- **Bulk game discovery** -- three ways to add several games at once,
  instead of one at a time:
  - **Scan Steam Library** automatically locates your Steam install (and
    every library folder, even on other drives) and adds every installed
    game it can find a main executable for.
  - **Scan Custom Folder...** does the same for any folder where each
    subfolder is a game (Epic, GOG, or your own organization).
  - **Add Recent Program...** lists up to the 10 most recent programs
    KeyBind Changer has seen in the foreground this session (most recent
    first, with icons) -- pick the ones that are games.

  All three show a review list before adding anything, so you can deselect
  anything that got guessed wrong.
- **Typing mode** -- a dedicated hotkey temporarily disables ALL remapping so
  you can type normally (e.g. in an in-game chat box or Discord overlay).
  Press the configured "end typing" key(s) to resume remapping. Each game
  has its own typing-mode hotkeys (shown as removable "chips"), separate
  from every other game's, plus one Default set used whenever no game is
  detected. New profiles start out with a copy of the Default.
  Out of the box, the Default is **Scroll Lock** to start typing mode and
  **Escape** or **Enter** to end it. These hotkeys always match the
  physical key pressed -- never a key that's merely remapped to look the
  same, and never a key a remap produces as output.

## Accessibility & Settings

Click **⚙ Settings** (top right) for:

- **Text & UI size** -- 100/125/150/175/200%. Scales fonts, the keyboard,
  buttons, and the window itself, live, with no restart needed.
- **Dark mode** -- applies immediately across the whole app.
- **Show game icons in the profile list** -- pulls each game's actual icon
  (the same one Explorer/Steam shows) next to its name. On by default; if
  an icon can't be extracted (e.g. the profile was added before its exe
  path was known), the game still shows up fine, just without an icon.
- **Global Hotkey** -- click **Set Hotkey...**, then hold a combination
  (e.g. Ctrl+Alt+K) and release. That combination will bring this window
  to the front from anywhere on your system, even while it's hidden in the
  tray or you're in a game -- it does **not** consume/block the keys
  involved, so it's safe to use even if that combination is also bound to
  something in a game. Not set by default. **Clear** removes it.
  Press it together with **Shift** to quit KeyBind Changer entirely
  (e.g. Ctrl+Alt+Shift+K if the hotkey is set to Ctrl+Alt+K) -- a fast way
  to fully stop remapping and exit without digging through the tray icon.

## Requirements


- Windows 10/11
- Python 3.9+
- Dependencies: [`psutil`](https://pypi.org/project/psutil/) (process detection),
  [`pystray`](https://pypi.org/project/pystray/) (system tray icon), and
  [`Pillow`](https://pypi.org/project/Pillow/) (tray icon + per-game icons
  in the profile list). `pystray`/`Pillow` are optional -- the app still
  runs fine without them, it just can't minimize to the tray or show game
  icons.

```
pip install -r requirements.txt
```

## Running it

```
python main.py
```

**Run it as Administrator if you can** (right-click your terminal/IDE and
choose "Run as administrator", or right-click `main.py` and "Run as
administrator" if you've associated `.py` files with `python.exe`).
Windows prevents a non-elevated process from sending input to an elevated
one (this is called UIPI). Many games — especially ones with anti-cheat —
run elevated, so if KeyBind Changer isn't elevated too, your remaps may
silently fail to reach the game.

## How to use it

1. Click **Add Game...** and browse to the game's `.exe` (often inside its
   install folder, e.g. `...\Steam\steamapps\common\<Game>\<Game>.exe`).
   Give it a display name.
2. With the profile selected, click any key on the keyboard map and press
   the key you want it to send instead. Click **Reset to Default** in that
   dialog to make a key behave normally again.
3. Launch the game. The status bar at the bottom of the window will show
   the detected process and which profile is active. Your remap takes
   effect automatically as soon as the game window has focus, and reverts
   automatically when you switch away from it.
4. While in-game, tap your **Start typing mode** key (Scroll Lock by
   default) before typing in chat, then press **Escape** or **Enter** (or
   whatever you've configured) when you're done to resume normal remapping.
   Each game profile has its own typing-mode hotkeys -- edit them in the
   "Typing Mode Hotkeys" card under the keyboard while that profile is
   selected, or select nothing to edit the Default ones used when no game
   is detected.

All profiles and settings are saved to `config.json` right next to
`main.py` (or, in a built .exe, right next to `KeyBindChanger.exe`) --
not `%APPDATA%`. This makes the whole app portable: copy the folder (or
the .exe) anywhere, including a USB drive or another PC, and your
profiles come with it. If that folder somehow isn't writable, it falls
back to the old `%APPDATA%\KeyBindChanger\` location automatically, and a
config already there from a previous version is migrated to the new
location the first time you run this version.

## Building a standalone .exe

The two `.bat` files turn this into a single downloadable `KeyBindChanger.exe`
that runs without needing Python installed, using [PyInstaller](https://pyinstaller.org/).

**This has to be run on Windows** -- PyInstaller bundles the actual Windows
Python interpreter and native libraries into the executable, so it can't be
cross-built from Linux/macOS; it has to run on the same OS it's building for.

1. Make sure Python and the dependencies in `requirements.txt` are installed.
2. Double-click **`build_exe.bat`** (or run it from a terminal in this folder).
   It installs PyInstaller if needed, then builds.
3. Your executable is at `dist\KeyBindChanger.exe` -- copy it anywhere and
   run it directly. `config.json` and `debug.log` will be created right
   next to wherever you put it.

This build has no console window (so logging only goes to `debug.log`, not
a visible terminal). If you want a build that keeps a console window open
so you can watch the live log while testing, use **`build_exe_debug.bat`**
instead -- it produces `dist\KeyBindChanger-debug.exe`.

Either way, `debug.log` next to the exe (or `main.py`) is always written
regardless of which build you use or how you launch it.

## System tray behavior

Closing the main window (the X button) does **not** quit the app -- it
hides the window and keeps running in the background, still remapping
keys for whatever game is focused. You'll see a one-time notification the
first time this happens. To get the window back, click the tray icon (its
default action) or right-click it and choose "Show KeyBind Changer". To
actually quit, right-click the tray icon and choose "Exit" -- this is the
only way to fully stop the app and its keyboard hook.

The tray icon's right-click menu also has a "Typing Mode" checkbox, so you
can toggle typing mode without reaching for the keyboard shortcut.

If `pystray`/`Pillow` aren't installed, the tray icon is silently disabled
and closing the window falls back to quitting normally, so the app is
still fully usable without them -- just without the background-tray
behavior.

## Bulk-adding games

- **Scan Steam Library**: finds Steam via the registry (or common install
  paths), reads `libraryfolders.vdf` to find every library you have (even on
  other drives), and reads each game's manifest for its real name. For each
  game it guesses the main executable by picking the largest `.exe` in that
  game's folder, skipping obvious installers/crash-handlers/redistributables.
  You'll get a review list to confirm before anything is added.
- **Scan Custom Folder...**: point it at any folder where each subfolder is
  one game (e.g. your Epic Games or GOG Games folder) and it applies the
  same executable-guessing heuristic per subfolder.
- The executable guess is a heuristic, not a guarantee -- always glance over
  the review list before clicking "Add Selected". If one's wrong, just
  remove that profile afterward and use **Add Game...** to point at the
  correct `.exe` directly.

## Diagnosing "remapping doesn't work in this game"

This app now logs every decision it makes to `debug.log` (right next to
`main.py` or the `.exe`, overwritten each run) and to the console if you
launch it from a terminal. If a key isn't remapping in-game, this is the
fastest way to find out why:

1. Launch the game, get into a spot where you can safely tap the key you
   remapped, and tap it a few times.
2. Open `debug.log` (next to `main.py`/the `.exe`) and look near the end. For
   each key press you should see one of:
   - `REMAPPING -> ...` followed by `send_key: ... SendInput OK` -- the app
     did its job correctly. If the game still doesn't react, the game
     itself is filtering out synthetic input (see below).
   - `SendInput FAILED` -- Windows refused to inject the key. This is
     almost always a UIPI/elevation mismatch (see #1 below).
   - Nothing at all for that key press -- the hook isn't seeing the game's
     keyboard input. Check `hook_installed` near the top of the log.
3. Also check for a line like `*** <game.exe> IS RUNNING AS ADMINISTRATOR,
   BUT THIS APP IS NOT ***` -- if you see this, that's almost certainly
   your answer.

The two realistic causes once the log shows `REMAPPING` and `SendInput OK`
but the game still doesn't respond:

1. **Elevation mismatch (UIPI).** If the game (or its anti-cheat) runs as
   Administrator and this app doesn't, Windows silently blocks synthetic
   input from reaching it. The app now offers to restart itself elevated
   on launch, and the process watcher actively checks for this mismatch
   and warns in the log every time you switch into an elevated game.
2. **The game ignores synthetic input entirely.** Some games -- usually
   ones with strict anti-cheat, or ones reading input straight from the
   raw HID device rather than through the normal Windows input stack --
   distinguish real hardware keystrokes from software-injected ones and
   discard the latter outright, regardless of which API was used to send
   them. There's no way to fix this from a regular Windows process; it
   requires a kernel-mode driver (the open-source **Interception** driver
   is the standard tool here) that makes the injected input indistinguishable
   from a real device at the driver level. That would be a bigger change
   to the project (swapping `SendInput` for Interception's driver API) --
   let me know if it comes to that and we can take it from there.

## Changelog

- **Added:** Shift+ the global hotkey (e.g. Ctrl+Alt+Shift+K if the
  hotkey is Ctrl+Alt+K) now fully quits KeyBind Changer from anywhere --
  the same clean shutdown as the tray icon's "Exit", just reachable
  without leaving a game.
- **Fixed:** "Remove Selected" (and potentially other buttons, depending
  on which one happened to have keyboard focus) could render with
  invisible text in light mode. This was a *different* state than the
  hover/pressed issue fixed earlier -- a button that's focused (shown
  with a dotted focus rectangle) but not currently hovered or clicked.
  Since this is native OS chrome under the `vista` theme that we can't
  reliably recolor, all buttons now skip keyboard-focus traversal
  entirely (they're simple one-click actions, not form fields, so this
  isn't a meaningful loss) -- which sidesteps the broken state rather
  than trying to restyle it.

- **Fixed:** typing-mode hotkey chips ("Scroll Lock ×", "+ Add", etc.)
  showed a white border/background after switching to dark mode live.
  Cause: the chips themselves were recreated with the right dark colors
  on a theme change, but the (persistent, not recreated) frame holding
  them kept its original light background -- which peeked through around
  the edges of the freshly-dark chips, looking like a white border. That
  container frame's color is now updated too whenever the theme changes.
- **Fixed:** "+ Add Game..." and, depending on hover state, other buttons
  could render with invisible text in light mode. Cause: `vista` (light
  mode's theme) draws the button face itself and ignores our background
  color entirely, so the white text configured for the accent button had
  nothing but a light native background to sit on. The accent button now
  uses normal dark text in light mode (still bold, for emphasis) and only
  becomes a genuinely accent-colored button with white text in dark mode
  (where `clam` actually draws the background we ask for). Hover/pressed
  states across all buttons now also set their text color explicitly as a
  safeguard against the same class of issue.

- **Changed:** profiles and settings (`config.json`) and the debug log
  now live in the app's own folder -- right next to `main.py` or the
  built `.exe` -- instead of `%APPDATA%\KeyBindChanger\`. This makes the
  whole app portable (copy the folder/exe anywhere and your profiles come
  with it). Falls back to the old `%APPDATA%` location if the app's own
  folder isn't writable, and automatically migrates an existing config
  from there the first time you run this version, so upgrading doesn't
  lose anything.

- **Fixed:** dialogs (Add from Recent Programs, Settings, etc.) still
  showed a lot of white in dark mode even after the button/checkbox fix
  above. Cause: a window's native title bar and surrounding chrome are
  drawn by Windows itself (DWM), not by ttk -- styling never reaches them.
  Every window (the main one and every dialog) now explicitly tells DWM to
  draw its title bar dark via `DwmSetWindowAttribute`, re-applied live
  whenever dark mode is toggled (including on whatever dialog happens to
  be open at the time, e.g. Settings itself).
- **Fixed:** hovering a checkbox in dark mode turned its whole row white,
  making the (still dark-colored) text and checkmark invisible against
  it. Cause: only the checkbox's *default* background was set to the dark
  color -- the separate *hover/active* state still fell back to clam's
  own light default. Both states are explicitly dark now.
- **Fixed:** stray thin black lines under "START TYPING MODE"/"END TYPING
  MODE" in light mode. Cause: the chip-holder frames sitting right below
  those labels never explicitly disabled Tk's default 1px highlight
  border, which rendered as a thin dark line. Disabled it explicitly on
  every plain (non-ttk) frame/label that shouldn't have one -- the chips
  themselves, their container frames, and the status bar.
- **Fixed:** dark mode left a lot of things white -- buttons, checkboxes,
  the scale dropdown, scrollbars. Cause: the `vista` ttk theme renders
  those natively through Windows and ignores color overrides almost
  entirely (it only respects fonts), so no amount of `style.configure()`
  could actually make them dark. Dark mode now forces the `clam` theme
  (fully Tk-drawn, respects every color we set) while light mode keeps
  `vista`'s nicer native look. Also fixed the checkbox/radio indicator
  square specifically, which uses different option names
  (`indicatorbackground`/`indicatorforeground`) than the rest of the
  widget and needed its own fix even after switching themes.
- **Added:** a horizontal scrollbar under the Game Profiles list, so long
  names (e.g. "The Elder Scrolls V: Skyrim Special Edition") can be
  scrolled into view instead of being permanently clipped.

## Recently-foreground picker

Click **Add Recent Program...** to add a profile for a game you've
recently switched to (alt-tabbed to, or it was focused/launched) while
KeyBind Changer was running. This list is session-only -- it starts empty
each time you launch the app and fills in as you play, so if it's empty,
just switch to (or launch) the game you want for a moment and try again.
It deliberately excludes KeyBind Changer's own process so it never
suggests adding itself.


- **Added:** Settings (gear icon): adjustable text/UI scale (100-200%,
  applies live, no restart), dark mode, a toggle for per-game icons in the
  profile list, and a global hotkey to bring the window to the front from
  anywhere (even hidden in the tray or while in a game).
- **Added:** the key a remap sends is now shown in **bold**, under the
  original key, so it's easier to tell at a glance which is which.
- **Added:** "Add Recent Program..." -- lists up to the 10 most recent
  programs seen in the foreground this session (most recent first, with
  icons), as a third way to bulk-add games alongside the Steam/folder
  scanners.
- **Confirmed (no change needed):** typing-mode start/end hotkeys already
  only ever match the physical key pressed, never a remapped result --
  traced and unit-tested this explicitly, and added comments in
  `hook_manager.py` documenting why that's guaranteed (remapped/injected
  key events never re-enter the hook's decision logic at all).
- **Removed:** the per-foreground-change debug log line in
  `process_watcher.py` that fired on every window switch (including just
  clicking around your own desktop) -- it was cluttering `debug.log` without
  adding diagnostic value beyond what the GUI/hook logs already show.

- **Added:** `build_exe.bat` / `build_exe_debug.bat` to package the app into
  a standalone `KeyBindChanger.exe` via PyInstaller, plus an `icon.ico` for
  it. See "Building a standalone .exe" above.
- **Fixed:** a real bug this packaging work surfaced before it could bite --
  a `--windowed` (no-console) build sets `sys.stdout`/`sys.stderr` to `None`
  rather than just hiding them, which would have crashed on the very first
  log call. Logging now skips the console handler when there's no real
  stream to write to, instead of crashing; `debug.log` is unaffected either way.

- **Added:** typing-mode hotkeys are now per-game instead of one global
  set. Select a profile and the "Typing Mode Hotkeys" card edits that
  game's hotkeys specifically; with no profile selected, it edits the
  Default (used whenever no game is detected). New profiles start out with
  a copy of the Default, and existing config files upgrade automatically.

- **Added:** a real UI redesign -- ttk-themed widgets throughout, a
  consistent color palette, a custom-drawn keyboard with rounded keys and
  hover feedback (replacing the old grid of plain OS buttons), and
  removable "chip" tags for typing-mode hotkeys instead of list boxes
  with +/- buttons. On Windows this also picks up the native 'vista' ttk
  theme automatically, so buttons/scrollbars look like normal Windows
  controls rather than the default Tk look.
- **Added:** a system tray icon (`pystray` + `Pillow`). Closing the window
  now minimizes to the tray instead of quitting -- see "System tray
  behavior" above.

- **Fixed:** `SendInput` failing with `WinError 87 (ERROR_INVALID_PARAMETER)`
  on every remap, even though everything upstream of it (hook, mapping
  lookup, scan-code translation) was working correctly. Windows' `INPUT`
  struct is a union of three possible payloads (mouse/keyboard/hardware),
  and its overall size is driven by the *largest* one -- `MOUSEINPUT` (32
  bytes), not `KEYBDINPUT` (24 bytes), which is the only one this app
  actually uses. The union only declared the keyboard member, so the
  computed struct size was smaller than what `SendInput` validates the
  `cbSize` parameter against, and it rejected every call. The union now
  includes all three real members so the size matches Windows' actual
  layout (40 bytes on 64-bit Windows), even though only the keyboard one
  is ever populated.

- **Fixed:** key-rebind / typing-mode-hotkey "press a key" dialogs not
  responding to any key press. The keyboard hook's callback declared its
  return type as a 32-bit value, but Windows' real `LRESULT` type is
  pointer-sized (64-bit on 64-bit Windows) -- the mismatch corrupted what
  Windows read back from the hook. All Win32 prototypes in `hook_manager.py`
  are now declared with correct, explicit, pointer-sized types, and a clear
  error is now shown if the hook ever fails to install at all (e.g. blocked
  by security software) instead of failing silently.
- **Changed:** key injection now uses scan codes (`KEYEVENTF_SCANCODE`)
  instead of virtual-key codes wherever possible. Many games -- especially
  ones using DirectInput, or reading raw input directly -- only recognize
  scan codes, since that's what a physical keyboard actually sends.
- **Added:** an elevation mismatch check. The app now detects when the
  focused game is running as Administrator while this app isn't (the other
  common reason remapping silently fails) and offers to restart itself
  elevated on launch.
- **Added:** comprehensive debug logging (console + `debug.log`) covering
  every key event, remap decision, profile load/save, process change, and
  scan result -- see "Diagnosing" above.
- **Added:** "Scan Steam Library" and "Scan Custom Folder..." bulk game
  discovery.

## How it works (high level)

- A low-level Windows keyboard hook (`WH_KEYBOARD_LL`) intercepts every key
  press system-wide before it reaches any application.
- A background thread checks the currently focused window a few times per
  second and looks up its process name against your saved profiles.
- When a key you've remapped is pressed, the original key event is
  swallowed and a synthetic event for the mapped key is injected with
  `SendInput` instead. Unmapped keys pass through untouched.
- Typing mode simply tells the hook to stop swallowing/replacing anything
  until one of your "end typing" keys shows up.

Everything lives in plain, readable `ctypes` calls against the public
Win32 API (no third-party hooking library), so it's easy to inspect or
modify -- see `hook_manager.py`.

## Known limitations (v1)

- **Anti-cheat:** Some games (e.g. those using Vanguard, EasyAntiCheat, or
  BattlEye) actively monitor for low-level input hooks and synthetic input,
  and may flag, block, or in rare cases penalize their use, since this is
  indistinguishable at a technical level from some cheat tools even though
  this app only does straightforward key substitution. Use at your own
  discretion in competitive/anti-cheat-protected games, and check each
  game's policy on third-party input remapping tools (many, like
  AutoHotkey-style remaps, are widely tolerated, but policies vary).
- **Numpad Enter** shares the same virtual key code as the main Enter key
  at the Windows API level, so they can't currently be bound separately.
- The Windows key can be finicky to capture in the "press a key" dialogs
  since the OS sometimes intercepts it for the Start Menu before the hook
  sees it consistently.
- Foreground-window detection polls a few times per second rather than
  using event-driven notifications -- simple and reliable, with a small
  (<1s) delay when switching windows. Could be upgraded to
  `SetWinEventHook` later for instant switching.
- No system tray icon yet -- closing the window exits the app and stops
  remapping (a tray icon + "run at startup" option would be a natural v2).

## Project layout

```
main.py             entry point
gui.py               Tkinter UI
theme.py              colors/fonts/ttk styling shared across the UI (light + dark, scaled)
tray_icon.py           system tray icon (pystray)
icon_extract.py        pulls a game's .exe icon for the profile list
hook_manager.py       low-level keyboard hook + SendInput remapping engine
process_watcher.py    detects the foreground game + elevation mismatch checks
profile_manager.py    loads/saves per-game profiles + settings (JSON)
game_scanner.py        finds games in your Steam library or any folder
logging_setup.py       configures console + debug.log logging
keymap.py             VK code constants + keyboard layout used by the GUI
requirements.txt
icon.ico              app icon, used when building the .exe
build_exe.bat          builds dist\KeyBindChanger.exe (no console window)
build_exe_debug.bat    builds dist\KeyBindChanger-debug.exe (keeps console)
```
