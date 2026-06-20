"""
gui.py
------
Tkinter front-end for KeyBind Changer.

Layout:
  Header: title + a Settings button (text/UI scale, dark mode, game icons,
          global "show window" hotkey -- all accessibility-oriented).
  Left:   card with the list of saved game profiles (with icons) + actions,
          including bulk-add from Steam/a folder/currently-running programs.
  Right:  a card with a custom-drawn (Canvas) keyboard map -- click a key
          to rebind it -- plus a card with the typing-mode hotkeys
  Bottom: status bar showing the currently detected game and whether
          typing mode is active

All "press a key" capture (rebinding a key, or setting a typing-mode
hotkey) is done via the same global low-level hook used for remapping
itself (see hook_manager.capture_next_key), so it works for every key
on the keyboard -- not just the ones Tkinter can normally see. Setting the
global "show window" hotkey uses hook_manager.capture_next_combo instead,
which records a whole chord (modifiers + a key) rather than a single key.

Closing the window (the X button) hides it instead of quitting -- the app
keeps remapping in the background and lives on in the system tray (see
tray_icon.py). Actually quitting is done from the tray icon's "Exit", or
by calling app.full_shutdown() directly.
"""

import logging
import os
import queue
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

import game_scanner
import hook_manager
import icon_extract
import keymap
import profile_manager
import theme

logger = logging.getLogger(__name__)

GROUP_GAP_UNITS = 0.8
BASE_KEY_UNIT = 38
BASE_KEY_GAP = 4
BASE_ICON_SIZE = 24
BASE_WINDOW_W, BASE_WINDOW_H = 1320, 740
BASE_MIN_W, BASE_MIN_H = 1180, 660
MAX_WINDOW_W, MAX_WINDOW_H = 1900, 1060


def _rounded_rect(canvas, x1, y1, x2, y2, radius=7, **kwargs):
    r = radius
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def _group_dimensions(rows):
    width_units = max((sum(span for (_l, _v, span) in row) for row in rows), default=0)
    return width_units, len(rows)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KeyBind Changer")

        self.config_data = profile_manager.load_config()
        self.selected_exe = None   # lowercase exe key currently shown in the editor
        self.active_exe = None     # exe name of the foreground process right now
        self.recent_foreground = []  # up to 10 recently-foreground {display_name, exe_name, exe_path}
        self._capture_purpose = None
        self._combo_capture_purpose = None

        self._process_queue = queue.Queue()
        self._capture_queue = queue.Queue()
        self._combo_capture_queue = queue.Queue()
        self._scan_queue = queue.Queue()
        self._tray_queue = queue.Queue()
        self._scanning_dialog = None

        self.tray_icon = None          # set by main.py after the tray starts (may stay None)
        self.full_shutdown = None      # set by main.py: the real "quit everything" callback
        self._shown_tray_notice = False
        self._settings_hotkey_var = tk.StringVar()

        self._recompute_scaled_sizes()
        theme.apply(self, scale=self._scale(), dark=self._dark())
        self._set_window_icon()
        self._apply_window_geometry()
        theme.set_titlebar_dark(self, self._dark())

        self._build_layout()
        self._refresh_profile_list()
        self._render_keyboard()
        self._refresh_hotkey_chips()
        self._update_typing_panel_label()
        self._update_show_window_hotkey_label()
        self._push_active_typing_hotkeys()

        hook_manager.set_show_window_callback(lambda: self.queue_tray_command("show"))
        hook_manager.set_kill_callback(lambda: self.queue_tray_command("exit"))
        hook_manager.set_show_window_hotkey(self.config_data["settings"]["show_window_hotkey"])

        self._poll_background()
        self._tick_status()

    # ------------------------------------------------------------------
    # Settings helpers (scale / dark mode live in config_data["settings"])
    # ------------------------------------------------------------------
    def _scale(self):
        return self.config_data["settings"]["ui_scale"]

    def _dark(self):
        return self.config_data["settings"]["dark_mode"]

    def _recompute_scaled_sizes(self):
        scale = self._scale()
        self.key_unit = int(BASE_KEY_UNIT * scale)
        self.key_gap = max(2, int(BASE_KEY_GAP * scale))
        self.icon_size = max(16, int(BASE_ICON_SIZE * scale))

    def _apply_window_geometry(self):
        scale = self._scale()
        w = min(int(BASE_WINDOW_W * scale), MAX_WINDOW_W)
        h = min(int(BASE_WINDOW_H * scale), MAX_WINDOW_H)
        self.geometry(f"{w}x{h}")
        self.minsize(min(int(BASE_MIN_W * scale), MAX_WINDOW_W), min(int(BASE_MIN_H * scale), MAX_WINDOW_H))

    def _set_window_icon(self):
        try:
            import tray_icon
            if tray_icon.AVAILABLE:
                from PIL import ImageTk
                self._icon_photo = ImageTk.PhotoImage(tray_icon.build_icon_image(64))
                self.iconphoto(True, self._icon_photo)
        except Exception:
            logger.debug("Couldn't set window icon (non-fatal)", exc_info=True)

    def _apply_theme_live(self):
        """Re-applies colors/fonts/sizes after a scale or dark-mode change,
        without rebuilding the window (so any open dialog, e.g. Settings
        itself, keeps working -- ttk widgets pick up style changes live;
        we just need to manually refresh the handful of plain tk widgets
        and anything drawn on a Canvas)."""
        self._recompute_scaled_sizes()
        theme.apply(self, scale=self._scale(), dark=self._dark())
        theme.set_titlebar_dark(self, self._dark())
        for child in self.winfo_children():
            if isinstance(child, tk.Toplevel):
                theme.set_titlebar_dark(child, self._dark())

        self.kb_canvas.configure(bg=theme.PANEL)
        self.list_wrap.configure(bg=theme.PANEL, highlightbackground=theme.BORDER, highlightcolor=theme.BORDER)
        self.start_chip_frame.configure(bg=theme.PANEL, highlightbackground=theme.PANEL, highlightcolor=theme.PANEL)
        self.end_chip_frame.configure(bg=theme.PANEL, highlightbackground=theme.PANEL, highlightcolor=theme.PANEL)
        self.status_bar_frame.configure(bg=theme.STATUS_BG)
        self.status_bar_label.configure(bg=theme.STATUS_BG, fg=theme.TEXT, font=theme.FONT_SMALL)
        self.status_dot.configure(bg=theme.STATUS_BG)

        self._apply_window_geometry()
        self._render_keyboard()
        self._refresh_hotkey_chips()
        self._refresh_profile_list()

    # ------------------------------------------------------------------
    # Layout construction
    # ------------------------------------------------------------------
    def _build_layout(self):
        header = ttk.Frame(self, padding=(20, 16, 20, 6))
        header.pack(fill="x")
        ttk.Label(header, text="KeyBind Changer", style="Heading.TLabel").pack(side="left")
        ttk.Label(header, text="  Per-game keyboard remapping", style="Muted.TLabel").pack(side="left")
        self._btn(header, text="\u2699 Settings", command=self._open_settings).pack(side="right")

        body = ttk.Frame(self, padding=(20, 0, 20, 0))
        body.pack(fill="both", expand=True)

        self._build_sidebar(body)
        self._build_main_panel(body)
        self._build_status_bar(self)

    def _build_sidebar(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=16, width=260)
        card.pack(side="left", fill="y", padx=(0, 16), pady=(0, 16))
        card.pack_propagate(False)

        ttk.Label(card, text="Game Profiles", style="CardHeading.TLabel").pack(anchor="w")
        ttk.Label(
            card, style="CardMuted.TLabel", justify="left", wraplength=220,
            text="Each game keeps its own key bindings. Switches automatically when you alt-tab.",
        ).pack(anchor="w", pady=(2, 10))

        self.list_wrap = tk.Frame(card, bg=theme.PANEL, highlightthickness=1,
                                   highlightbackground=theme.BORDER, highlightcolor=theme.BORDER)
        self.list_wrap.pack(fill="both", expand=True)

        v_scroll = ttk.Scrollbar(self.list_wrap, orient="vertical")
        v_scroll.pack(side="right", fill="y")
        h_scroll = ttk.Scrollbar(self.list_wrap, orient="horizontal")
        h_scroll.pack(side="bottom", fill="x")
        self.profile_tree = ttk.Treeview(
            self.list_wrap, show="tree", selectmode="browse",
            yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set,
        )
        self.profile_tree.pack(fill="both", expand=True, padx=1, pady=1)
        v_scroll.config(command=self.profile_tree.yview)
        h_scroll.config(command=self.profile_tree.xview)
        # stretch=False is what makes horizontal scrolling possible at all --
        # otherwise the tree column always resizes to fit the visible area
        # and long names just get clipped with nothing to scroll to.
        self.profile_tree.column("#0", stretch=False)
        self.profile_tree.bind("<<TreeviewSelect>>", self._on_profile_select)

        ttk.Separator(card).pack(fill="x", pady=10)
        self._btn(card, text="+ Add Game...", style="Accent.TButton", command=self._add_game).pack(fill="x", pady=2)
        self._btn(card, text="Scan Steam Library", command=self._scan_steam).pack(fill="x", pady=2)
        self._btn(card, text="Scan Custom Folder...", command=self._scan_custom_folder).pack(fill="x", pady=2)
        self._btn(card, text="Add Recent Program...", command=self._choose_running_program).pack(fill="x", pady=2)
        ttk.Separator(card).pack(fill="x", pady=10)
        self._btn(card, text="Remove Selected", command=self._remove_game).pack(fill="x", pady=2)
        self._btn(card, text="Reset All Keys", command=self._reset_all).pack(fill="x", pady=2)

    def _build_main_panel(self, parent):
        right = ttk.Frame(parent)
        right.pack(side="left", fill="both", expand=True, pady=(0, 16))

        kb_card = ttk.Frame(right, style="Card.TFrame", padding=16)
        kb_card.pack(fill="both", expand=True)

        self.editing_label = ttk.Label(kb_card, text="No profile selected", style="CardHeading.TLabel")
        self.editing_label.pack(anchor="w", pady=(0, 10))

        self.kb_canvas = tk.Canvas(kb_card, bg=theme.PANEL, highlightthickness=0)
        self.kb_canvas.pack(fill="both", expand=True)

        self._build_typing_panel(right)

    def _build_typing_panel(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=16)
        card.pack(fill="x", pady=(16, 0))

        ttk.Label(card, text="Typing Mode Hotkeys", style="CardHeading.TLabel").pack(anchor="w")
        self.typing_hotkeys_label = ttk.Label(card, style="CardMuted.TLabel", font=theme.FONT_CARD_HEADING)
        self.typing_hotkeys_label.pack(anchor="w", pady=(2, 2))
        ttk.Label(
            card, style="CardMuted.TLabel", wraplength=760,
            text="While typing mode is on, every key behaves normally (no remapping). "
                 "Each game can have its own hotkeys here, separate from every other game's. "
                 "These always match the physical key you press, never a remapped result.",
        ).pack(anchor="w", pady=(0, 10))

        row = ttk.Frame(card, style="Card.TFrame")
        row.pack(fill="x")

        start_col = ttk.Frame(row, style="Card.TFrame")
        start_col.pack(side="left", padx=(0, 36))
        ttk.Label(start_col, text="START TYPING MODE", style="CardLabel.TLabel").pack(anchor="w")
        self.start_chip_frame = tk.Frame(start_col, bg=theme.PANEL, highlightthickness=0, bd=0,
                                          highlightbackground=theme.PANEL, highlightcolor=theme.PANEL, takefocus=0)
        self.start_chip_frame.pack(anchor="w", pady=(8, 0))

        end_col = ttk.Frame(row, style="Card.TFrame")
        end_col.pack(side="left")
        ttk.Label(end_col, text="END TYPING MODE", style="CardLabel.TLabel").pack(anchor="w")
        self.end_chip_frame = tk.Frame(end_col, bg=theme.PANEL, highlightthickness=0, bd=0,
                                        highlightbackground=theme.PANEL, highlightcolor=theme.PANEL, takefocus=0)
        self.end_chip_frame.pack(anchor="w", pady=(8, 0))

    def _build_status_bar(self, parent):
        self.status_bar_frame = tk.Frame(parent, bg=theme.STATUS_BG, height=36, highlightthickness=0, bd=0)
        self.status_bar_frame.pack(fill="x", side="bottom")
        self.status_dot = tk.Canvas(self.status_bar_frame, width=10, height=10, bg=theme.STATUS_BG, highlightthickness=0)
        self.status_dot.pack(side="left", padx=(20, 8), pady=12)
        self._status_dot_id = self.status_dot.create_oval(1, 1, 9, 9, fill=theme.STATUS_OK, outline="")
        self.status_var = tk.StringVar(value="Starting...")
        self.status_bar_label = tk.Label(
            self.status_bar_frame, textvariable=self.status_var, bg=theme.STATUS_BG, fg=theme.TEXT,
            font=theme.FONT_SMALL, anchor="w", highlightthickness=0, bd=0,
        )
        self.status_bar_label.pack(side="left", pady=8)

    # ------------------------------------------------------------------
    # Settings dialog (accessibility: text/UI scale, dark mode, icons,
    # global show-window hotkey)
    # ------------------------------------------------------------------
    def _open_settings(self):
        dlg = self._new_dialog("Settings")
        settings = self.config_data["settings"]

        frame = ttk.Frame(dlg, padding=22)
        frame.pack()

        ttk.Label(frame, text="Accessibility", style="SettingsHeading.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(frame, text="Text & UI size:").grid(row=1, column=0, sticky="w", pady=4)
        scale_var = tk.StringVar(value=f"{int(settings['ui_scale'] * 100)}%")
        scale_combo = ttk.Combobox(
            frame, textvariable=scale_var, state="readonly", width=8,
            values=[f"{int(s * 100)}%" for s in theme.SCALE_OPTIONS],
        )
        scale_combo.grid(row=1, column=1, sticky="w", pady=4, padx=(8, 0))

        def on_scale_change(_event=None):
            pct = int(scale_var.get().rstrip("%"))
            self.config_data["settings"]["ui_scale"] = pct / 100.0
            profile_manager.save_config(self.config_data)
            logger.info("GUI: UI scale changed to %d%%", pct)
            self._apply_theme_live()

        scale_combo.bind("<<ComboboxSelected>>", on_scale_change)

        dark_var = tk.BooleanVar(value=settings["dark_mode"])

        def on_dark_toggle():
            self.config_data["settings"]["dark_mode"] = dark_var.get()
            profile_manager.save_config(self.config_data)
            logger.info("GUI: dark mode -> %s", dark_var.get())
            self._apply_theme_live()

        ttk.Checkbutton(frame, text="Dark mode", variable=dark_var, command=on_dark_toggle).grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 4))

        icons_var = tk.BooleanVar(value=settings["show_game_icons"])

        def on_icons_toggle():
            self.config_data["settings"]["show_game_icons"] = icons_var.get()
            profile_manager.save_config(self.config_data)
            logger.info("GUI: show game icons -> %s", icons_var.get())
            self._refresh_profile_list()

        ttk.Checkbutton(frame, text="Show game icons in the profile list", variable=icons_var,
                         command=on_icons_toggle).grid(row=3, column=0, columnspan=2, sticky="w", pady=4)

        ttk.Separator(frame).grid(row=4, column=0, columnspan=2, sticky="ew", pady=14)

        ttk.Label(frame, text="Global Hotkey", style="SettingsHeading.TLabel").grid(
            row=5, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ttk.Label(
            frame, style="Muted.TLabel", wraplength=340, justify="left",
            text="Brings this window to the front, even while it's hidden in the "
                 "tray -- works anywhere on your system, including in-game. "
                 "Press it together with Shift to quit KeyBind Changer entirely "
                 "(e.g. Ctrl+Alt+Shift+K if this is set to Ctrl+Alt+K).",
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 8))

        hotkey_row = ttk.Frame(frame)
        hotkey_row.grid(row=7, column=0, columnspan=2, sticky="w")
        ttk.Label(hotkey_row, textvariable=self._settings_hotkey_var, width=20).pack(side="left")
        self._btn(hotkey_row, text="Set Hotkey...", command=self._capture_show_window_hotkey).pack(side="left", padx=(8, 0))
        self._btn(hotkey_row, text="Clear", command=self._clear_show_window_hotkey).pack(side="left", padx=(6, 0))

        self._btn(frame, text="Close", command=dlg.destroy).grid(row=8, column=0, columnspan=2, pady=(20, 0))

    def _capture_show_window_hotkey(self):
        dlg = self._new_dialog("Set Global Hotkey")
        ttk.Label(
            dlg, padding=(28, 22, 28, 16), justify="center",
            text="Press the key combination you want\n(hold modifiers + a key, e.g. Ctrl+Alt+K)",
        ).pack()

        def cancel():
            hook_manager.cancel_combo_capture()
            self._combo_capture_purpose = None
            if dlg.winfo_exists():
                dlg.destroy()

        self._btn(dlg, text="Cancel", command=cancel).pack(pady=(0, 16))
        dlg.protocol("WM_DELETE_WINDOW", cancel)

        def on_result(combo):
            vks = sorted(combo)
            self.config_data["settings"]["show_window_hotkey"] = vks
            profile_manager.save_config(self.config_data)
            hook_manager.set_show_window_hotkey(vks)
            logger.info("GUI: global show-window hotkey set to %s",
                        "+".join(keymap.label_for(v) for v in vks))
            self._update_show_window_hotkey_label()
            if dlg.winfo_exists():
                dlg.destroy()

        self._start_combo_capture(on_result)
        dlg.grab_set()

    def _clear_show_window_hotkey(self):
        self.config_data["settings"]["show_window_hotkey"] = []
        profile_manager.save_config(self.config_data)
        hook_manager.set_show_window_hotkey([])
        logger.info("GUI: global show-window hotkey cleared")
        self._update_show_window_hotkey_label()

    def _update_show_window_hotkey_label(self):
        vks = self.config_data["settings"]["show_window_hotkey"]
        self._settings_hotkey_var.set("+".join(keymap.label_for(v) for v in vks) if vks else "(not set)")

    # ------------------------------------------------------------------
    # Small reusable dialog helpers
    # ------------------------------------------------------------------
    def _btn(self, parent, **kwargs):
        """ttk.Button wrapper used everywhere instead of calling ttk.Button
        directly. Disables keyboard-focus traversal (takefocus=False) by
        default: a *focused* (not just hovered/pressed) button under the
        'vista' theme (light mode) can render with invisible text -- a
        separate ttk state from the hover/pressed ones already fixed in
        theme.py, and not one we can reliably recolor since vista's focus
        rendering is native OS chrome. These are simple action buttons,
        not form fields, so losing tab-focus on them is a fair trade for
        never showing that broken state."""
        kwargs.setdefault("takefocus", False)
        return ttk.Button(parent, **kwargs)

    def _new_dialog(self, title):
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.configure(bg=theme.BG)
        dlg.resizable(False, False)
        dlg.transient(self)
        theme.set_titlebar_dark(dlg, self._dark())
        return dlg

    def _ask_string(self, title, prompt, initial=""):
        result = {"value": None}
        dlg = self._new_dialog(title)

        ttk.Label(dlg, text=prompt, padding=(24, 20, 24, 6)).pack()
        entry_var = tk.StringVar(value=initial)
        entry = ttk.Entry(dlg, textvariable=entry_var, width=34)
        entry.pack(padx=24, pady=(0, 16))
        entry.focus_set()
        entry.icursor(tk.END)
        entry.select_range(0, tk.END)

        btn_row = ttk.Frame(dlg, padding=(0, 0, 0, 18))
        btn_row.pack()

        def confirm():
            result["value"] = entry_var.get().strip()
            dlg.destroy()

        def cancel():
            dlg.destroy()

        self._btn(btn_row, text="OK", style="Accent.TButton", command=confirm).pack(side="left", padx=6)
        self._btn(btn_row, text="Cancel", command=cancel).pack(side="left", padx=6)
        entry.bind("<Return>", lambda e: confirm())
        dlg.bind("<Escape>", lambda e: cancel())
        dlg.protocol("WM_DELETE_WINDOW", cancel)
        dlg.grab_set()
        self.wait_window(dlg)
        return result["value"]

    # ------------------------------------------------------------------
    # Profile list (Treeview, with optional per-game icons)
    # ------------------------------------------------------------------
    def _refresh_profile_list(self):
        for item in self.profile_tree.get_children():
            self.profile_tree.delete(item)

        show_icons = self.config_data["settings"]["show_game_icons"]
        keys_sorted = sorted(
            self.config_data["profiles"].keys(),
            key=lambda k: self.config_data["profiles"][k]["display_name"].lower(),
        )

        font = tkfont.Font(font=theme.FONT_NORMAL)
        icon_allowance = self.icon_size + 12 if show_icons else 0
        max_width = 200  # floor so a short list still visually fills the panel

        for key in keys_sorted:
            profile = self.config_data["profiles"][key]
            icon = None
            if show_icons:
                icon = icon_extract.get_icon_photo(profile.get("exe_path"), size=self.icon_size)
            display = profile["display_name"]
            max_width = max(max_width, font.measure(display) + icon_allowance + 30)
            if icon is not None:
                self.profile_tree.insert("", "end", iid=key, text=" " + display, image=icon)
            else:
                self.profile_tree.insert("", "end", iid=key, text=display)

        self.profile_tree.column("#0", width=max_width, stretch=False)

        if self.selected_exe and self.profile_tree.exists(self.selected_exe):
            self.profile_tree.selection_set(self.selected_exe)

    def _on_profile_select(self, _event):
        sel = self.profile_tree.selection()
        self.selected_exe = sel[0] if sel else None
        name = self.config_data["profiles"][self.selected_exe]["display_name"] if self.selected_exe else "No profile selected"
        logger.debug("GUI: editor now showing profile '%s'", name)
        self.editing_label.config(text=f"Editing: {name}" if self.selected_exe else "No profile selected (select or add a game on the left)")
        self._render_keyboard()
        self._refresh_hotkey_chips()
        self._update_typing_panel_label()

    def _add_game(self):
        path = filedialog.askopenfilename(
            title="Select the game's .exe", filetypes=[("Executable", "*.exe"), ("All files", "*.*")]
        )
        if not path:
            return
        exe_name = os.path.basename(path)
        default_display = os.path.splitext(exe_name)[0]
        display_name = self._ask_string("Profile name", "Display name for this profile:", default_display) or default_display
        key = profile_manager.add_profile(self.config_data, exe_name, display_name, exe_path=path)
        logger.info("GUI: added new profile via 'Add Game...': %s (%s)", display_name, exe_name)
        self.selected_exe = key
        self._refresh_profile_list()
        self._on_profile_select(None)

    def _remove_game(self):
        if self.selected_exe is None:
            messagebox.showinfo("No selection", "Select a profile to remove first.")
            return
        name = self.config_data["profiles"][self.selected_exe]["display_name"]
        if not messagebox.askyesno("Remove profile", f"Remove the keybind profile for '{name}'?"):
            return
        profile_manager.remove_profile(self.config_data, self.selected_exe)
        logger.info("GUI: removed profile '%s'", name)
        self.selected_exe = None
        self._refresh_profile_list()
        self._on_profile_select(None)
        self._refresh_active_mapping()
        self._push_active_typing_hotkeys()

    def _reset_all(self):
        if self.selected_exe is None:
            messagebox.showinfo("No selection", "Select a profile first.")
            return
        if not messagebox.askyesno("Reset profile", "Reset every key in this profile back to default?"):
            return
        profile_manager.reset_all_mappings(self.config_data, self.selected_exe)
        logger.info("GUI: reset all keys for profile '%s'", self.selected_exe)
        self._render_keyboard()
        self._refresh_active_mapping()

    # ------------------------------------------------------------------
    # Bulk game discovery (Steam library / arbitrary folder / running programs)
    # ------------------------------------------------------------------
    def _scan_steam(self):
        logger.info("GUI: starting Steam library scan...")
        self._show_scanning_modal("Scanning your Steam library...\nThis can take a moment.")
        threading.Thread(target=self._do_steam_scan, daemon=True).start()

    def _do_steam_scan(self):
        try:
            result = game_scanner.scan_steam_games()
            logger.info("Steam scan finished: %s", "Steam not found" if result is None else f"{len(result)} game(s) found")
        except Exception as exc:  # noqa: BLE001 - report any scan failure to the user
            logger.exception("Steam scan raised an exception")
            result = {"error": str(exc)}
        self._scan_queue.put(result)

    def _scan_custom_folder(self):
        path = filedialog.askdirectory(title="Select a folder to scan for games")
        if not path:
            return
        logger.info("GUI: starting custom folder scan: %s", path)
        self._show_scanning_modal(f"Scanning:\n{path}\n\nThis can take a moment for large folders.")
        threading.Thread(target=self._do_folder_scan, args=(path,), daemon=True).start()

    def _do_folder_scan(self, path):
        try:
            result = game_scanner.scan_folder_for_games(path)
            logger.info("Folder scan of '%s' finished: %d game(s) found", path, len(result))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Folder scan raised an exception")
            result = {"error": str(exc)}
        self._scan_queue.put(result)

    def _choose_running_program(self):
        if not self.recent_foreground:
            messagebox.showinfo(
                "Nothing tracked yet",
                "KeyBind Changer hasn't seen any other program in the foreground yet "
                "this session. Switch to (or launch) the game you want to add -- even "
                "just alt-tabbing to it for a moment is enough -- then try again.",
            )
            return
        self._show_recent_programs_dialog()

    def _show_recent_programs_dialog(self):
        entries = list(self.recent_foreground)

        dlg = self._new_dialog("Add from Recent Programs")
        dlg.resizable(True, True)
        dlg.geometry("520x440")

        ttk.Label(
            dlg, padding=(16, 14, 16, 6), justify="left", wraplength=480,
            text=f"The last {len(entries)} program(s) seen in the foreground this "
                 "session (most recent first). Select the ones you'd like to add:",
        ).pack(fill="x")

        list_wrap = tk.Frame(dlg, bg=theme.PANEL, highlightthickness=1,
                              highlightbackground=theme.BORDER, highlightcolor=theme.BORDER)
        list_wrap.pack(fill="both", expand=True, padx=16)
        scrollbar = ttk.Scrollbar(list_wrap)
        scrollbar.pack(side="right", fill="y")
        tree = ttk.Treeview(
            list_wrap, show="tree", selectmode="extended", yscrollcommand=scrollbar.set,
        )
        tree.pack(fill="both", expand=True, padx=1, pady=1)
        scrollbar.config(command=tree.yview)

        show_icons = self.config_data["settings"]["show_game_icons"]
        existing_keys = set(self.config_data["profiles"].keys())
        for idx, entry in enumerate(entries):
            already = entry["exe_name"].lower() in existing_keys
            label = f"{entry['display_name']}  \u2014  {entry['exe_path'] or entry['exe_name']}"
            if already:
                label += "   (already added)"
            icon = icon_extract.get_icon_photo(entry.get("exe_path"), size=self.icon_size) if show_icons else None
            iid = str(idx)
            if icon is not None:
                tree.insert("", "end", iid=iid, text=" " + label, image=icon)
            else:
                tree.insert("", "end", iid=iid, text=label)
        tree.selection_set(*[str(i) for i in range(len(entries))])

        btn_row = ttk.Frame(dlg, padding=14)
        btn_row.pack()

        def commit():
            added, skipped = 0, 0
            for iid in tree.selection():
                entry = entries[int(iid)]
                key = entry["exe_name"].lower()
                if key in self.config_data["profiles"]:
                    skipped += 1
                    continue
                profile_manager.add_profile(
                    self.config_data, entry["exe_name"], entry["display_name"], exe_path=entry.get("exe_path")
                )
                added += 1
            self._refresh_profile_list()
            dlg.destroy()
            extra = f" ({skipped} already added were skipped.)" if skipped else ""
            messagebox.showinfo("Done", f"Added {added} game profile(s).{extra}")

        self._btn(btn_row, text="Add Selected", style="Accent.TButton", command=commit).pack(side="left", padx=6)
        self._btn(btn_row, text="Cancel", command=dlg.destroy).pack(side="left", padx=6)

    def _show_scanning_modal(self, text):
        dlg = self._new_dialog("Scanning")
        ttk.Label(dlg, text=text, padding=(32, 26, 32, 26), justify="center").pack()
        dlg.protocol("WM_DELETE_WINDOW", lambda: None)  # scan can't be cancelled mid-flight
        dlg.grab_set()
        self._scanning_dialog = dlg

    def _handle_scan_result(self, result):
        if self._scanning_dialog is not None and self._scanning_dialog.winfo_exists():
            self._scanning_dialog.destroy()
        self._scanning_dialog = None

        if isinstance(result, dict) and "error" in result:
            messagebox.showerror("Scan failed", f"Something went wrong while scanning:\n\n{result['error']}")
            return
        if result is None:
            messagebox.showinfo(
                "Steam not found",
                "Couldn't locate a Steam installation automatically.\n\n"
                "You can use 'Scan Custom Folder...' and point it at your Steam "
                "library's steamapps\\common folder instead, or add games individually.",
            )
            return
        self._show_scan_results_dialog(result)

    def _show_scan_results_dialog(self, games):
        if not games:
            messagebox.showinfo("No games found", "No games were found at that location.")
            return

        dlg = self._new_dialog("Add detected games")
        dlg.resizable(True, True)
        dlg.geometry("580x460")

        ttk.Label(
            dlg, padding=(16, 14, 16, 6), justify="left", wraplength=540,
            text=f"Found {len(games)} item(s). Review the path for each, then select "
                 "the ones you'd like to add (click to select, Ctrl/Shift+click for multiple):",
        ).pack(fill="x")

        list_wrap = tk.Frame(dlg, bg=theme.PANEL, highlightthickness=1,
                              highlightbackground=theme.BORDER, highlightcolor=theme.BORDER)
        list_wrap.pack(fill="both", expand=True, padx=16)
        scrollbar = ttk.Scrollbar(list_wrap)
        scrollbar.pack(side="right", fill="y")
        listbox = tk.Listbox(
            list_wrap, selectmode="extended", yscrollcommand=scrollbar.set,
            relief="flat", bd=0, bg=theme.PANEL, fg=theme.TEXT, font=theme.FONT_NORMAL,
            selectbackground=theme.ACCENT, selectforeground="white", highlightthickness=0,
        )
        listbox.pack(fill="both", expand=True, padx=1, pady=1)
        scrollbar.config(command=listbox.yview)

        existing_keys = set(self.config_data["profiles"].keys())
        for game in games:
            already = game["exe_name"].lower() in existing_keys
            suffix = "   (already added)" if already else ""
            listbox.insert(tk.END, f"{game['display_name']}  \u2014  {game['exe_path']}{suffix}")
        listbox.selection_set(0, tk.END)

        btn_row = ttk.Frame(dlg, padding=14)
        btn_row.pack()

        def commit():
            added, skipped = 0, 0
            for idx in listbox.curselection():
                game = games[idx]
                key = game["exe_name"].lower()
                if key in self.config_data["profiles"]:
                    skipped += 1
                    continue
                profile_manager.add_profile(
                    self.config_data, game["exe_name"], game["display_name"], exe_path=game.get("exe_path")
                )
                added += 1
            self._refresh_profile_list()
            dlg.destroy()
            extra = f" ({skipped} already added were skipped.)" if skipped else ""
            messagebox.showinfo("Done", f"Added {added} game profile(s).{extra}")

        self._btn(btn_row, text="Add Selected", style="Accent.TButton", command=commit).pack(side="left", padx=6)
        self._btn(btn_row, text="Cancel", command=dlg.destroy).pack(side="left", padx=6)

    # ------------------------------------------------------------------
    # Keyboard map rendering + rebinding
    # ------------------------------------------------------------------
    def _render_keyboard(self):
        profile = profile_manager.get_profile(self.config_data, self.selected_exe) if self.selected_exe else None
        mapping = profile["mappings"] if profile else {}

        self.kb_canvas.delete("all")

        main_w, main_h = _group_dimensions(keymap.MAIN_ROWS)
        nav_w, nav_h = _group_dimensions(keymap.NAV_ROWS)
        numpad_w, numpad_h = _group_dimensions(keymap.NUMPAD_ROWS)

        unit = self.key_unit
        main_x = 6
        nav_x = main_x + (main_w + GROUP_GAP_UNITS) * unit
        numpad_x = nav_x + (nav_w + GROUP_GAP_UNITS) * unit
        y_off = 6

        total_w = int(numpad_x + numpad_w * unit + 10)
        total_h = int(max(main_h, nav_h, numpad_h) * unit + 10)
        self.kb_canvas.configure(width=total_w, height=total_h)

        self._draw_key_group(keymap.MAIN_ROWS, main_x, y_off, mapping)
        self._draw_key_group(keymap.NAV_ROWS, nav_x, y_off, mapping)
        self._draw_key_group(keymap.NUMPAD_ROWS, numpad_x, y_off, mapping)

    def _draw_key_group(self, rows, x_offset, y_offset, mapping):
        canvas = self.kb_canvas
        unit, gap = self.key_unit, self.key_gap
        for r, row in enumerate(rows):
            col = 0
            for label, vk, span in row:
                if vk is None:
                    col += span
                    continue
                x1 = x_offset + col * unit + gap / 2
                y1 = y_offset + r * unit + gap / 2
                x2 = x_offset + (col + span) * unit - gap / 2
                y2 = y_offset + (r + 1) * unit - gap / 2
                col += span

                target = mapping.get(vk, vk)
                remapped = target != vk
                if self.selected_exe is None:
                    fill, border, text_color = theme.KEY_DISABLED_FILL, theme.BORDER, theme.TEXT_MUTED
                elif remapped:
                    fill, border, text_color = theme.KEY_REMAP_FILL, theme.KEY_REMAP_BORDER, theme.KEY_REMAP_BORDER
                else:
                    fill, border, text_color = theme.KEY_FILL, theme.KEY_BORDER, theme.TEXT

                tag = f"key{vk}"
                rect_id = _rounded_rect(canvas, x1, y1, x2, y2, radius=7,
                                         fill=fill, outline=border, width=1.3, tags=(tag, "keybtn"))
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                if remapped:
                    # Original key (normal weight) on top, the key it now
                    # SENDS (bold, per accessibility request) underneath.
                    canvas.create_text(cx, cy - unit * 0.18, text=label, font=theme.FONT_KEY_SMALL,
                                        fill=text_color, tags=(tag, "keybtn"), justify="center")
                    canvas.create_text(cx, cy + unit * 0.18, text=f"\u2192{keymap.label_for(target)}",
                                        font=theme.FONT_KEY_SMALL_BOLD, fill=text_color,
                                        tags=(tag, "keybtn"), justify="center")
                else:
                    canvas.create_text(cx, cy, text=label, font=theme.FONT_KEY,
                                        fill=text_color, tags=(tag, "keybtn"), justify="center")

                canvas.tag_bind(tag, "<Button-1>", lambda e, v=vk: self._on_key_click(v))
                canvas.tag_bind(tag, "<Enter>", lambda e, rid=rect_id, c=canvas: c.itemconfig(rid, fill=theme.KEY_HOVER))
                canvas.tag_bind(tag, "<Leave>", lambda e, rid=rect_id, c=canvas, f=fill: c.itemconfig(rid, fill=f))
                canvas.tag_bind(tag, "<Enter>", lambda e, c=canvas: c.configure(cursor="hand2"), add="+")
                canvas.tag_bind(tag, "<Leave>", lambda e, c=canvas: c.configure(cursor=""), add="+")

    def _on_key_click(self, vk):
        if self.selected_exe is None:
            messagebox.showinfo(
                "No profile selected",
                "Select or add a game profile on the left before editing key bindings.",
            )
            return

        dlg = self._new_dialog(f"Rebind {keymap.label_for(vk)}")
        logger.debug("GUI: opened rebind dialog for %s (0x%02X) on profile '%s'", keymap.label_for(vk), vk, self.selected_exe)

        ttk.Label(
            dlg, padding=(28, 24, 28, 2), justify="center",
            text=f"Press the key you want '{keymap.label_for(vk)}' to send.",
        ).pack()
        ttk.Label(
            dlg, padding=(28, 0, 28, 16), justify="center", style="Muted.TLabel",
            text="(this works anywhere on your system right now)",
        ).pack()

        btn_row = ttk.Frame(dlg, padding=(0, 0, 0, 18))
        btn_row.pack()

        def cancel():
            hook_manager.cancel_capture()
            self._capture_purpose = None
            if dlg.winfo_exists():
                dlg.destroy()

        def reset_to_default():
            self._apply_remap(vk, vk)
            cancel()

        self._btn(btn_row, text="Reset to Default", command=reset_to_default).pack(side="left", padx=6)
        self._btn(btn_row, text="Cancel", command=cancel).pack(side="left", padx=6)
        dlg.protocol("WM_DELETE_WINDOW", cancel)

        def on_result(captured_vk):
            self._apply_remap(vk, captured_vk)
            if dlg.winfo_exists():
                dlg.destroy()

        self._start_capture(on_result)
        dlg.grab_set()

    def _apply_remap(self, physical_vk, target_vk):
        logger.debug("GUI: applying remap for profile '%s': 0x%02X -> 0x%02X",
                     self.selected_exe, physical_vk, target_vk)
        profile_manager.set_mapping(self.config_data, self.selected_exe, physical_vk, target_vk)
        self._render_keyboard()
        self._refresh_active_mapping()

    # ------------------------------------------------------------------
    # Typing-mode hotkeys (rendered as removable "chips")
    # ------------------------------------------------------------------
    def _update_typing_panel_label(self):
        if self.selected_exe:
            name = self.config_data["profiles"][self.selected_exe]["display_name"]
            self.typing_hotkeys_label.config(text=f"Hotkeys for: {name}")
        else:
            self.typing_hotkeys_label.config(text="Hotkeys for: Default (used whenever no game is detected)")

    def _refresh_hotkey_chips(self):
        start, end = profile_manager.get_typing_hotkeys(self.config_data, self.selected_exe)
        self._render_chip_row(self.start_chip_frame, start, "start")
        self._render_chip_row(self.end_chip_frame, end, "end")

    def _render_chip_row(self, frame, vks, which):
        for child in frame.winfo_children():
            child.destroy()
        for vk in vks:
            chip = tk.Frame(frame, bg=theme.CHIP_BG, highlightthickness=0, bd=0,
                             highlightbackground=theme.CHIP_BG, highlightcolor=theme.CHIP_BG, takefocus=0)
            chip.pack(side="left", padx=(0, 6), pady=2)
            tk.Label(chip, text=keymap.label_for(vk), bg=theme.CHIP_BG, fg=theme.CHIP_TEXT,
                     font=theme.FONT_SMALL, padx=8, pady=4, highlightthickness=0, bd=0,
                     highlightbackground=theme.CHIP_BG, highlightcolor=theme.CHIP_BG, takefocus=0).pack(side="left")
            close = tk.Label(chip, text="\u2715", bg=theme.CHIP_BG, fg=theme.CHIP_CLOSE,
                              font=theme.FONT_SMALL, cursor="hand2", padx=6, pady=4,
                              highlightthickness=0, bd=0,
                              highlightbackground=theme.CHIP_BG, highlightcolor=theme.CHIP_BG, takefocus=0)
            close.pack(side="left")
            close.bind("<Button-1>", lambda e, v=vk, w=which: self._remove_specific_hotkey(w, v))
        add_label = tk.Label(frame, text="+ Add", bg=theme.PANEL, fg=theme.ACCENT,
                              font=theme.FONT_SMALL, cursor="hand2", padx=6, pady=4,
                              highlightthickness=0, bd=0,
                              highlightbackground=theme.PANEL, highlightcolor=theme.PANEL, takefocus=0)
        add_label.pack(side="left")
        add_label.bind("<Button-1>", lambda e, w=which: self._add_hotkey(w))

    def _add_hotkey(self, which):
        dlg = self._new_dialog("Add hotkey")
        ttk.Label(dlg, text="Press the key you want to add...", padding=(28, 22, 28, 16)).pack()

        def cancel():
            hook_manager.cancel_capture()
            self._capture_purpose = None
            if dlg.winfo_exists():
                dlg.destroy()

        self._btn(dlg, text="Cancel", command=cancel).pack(pady=(0, 16))
        dlg.protocol("WM_DELETE_WINDOW", cancel)

        def on_result(vk):
            start, end = profile_manager.get_typing_hotkeys(self.config_data, self.selected_exe)
            target = start if which == "start" else end
            if vk not in target:
                target.append(vk)
                profile_manager.set_typing_hotkeys(self.config_data, self.selected_exe, start, end)
                logger.info("GUI: added %s-typing hotkey %s for %s",
                            which, keymap.label_for(vk), self.selected_exe or "Default")
                self._refresh_hotkey_chips()
                self._push_active_typing_hotkeys()
            if dlg.winfo_exists():
                dlg.destroy()

        self._start_capture(on_result)
        dlg.grab_set()

    def _remove_specific_hotkey(self, which, vk):
        start, end = profile_manager.get_typing_hotkeys(self.config_data, self.selected_exe)
        target = start if which == "start" else end
        if vk in target:
            target.remove(vk)
            profile_manager.set_typing_hotkeys(self.config_data, self.selected_exe, start, end)
            logger.info("GUI: removed %s-typing hotkey %s for %s",
                        which, keymap.label_for(vk), self.selected_exe or "Default")
            self._refresh_hotkey_chips()
            self._push_active_typing_hotkeys()

    def _push_active_typing_hotkeys(self):
        """Pushes the EFFECTIVE typing-mode hotkeys for whichever game is
        currently detected as running (self.active_exe) -- NOT necessarily
        the same profile currently being edited (self.selected_exe)."""
        start, end = profile_manager.get_typing_hotkeys(self.config_data, self.active_exe)
        hook_manager.set_typing_hotkeys(start, end)

    # ------------------------------------------------------------------
    # Cross-thread plumbing (process watcher + key/combo capture + tray icon)
    # ------------------------------------------------------------------
    def queue_process_change(self, exe_name, exe_path=None):
        """Called from the ProcessWatcher thread -- just queues the value."""
        self._process_queue.put((exe_name, exe_path))

    def queue_tray_command(self, command):
        """Called from the tray icon's thread (or the hook thread, for the
        global show-window hotkey) -- just queues the command."""
        self._tray_queue.put(command)

    def _start_capture(self, on_result):
        self._capture_purpose = on_result
        hook_manager.capture_next_key(lambda vk: self._capture_queue.put(vk))

    def _handle_captured_key(self, vk):
        if self._capture_purpose is None:
            return
        on_result = self._capture_purpose
        self._capture_purpose = None
        on_result(vk)

    def _start_combo_capture(self, on_result):
        self._combo_capture_purpose = on_result
        hook_manager.capture_next_combo(lambda combo: self._combo_capture_queue.put(combo))

    def _handle_captured_combo(self, combo):
        if self._combo_capture_purpose is None:
            return
        on_result = self._combo_capture_purpose
        self._combo_capture_purpose = None
        on_result(combo)

    def _handle_tray_command(self, command):
        logger.debug("GUI: handling tray command '%s'", command)
        if command == "show":
            self.deiconify()
            self.state("normal")
            self.lift()
            self.focus_force()
        elif command == "exit":
            if self.full_shutdown:
                self.full_shutdown()

    def _poll_background(self):
        try:
            while True:
                name, exe_path = self._process_queue.get_nowait()
                self._apply_process_change(name, exe_path)
        except queue.Empty:
            pass
        try:
            while True:
                vk = self._capture_queue.get_nowait()
                self._handle_captured_key(vk)
        except queue.Empty:
            pass
        try:
            while True:
                combo = self._combo_capture_queue.get_nowait()
                self._handle_captured_combo(combo)
        except queue.Empty:
            pass
        try:
            while True:
                result = self._scan_queue.get_nowait()
                self._handle_scan_result(result)
        except queue.Empty:
            pass
        try:
            while True:
                command = self._tray_queue.get_nowait()
                self._handle_tray_command(command)
        except queue.Empty:
            pass
        self.after(150, self._poll_background)

    # Process names we never want to suggest adding as a "game" -- this app
    # itself, under any of the ways it might show up as the foreground window.
    _SELF_PROCESS_NAMES = {
        "python.exe", "pythonw.exe", "keybindchanger.exe", "keybindchanger-debug.exe",
    }
    MAX_RECENT_FOREGROUND = 10

    def _apply_process_change(self, exe_name, exe_path=None):
        logger.debug("GUI: handling process change -> %s", exe_name)
        self.active_exe = exe_name
        self._refresh_active_mapping()
        self._push_active_typing_hotkeys()
        self._record_recent_foreground(exe_name, exe_path)

    def _record_recent_foreground(self, exe_name, exe_path):
        if not exe_name or exe_name.lower() in self._SELF_PROCESS_NAMES:
            return
        entry = {
            "display_name": os.path.splitext(exe_name)[0],
            "exe_name": exe_name,
            "exe_path": exe_path,
        }
        # Most-recent-first, de-duplicated by exe name, capped at 10.
        self.recent_foreground = [
            e for e in self.recent_foreground if e["exe_name"].lower() != exe_name.lower()
        ]
        self.recent_foreground.insert(0, entry)
        self.recent_foreground = self.recent_foreground[: self.MAX_RECENT_FOREGROUND]

    def _refresh_active_mapping(self):
        profile = profile_manager.get_profile(self.config_data, self.active_exe) if self.active_exe else None
        mapping = profile_manager.build_mapping_dict(profile)
        logger.debug(
            "GUI: pushing mapping to hook for active_exe='%s' -> profile=%s, %d override(s)",
            self.active_exe, profile["display_name"] if profile else None, len(mapping),
        )
        hook_manager.set_active_mapping(mapping)

    # ------------------------------------------------------------------
    # Status bar / window close behavior
    # ------------------------------------------------------------------
    def _tick_status(self):
        status = hook_manager.get_status()
        if not status.get("hook_installed"):
            self.status_dot.itemconfig(self._status_dot_id, fill=theme.STATUS_BAD)
            self.status_var.set(
                f"Keyboard hook NOT installed ({status.get('last_error')}) "
                "\u2014 remapping and key capture will not work. Try restarting as Administrator."
            )
            self.after(500, self._tick_status)
            return

        profile = profile_manager.get_profile(self.config_data, self.active_exe) if self.active_exe else None
        profile_text = profile["display_name"] if profile else "Default (unmodified keys)"
        if status["typing_mode"]:
            dot_color, typing_text = theme.STATUS_WARN, "ON \u2014 all keys normal"
        else:
            dot_color, typing_text = theme.STATUS_OK, "off"
        self.status_dot.itemconfig(self._status_dot_id, fill=dot_color)
        self.status_var.set(
            f"Detected process: {self.active_exe or '--'}    |    "
            f"Active profile: {profile_text}    |    Typing mode: {typing_text}"
        )
        self.after(500, self._tick_status)

    def minimize_to_tray(self):
        """Bound to the window's close (X) button. Hides the window instead
        of quitting, since the whole point is to keep remapping running in
        the background while you're in a game. Falls back to a full exit
        if no tray icon is available (e.g. pystray isn't installed)."""
        if self.tray_icon is None:
            logger.info("GUI: window closed, no tray icon available -- shutting down fully.")
            if self.full_shutdown:
                self.full_shutdown()
            return

        logger.info("GUI: window closed -- minimizing to system tray (still running in the background).")
        self.withdraw()
        if not self._shown_tray_notice:
            self._shown_tray_notice = True
            try:
                self.tray_icon.notify("KeyBind Changer is still running in the system tray.", "KeyBind Changer")
            except Exception:
                logger.debug("Tray notify failed (non-fatal)", exc_info=True)
