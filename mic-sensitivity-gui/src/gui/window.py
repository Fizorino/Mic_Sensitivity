from cProfile import label
import pyvisa
import json
import math
import threading
import time  # added for non-blocking sweep polling
import queue  # NEW: for decoupling acquisition from GUI
from pathlib import Path
from tkinter import Tk, Frame, Button, Label, filedialog, messagebox, Canvas, Scrollbar
from upv.upv_auto_config import find_upv_ip, apply_grouped_settings, fetch_and_plot_trace, load_config, save_config
from tkinter import ttk, Entry
from gui.display_map import (
    INSTRUMENT_GENERATOR_OPTIONS,
    CHANNEL_GENERATOR_OPTIONS,
    OUTPUT_TYPE_OPTIONS,
    IMPEDANCE_OPTIONS_BAL,
    IMPEDANCE_OPTIONS_UNBAL,
    DISPLAY_LABEL_OVERRIDES
)

SETTINGS_FILE = r"c:\Users\AU001A0W\OneDrive - WSA\Documents\Mic_Sensitivity\settings.json"
# Default preset base name (without .json). When user edits any control after loading a non-default preset,
# the active preset label reverts to this default to signal divergence from the loaded preset.
DEFAULT_PRESET_NAME = "settings"  # Changed from 'main_settings' per user request

reverse_output_type_map = {v: k for k, v in OUTPUT_TYPE_OPTIONS.items()}

class MainWindow(Frame):
    def __init__(self, master, run_upv_callback):
        super().__init__(master)
        self.run_upv_callback = run_upv_callback
        self.master = master
        self.master.title("UPV GUI")
        self.master.geometry("1200x700")  # Wider window for all sections

        self.top_frame = Frame(self.master)
        self.top_frame.pack(pady=20, fill="x")

        # Left spacer
        self.left_spacer = Frame(self.top_frame)
        self.left_spacer.pack(side="left", expand=True)

        # Left column for main controls
        self.left_frame = Frame(self.top_frame)
        self.left_frame.pack(side="left", padx=(0, 20), anchor="n")

        Label(self.left_frame, text="UPV GUI", font=("Helvetica", 16)).pack(pady=10)

        # Use grid for button rows to prevent shifting
        btn_width = 18
        button_row1 = Frame(self.left_frame)
        button_row1.pack(pady=5)
        btn1 = Button(button_row1, text="Connect to UPV", command=self.connect_to_upv, width=btn_width)
        self.connect_btn = btn1
        btn2 = Button(button_row1, text="Save Preset", command=self.save_preset, width=btn_width)
        btn1.grid(row=0, column=0, padx=(0, 8), pady=0)
        btn2.grid(row=0, column=1, padx=(0, 0), pady=0)

        button_row2 = Frame(self.left_frame)
        button_row2.pack(pady=5)
        btn3 = Button(button_row2, text="Apply Settings", command=self.apply_settings, width=btn_width)
        btn4 = Button(button_row2, text="Load Preset", command=self.load_preset, width=btn_width)
        btn3.grid(row=0, column=0, padx=(0, 8), pady=0)
        btn4.grid(row=0, column=1, padx=(0, 0), pady=0)

        btn5 = Button(self.left_frame, text="Start Sweep", command=self.start_sweep, width=btn_width)
        btn5.pack(pady=5)
        self.start_sweep_btn = btn5
        # Require Apply Settings before allowing sweep start
        self._settings_applied = False
        self.start_sweep_btn.config(state="disabled")

        # Stop button for continuous sweep (disabled until a continuous sweep is started)
        self.stop_sweep_btn = Button(
            self.left_frame,
            text="Stop Continuous",
            command=self.stop_continuous_sweep,
            width=btn_width,
            state="disabled"
        )
        self.stop_sweep_btn.pack(pady=2)

        # Internal state tracking for continuous sweep
        self._continuous_active = False
        # Track if a single (non-continuous) sweep is currently running so we can live-update
        self._single_sweep_in_progress = False
        # Track currently loaded preset base name for export working title (default active at startup)
        self._current_preset_name = DEFAULT_PRESET_NAME

        # Snapshot (read-back) button
        btn_snapshot = Button(self.left_frame, text="Snapshot Settings", command=self.snapshot_upv, width=btn_width)
        btn_snapshot.pack(pady=2)

        # Show Sweep Display (instrument + embedded plot)
        btn_show_disp = Button(self.left_frame, text="Show Sweep Display", command=self.show_sweep_display, width=btn_width)
        btn_show_disp.pack(pady=2)
        # Keep reference to display button (we may disable/hide if switching to fully automatic live view later)
        self._show_display_btn = btn_show_disp

        # Right spacer
        self.right_spacer = Frame(self.top_frame)
        self.right_spacer.pack(side="left", expand=True)

        self.status_label = Label(self.left_frame, text="", fg="green")
        self.status_label.pack(pady=10)
        # Display currently loaded preset (default on startup)
        self.preset_label = Label(self.left_frame, text=f"Preset: {self._current_preset_name}", fg="#555555")
        self.preset_label.pack(pady=(0,8))

        # 2x2 grid container for four independently scrollable panels
        self.grid_frame = Frame(self.master)
        self.grid_frame.pack(side="top", expand=True, fill="both")
        for r in range(2):
            self.grid_frame.grid_rowconfigure(r, weight=1)
        for c in range(2):
            self.grid_frame.grid_columnconfigure(c, weight=1)

        # Placeholder so older methods referencing self.canvas don't break; each panel has its own canvas
        self.canvas = None
        self.log_text = None
        self.log_file = None
        self.enable_logging = False

        # Global scroll management
        self.active_scroll_canvas = None  # Canvas currently under mouse
        self._suspend_global_scroll = False  # Temporarily disable (e.g., when over combobox)
        # Bind a single global mouse wheel handler (Windows uses <MouseWheel>)
        self.master.bind_all("<MouseWheel>", self._on_global_mousewheel, add="+")
        # Optional: Linux (ignored on Windows but harmless)
        self.master.bind_all("<Button-4>", self._on_button4, add="+")
        self.master.bind_all("<Button-5>", self._on_button5, add="+")

        self.entries = {}
        self.load_settings()
        self.upv = None
        # Ensure initial state
        self._refresh_start_sweep_state()
        # Connection state helpers
        self._connecting = False
        self._scan_anim_phase = 0
        # Cached display frequency limits (fmin, fmax) from instrument display (DISP:SWE:A:BOTT?/TOP?)
        self._display_freq_limits = None  # (fmin, fmax)
        self._display_amp_limits = None   # (amin, amax) from DISP:SWE:A:BOTT?/TOP?
        # Simple counter to throttle SCPI queries for display limits during live polling
        self._display_axis_query_counter = 0
        # Persistently locked Y-limits (once fetched from instrument) so plot does not rescale
        self._locked_y_limits = None
        # Thread-safe VISA access & background acquisition pipeline
        self._visa_lock = threading.Lock()
        self._data_queue = queue.Queue(maxsize=2)  # keep freshest sample pairs only
        self._acq_thread = None
        self._acq_stop_event = threading.Event()
        self._acq_fail_count = 0
        self._live_consumer_started = False

    # ---------------- Safe VISA Helpers -----------------
    def _safe_query(self, cmd: str, *, timeout_ms: int = 1500, strip: bool = True):
        """Thread-safe query that enforces a temporary timeout and never blocks GUI.

        Returns: response string (optionally stripped) or None on failure/timeout.
        """
        upv = self.upv
        if upv is None:
            return None
        try:
            with self._visa_lock:
                old_timeout = getattr(upv, 'timeout', None)
                if old_timeout is not None:
                    try:
                        upv.timeout = timeout_ms
                    except Exception:
                        pass
                try:
                    resp = upv.query(cmd)
                finally:
                    if old_timeout is not None:
                        try:
                            upv.timeout = old_timeout
                        except Exception:
                            pass
            if strip and isinstance(resp, str):
                return resp.strip()
            return resp
        except Exception:
            return None

    def _safe_write(self, cmd: str):
        upv = self.upv
        if upv is None:
            return False
        try:
            with self._visa_lock:
                upv.write(cmd)
            return True
        except Exception:
            return False

    # ---------------- Shared Unit Resolution -----------------
    def _resolve_y_unit_from_settings(self):
        """Replicate unit resolution logic used in fetch_and_plot_trace.

        Priority:
          1. SENS:USER (sanitized) if present and non-empty
          2. SENS:UNIT or SENS1:UNIT (mapped to display forms)
          3. Fallback 'dBV'
        Returns sanitized display string.
        """
        try:
            import json as _json
            from pathlib import Path as _Path
            if not _Path(SETTINGS_FILE).exists():
                return 'dBV'
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as sf:
                data = _json.load(sf)
            user_unit_raw = data.get('SENS:USER')
            std_unit_raw = data.get('SENS:UNIT') or data.get('SENS1:UNIT')

            def _sanitize_user_unit(s: str) -> str:
                if not isinstance(s, str):
                    return ''
                s2 = s.strip().strip('"').strip("'")
                low = s2.lower()
                if low.startswith('db'):
                    rest = s2[2:].lstrip()
                    tokens = rest.split()
                    tokens = [t.upper() if t.lower() == 'spl' else t for t in tokens]
                    if tokens:
                        return 'dB ' + ' '.join(tokens)
                    return 'dB'
                return s2

            if isinstance(user_unit_raw, str) and user_unit_raw.strip():
                cand = _sanitize_user_unit(user_unit_raw)
                if cand:
                    return cand
            if isinstance(std_unit_raw, str):
                yu = std_unit_raw.strip().upper()
                unit_map = {
                    'DBR': 'dBr', 'DBV': 'dBV', 'DBU': 'dBu', 'DBM': 'dBm',
                    'V': 'V', 'MV': 'mV', 'UV': 'μV', 'UVR': 'μV', 'UV RMS': 'μV',
                    'UVRMS': 'μV', 'PCT': '%', '%': '%'
                }
                return unit_map.get(yu, std_unit_raw.strip())
        except Exception:
            pass
        return 'dBV'

    def _freeze_axis_limits(self, ax, x_vals, y_vals):
        """Deprecated: retained for backward compatibility (no-op after fixed range change)."""
        try:
            # No action; fixed frequency range logic now applied via _apply_fixed_freq_and_auto_level.
            return
        except Exception:
            pass

    # New helper now locking Y-axis strictly to instrument limits once acquired.
    def _apply_fixed_freq_and_auto_level(self, ax, x_vals, y_vals):  # keeping name for compatibility
        """Apply fixed X (100–12k Hz) and lock Y to instrument limits ONLY when they become non-trivial.

        Rules:
          1. Query DISP:SWE:A:BOTT?/TOP? each call until a NON-TRIVIAL span is found.
             A span is considered trivial if:
                - (amin, amax) == (0, 1) OR
                - amax - amin < 0.5 (very small) OR
                - amin == amax
          2. Before lock is established, fall back to data-driven autoscale (with 5% padding) so the user sees data.
          3. Once a valid span is acquired it is frozen in self._locked_y_limits and reused thereafter.
          4. If no data yet and no valid span, show provisional (0,1) once (avoid flicker) until something better arrives.
        """
        try:
            FMIN, FMAX = 100.0, 12000.0
            try:
                ax.set_xlim(FMIN, FMAX)
            except Exception:
                pass

            have_data = bool(x_vals) and bool(y_vals)

            # If already locked, just apply and exit
            if self._locked_y_limits is not None:
                try:
                    ax.set_ylim(*self._locked_y_limits)
                except Exception:
                    pass
                return

            # Attempt to read instrument limits
            inst_limits = None
            if self.upv is not None:
                try:
                    amin_q = float(self.upv.query("DISP:SWE:A:BOTT?").strip())
                    amax_q = float(self.upv.query("DISP:SWE:A:TOP?").strip())
                    if amax_q > amin_q:
                        inst_limits = (amin_q, amax_q)
                        self._display_amp_limits = inst_limits
                except Exception:
                    inst_limits = self._display_amp_limits  # cached (may be None)
            else:
                inst_limits = self._display_amp_limits

            locked_this_call = False
            if inst_limits is not None:
                amin, amax = inst_limits
                span = amax - amin
                trivial = (
                    (abs(amin) < 1e-9 and abs(amax - 1.0) < 1e-9) or  # exactly 0..1
                    span < 0.5 or
                    amax <= amin
                )
                if not trivial:
                    # Lock now
                    self._locked_y_limits = inst_limits
                    locked_this_call = True

            if self._locked_y_limits is not None:
                # Apply locked (either from this call or previously)
                try:
                    ax.set_ylim(*self._locked_y_limits)
                except Exception:
                    pass
                # Optional: surface once that we locked
                if locked_this_call:
                    try:
                        self.update_status(f"Y locked: {self._locked_y_limits[0]:.2f}..{self._locked_y_limits[1]:.2f}")
                    except Exception:
                        pass
                return

            # Not locked yet -> fallback to data autoscale so user sees something meaningful
            if have_data:
                ys_window = [y for x, y in zip(x_vals, y_vals) if FMIN <= x <= FMAX]
                if not ys_window:
                    ys_window = y_vals
                try:
                    dmin = min(ys_window)
                    dmax = max(ys_window)
                    if dmax == dmin:
                        dmin -= 0.1
                        dmax += 0.1
                    span = dmax - dmin
                    pad = span * 0.05 if span > 0 else 0.5
                    ymin = dmin - pad
                    ymax = dmax + pad
                except Exception:
                    ymin, ymax = 0.0, 1.0
            else:
                ymin, ymax = 0.0, 1.0

            try:
                ax.set_ylim(ymin, ymax)
            except Exception:
                pass
        except Exception:
            pass

    # ---------------- Connection / Scanning -----------------
    def _anim_scan_tick(self):
        """Animate scanning status while background thread searches for UPV."""
        if not self._connecting:
            return
        dots = '.' * (self._scan_anim_phase % 4)
        base = "Scanning for UPV"  # concise to reduce flicker
        self.update_status(f"🔍 {base}{dots}", color="green")
        self._scan_anim_phase += 1
        self.after(350, self._anim_scan_tick)

    def _thread_safe_status(self, msg, color="green"):
        try:
            self.after(0, lambda m=msg, c=color: self.update_status(m, c))
        except Exception:
            pass

    def _refresh_start_sweep_state(self):
        """Enable Start Sweep only when settings applied AND UPV connected."""
        try:
            if not hasattr(self, 'start_sweep_btn'):
                return
            if getattr(self, '_settings_applied', False) and self.upv is not None:
                self.start_sweep_btn.config(state="normal")
            else:
                self.start_sweep_btn.config(state="disabled")
        except Exception:
            pass

    def _create_combo(self, parent, values, current_display, *, width=20, grid_kwargs=None, entry_key=None, store_attr=None):
        """Utility to build a readonly ttk.Combobox with unified wheel binding.

        params:
            parent: tk container
            values: list[str] values to display
            current_display: value to set
            width: combobox width
            grid_kwargs: dict passed to grid()
            entry_key: if provided, tuple key for self.entries registration
            store_attr: if provided, attribute name on self to store the widget (e.g. 'output_type_combo')
        """
        combo = ttk.Combobox(parent, values=values, width=width, state="readonly")
        combo.set(current_display)
        if grid_kwargs:
            combo.grid(**grid_kwargs)
        # Ensure wheel events go to panel scroll
        combo.unbind("<MouseWheel>")
        self.bind_combobox_mousewheel(combo)
        # Any combobox selection change marks configuration as modified
        combo.bind('<<ComboboxSelected>>', lambda e: self._mark_modified(), add='+')
        if entry_key is not None:
            self.entries[entry_key] = combo
        if store_attr:
            setattr(self, store_attr, combo)
        return combo

    def load_settings(self):
        # Clear existing panel containers (if any)
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.entries.clear()
        # Reset analyzer hidden rows registry early so captures during rebuild are guaranteed
        self._an_func_hidden_rows = {}

        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)

            # --- Normalization: convert legacy/snapshot unit variants to canonical display ---
            # Handles: PCT -> %, DBV/DBU/DBM case, HZ/KHZ casing, OHM/KOHM/Ω, time units, micro volts (uV/UV -> μV)
            import re
            def _normalize_value(val: str) -> str:
                original = val
                s = val.strip()
                if not s:
                    return s
                # Only attempt heavy normalization if there's at least one digit (avoid enumerations like AUTO, OFF)
                if not any(ch.isdigit() for ch in s):
                    # Still convert pure unit tokens like 'OHM'
                    pass
                # Collapse multiple spaces
                s = re.sub(r"\s+", " ", s)
                # Guard: skip normalization for pure code tokens (pattern Letter + digits + optional letters, no spaces)
                # Examples: S256K, R200K, S1K, LINP, LOGS
                if ' ' not in s and re.fullmatch(r"[A-Za-z]{1,6}\d{1,5}[A-Za-z]{0,4}", s):
                    return original  # leave as-is
                # Percent: replace trailing/standalone PCT with %
                s = re.sub(r"(?i)\bPCT\b", "%", s)
                # Ensure a space before % if number immediately followed by % without space
                s = re.sub(r"(\d)(%)", r"\1 \2", s)
                # dBV / dBu / dBm casing (avoid changing already correct)
                s = re.sub(r"(?i)\bDBV\b", "dBV", s)
                s = re.sub(r"(?i)\bDBU\b", "dBu", s)
                s = re.sub(r"(?i)\bDBM\b", "dBm", s)
                # Frequency units
                s = re.sub(r"(?i)\bHZ\b", "Hz", s)
                s = re.sub(r"(?i)\bKHZ\b", "kHz", s)
                # Time units (S, MS, US, MIN)
                # Convert US/us to μs for display, keep ms/s/min lowercase
                s = re.sub(r"(?i)(\d)\s*US\b", r"\1 μs", s)
                s = re.sub(r"(?i)\bMS\b", "ms", s)
                s = re.sub(r"(?i)\bS\b", "s", s)
                s = re.sub(r"(?i)\bMIN\b", "min", s)
                # Voltage micro symbol: uV/UV -> μV (display convention)
                s = re.sub(r"(?i)\buV\b", "μV", s)
                # Impedance: OHM/Ω -> ohm; KOHM/KΩ -> kohm
                s = re.sub(r"(?i)\bKOHM\b", "kohm", s)
                s = re.sub(r"(?i)\bKΩ\b", "kohm", s)
                s = re.sub(r"(?i)\bOHM\b", "ohm", s)
                # Replace standalone Ω with ohm
                s = re.sub(r"Ω", "ohm", s)
                # Normalize kohm casing
                s = re.sub(r"(?i)\bkohm\b", "kohm", s)
                # Ensure single space between numeric and unit if they are concatenated (e.g., 100Hz -> 100 Hz)
                # Avoid splitting embedded code tokens like S256K (preceded by a letter before the digits)
                s = re.sub(r"(?<![A-Za-z])(\d+)([a-zA-Zμ])", r"\1 \2", s)
                # Repair accidental earlier snapshot mutations that may have split code tokens (R200 K -> R200K)
                s = re.sub(r"\b([A-Za-z])(\d{1,5})\s+([A-Za-z]{1,3})\b",
                            lambda m: (m.group(1)+m.group(2)+m.group(3))
                                      if re.fullmatch(r"[A-Za-z]{1,6}\d{1,5}[A-Za-z]{0,4}", m.group(1)+m.group(2)+m.group(3))
                                      else m.group(0),
                            s)
                # Trim again
                s = s.strip()
                return s if s != original else original

            try:
                normalization_changes = []  # collect (section, key, old, new)
                for section_name in ("Analyzer Function", "Generator Function", "Analyzer Config", "Generator Config"):
                    section_dict = settings.get(section_name)
                    if not isinstance(section_dict, dict):
                        continue
                    for key, val in list(section_dict.items()):
                        if isinstance(val, str):
                            norm = _normalize_value(val)
                            if norm != val:
                                section_dict[key] = norm
                                normalization_changes.append((section_name, key, val, norm))
                # Persist back to settings.json if any normalization changes occurred
                if normalization_changes:
                    try:
                        with open(SETTINGS_FILE, 'w', encoding='utf-8') as wf:
                            json.dump(settings, wf, indent=2, ensure_ascii=False)
                    except Exception:
                        pass
                    # Expose count for diagnostics (optional)
                    self._last_normalization_change_count = len(normalization_changes)
            except Exception:
                pass

            # Ensure 'Frequency' exists in 'Generator Function' so it can be shown when Sweep Ctrl is Off
            try:
                if isinstance(settings, dict) and "Generator Function" in settings:
                    gf = settings["Generator Function"]
                    if isinstance(gf, dict) and "Frequency" not in gf:
                        # Insert Frequency after 'Sweep Ctrl' if present, else at beginning
                        default_freq = "1000 Hz"
                        new_gf = {}
                        inserted = False
                        for k, v in gf.items():
                            new_gf[k] = v
                            if k == "Sweep Ctrl":
                                new_gf["Frequency"] = default_freq
                                inserted = True
                        if not inserted:
                            # Prepend Frequency
                            new_gf = {"Frequency": default_freq, **new_gf}
                        settings["Generator Function"] = new_gf
            except Exception:
                pass

            sections = [
                ("Generator Config", 0, 0),
                ("Analyzer Config", 0, 1),
                ("Generator Function", 1, 0),
                ("Analyzer Function", 1, 1)
            ]

            frames = {}
            # Build four scrollable panels with fixed header and subtle styling
            header_bg = "#2c3e50"
            header_fg = "#ffffff"
            panel_bg = "#f7f9fa"
            for section, row, col in sections:
                container = Frame(self.grid_frame, bd=1, relief="solid", background=panel_bg)
                container.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
                container.grid_rowconfigure(1, weight=1)
                container.grid_columnconfigure(0, weight=1)
                # Ensure scrollbar column (index 1) reserves space and never collapses
                container.grid_columnconfigure(1, minsize=14)

                # Header bar (fixed, not scrolling)
                header = Frame(container, bg=header_bg)
                header.grid(row=0, column=0, columnspan=2, sticky="ew")
                # Header label with zero vertical padding to eliminate gap above first row
                Label(header, text=section, font=("Helvetica", 12, "bold"), fg=header_fg, bg=header_bg, pady=0, padx=10).pack(side="left")
                # Add a subtle 1px separator line at bottom to clearly delineate header from scroll area
                sep = Frame(header, height=1, bg="#1b2732")
                sep.pack(fill="x", side="bottom")

                # Scrollable content area
                panel_canvas = Canvas(container, highlightthickness=0, bd=0, background=panel_bg)
                vscroll = Scrollbar(container, orient="vertical", command=panel_canvas.yview)
                panel_canvas.configure(yscrollcommand=vscroll.set)
                panel_canvas.grid(row=1, column=0, sticky="nsew")
                vscroll.grid(row=1, column=1, sticky="ns")

                # Removed top padding (was pady=10). Keep standard y=0 and rely on visual separator.
                inner_frame = Frame(panel_canvas, bd=0, background=panel_bg, padx=14, pady=0)
                window_id = panel_canvas.create_window((0, 0), window=inner_frame, anchor="nw")

                def _make_configure_callback(pc=panel_canvas, fr=inner_frame, wid=window_id):
                    def _on_configure(event):
                        # Always ensure the embedded frame matches the current canvas width
                        pc.itemconfig(wid, width=pc.winfo_width())
                        bbox = pc.bbox("all")
                        if bbox:
                            content_height = bbox[3] - bbox[1]
                            canvas_height = pc.winfo_height()
                            # Normal scrollregion update
                            pc.configure(scrollregion=bbox)
                            # Scenario: when the window is maximized the canvas grows taller so the
                            # entire content may fit. If the user had previously scrolled, Tk keeps the
                            # previous yview which produces an apparent blank gap at the top because the
                            # content is now shorter than the visible area. Force re-alignment to the top
                            # whenever content fits fully inside the canvas.
                            if content_height <= canvas_height:
                                # Keep scrollbar visibility consistent (extend region by 1px so OS themes
                                # don't sometimes hide the thumb completely on some platforms).
                                pc.configure(scrollregion=(0, 0, bbox[2], max(canvas_height, content_height) + 1))
                                pc.yview_moveto(0)
                            else:
                                # Only pin to top once on first realization to avoid fighting user scroll.
                                if not getattr(pc, '_initial_pinned', False):
                                    pc.yview_moveto(0)
                                    pc._initial_pinned = True
                        else:
                            # Fallback: no bbox yet; do nothing special.
                            pass
                    return _on_configure
                cb = _make_configure_callback()
                inner_frame.bind("<Configure>", cb)
                # Also react when canvas itself resizes (first map / window resize)
                panel_canvas.bind("<Configure>", lambda e, f=cb: f(e))
                # Keep a reference for manual triggering later
                panel_canvas._recalc = cb

                # Activate scroll focus when pointer enters this panel
                panel_canvas.bind("<Enter>", lambda e, pc=panel_canvas: self._activate_scroll(pc))
                inner_frame.bind("<Enter>", lambda e, pc=panel_canvas: self._activate_scroll(pc))

                frames[section] = (inner_frame, panel_canvas)

            for section, row, col in sections:
                frame, frame_canvas = frames[section]
                if section in settings:
                    impedance_row = None
                    impedance_frame = None
                    impedance_value = None
                    if section == "Generator Config":
                        self.output_type_combo = None  # <-- Only reset for Generator Config

                    for i, (label, value) in enumerate(settings[section].items(), start=0):
                        # Remove extra top gap specifically for first row in Generator Config (use int 0 not tuple)
                        row_pady = 0 if (section == "Generator Config" and i == 0) else 2
                        # Dynamic sweep control visibility support for Generator Function section
                        if section == "Generator Function" and i == 0:
                            # Initialize storage for row widgets (label + control) we may hide/show
                            self._gen_func_widgets = {}
                            self._gen_func_dynamic_labels = {"Frequency", "Next Step", "X Axis", "Z Axis", "Spacing", "Start", "Stop", "Points", "Halt"}
                        # Friendly display names while keeping underlying JSON keys
                        shown_label = DISPLAY_LABEL_OVERRIDES.get(label, label)
                        label_widget = Label(frame, text=shown_label, anchor="w", width=22, bg=frame["background"])
                        label_widget.grid(row=i, column=0, sticky="w", padx=(0,8), pady=row_pady)
                        if section == "Generator Function" and label in getattr(self, '_gen_func_dynamic_labels', set()):
                            self._gen_func_widgets.setdefault(label, []).append(label_widget)
                        if section == "Generator Config" and label == "Instrument Generator":
                            display_values = list(INSTRUMENT_GENERATOR_OPTIONS.values())
                            current_display = INSTRUMENT_GENERATOR_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": row_pady},
                                               entry_key=("Generator Config", label))
                        elif section == "Generator Config" and label == "Channel Generator":
                            display_values = list(CHANNEL_GENERATOR_OPTIONS.values())
                            current_display = CHANNEL_GENERATOR_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": row_pady},
                                               entry_key=("Generator Config", label))
                        elif section == "Generator Config" and label == "Output Type (Unbal/Bal)":
                            display_values = list(OUTPUT_TYPE_OPTIONS.values())
                            current_display = OUTPUT_TYPE_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": row_pady},
                                               entry_key=("Generator Config", label),
                                               store_attr="output_type_combo")
                            output_type_row = i
                        elif section == "Generator Config" and label == "Common (Float/Ground)":
                            # Use Radiobuttons for GRO/FLO
                            from gui.display_map import COMMON_OPTIONS
                            import tkinter as tk
                            self.common_var = tk.StringVar()
                            self.common_var.set(value if value in COMMON_OPTIONS else "GRO")
                            radio_frame = Frame(frame)
                            radio_frame.grid(row=i, column=1, sticky="w", pady=row_pady)
                            for code, display in COMMON_OPTIONS.items():
                                rb = ttk.Radiobutton(radio_frame, text=display, variable=self.common_var, value=code)
                                rb.pack(side="left", padx=5)
                            self.entries[("Generator Config", label)] = self.common_var
                        elif section == "Generator Config" and label == "Impedance":
                            self.impedance_row = i
                            self.impedance_frame = frame
                            impedance_value = value
                        elif section == "Generator Config" and label == "Bandwidth Generator":
                            from gui.display_map import BANDWIDTH_GENERATOR_OPTIONS
                            display_values = list(BANDWIDTH_GENERATOR_OPTIONS.values())
                            current_display = BANDWIDTH_GENERATOR_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": row_pady},
                                               entry_key=("Generator Config", label))
                        elif section == "Generator Config" and label == "Volt Range (Auto/Fix)":
                            from gui.display_map import VOLT_RANGE_OPTIONS
                            import tkinter as tk
                            self.volt_range_var = tk.StringVar()
                            self.volt_range_var.set(value if value in VOLT_RANGE_OPTIONS else "AUTO")
                            radio_frame = Frame(frame)
                            radio_frame.grid(row=i, column=1, sticky="w", pady=row_pady)
                            for code, display in VOLT_RANGE_OPTIONS.items():
                                rb = ttk.Radiobutton(radio_frame, text=display, variable=self.volt_range_var, value=code)
                                rb.pack(side="left", padx=5)
                            self.entries[("Generator Config", label)] = self.volt_range_var
                        elif section == "Generator Config" and label == "Max Voltage":
                            # Split value and unit if possible (case-insensitive, normalize dB units)
                            import re
                            unit_options = ["V", "mV", "μV", "dBV", "dBu", "dBm"]
                            val_str = str(value)
                            match = re.match(r"^([\-\d\.]+)\s*([a-zA-Zμ]+)?$", val_str)
                            if match:
                                val_part = match.group(1)
                                raw_unit = match.group(2)
                                if raw_unit:
                                    # normalize by case-insensitive match against unit_options
                                    unit_part = None
                                    for opt in unit_options:
                                        if raw_unit.lower() == opt.lower():
                                            unit_part = opt
                                            break
                                    if unit_part is None:
                                        unit_part = unit_options[0]
                                else:
                                    unit_part = unit_options[0]
                            else:
                                val_part = val_str
                                unit_part = unit_options[0]
                            hv_frame = Frame(frame)
                            hv_frame.grid(row=i, column=1, sticky="w", pady=row_pady)
                            entry = Entry(hv_frame, width=22)
                            entry.insert(0, val_part)
                            entry.pack(side="left", padx=(0, 8))
                            combo = ttk.Combobox(hv_frame, values=unit_options, width=6, state="readonly")
                            combo.set(unit_part)
                            combo.pack(side="left")
                            import math
                            def convert_voltage_unit(event=None, entry=entry, combo=combo):
                                try:
                                    val = float(entry.get())
                                except Exception:
                                    return
                                old_unit = getattr(combo, '_last_unit', unit_part)
                                new_unit = combo.get()
                                scale = {"V": 1, "mV": 1e-3, "μV": 1e-6}
                                Z = 600  # Ohms, for dBm conversion
                                # Convert any unit to SI volts first
                                def to_volts(val, unit):
                                    if unit in scale:
                                        return val * scale[unit]
                                    elif unit == "dBV":
                                        return 10 ** (val / 20)
                                    elif unit == "dBu":
                                        return 0.775 * (10 ** (val / 20))
                                    elif unit == "dBm":
                                        p = 10 ** (val / 10) / 1000
                                        return (p * Z) ** 0.5
                                    else:
                                        return val
                                # Convert SI volts to any unit
                                def from_volts(v, unit):
                                    if unit in scale:
                                        new_val = v / scale[unit]
                                        return int(new_val) if new_val.is_integer() else round(new_val, 6)
                                    elif unit == "dBV":
                                        return round(20 * math.log10(v / 1.0), 6) if v > 0 else ""
                                    elif unit == "dBu":
                                        return round(20 * math.log10(v / 0.775), 6) if v > 0 else ""
                                    elif unit == "dBm":
                                        p = (v ** 2) / Z
                                        return round(10 * math.log10(p * 1000), 6) if v > 0 else ""
                                    else:
                                        return v
                                v_si = to_volts(val, old_unit)
                                result = from_volts(v_si, new_unit)
                                entry.delete(0, 'end')
                                entry.insert(0, str(result))
                                combo._last_unit = new_unit
                            combo._last_unit = unit_part
                            combo.bind('<<ComboboxSelected>>', convert_voltage_unit)
                            combo.unbind("<MouseWheel>")
                            self.bind_combobox_mousewheel(combo)
                            self.entries[(section, label)] = (entry, combo)
                        elif section == "Generator Config" and label == "Ref Voltage":
                            # Same as Max Voltage: value + unit (case-insensitive)
                            import re
                            unit_options = ["V", "mV", "μV", "dBV", "dBu", "dBm"]
                            val_str = str(value)
                            match = re.match(r"^([\-\d\.]+)\s*([a-zA-Zμ]+)?$", val_str)
                            if match:
                                val_part = match.group(1)
                                raw_unit = match.group(2)
                                if raw_unit:
                                    unit_part = None
                                    for opt in unit_options:
                                        if raw_unit.lower() == opt.lower():
                                            unit_part = opt
                                            break
                                    if unit_part is None:
                                        unit_part = unit_options[0]
                                else:
                                    unit_part = unit_options[0]
                            else:
                                val_part = val_str
                                unit_part = unit_options[0]
                            hv_frame = Frame(frame)
                            hv_frame.grid(row=i, column=1, sticky="w", pady=row_pady)
                            entry = Entry(hv_frame, width=22)
                            entry.insert(0, val_part)
                            entry.pack(side="left", padx=(0, 8))
                            combo = ttk.Combobox(hv_frame, values=unit_options, width=6, state="readonly")
                            combo.set(unit_part)
                            combo.pack(side="left")
                            import math
                            def convert_voltage_unit(event=None, entry=entry, combo=combo):
                                try:
                                    val = float(entry.get())
                                except Exception:
                                    return
                                old_unit = getattr(combo, '_last_unit', unit_part)
                                new_unit = combo.get()
                                scale = {"V": 1, "mV": 1e-3, "μV": 1e-6}
                                Z = 600  # Ohms, for dBm conversion
                                def to_volts(val, unit):
                                    if unit in scale:
                                        return val * scale[unit]
                                    elif unit == "dBV":
                                        return 10 ** (val / 20)
                                    elif unit == "dBu":
                                        return 0.775 * (10 ** (val / 20))
                                    elif unit == "dBm":
                                        p = 10 ** (val / 10) / 1000
                                        return (p * Z) ** 0.5
                                    else:
                                        return val
                                def from_volts(v, unit):
                                    if unit in scale:
                                        new_val = v / scale[unit]
                                        return int(new_val) if new_val.is_integer() else round(new_val, 6)
                                    elif unit == "dBV":
                                        return round(20 * math.log10(v / 1.0), 6) if v > 0 else ""
                                    elif unit == "dBu":
                                        return round(20 * math.log10(v / 0.775), 6) if v > 0 else ""
                                    elif unit == "dBm":
                                        p = (v ** 2) / Z
                                        return round(10 * math.log10(p * 1000), 6) if v > 0 else ""
                                    else:
                                        return v
                                v_si = to_volts(val, old_unit)
                                result = from_volts(v_si, new_unit)
                                entry.delete(0, 'end')
                                entry.insert(0, str(result))
                                combo._last_unit = new_unit
                            combo._last_unit = unit_part
                            combo.bind('<<ComboboxSelected>>', convert_voltage_unit)
                            combo.unbind("<MouseWheel>")
                            self.bind_combobox_mousewheel(combo)
                            self.entries[(section, label)] = (entry, combo)
                        elif section == "Generator Config" and label == "Ref Frequency":
                            # Value + unit, only Hz and kHz
                            import re
                            unit_options = ["Hz", "kHz"]
                            val_str = str(value)
                            match = re.match(r"^([\-\d\.]+)\s*([a-zA-Z]+)?$", val_str)
                            if match:
                                val_part = match.group(1)
                                unit_part = match.group(2) if match.group(2) in unit_options else unit_options[0]
                            else:
                                val_part = val_str
                                unit_part = unit_options[0]
                            hv_frame = Frame(frame)
                            hv_frame.grid(row=i, column=1, sticky="w", pady=row_pady)
                            entry = Entry(hv_frame, width=22)
                            entry.insert(0, val_part)
                            entry.pack(side="left", padx=(0, 8))
                            combo = ttk.Combobox(hv_frame, values=unit_options, width=6, state="readonly")
                            combo.set(unit_part)
                            combo.pack(side="left")
                            def convert_freq_unit(event=None, entry=entry, combo=combo):
                                try:
                                    val = float(entry.get())
                                except Exception:
                                    return
                                old_unit = getattr(combo, '_last_unit', unit_part)
                                new_unit = combo.get()
                                scale = {"Hz": 1, "kHz": 1e3}
                                if old_unit in scale and new_unit in scale:
                                    val_si = val * scale[old_unit]
                                    new_val = val_si / scale[new_unit]
                                    entry.delete(0, 'end')
                                    entry.insert(0, str(int(new_val) if new_val.is_integer() else round(new_val, 6)))
                                combo._last_unit = new_unit
                            combo._last_unit = unit_part
                            combo.bind('<<ComboboxSelected>>', convert_freq_unit)
                            combo.unbind("<MouseWheel>")
                            self.bind_combobox_mousewheel(combo)
                            self.entries[(section, label)] = (entry, combo)
                        elif label == "Low Dist":
                            import tkinter as tk
                            var = tk.StringVar()
                            var.set("ON" if str(value).upper() == "ON" else "OFF")
                            cb = tk.Checkbutton(frame, variable=var, onvalue="ON", offvalue="OFF")
                            cb.grid(row=i, column=1, sticky="w", pady=2)
                            if var.get() == "ON":
                                cb.select()
                            else:
                                cb.deselect()
                            self.entries[(section, label)] = var
                        elif section == "Generator Function" and label == "Function Generator":
                            from gui.display_map import FUNCTION_GENERATOR_OPTIONS
                            display_values = list(FUNCTION_GENERATOR_OPTIONS.values())
                            current_display = FUNCTION_GENERATOR_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Generator Function" and label == "Sweep Ctrl":
                            from gui.display_map import SWEEP_CTRL_OPTIONS
                            display_values = list(SWEEP_CTRL_OPTIONS.values())
                            current_display = SWEEP_CTRL_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                            # We'll bind visibility update after building all rows
                        elif section == "Generator Function" and label == "Frequency":
                            # Value + unit (Hz / kHz)
                            import re
                            unit_options = ["Hz", "kHz"]
                            val_str = str(value)
                            match = re.match(r"^([\-\d\.]+)\s*([a-zA-Z]+)?$", val_str)
                            if match:
                                val_part = match.group(1)
                                unit_part = match.group(2)
                                # Normalize provided unit to expected capitalization
                                if unit_part:
                                    unit_part_norm = unit_part.lower()
                                    if unit_part_norm in ("hz",):
                                        unit_part = "Hz"
                                    elif unit_part_norm in ("khz",):
                                        unit_part = "kHz"
                                if unit_part not in unit_options:
                                    unit_part = unit_options[0]
                            else:
                                val_part = val_str
                                unit_part = unit_options[0]
                            freq_frame = Frame(frame)
                            freq_frame.grid(row=i, column=1, sticky="w", pady=2)
                            entry = Entry(freq_frame, width=22)
                            entry.insert(0, val_part)
                            entry.pack(side="left", padx=(0, 8))
                            combo = ttk.Combobox(freq_frame, values=unit_options, width=6, state="readonly")
                            combo.set(unit_part)
                            combo.pack(side="left")
                            def convert_freq_unit(event=None, entry=entry, combo=combo):
                                try:
                                    val = float(entry.get())
                                except Exception:
                                    return
                                old_unit = getattr(combo, '_last_unit', unit_part)
                                new_unit = combo.get()
                                scale = {"Hz": 1, "kHz": 1e3}
                                if old_unit in scale and new_unit in scale:
                                    val_si = val * scale[old_unit]
                                    new_val = val_si / scale[new_unit]
                                    entry.delete(0, 'end')
                                    entry.insert(0, str(int(new_val) if new_val.is_integer() else round(new_val, 6)))
                                combo._last_unit = new_unit
                            combo._last_unit = unit_part
                            combo.bind('<<ComboboxSelected>>', convert_freq_unit)
                            combo.unbind("<MouseWheel>")
                            self.bind_combobox_mousewheel(combo)
                            self.entries[(section, label)] = (entry, combo)
                            # Track for dynamic visibility
                            if section == "Generator Function":
                                self._gen_func_widgets.setdefault(label, []).append(freq_frame)
                        elif section == "Generator Function" and label == "Next Step":
                            from gui.display_map import NEXT_STEP_OPTIONS
                            display_values = list(NEXT_STEP_OPTIONS.values())
                            current_display = NEXT_STEP_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                            if section == "Generator Function":
                                self._gen_func_widgets.setdefault(label, []).append(self.entries[(section, label)])
                        elif section == "Generator Function" and label == "X Axis":
                            from gui.display_map import X_AXIS_OPTIONS
                            display_values = list(X_AXIS_OPTIONS.values())
                            current_display = X_AXIS_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                            if section == "Generator Function":
                                self._gen_func_widgets.setdefault(label, []).append(self.entries[(section, label)])
                        elif section == "Generator Function" and label == "Z Axis":
                            from gui.display_map import Z_AXIS_OPTIONS
                            display_values = list(Z_AXIS_OPTIONS.values())
                            current_display = Z_AXIS_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                            if section == "Generator Function":
                                self._gen_func_widgets.setdefault(label, []).append(self.entries[(section, label)])
                        elif section == "Generator Function" and label == "Spacing":
                            from gui.display_map import SPACING_OPTIONS
                            display_values = list(SPACING_OPTIONS.values())
                            current_display = SPACING_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                            if section == "Generator Function":
                                self._gen_func_widgets.setdefault(label, []).append(self.entries[(section, label)])
                        elif section == "Generator Function" and label in ("Start", "Stop"):
                            import re
                            unit_options = ["Hz", "kHz"]
                            val_str = str(value)
                            match = re.match(r"^([\-\d\.]+)\s*([a-zA-Z]+)?$", val_str)
                            if match:
                                val_part = match.group(1)
                                unit_part = match.group(2) if match.group(2) in unit_options else unit_options[0]
                            else:
                                val_part = val_str
                                unit_part = unit_options[0]
                            hv_frame = Frame(frame)
                            hv_frame.grid(row=i, column=1, sticky="w", pady=2)
                            entry = Entry(hv_frame, width=22)
                            entry.insert(0, val_part)
                            entry.pack(side="left", padx=(0, 8))
                            combo = ttk.Combobox(hv_frame, values=unit_options, width=6, state="readonly")
                            combo.set(unit_part)
                            combo.pack(side="left")
                            def convert_freq_unit(event=None, entry=entry, combo=combo):
                                try:
                                    val = float(entry.get())
                                except Exception:
                                    return
                                old_unit = getattr(combo, '_last_unit', unit_part)
                                new_unit = combo.get()
                                scale = {"Hz": 1, "kHz": 1e3}
                                if old_unit in scale and new_unit in scale:
                                    val_si = val * scale[old_unit]
                                    new_val = val_si / scale[new_unit]
                                    entry.delete(0, 'end')
                                    entry.insert(0, str(int(new_val) if new_val.is_integer() else round(new_val, 6)))
                                combo._last_unit = new_unit
                            combo._last_unit = unit_part
                            combo.bind('<<ComboboxSelected>>', convert_freq_unit)
                            combo.unbind("<MouseWheel>")
                            self.bind_combobox_mousewheel(combo)
                            self.entries[(section, label)] = (entry, combo)
                            if section == "Generator Function":
                                self._gen_func_widgets.setdefault(label, []).append(hv_frame)
                        elif section == "Generator Function" and label == "Voltage":
                            # Same as Max Voltage: value + unit (case-insensitive, ensure DBR -> dBr)
                            import re
                            unit_options = ["V", "mV", "μV", "dBV", "dBu", "dBm", "dBr"]
                            val_str = str(value)
                            match = re.match(r"^([\-\d\.]+)\s*([a-zA-Zμ]+)?$", val_str)
                            if match:
                                val_part = match.group(1)
                                raw_unit = match.group(2)
                                if raw_unit:
                                    unit_part = None
                                    for opt in unit_options:
                                        if raw_unit.lower() == opt.lower():
                                            unit_part = opt
                                            break
                                    if unit_part is None:
                                        unit_part = unit_options[0]
                                else:
                                    unit_part = unit_options[0]
                            else:
                                val_part = val_str
                                unit_part = unit_options[0]
                            hv_frame = Frame(frame)
                            hv_frame.grid(row=i, column=1, sticky="w", pady=2)
                            entry = Entry(hv_frame, width=22)
                            entry.insert(0, val_part)
                            entry.pack(side="left", padx=(0, 8))
                            combo = ttk.Combobox(hv_frame, values=unit_options, width=6, state="readonly")
                            combo.set(unit_part)
                            combo.pack(side="left")
                            import math

                            def get_ref_voltage_volts():
                                # Fetch the Ref Voltage entry and combo from self.entries
                                ref_entry, ref_combo = self.entries.get(("Generator Config", "Ref Voltage"), (None, None))
                                if ref_entry is None or ref_combo is None:
                                    return 1.0  # fallback
                                try:
                                    val = float(ref_entry.get())
                                except Exception:
                                    return 1.0
                                unit = ref_combo.get()
                                scale = {"V": 1, "mV": 1e-3, "μV": 1e-6}
                                if unit in scale:
                                    return val * scale[unit]
                                elif unit == "dBV":
                                    return 10 ** (val / 20)
                                elif unit == "dBu":
                                    return 0.775 * (10 ** (val / 20))
                                elif unit == "dBm":
                                    Z = 600
                                    p = 10 ** (val / 10) / 1000
                                    return (p * Z) ** 0.5
                                else:
                                    return val

                            def convert_voltage_unit(event=None, entry=entry, combo=combo):
                                try:
                                    val = float(entry.get())
                                except Exception:
                                    return
                                old_unit = getattr(combo, '_last_unit', unit_part)
                                new_unit = combo.get()
                                scale = {"V": 1, "mV": 1e-3, "μV": 1e-6}
                                Z = 600  # Ohms, for dBm conversion

                                VREF_DBR = get_ref_voltage_volts()

                                def to_volts(val, unit):
                                    if unit in scale:
                                        return val * scale[unit]
                                    elif unit == "dBV":
                                        return 10 ** (val / 20)
                                    elif unit == "dBu":
                                        return 0.775 * (10 ** (val / 20))
                                    elif unit == "dBm":
                                        p = 10 ** (val / 10) / 1000
                                        return (p * Z) ** 0.5
                                    elif unit == "dBr":
                                        # dBr: V = Vref * 10^(dBr/20)
                                        return VREF_DBR * (10 ** (val / 20))
                                    else:
                                        return val

                                def from_volts(v, unit):
                                    if unit in scale:
                                        new_val = v / scale[unit]
                                        return int(new_val) if new_val.is_integer() else round(new_val, 6)
                                    elif unit == "dBV":
                                        return round(20 * math.log10(v / 1.0), 6) if v > 0 else ""
                                    elif unit == "dBu":
                                        return round(20 * math.log10(v / 0.775), 6) if v > 0 else ""
                                    elif unit == "dBm":
                                        p = (v ** 2) / Z
                                        return round(10 * math.log10(p * 1000), 6) if v > 0 else ""
                                    elif unit == "dBr":
                                        # dBr: dBr = 20 * log10(V / Vref)
                                        return round(20 * math.log10(v / VREF_DBR), 6) if v > 0 else ""
                                    else:
                                        return v

                                v_si = to_volts(val, old_unit)
                                result = from_volts(v_si, new_unit)
                                entry.delete(0, 'end')
                                entry.insert(0, str(result))
                                combo._last_unit = new_unit

                            combo._last_unit = unit_part
                            combo.bind('<<ComboboxSelected>>', convert_voltage_unit)
                            combo.unbind("<MouseWheel>")
                            self.bind_combobox_mousewheel(combo)
                            self.entries[(section, label)] = (entry, combo)
                        elif section == "Generator Function" and label == "Filter":
                            from gui.display_map import FILTER_OPTIONS
                            filter_keys = list(FILTER_OPTIONS.keys())
                            filter_values = [FILTER_OPTIONS[k] for k in filter_keys]
                            try:
                                idx = filter_keys.index(value)
                                display_val = filter_values[idx]
                            except Exception:
                                display_val = filter_values[0]
                            combo = ttk.Combobox(frame, values=filter_values, width=20, state="readonly")
                            combo.set(display_val)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.unbind("<MouseWheel>")
                            self.bind_combobox_mousewheel(combo)
                            self.entries[(section, label)] = (combo, filter_keys, filter_values)
                        elif section == "Generator Function" and label == "Halt":
                            from gui.display_map import HALT_OPTIONS
                            display_values = list(HALT_OPTIONS.values())
                            reverse_map = {v: k for k, v in HALT_OPTIONS.items()}
                            current_display = HALT_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.unbind("<MouseWheel>")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                            if section == "Generator Function":
                                self._gen_func_widgets.setdefault(label, []).append(combo)
                        elif section == "Generator Function" and label == "Equalizer":
                            import tkinter as tk
                            var = tk.StringVar()
                            var.set("ON" if str(value).upper() == "ON" else "OFF")
                            cb = tk.Checkbutton(frame, variable=var, onvalue="ON", offvalue="OFF")
                            cb.grid(row=i, column=1, sticky="w", pady=2)
                            if var.get() == "ON":
                                cb.select()
                            else:
                                cb.deselect()
                            self.entries[(section, label)] = var
                        elif section == "Generator Function" and label == "DC Offset":
                            import tkinter as tk
                            var = tk.StringVar()
                            var.set("ON" if str(value).upper() == "ON" else "OFF")
                            cb = tk.Checkbutton(frame, variable=var, onvalue="ON", offvalue="OFF")
                            cb.grid(row=i, column=1, sticky="w", pady=2)
                            if var.get() == "ON":
                                cb.select()
                            else:
                                cb.deselect()
                            self.entries[(section, label)] = var
                        elif section == "Analyzer Config" and label == "Instrument Analyzer":
                            from gui.display_map import INSTRUMENT_ANALYZER_OPTIONS
                            display_values = list(INSTRUMENT_ANALYZER_OPTIONS.values())
                            current_display = INSTRUMENT_ANALYZER_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Config" and label == "Channel Analyzer":
                            from gui.display_map import CHANNEL_ANALYZER_OPTIONS
                            display_values = list(CHANNEL_ANALYZER_OPTIONS.values())
                            current_display = CHANNEL_ANALYZER_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Config" and label == "CH1 Coupling":
                            from gui.display_map import CH1_COUPLING_OPTIONS
                            import tkinter as tk
                            ch1_coupling_var = tk.StringVar()
                            ch1_coupling_var.set(value if value in CH1_COUPLING_OPTIONS else "AC")
                            radio_frame = Frame(frame)
                            radio_frame.grid(row=i, column=1, sticky="w", pady=2)
                            for code, display in CH1_COUPLING_OPTIONS.items():
                                rb = ttk.Radiobutton(radio_frame, text=display, variable=ch1_coupling_var, value=code)
                                rb.pack(side="left", padx=5)
                            self.entries[(section, label)] = ch1_coupling_var
                        elif section == "Analyzer Config" and label == "Bandwidth Analyzer":
                            from gui.display_map import BANDWIDTH_ANALYZER_OPTIONS
                            display_values = list(BANDWIDTH_ANALYZER_OPTIONS.values())
                            current_display = BANDWIDTH_ANALYZER_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        
                        elif section == "Analyzer Config" and label == "Pre Filter":
                            from gui.display_map import PRE_FILTER_OPTIONS
                            display_values = list(PRE_FILTER_OPTIONS.values())
                            current_display = PRE_FILTER_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Config" and label == "CH1 Input":
                            from gui.display_map import CH1_INPUT_OPTIONS
                            display_values = list(CH1_INPUT_OPTIONS.values())
                            current_display = CH1_INPUT_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Config" and label == "CH1 Impedance":
                            from gui.display_map import CH1_IMPEDANCE_OPTIONS
                            display_values = list(CH1_IMPEDANCE_OPTIONS.values())
                            current_display = CH1_IMPEDANCE_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Config" and label == "CH1 Ground/Common":
                            from gui.display_map import CH1_COMMON_OPTIONS
                            import tkinter as tk
                            ch1_common_var = tk.StringVar()
                            ch1_common_var.set(value if value in CH1_COMMON_OPTIONS else "FLOat")
                            radio_frame = Frame(frame)
                            radio_frame.grid(row=i, column=1, sticky="w", pady=2)
                            for code, display in CH1_COMMON_OPTIONS.items():
                                rb = ttk.Radiobutton(radio_frame, text=display, variable=ch1_common_var, value=code)
                                rb.pack(side="left", padx=5)
                            self.entries[(section, label)] = ch1_common_var
                        elif section == "Analyzer Config" and label == "CH1 Range":
                            from gui.display_map import CH1_RANGE_OPTIONS
                            display_values = list(CH1_RANGE_OPTIONS.values())
                            current_display = CH1_RANGE_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Config" and label == "Ref Imped":
                            import tkinter as tk
                            import re
                            hv_frame = Frame(frame)
                            hv_frame.grid(row=i, column=1, sticky="w", pady=2)
                            entry = Entry(hv_frame, width=22)
                            # Parse value and unit (handles "600 Ω", "0.6 kΩ", "600", "0.6kΩ", etc.)
                            val_str = str(value)
                            match = re.match(r"^\s*([\d\.\-]+)\s*(k?Ω|k?ohm|k?Ohm)?\s*$", val_str, re.IGNORECASE)
                            if match:
                                val_part = match.group(1)
                                unit_part = match.group(2) or "Ω"
                                unit_part = unit_part.replace("ohm", "Ω").replace("Ohm", "Ω")
                                if unit_part.lower().startswith("k"):
                                    unit_part = "kΩ"
                                else:
                                    unit_part = "Ω"
                            else:
                                val_part = val_str
                                unit_part = "Ω"
                            entry.insert(0, val_part)
                            entry.pack(side="left", padx=(0, 8))
                            combo = ttk.Combobox(hv_frame, values=["Ω", "kΩ"], width=6, state="readonly")
                            combo.set(unit_part)
                            combo.pack(side="left")
                            # Conversion logic: when unit changes, convert value
                            def convert_impedance_unit(event=None, entry=entry, combo=combo):
                                try:
                                    val = float(entry.get())
                                except Exception:
                                    return
                                old_unit = getattr(combo, '_last_unit', unit_part)
                                new_unit = combo.get()
                                if old_unit == new_unit:
                                    return
                                if old_unit == "Ω" and new_unit == "kΩ":
                                    val = val / 1000
                                elif old_unit == "kΩ" and new_unit == "Ω":
                                    val = val * 1000
                                entry.delete(0, 'end')
                                entry.insert(0, str(int(val) if val.is_integer() else round(val, 6)))
                                combo._last_unit = new_unit
                            combo._last_unit = unit_part
                            combo.bind('<<ComboboxSelected>>', convert_impedance_unit)
                            combo.unbind("<MouseWheel>")
                            self.bind_combobox_mousewheel(combo)
                            self.entries[(section, label)] = (entry, combo)
                        elif section == "Analyzer Config" and label == "Start Cond":
                            from gui.display_map import START_COND_OPTIONS
                            display_values = list(START_COND_OPTIONS.values())
                            current_display = START_COND_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Config" and label == "Delay":
                            import tkinter as tk
                            import re
                            delay_frame = Frame(frame)
                            delay_frame.grid(row=i, column=1, sticky="w", pady=2)
                            entry = Entry(delay_frame, width=22)
                            # Parse value and unit (handles "2 s", "2000 ms", "0.5 min", etc.)
                            val_str = str(value)
                            match = re.match(r"^\s*([\d\.\-]+)\s*(s|ms|us|min)?\s*$", val_str, re.IGNORECASE)
                            if match:
                                val_part = match.group(1)
                                unit_part = match.group(2) or "s"
                                unit_part = unit_part.lower()
                            else:
                                val_part = val_str
                                unit_part = "s"
                            entry.insert(0, val_part)
                            entry.pack(side="left", padx=(0, 8))
                            unit_display_map = {"s": "s", "ms": "ms", "us": "μs", "min": "min"}
                            unit_reverse_map = {v: k for k, v in unit_display_map.items()}
                            combo = ttk.Combobox(delay_frame, values=list(unit_display_map.values()), width=6, state="readonly")
                            combo.set(unit_display_map.get(unit_part, unit_part))
                            combo.pack(side="left")
                            # Conversion logic: when unit changes, convert value
                            def convert_delay_unit(event=None, entry=entry, combo=combo):
                                try:
                                    val = float(entry.get())
                                except Exception:
                                    return
                                # Use the display-to-code map
                                old_unit_display = getattr(combo, '_last_unit', unit_part)
                                new_unit_display = combo.get()
                                old_unit = unit_reverse_map.get(old_unit_display, old_unit_display)
                                new_unit = unit_reverse_map.get(new_unit_display, new_unit_display)
                                if old_unit == new_unit:
                                    return
                                # Conversion factors to seconds
                                to_sec = {"us": 1e-6, "ms": 1e-3, "s": 1, "min": 60}
                                from_sec = {"us": 1e6, "ms": 1e3, "s": 1, "min": 1/60}
                                val_in_sec = val * to_sec.get(old_unit, 1)
                                new_val = val_in_sec * from_sec.get(new_unit, 1)
                                entry.delete(0, 'end')
                                entry.insert(0, str(int(new_val) if new_val.is_integer() else round(new_val, 6)))
                                combo._last_unit = new_unit_display
                            combo._last_unit = unit_part
                            combo.bind('<<ComboboxSelected>>', convert_delay_unit)
                            combo.unbind("<MouseWheel>")
                            self.bind_combobox_mousewheel(combo)
                            self.entries[(section, label)] = (entry, combo)
                        elif section == "Analyzer Config" and label == "MAX FFT Size":
                            from gui.display_map import MAX_FFT_SIZE_OPTIONS
                            display_values = list(MAX_FFT_SIZE_OPTIONS.values())
                            current_display = MAX_FFT_SIZE_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Function" and label == "Function Analyzer":
                            from gui.display_map import FUNCTION_ANALYZER_OPTIONS
                            display_values = list(FUNCTION_ANALYZER_OPTIONS.values())
                            current_display = FUNCTION_ANALYZER_OPTIONS.get(value, value)
                            combo = self._create_combo(frame, display_values, current_display,
                                                       width=24,
                                                       grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                                       entry_key=(section, label))
                            # Bind for dynamic S/N Sequence visibility updates
                            def _fa_changed(event=None, self=self):
                                try:
                                    self._update_analyzer_function_visibility()
                                except Exception:
                                    pass
                            combo.bind('<<ComboboxSelected>>', _fa_changed, add='+')
                            # Initialize storage for analyzer function rows we may hide dynamically
                            self._an_func_hidden_rows = getattr(self, '_an_func_hidden_rows', {})
                        elif section == "Analyzer Function" and label == "S/N Sequence":
                            import tkinter as tk
                            var = tk.BooleanVar()
                            var.set(str(value).upper() == "ON")
                            chk = tk.Checkbutton(frame, variable=var)
                            chk.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = var
                            # Capture row widgets so we can hide/show dynamically
                            try:
                                row_widgets = frame.grid_slaves(row=i)
                                # Store tuples of (widget, grid_info)
                                self._sn_sequence_widgets = [(w, w.grid_info()) for w in row_widgets]
                                self._sn_sequence_row = i
                                self._an_func_frame = frame
                            except Exception:
                                pass
                        elif section == "Analyzer Function" and label == "Meas Time":
                            from gui.display_map import MEAS_TIME_OPTIONS
                            display_values = list(MEAS_TIME_OPTIONS.values())
                            current_display = MEAS_TIME_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Function" and label == "Freq Mode":
                            from gui.display_map import FREQ_MODE_OPTIONS
                            display_values = list(FREQ_MODE_OPTIONS.values())
                            current_display = FREQ_MODE_OPTIONS.get(value, value)
                            combo = self._create_combo(frame, display_values, current_display,
                                                       grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                                       entry_key=(section, label))
                            # Bind to update Factor visibility when Freq Mode changes
                            def _freq_mode_changed(event=None, self=self):
                                try:
                                    self._update_analyzer_function_visibility()
                                except Exception:
                                    pass
                            combo.bind('<<ComboboxSelected>>', _freq_mode_changed, add='+')
                            # Capture widgets for dynamic hide when Function Analyzer == RMS
                            try:
                                row_widgets = frame.grid_slaves(row=i)
                                self._an_func_hidden_rows.setdefault('Freq Mode', [(w, w.grid_info()) for w in row_widgets])
                            except Exception:
                                pass
                        elif section == "Analyzer Function" and label == "Notch(Gain)":
                            from gui.display_map import NOTCH_OPTIONS
                            display_values = list(NOTCH_OPTIONS.values())
                            current_display = NOTCH_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Function" and label == "Filter1":
                            from gui.display_map import FILTER1_OPTIONS
                            display_values = list(FILTER1_OPTIONS.values())
                            current_display = FILTER1_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                            # Capture for potential RMS Selective hide
                            try:
                                row_widgets = frame.grid_slaves(row=i)
                                self._an_func_hidden_rows.setdefault('Filter1', [(w, w.grid_info()) for w in row_widgets])
                            except Exception:
                                pass
                        elif section == "Analyzer Function" and label == "Filter2":
                            from gui.display_map import FILTER2_OPTIONS
                            display_values = list(FILTER2_OPTIONS.values())
                            current_display = FILTER2_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Function" and label == "Filter3":
                            from gui.display_map import FILTER3_OPTIONS
                            display_values = list(FILTER3_OPTIONS.values())
                            current_display = FILTER3_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                            # Capture for potential RMS Selective hide
                            try:
                                row_widgets = frame.grid_slaves(row=i)
                                self._an_func_hidden_rows.setdefault('Filter3', [(w, w.grid_info()) for w in row_widgets])
                            except Exception:
                                pass
                        elif section == "Analyzer Function" and label == "Fnct Settling":
                            from gui.display_map import FNCT_SETTLING_OPTIONS
                            display_values = list(FNCT_SETTLING_OPTIONS.values())
                            current_display = FNCT_SETTLING_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Function" and label == "Samples":
                            # Create an entry for Samples (was missing previously causing empty cell)
                            try:
                                entry = Entry(frame, width=22)
                                entry.insert(0, str(value))
                                entry.grid(row=i, column=1, sticky="w", pady=2)
                                self.entries[(section, label)] = entry
                                # Capture row widgets (label + entry) for dynamic RMS-only visibility
                                row_widgets = frame.grid_slaves(row=i)
                                self._an_func_hidden_rows.setdefault('Samples', [(w, w.grid_info()) for w in row_widgets])
                            except Exception:
                                pass
                        elif section == "Analyzer Function" and label == "Tolerance":
                            import tkinter as tk
                            import re
                            tol_frame = Frame(frame)
                            tol_frame.grid(row=i, column=1, sticky="w", pady=2)
                            entry = Entry(tol_frame, width=22)
                            # Parse value and unit (handles "0.1 %", "0.1 dB", "0.1", etc.)
                            val_str = str(value)
                            match = re.match(r"^\s*([\d\.\-]+)\s*(%|dB)?\s*$", val_str, re.IGNORECASE)
                            if match:
                                val_part = match.group(1)
                                unit_part = match.group(2) or "%"
                            else:
                                val_part = val_str
                                unit_part = "%"
                            entry.insert(0, val_part)
                            entry.pack(side="left", padx=(0, 8))
                            combo = ttk.Combobox(tol_frame, values=["%", "dB"], width=5, state="readonly")
                            combo.set(unit_part)
                            combo.pack(side="left")

                            def convert_tolerance_unit(event=None, entry=entry, combo=combo):
                                try:
                                    val = float(entry.get())
                                except Exception:
                                    return
                                old_unit = getattr(combo, '_last_unit', unit_part)
                                new_unit = combo.get()
                                if old_unit == new_unit:
                                    return
                                if old_unit == "%" and new_unit == "dB":
                                    # Convert percentage to dB using new formula
                                    if val <= -100:
                                        entry.delete(0, 'end')
                                        entry.insert(0, "")
                                    else:
                                        db_val = 20 * math.log10(1 + (val / 100))
                                        entry.delete(0, 'end')
                                        entry.insert(0, str(round(db_val, 6)))
                                elif old_unit == "dB" and new_unit == "%":
                                    # Convert dB to percentage using new formula
                                    percent_val = (10 ** (val / 20) - 1) * 100
                                    entry.delete(0, 'end')
                                    entry.insert(0, str(round(percent_val, 6)))
                                combo._last_unit = new_unit

                            combo._last_unit = unit_part
                            combo.bind('<<ComboboxSelected>>', convert_tolerance_unit)
                            combo.unbind("<MouseWheel>")
                            self.bind_combobox_mousewheel(combo)
                            self.entries[(section, label)] = (entry, combo)
                        elif section == "Analyzer Function" and label == "Factor":
                            # Simple numeric factor with a trailing '*' unit indicator
                            import tkinter as tk
                            import re
                            fac_frame = Frame(frame)
                            fac_frame.grid(row=i, column=1, sticky="w", pady=2)
                            entry = Entry(fac_frame, width=22)
                            raw_val = str(value).strip()
                            # Extract leading numeric (float or int, optional scientific), ignore trailing tokens like 'MLT'
                            num_match = re.match(r"^[\s]*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)", raw_val)
                            cleaned = num_match.group(1) if num_match else raw_val
                            entry.insert(0, cleaned)
                            # Optionally normalize settings in-memory so future saves drop 'MLT'
                            try:
                                if settings.get(section, {}).get(label) != cleaned:
                                    settings[section][label] = cleaned
                            except Exception:
                                pass
                            entry.pack(side="left", padx=(0, 4))
                            unit_lbl = Label(fac_frame, text="*", bg=frame["background"], fg="#333")
                            unit_lbl.pack(side="left")
                            self.entries[(section, label)] = entry
                            # Capture for dynamic hide (same rule set as Bandwidth / Sweep Ctrl / Freq Mode)
                            try:
                                row_widgets = frame.grid_slaves(row=i)
                                self._an_func_hidden_rows.setdefault('Factor', [(w, w.grid_info()) for w in row_widgets])
                            except Exception:
                                pass
                        elif section == "Analyzer Function" and label == "Resolution":
                            import tkinter as tk
                            import re
                            import math
                            res_frame = Frame(frame)
                            res_frame.grid(row=i, column=1, sticky="w", pady=2)
                            entry = Entry(res_frame, width=22)
                            # Parse value and unit (handles "0.1 dBV", "0.1 V", etc.)
                            val_str = str(value)
                            match = re.match(r"^\s*([\d\.\-]+)\s*([a-zA-Z]+)?\s*$", val_str)
                            if match:
                                val_part = match.group(1)
                                unit_part = match.group(2) or "V"
                            else:
                                val_part = val_str
                                unit_part = "V"
                            entry.insert(0, val_part)
                            entry.pack(side="left", padx=(0, 8))
                            units = ["V", "mV", "uV", "dBV", "dBu", "W", "mW", "uW", "dBm"]
                            combo = ttk.Combobox(res_frame, values=units, width=6, state="readonly")
                            combo.set(unit_part)
                            combo.pack(side="left")

                            def convert_resolution_unit(event=None, entry=entry, combo=combo):
                                try:
                                    val = float(entry.get())
                                except Exception:
                                    return
                                old_unit = getattr(combo, '_last_unit', unit_part)
                                new_unit = combo.get()
                                if old_unit == new_unit:
                                    return

                                # Conversion logic
                                # All conversions go through volts (V) for voltage units and watts (W) for power units
                                # Reference: 0 dBV = 1 V, 0 dBu = 0.775 V, 0 dBm = 1 mW (in 600 ohm, but usually 1 mW in 1 kohm or 50 ohm for audio/RF)
                                # We'll use 600 ohm for dBm unless you specify otherwise

                                # Helper functions
                                def to_volts(val, unit):
                                    if unit == "V":
                                        return val
                                    elif unit == "mV":
                                        return val / 1e3
                                    elif unit == "uV":
                                        return val / 1e6
                                    elif unit == "dBV":
                                        return 10 ** (val / 20)
                                    elif unit == "dBu":
                                        return 0.775 * (10 ** (val / 20))
                                    elif unit == "W":
                                        return math.sqrt(val * 600)
                                    elif unit == "mW":
                                        return math.sqrt((val / 1e3) * 600)
                                    elif unit == "uW":
                                        return math.sqrt((val / 1e6) * 600)
                                    elif unit == "dBm":
                                        # dBm to W: P = 10^(dBm/10) * 1mW, then V = sqrt(P*R)
                                        p_watt = 10 ** (val / 10) * 1e-3
                                        return math.sqrt(p_watt * 600)
                                    else:
                                        return val

                                def from_volts(v, unit):
                                    if unit == "V":
                                        return v
                                    elif unit == "mV":
                                        return v * 1e3
                                    elif unit == "uV":
                                        return v * 1e6
                                    elif unit == "dBV":
                                        return 20 * math.log10(v) if v > 0 else ""
                                    elif unit == "dBu":
                                        return 20 * math.log10(v / 0.775) if v > 0 else ""
                                    elif unit == "W":
                                        return (v ** 2) / 600
                                    elif unit == "mW":
                                        return ((v ** 2) / 600) * 1e3
                                    elif unit == "uW":
                                        return ((v ** 2) / 600) * 1e6
                                    elif unit == "dBm":
                                        p_watt = (v ** 2) / 600
                                        return 10 * math.log10(p_watt / 1e-3) if p_watt > 0 else ""
                                    else:
                                        return v

                                # Convert old value to volts or watts
                                v = to_volts(val, old_unit)
                                # Convert volts to new unit
                                new_val = from_volts(v, new_unit)
                                if new_val == "":
                                    entry.delete(0, 'end')
                                else:
                                    entry.delete(0, 'end')
                                    entry.insert(0, str(round(new_val, 6)))
                                combo._last_unit = new_unit

                            combo._last_unit = unit_part
                            combo.bind('<<ComboboxSelected>>', convert_resolution_unit)
                            combo.unbind("<MouseWheel>")
                            self.bind_combobox_mousewheel(combo)
                            self.entries[(section, label)] = (entry, combo)
                        elif section == "Analyzer Function" and label == "Timeout":
                            import tkinter as tk
                            import re
                            timeout_frame = Frame(frame)
                            timeout_frame.grid(row=i, column=1, sticky="w", pady=2)
                            entry = Entry(timeout_frame, width=22)
                            # Parse value and unit (handles "10 s", "10000 ms", etc.)
                            val_str = str(value)
                            match = re.match(r"^\s*([\d\.\-]+)\s*(s|ms|us|min)?\s*$", val_str, re.IGNORECASE)
                            if match:
                                val_part = match.group(1)
                                unit_part = match.group(2) or "s"
                                unit_part = unit_part.lower()
                            else:
                                val_part = val_str
                                unit_part = "s"
                            entry.insert(0, val_part)
                            entry.pack(side="left", padx=(0, 8))
                            unit_display_map = {"s": "s", "ms": "ms", "us": "μs", "min": "min"}
                            unit_reverse_map = {v: k for k, v in unit_display_map.items()}
                            combo = ttk.Combobox(timeout_frame, values=list(unit_display_map.values()), width=6, state="readonly")
                            combo.set(unit_display_map.get(unit_part, unit_part))
                            combo.pack(side="left")
                            # Conversion logic: when unit changes, convert value
                            def convert_timeout_unit(event=None, entry=entry, combo=combo):
                                try:
                                    val = float(entry.get())
                                except Exception:
                                    return
                                old_unit_display = getattr(combo, '_last_unit', unit_part)
                                new_unit_display = combo.get()
                                old_unit = unit_reverse_map.get(old_unit_display, old_unit_display)
                                new_unit = unit_reverse_map.get(new_unit_display, new_unit_display)
                                if old_unit == new_unit:
                                    return
                                # Conversion factors to seconds
                                to_sec = {"us": 1e-6, "ms": 1e-3, "s": 1, "min": 60}
                                from_sec = {"us": 1e6, "ms": 1e3, "s": 1, "min": 1/60}
                                val_in_sec = val * to_sec.get(old_unit, 1)
                                new_val = val_in_sec * from_sec.get(new_unit, 1)
                                entry.delete(0, 'end')
                                entry.insert(0, str(int(new_val) if new_val.is_integer() else round(new_val, 6)))
                                combo._last_unit = new_unit_display
                            combo._last_unit = unit_part
                            combo.bind('<<ComboboxSelected>>', convert_timeout_unit)
                            combo.unbind("<MouseWheel>")
                            self.bind_combobox_mousewheel(combo)
                            self.entries[(section, label)] = (entry, combo)
                        elif section == "Analyzer Function" and label == "Bargraph":
                            import tkinter as tk
                            var = tk.BooleanVar()
                            var.set(str(value).upper() == "ON")
                            chk = tk.Checkbutton(frame, variable=var)
                            chk.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = var
                        elif section == "Analyzer Function" and label == "POST FFT":
                            import tkinter as tk
                            var = tk.BooleanVar()
                            var.set(str(value).upper() == "ON")
                            chk = tk.Checkbutton(frame, variable=var)
                            chk.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = var
                        elif section == "Analyzer Function" and label == "Level Monitor":
                            from gui.display_map import LEVEL_MONITOR_OPTIONS
                            display_values = list(LEVEL_MONITOR_OPTIONS.values())
                            current_display = LEVEL_MONITOR_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Function" and label == "Second Monitor":
                            from gui.display_map import SECOND_MONITOR_OPTIONS
                            display_values = list(SECOND_MONITOR_OPTIONS.values())
                            current_display = SECOND_MONITOR_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Function" and label == "Input Monitor":
                            from gui.display_map import INPUT_MONITOR_OPTIONS
                            display_values = list(INPUT_MONITOR_OPTIONS.values())
                            current_display = INPUT_MONITOR_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Function" and label == "Freq/Phase":
                            from gui.display_map import FREQ_OPTIONS
                            display_values = list(FREQ_OPTIONS.values())
                            current_display = FREQ_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                        elif section == "Analyzer Function" and label == "Bandwidth Analyzer Config":
                            # New combobox for detailed bandwidth pass/stop configuration
                            from gui.display_map import BANDWIDTH_ANALYZER_CONFIG_OPTIONS
                            display_values = list(BANDWIDTH_ANALYZER_CONFIG_OPTIONS.values())
                            current_display = BANDWIDTH_ANALYZER_CONFIG_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                            # Capture row widgets for dynamic hide when Function Analyzer == RMS
                            try:
                                row_widgets = frame.grid_slaves(row=i)
                                self._an_func_hidden_rows.setdefault('Bandwidth Analyzer Config', [(w, w.grid_info()) for w in row_widgets])
                            except Exception:
                                pass
                        elif section == "Analyzer Function" and label == "Sweep Ctrl Analyzer Config":
                            # Analyzer sweep control (same display set as generator sweep control)
                            from gui.display_map import SWEEP_CTRL_OPTIONS
                            display_values = list(SWEEP_CTRL_OPTIONS.values())
                            current_display = SWEEP_CTRL_OPTIONS.get(value, value)
                            self._create_combo(frame, display_values, current_display,
                                               grid_kwargs={"row": i, "column": 1, "sticky": "w", "pady": 2},
                                               entry_key=(section, label))
                            # Capture row widgets for dynamic hide when Function Analyzer == RMS
                            try:
                                row_widgets = frame.grid_slaves(row=i)
                                self._an_func_hidden_rows.setdefault('Sweep Ctrl Analyzer Config', [(w, w.grid_info()) for w in row_widgets])
                            except Exception:
                                pass
                        elif section == "Analyzer Function" and label == "Waveform":
                            import tkinter as tk
                            var = tk.BooleanVar()
                            var.set(str(value).upper() == "ON")
                            chk = tk.Checkbutton(frame, variable=var)
                            chk.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = var
                        else:
                            entry = Entry(frame, width=22)
                            entry.insert(0, str(value))
                            entry.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = entry
                            # Ensure generic dynamic labels (e.g., Points) register their control
                            if section == "Generator Function" and label in getattr(self, '_gen_func_dynamic_labels', set()):
                                self._gen_func_widgets.setdefault(label, []).append(entry)

                    # --- Impedance widget logic ---
                    def set_impedance_widget(output_type_display, selected_code=None):
                        # Remove previous widget if exists
                        for widget in self.impedance_frame.grid_slaves(row=self.impedance_row, column=1):
                            widget.destroy()
                        if output_type_display == "Unbal":
                            entry = Entry(self.impedance_frame, width=22, state="normal")
                            entry.insert(0, IMPEDANCE_OPTIONS_UNBAL["R5"])
                            entry.config(state="readonly")
                            entry.grid(row=self.impedance_row, column=1, sticky="w", pady=2)
                            self.entries[("Generator Config", "Impedance")] = entry
                        else:
                            display_values = list(IMPEDANCE_OPTIONS_BAL.values())
                            reverse_map = {v: k for k, v in IMPEDANCE_OPTIONS_BAL.items()}
                            if selected_code and selected_code in IMPEDANCE_OPTIONS_BAL:
                                current_display = IMPEDANCE_OPTIONS_BAL[selected_code]
                            else:
                                current_display = display_values[0]
                            combo = ttk.Combobox(self.impedance_frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=self.impedance_row, column=1, sticky="w", pady=2)
                            combo.unbind("<MouseWheel>")
                            self.entries[("Generator Config", "Impedance")] = combo
                            self.bind_combobox_mousewheel(combo)

                    # Initial setup for Impedance widget
                    if self.output_type_combo:
                        selected_output_type = self.output_type_combo.get()
                        set_impedance_widget(selected_output_type, selected_code=impedance_value)

                        # Bind event to Output Type combobox to update Impedance field
                        def on_output_type_change(event):
                            selected_display = self.output_type_combo.get()
                            set_impedance_widget(selected_display)
                        # Use add='+' so we don't overwrite the preset modification watcher bound in _create_combo
                        self.output_type_combo.bind("<<ComboboxSelected>>", on_output_type_change, add='+')

            # After building all sections, bind sweep control visibility if present
            # (Do this inside outer loop but after each section processed; harmless to re-run if not generator function)
            if ("Generator Function", "Sweep Ctrl") in self.entries and hasattr(self, '_gen_func_widgets'):
                try:
                    sc_widget = self.entries[("Generator Function", "Sweep Ctrl")]
                    # Ensure single binding
                    # add='+' so existing modification watcher from _create_combo remains
                    sc_widget.bind("<<ComboboxSelected>>", lambda e: self._update_sweep_ctrl_visibility(), add='+')
                    # Apply initial visibility
                    self._update_sweep_ctrl_visibility()
                except Exception:
                    pass

            # Store frames so we can access canvases later
            self._panel_frames = frames
            # Force one immediate recalculation (helps on Windows where first draw is blank)
            for _section, (inner, canvas) in frames.items():
                if hasattr(canvas, '_recalc'):
                    try:
                        canvas._recalc()
                    except Exception:
                        pass
            # Defer a second pass after geometry is fully settled
            self.after(80, self._reset_all_panel_views)
            # Ensure analyzer function dependent visibility matches initial Function Analyzer selection
            try:
                # Immediate attempt (handles RMSS presets so Filter1/Filter3 hide right away)
                self._update_analyzer_function_visibility()
                # Follow-up after a short delay in case some rows weren't realized yet
                self.after(120, self._update_analyzer_function_visibility)
            except Exception:
                pass

        except Exception as e:
            messagebox.showerror("Settings Error", f"Could not load settings.json: {e}")
        # After (re)loading settings, force user to Apply before sweep
        if hasattr(self, 'start_sweep_btn'):
            # Attach modification watchers so ANY change in any panel reverts preset to default
            try:
                self._attach_modification_watchers()
            except Exception:
                pass
            self._settings_applied = False
            self._refresh_start_sweep_state()

    def _mark_modified(self, *args):
        """Handle any user modification.

        Actions:
          - Revert preset label to DEFAULT_PRESET_NAME if a different preset was active (signals divergence).
          - Mark settings as not applied (_settings_applied = False).
          - Disable Start Sweep until user clicks 'Apply Settings' again.
        """
        try:
            # Revert preset name if diverged
            if self._current_preset_name != DEFAULT_PRESET_NAME:
                self._current_preset_name = DEFAULT_PRESET_NAME
                if hasattr(self, 'preset_label'):
                    try:
                        self.preset_label.config(text=f"Preset: {self._current_preset_name}")
                    except Exception:
                        pass
            # Invalidate applied settings and disable sweep button
            if getattr(self, '_settings_applied', False):
                self._settings_applied = False
                if hasattr(self, 'start_sweep_btn'):
                    try:
                        self.start_sweep_btn.config(state='disabled')
                    except Exception:
                        pass
            # Ensure gating reflects latest state
            try:
                self._refresh_start_sweep_state()
            except Exception:
                pass
        except Exception:
            pass

    def _attach_modification_watchers(self):
        """Attach change listeners to all interactive widgets across all panels.

        Covers:
          - ttk.Combobox (both those stored directly and inside tuples)
          - Entry widgets (direct or inside tuples)
          - tk.StringVar / tk.BooleanVar variables (checkboxes, radio groups)
        """
        import tkinter as tk
        # Prevent duplicate attachment within same settings load (optional)
        if getattr(self, '_mod_watchers_attached', False):
            return
        for key, widget in list(self.entries.items()):
            # Unpack composite tuples like (Entry, Combobox) or (Combobox, filter_keys, filter_values)
            candidates = []
            if isinstance(widget, tuple):
                # First pass: include widget-like elements
                for part in widget:
                    candidates.append(part)
            else:
                candidates.append(widget)
            for w in candidates:
                try:
                    # Skip non-widget simple data (e.g., list, str)
                    if isinstance(w, ttk.Combobox):
                        w.bind('<<ComboboxSelected>>', lambda e, self=self: self._mark_modified(), add='+')
                    elif isinstance(w, Entry):
                        w.bind('<KeyRelease>', lambda e, self=self: self._mark_modified(), add='+')
                    elif hasattr(w, 'bind') and w.__class__.__name__ == 'Entry':  # fallback generic Entry subclass
                        w.bind('<KeyRelease>', lambda e, self=self: self._mark_modified(), add='+')
                except Exception:
                    continue
            # Variable traces (checkboxes / radiobuttons) stored as tk.StringVar / tk.BooleanVar
            try:
                if isinstance(widget, (tk.StringVar, tk.BooleanVar)):
                    widget.trace_add('write', lambda *a, self=self: self._mark_modified())
            except Exception:
                pass
        self._mod_watchers_attached = True

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
            for (section, label), entry in self.entries.items():
                if section in settings and label in settings[section]:
                    settings[section][label] = entry.get()
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            self.status_label.config(text="Settings saved successfully.", fg="green")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save settings: {e}")

    def connect_to_upv(self):
        visa_address = load_config()
        rm = pyvisa.ResourceManager()
        self.status_label.config(text="Connecting to UPV...")
        self.status_label.update_idletasks()
        self.upv = None

        def status_callback(msg):
            self.status_label.config(text=msg)
            self.status_label.update_idletasks()

        if visa_address:
            try:
                status_callback(f"🔌 Trying saved UPV address: {visa_address}")
                upv = rm.open_resource(visa_address)
                upv.timeout = 3000
                idn = upv.query("*IDN?").strip()
                status_callback(f"✅ Connected to: {idn}")
                self.upv = upv
                return
            except Exception as e:
                status_callback(f"❌ Saved address failed: {e}\nSearching for a new UPV (LAN/USB)...")
                visa_address = None

        if not visa_address:
            visa_address = find_upv_ip(status_callback)
            if not visa_address:
                status_callback("❌ No UPV found. Please check LAN/USB connection and power.")
                self.upv = None
                return
            try:
                upv = rm.open_resource(visa_address)
                upv.timeout = 5000
                idn = upv.query("*IDN?").strip()
                status_callback(f"✅ Connected to new UPV: {idn}")
                save_config(visa_address)
                self.upv = upv
            except Exception as e:
                status_callback(f"❌ Failed to connect to newly found UPV: {e}")
                self.upv = None

    def apply_settings(self):
        try:
            # If a continuous sweep is active, stop it silently before applying new settings
            if getattr(self, '_continuous_active', False):
                try:
                    self.stop_continuous_sweep(silent=True)
                except Exception:
                    pass
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)

            reverse_instrument_map = {v: k for k, v in INSTRUMENT_GENERATOR_OPTIONS.items()}
            reverse_channel_map = {v: k for k, v in CHANNEL_GENERATOR_OPTIONS.items()}

            unit_display_map = {"s": "s", "ms": "ms", "us": "μs", "min": "min"}
            unit_reverse_map = {v: k for k, v in unit_display_map.items()}

            for (section, label), widget in self.entries.items():
                if section == "Generator Config" and label == "Instrument Generator":
                    display_value = widget.get()
                    code_value = reverse_instrument_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Generator Config" and label == "Channel Generator":
                    display_value = widget.get()
                    code_value = reverse_channel_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Generator Config" and label == "Output Type (Unbal/Bal)":
                    display_value = widget.get()
                    code_value = reverse_output_type_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Generator Config" and label == "Common (Float/Ground)":
                    settings[section][label] = widget.get()
                elif section == "Generator Config" and label == "Bandwidth Generator":
                    from gui.display_map import BANDWIDTH_GENERATOR_OPTIONS
                    reverse_bw_map = {v: k for k, v in BANDWIDTH_GENERATOR_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_bw_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Generator Config" and label == "Volt Range":
                    settings[section][label] = widget.get()
                elif section == "Generator Config" and label == "Max Voltage":
                    entry, combo = widget
                    val = entry.get().strip()
                    unit = combo.get().strip()
                    # Convert micro symbol to ASCII 'u' for UPV compatibility
                    if unit == "μV":
                        unit_ascii = "uV"
                    else:
                        unit_ascii = unit
                    # Normalize DBR variants if ever present (shouldn't appear here but keep consistent)
                    if unit_ascii.lower() == 'dbr':
                        unit_ascii = 'dBr'
                    settings[section][label] = f"{val} {unit_ascii}" if val else ""
                elif section == "Generator Config" and label == "Ref Voltage":
                    entry, combo = widget
                    val = entry.get().strip()
                    unit = combo.get().strip()
                    if unit == "μV":
                        unit_ascii = "uV"
                    else:
                        unit_ascii = unit
                    if unit_ascii.lower() == 'dbr':
                        unit_ascii = 'dBr'
                    settings[section][label] = f"{val} {unit_ascii}" if val else ""
                elif section == "Generator Config" and label == "Ref Frequency":
                    entry, combo = widget
                    val = entry.get().strip()
                    unit = combo.get().strip()
                    settings[section][label] = f"{val} {unit}" if val else ""
                elif label == "Low Dist":
                    settings[section][label] = widget.get()
                elif section == "Generator Function" and label == "Function Generator":
                    from gui.display_map import FUNCTION_GENERATOR_OPTIONS
                    reverse_map = {v: k for k, v in FUNCTION_GENERATOR_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Generator Function" and label == "Sweep Ctrl":
                    from gui.display_map import SWEEP_CTRL_OPTIONS
                    reverse_map = {v: k for k, v in SWEEP_CTRL_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Generator Function" and label == "Next Step":
                    from gui.display_map import NEXT_STEP_OPTIONS
                    reverse_map = {v: k for k, v in NEXT_STEP_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Generator Function" and label == "X Axis":
                    from gui.display_map import X_AXIS_OPTIONS
                    reverse_map = {v: k for k, v in X_AXIS_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Generator Function" and label == "Z Axis":
                    from gui.display_map import Z_AXIS_OPTIONS
                    reverse_map = {v: k for k, v in Z_AXIS_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Generator Function" and label == "Spacing":
                    from gui.display_map import SPACING_OPTIONS
                    reverse_map = {v: k for k, v in SPACING_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Generator Function" and label == "Frequency":
                    entry, combo = widget
                    val = entry.get().strip()
                    unit = combo.get().strip()
                    settings[section][label] = f"{val} {unit}" if val else ""
                elif section == "Generator Function" and label in ("Start", "Stop"):
                    entry, combo = widget
                    val = entry.get().strip()
                    unit = combo.get().strip()
                    settings[section][label] = f"{val} {unit}" if val else ""
                elif section == "Generator Function" and label == "Voltage":
                    entry, combo = widget
                    val = entry.get().strip()
                    unit = combo.get().strip()
                    if unit == "μV":
                        unit_ascii = "uV"
                    else:
                        unit_ascii = unit
                    # Normalize DBR variants to canonical dBr
                    if unit_ascii.lower() == 'dbr':
                        unit_ascii = 'dBr'
                    settings[section][label] = f"{val} {unit_ascii}" if val else ""
                elif section == "Generator Function" and label == "Filter":
                    combo, filter_keys, filter_values = widget
                    selected_display = combo.get()
                    try:
                        idx = filter_values.index(selected_display)
                        selected_key = filter_keys[idx]
                    except Exception:
                        selected_key = filter_keys[0]
                    settings[section][label] = selected_key
                elif section == "Generator Function" and label == "Halt":
                    from gui.display_map import HALT_OPTIONS
                    reverse_map = {v: k for k, v in HALT_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Generator Function" and label == "Equalizer":
                    settings[section][label] = widget.get()
                elif section == "Generator Function" and label == "DC Offset":
                    settings[section][label] = widget.get()
                elif section == "Analyzer Config" and label == "Instrument Analyzer":
                    from gui.display_map import INSTRUMENT_ANALYZER_OPTIONS
                    reverse_map = {v: k for k, v in INSTRUMENT_ANALYZER_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Config" and label == "Channel Analyzer":
                    from gui.display_map import CHANNEL_ANALYZER_OPTIONS
                    reverse_map = {v: k for k, v in CHANNEL_ANALYZER_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Config" and label == "CH1 Coupling":
                    settings[section][label] = widget.get()
                elif section == "Analyzer Config" and label == "Bandwidth Analyzer":
                    from gui.display_map import BANDWIDTH_ANALYZER_OPTIONS
                    reverse_map = {v: k for k, v in BANDWIDTH_ANALYZER_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Config" and label == "Pre Filter":
                    from gui.display_map import PRE_FILTER_OPTIONS
                    reverse_map = {v: k for k, v in PRE_FILTER_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Config" and label == "CH1 Input":
                    from gui.display_map import CH1_INPUT_OPTIONS
                    reverse_map = {v: k for k, v in CH1_INPUT_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Config" and label == "CH1 Impedance":
                    from gui.display_map import CH1_IMPEDANCE_OPTIONS
                    reverse_map = {v: k for k, v in CH1_IMPEDANCE_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Config" and label == "CH1 Ground/Common":
                    settings[section][label] = widget.get()
                elif section == "Analyzer Config" and label == "CH1 Range":
                    from gui.display_map import CH1_RANGE_OPTIONS
                    reverse_map = {v: k for k, v in CH1_RANGE_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Config" and label == "Ref Imped":
                    entry, combo = widget
                    val = entry.get().strip()
                    unit = combo.get().strip()
                    # Convert symbol to word
                    if unit == "Ω":
                        unit_word = "ohm"
                    elif unit == "kΩ":
                        unit_word = "kohm"
                    else:
                        unit_word = unit
                    settings[section][label] = f"{val} {unit_word}" if val else ""
                elif section == "Analyzer Config" and label == "Start Cond":
                    from gui.display_map import START_COND_OPTIONS
                    reverse_map = {v: k for k, v in START_COND_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                elif section == "Analyzer Config" and label == "Delay":
                    entry, combo = widget
                    val = entry.get().strip()
                    unit_display = combo.get().strip()
                    unit = unit_reverse_map.get(unit_display, unit_display)
                    settings[section][label] = f"{val} {unit}" if val else ""
                elif section == "Analyzer Config" and label == "MAX FFT Size":
                    from gui.display_map import MAX_FFT_SIZE_OPTIONS
                    reverse_map = {v: k for k, v in MAX_FFT_SIZE_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "Function Analyzer":
                    from gui.display_map import FUNCTION_ANALYZER_OPTIONS
                    reverse_map = {v: k for k, v in FUNCTION_ANALYZER_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "S/N Sequence":
                    var = widget
                    settings[section][label] = "ON" if var.get() else "OFF"
                elif section == "Analyzer Function" and label == "Meas Time":
                    from gui.display_map import MEAS_TIME_OPTIONS
                    reverse_map = {v: k for k, v in MEAS_TIME_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "Freq Mode":
                    from gui.display_map import FREQ_MODE_OPTIONS
                    reverse_map = {v: k for k, v in FREQ_MODE_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "Notch(Gain)":
                    from gui.display_map import NOTCH_OPTIONS
                    reverse_map = {v: k for k, v in NOTCH_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "Filter1":
                    from gui.display_map import FILTER1_OPTIONS
                    reverse_map = {v: k for k, v in FILTER1_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "Filter2":
                    from gui.display_map import FILTER2_OPTIONS
                    reverse_map = {v: k for k, v in FILTER2_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "Filter3":
                    from gui.display_map import FILTER3_OPTIONS
                    reverse_map = {v: k for k, v in FILTER3_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "Fnct Settling":
                    from gui.display_map import FNCT_SETTLING_OPTIONS
                    reverse_map = {v: k for k, v in FNCT_SETTLING_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                elif section == "Analyzer Function" and label == "Tolerance":
                    entry, combo = widget
                    val = entry.get().strip()
                    unit = combo.get().strip()
                    settings[section][label] = f"{val} {unit}" if val else ""

                elif section == "Analyzer Function" and label == "Factor":
                    # Simple numeric field, store raw string (trimmed)
                    import re
                    val = widget.get().strip()
                    # Extract numeric portion only
                    num_match = re.match(r"^[\s]*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)", val)
                    if num_match:
                        val = num_match.group(1)
                    settings[section][label] = val
                elif section == "Analyzer Function" and label == "Resolution":
                    entry, combo = widget
                    val = entry.get().strip()
                    unit = combo.get().strip()
                    # Force unit to match combobox value exactly (prevents "DBV" if not in combobox)
                    allowed_units = ["V", "mV", "uV", "dBV", "dBu", "W", "mW", "uW", "dBm"]
                    if unit not in allowed_units:
                        # Try to match ignoring case
                        for u in allowed_units:
                            if unit.lower() == u.lower():
                                unit = u
                                break
                    settings[section][label] = f"{val} {unit}" if val else ""
                elif section == "Analyzer Function" and label == "Timeout":
                    entry, combo = widget
                    val = entry.get().strip()
                    unit_display = combo.get().strip()
                    unit_reverse_map = {"s": "s", "ms": "ms", "μs": "us", "min": "min"}
                    unit = unit_reverse_map.get(unit_display, unit_display)
                    settings[section][label] = f"{val} {unit}" if val else ""
                elif section == "Analyzer Function" and label == "Bargraph":
                    var = widget
                    settings[section][label] = "ON" if var.get() else "OFF"
                elif section == "Analyzer Function" and label == "POST FFT":
                    var = widget
                    settings[section][label] = "ON" if var.get() else "OFF"
                elif section == "Analyzer Function" and label == "Level Monitor":
                    from gui.display_map import LEVEL_MONITOR_OPTIONS
                    reverse_map = {v: k for k, v in LEVEL_MONITOR_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "Second Monitor":
                    from gui.display_map import SECOND_MONITOR_OPTIONS
                    reverse_map = {v: k for k, v in SECOND_MONITOR_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "Input Monitor":
                    from gui.display_map import INPUT_MONITOR_OPTIONS
                    reverse_map = {v: k for k, v in INPUT_MONITOR_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "Freq/Phase":
                    from gui.display_map import FREQ_OPTIONS
                    reverse_map = {v: k for k, v in FREQ_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "Waveform":
                    var = widget
                    settings[section][label] = "ON" if var.get() else "OFF"
                elif section == "Analyzer Function" and label == "Sweep Ctrl Analyzer Config":
                    from gui.display_map import SWEEP_CTRL_OPTIONS
                    reverse_map = {v: k for k, v in SWEEP_CTRL_OPTIONS.items()}
                    display_value = widget.get()
                    code_value = reverse_map.get(display_value, display_value)
                    settings[section][label] = code_value
                elif section == "Analyzer Function" and label == "Bandwidth Analyzer Config":
                            # New detailed bandwidth pass/stop configuration reverse mapping
                            from gui.display_map import BANDWIDTH_ANALYZER_CONFIG_OPTIONS
                            reverse_map = {v: k for k, v in BANDWIDTH_ANALYZER_CONFIG_OPTIONS.items()}
                            display_value = widget.get()
                            code_value = reverse_map.get(display_value, display_value)
                            settings[section][label] = code_value
                else:
                    settings[section][label] = widget.get()

            # Special handling for Impedance based on widget type
            imp_widget = self.entries[("Generator Config", "Impedance")]
            if isinstance(imp_widget, ttk.Combobox):
                reverse_map = {v: k for k, v in IMPEDANCE_OPTIONS_BAL.items()}
                display_value = imp_widget.get().strip()
                code_value = reverse_map.get(display_value)
                if code_value is None:
                    for v, k in reverse_map.items():
                        if v.replace(" ", "").lower() == display_value.replace(" ", "").lower():
                            code_value = k
                            break
                if code_value is None:
                    code_value = "R10"
                settings["Generator Config"]["Impedance"] = code_value
            else:
                settings["Generator Config"]["Impedance"] = "R5"

            # --- Prompt user for sweep mode (continuous vs single) and persist to settings.json ---
            try:
                mode_continuous = messagebox.askyesno(
                    "Sweep Mode",
                    "Apply settings as continuous sweep?\nYes = Continuous\nNo = Single"
                )
                settings["INIT:CONT"] = "ON" if mode_continuous else "OFF"
            except Exception:
                # If dialog fails for any reason, default to existing value or OFF
                settings.setdefault("INIT:CONT", "OFF")

            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)

        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save settings: {e}")
            return

        if self.upv:
            with open(SETTINGS_FILE, "r") as f:
                updated_settings = json.load(f)
            apply_grouped_settings(self.upv, data=updated_settings)
            self.status_label.config(text="Settings applied and saved successfully.")
        else:
            messagebox.showwarning("Warning", "Not connected to UPV.")
        # Mark settings as applied regardless of connection so user can attempt sweep after connecting
        self._settings_applied = True
        self._refresh_start_sweep_state()

    def fetch_data(self):
        if self.upv:
            export_path = filedialog.asksaveasfilename(defaultextension=".hxml",
                                                       filetypes=[("HXML files", "*.hxml"), ("All files", "*.*")])
            if export_path:
                # Use preset name for working title if one has been loaded; fallback handled in fetch_and_plot_trace
                try:
                    fetch_and_plot_trace(self.upv, export_path, working_title=self._current_preset_name)
                except TypeError:
                    # Backwards compatibility if older function signature present
                    fetch_and_plot_trace(self.upv, export_path)
        else:
            messagebox.showwarning("Warning", "Not connected to UPV.")

    def start_sweep(self):
        # Enforce that settings were applied first
        if not getattr(self, '_settings_applied', False):
            messagebox.showinfo("Apply Required", "Please press 'Apply Settings' before starting a sweep.")
            return
        if self.upv is None:
            messagebox.showerror("Sweep Error", "UPV is not connected.")
            return

        def status_callback(msg):
            self.update_status(msg)

        try:
            continuous = False
            try:
                continuous = self._is_continuous_sweep_enabled()
            except Exception:
                pass
            try:
                self.upv.timeout = 30000
            except Exception:
                pass
            status_callback("⚙️ Preparing for {} sweep...".format("continuous" if continuous else "single"))
            try:
                self.upv.write("OUTP ON")
            except Exception:
                pass
            try:
                self.upv.write("INIT:CONT ON" if continuous else "INIT:CONT OFF")
            except Exception:
                pass
            status_callback("▶️ Starting {} sweep...".format("continuous" if continuous else "single"))
            try:
                self.upv.write("INIT")
            except Exception:
                pass
            if continuous:
                status_callback("🔄 Continuous sweep running (preset override).")
                try:
                    messagebox.showinfo("Sweep", "Continuous sweep started (from preset).")
                except Exception:
                    pass
                self._continuous_active = True
                if hasattr(self, 'start_sweep_btn'):
                    self.start_sweep_btn.config(state="disabled")
                if hasattr(self, 'stop_sweep_btn'):
                    self.stop_sweep_btn.config(state="normal")
                self.after(600, lambda: self._init_live_sweep_display())
            else:
                try:
                    self.upv.write("*CLS")
                    self.upv.write("*OPC")
                except Exception:
                    pass
                status_callback("⏳ Single sweep running (live)...")
                self._single_sweep_in_progress = True
                self._single_sweep_done = False
                if hasattr(self, 'start_sweep_btn'):
                    try:
                        self.start_sweep_btn.config(state="disabled")
                    except Exception:
                        pass
                self.after(80, self._init_live_sweep_display)
                self._single_prev_point_count = 0
            try:
                self._refresh_start_sweep_state()
            except Exception:
                pass
        except Exception as e:
            status_callback(f"❌ Failed to start sweep: {e}")
            try:
                messagebox.showerror("Sweep Error", f"Failed to start sweep: {e}")
            except Exception:
                pass
            self._continuous_active = False
            if hasattr(self, 'stop_sweep_btn'):
                self.stop_sweep_btn.config(state="disabled")
            if hasattr(self, 'start_sweep_btn'):
                self.start_sweep_btn.config(state="normal")

    def _on_single_sweep_complete(self, success: bool):
        if getattr(self, '_single_sweep_done', False):
            return
        self._single_sweep_done = True
        self._single_sweep_in_progress = False
        # Stop acquisition thread for single sweep (prevents late queue pushes during dialogs)
        try:
            if not self._continuous_active:
                self._stop_acquisition_thread()
                self._live_consumer_started = False
        except Exception:
            pass
        # Update status first
        if success:
            self.update_status("✔️ Single sweep completed.")
        else:
            self.update_status("⚠️ Single sweep ended (timeout/abort).", color="orange")
        # One last gentle axis freeze (skip full polling to reduce race risk)
        try:
            if hasattr(self, '_live_ax') and hasattr(self, '_live_line') and self._live_line is not None:
                xdata = list(getattr(self._live_line, 'get_xdata', lambda: [])())
                ydata = list(getattr(self._live_line, 'get_ydata', lambda: [])())
                if xdata and ydata:
                    self._apply_fixed_freq_and_auto_level(self._live_ax, xdata, ydata)
                    if hasattr(self, '_live_canvas'):
                        self._live_canvas.draw_idle()
        except Exception:
            pass
        # Show popup only if root still alive
        try:
            if self.winfo_exists():
                messagebox.showinfo("Sweep", "Single sweep completed!" if success else "Single sweep ended (timeout/abort)")
        except Exception:
            pass
        # Offer export only after popup (user acknowledgement) to avoid stacked dialogs
        if success:
            try:
                self.fetch_data()
            except Exception:
                pass
        try:
            self._settings_applied = False
            if hasattr(self, 'start_sweep_btn'):
                self.start_sweep_btn.config(state="disabled")
            self.update_status("Sweep finished. Apply Settings again to enable start.", color="green")
        except Exception:
            pass
        try:
            self._refresh_start_sweep_state()
        except Exception:
            pass

    def stop_continuous_sweep(self, silent: bool = False):
        """Stop an active continuous sweep and (optionally) fetch current data.

        Parameters:
            silent (bool): When True, suppress dialogs and data fetch. Used when stopping
                           implicitly (e.g., before applying settings)."""
        if self.upv is None:
            messagebox.showerror("Sweep Error", "UPV is not connected.")
            return
        if not self._continuous_active:
            if not silent:
                messagebox.showinfo("Sweep", "No continuous sweep is currently running.")
            return
        try:
            self.update_status("⏹ Stopping continuous sweep...")
            # Turn off continuous mode; this stops further automatic re-triggers
            self.upv.write("INIT:CONT OFF")
            # Optional abort (ignore if unsupported)
            try:
                self.upv.write("ABOR")
            except Exception:
                pass
            # Small confirmation wait (best-effort)
            prev_timeout = getattr(self.upv, 'timeout', 2000)
            try:
                self.upv.timeout = 5000
                try:
                    self.upv.query("*OPC?")
                except Exception:
                    pass
            finally:
                self.upv.timeout = prev_timeout
            self._continuous_active = False
            if hasattr(self, 'stop_sweep_btn'):
                self.stop_sweep_btn.config(state="disabled")
            if hasattr(self, 'start_sweep_btn'):
                # Respect gating (may remain disabled if settings not applied or not connected)
                try:
                    # Mark settings as needing re-apply after a run stop
                    self._settings_applied = False
                    self.start_sweep_btn.config(state="disabled")
                except Exception:
                    pass
                self._refresh_start_sweep_state()
            # Terminate any live update loop
            try:
                self._live_sweep_running = False
            except Exception:
                pass
            self.update_status("✅ Continuous sweep stopped.")
            if not silent:
                # No automatic fetch or dialog per user request; simply end silently with status label update
                pass
        except Exception as e:
            self.update_status(f"❌ Failed to stop sweep: {e}", color="red")
            if not silent:
                messagebox.showerror("Sweep Error", f"Failed to stop continuous sweep: {e}")

    def connect_to_upv(self):
        """Connect to the UPV asynchronously to avoid GUI freeze / flicker."""
        if self._connecting:
            return  # already in progress
        self._connecting = True
        self._scan_anim_phase = 0
        try:
            if hasattr(self, 'connect_btn'):
                self.connect_btn.config(state='disabled')
        except Exception:
            pass
        self.upv = None
        self._anim_scan_tick()

        def worker():
            rm = None
            try:
                rm = pyvisa.ResourceManager()
                visa_address = load_config()
                if visa_address:
                    for attempt in range(2):
                        try:
                            self._thread_safe_status(f"🔌 Trying saved address ({attempt+1}/2)...")
                            inst = rm.open_resource(visa_address)
                            inst.timeout = 5000
                            idn = inst.query("*IDN?").strip()
                            self.upv = inst
                            self._thread_safe_status(f"✅ Connected: {idn}")
                            break
                        except Exception as e:  # retry next
                            if attempt == 1:
                                visa_address = None
                if not self.upv:
                    # perform scan
                    def cb(msg):
                        # throttle noisy messages
                        if 'Found UPV' in msg or 'not found' in msg:
                            self._thread_safe_status(msg)
                    visa_address = find_upv_ip(status_callback=cb)
                    if not visa_address:
                        self._thread_safe_status("❌ UPV not found. Check cables/power.", color="red")
                        return
                    try:
                        inst = rm.open_resource(visa_address)
                        inst.timeout = 5000
                        idn = inst.query("*IDN?").strip()
                        self.upv = inst
                        self._thread_safe_status(f"✅ Connected: {idn}")
                    except Exception as e:
                        self._thread_safe_status(f"❌ Failed to connect: {e}", color="red")
                        return
            finally:
                self._connecting = False
                try:
                    if hasattr(self, 'connect_btn'):
                        self.after(0, lambda: self.connect_btn.config(state='normal'))
                except Exception:
                    pass
                # Refresh sweep start gating once connection done
                self.after(0, self._refresh_start_sweep_state)

        threading.Thread(target=worker, daemon=True).start()
    def snapshot_upv(self):
        """Capture current UPV settings and save them to a JSON snapshot file (async-safe)."""
        if self.upv is None:
            messagebox.showerror("Snapshot Error", "UPV is not connected.")
            return
        try:
            from upv.upv_readback import save_settings_snapshot
            dest = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json")],
                title="Save UPV Settings Snapshot As",
                initialfile="snapshot.json"
            )
            if not dest:
                self.update_status("Snapshot cancelled.", color="orange")
                return
            mode_continuous = messagebox.askyesno(
                "Sweep Mode",
                "Save snapshot as continuous sweep?\nYes = Continuous\nNo = Single"
            )
            out_path = save_settings_snapshot(self.upv, Path(dest))
            try:
                with open(out_path, 'r', encoding='utf-8') as f:
                    snap_data = json.load(f)
                snap_data["INIT:CONT"] = "ON" if mode_continuous else "OFF"
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(snap_data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
            self.update_status(f"Snapshot saved: {out_path.name}")
            messagebox.showinfo(
                "Snapshot Saved",
                f"Settings snapshot saved to:\n{out_path}\nSweep Mode: {'Continuous' if mode_continuous else 'Single'}"
            )
        except Exception as e:
            self.update_status("Snapshot failed", color="red")
            messagebox.showerror("Snapshot Error", f"Failed to create snapshot: {e}")

    def show_sweep_display(self):
        """Send DISPlay:SWEep:SHOW to UPV and embed current sweep trace in a popup window.

        Steps:
          1. Ensure connection.
          2. Issue SCPI to force instrument display.
          3. Query trace data (frequency & magnitude).
          4. Resolve Y units (SENS:USER > SENS:UNIT > SENS1:UNIT > dBV).
          5. Render matplotlib plot inside a transient Toplevel without blocking main UI.
        """
        if self.upv is None:
            messagebox.showwarning("UPV", "Not connected to UPV.")
            return
        try:
            # Tell instrument to show its sweep display (best-effort)
            try:
                self.upv.write("DISPlay:SWEep:SHOW")
            except Exception:
                pass  # Non-fatal if instrument firmware variant differs

            # Fetch trace data directly
            try:
                x_raw = self.upv.query("TRAC:SWE1:LOAD:AX?")
                y_raw = self.upv.query("TRAC:SWE1:LOAD:AY?")
            except Exception as e:
                messagebox.showerror("Trace Error", f"Failed to read sweep trace: {e}")
                return
            import numpy as _np
            try:
                x_vals = _np.fromstring(x_raw, sep=',')
                y_vals = _np.fromstring(y_raw, sep=',')
            except Exception as e:
                messagebox.showerror("Parse Error", f"Failed to parse trace data: {e}")
                return
            if len(x_vals) == 0 or len(x_vals) != len(y_vals):
                messagebox.showerror("Trace Error", "Empty or mismatched trace data.")
                return

            # Unit resolution (reuse logic priorities)
            y_unit_display = 'dBV'
            try:
                import json as _json
                if Path(SETTINGS_FILE).exists():
                    with open(SETTINGS_FILE, 'r', encoding='utf-8') as _sf:
                        _settings_data = _json.load(_sf)
                    user_unit_raw = _settings_data.get('SENS:USER')
                    std_unit_raw = _settings_data.get('SENS:UNIT') or _settings_data.get('SENS1:UNIT')
                    def _sanitize(s: str) -> str:
                        if not isinstance(s, str):
                            return ''
                        s2 = s.strip().strip('"').strip("'")
                        low = s2.lower()
                        if low.startswith('db'):
                            rest = s2[2:].lstrip()
                            toks = [t.upper() if t.lower() == 'spl' else t for t in rest.split()]
                            return 'dB ' + ' '.join(toks) if toks else 'dB'
                        return s2
                    if isinstance(user_unit_raw, str) and user_unit_raw.strip():
                        cand = _sanitize(user_unit_raw)
                        if cand:
                            y_unit_display = cand
                        else:
                            if isinstance(std_unit_raw, str):
                                yu = std_unit_raw.strip().upper()
                                unit_map = {'DBR':'dBr','DBV':'dBV','DBU':'dBu','DBM':'dBm','V':'V','MV':'mV','UV':'μV','UVR':'μV','UV RMS':'μV','UVRMS':'μV','PCT':'%','%':'%'}
                                y_unit_display = unit_map.get(yu, std_unit_raw.strip())
                    elif isinstance(std_unit_raw, str):
                        yu = std_unit_raw.strip().upper()
                        unit_map = {'DBR':'dBr','DBV':'dBV','DBU':'dBu','DBM':'dBm','V':'V','MV':'mV','UV':'μV','UVR':'μV','UV RMS':'μV','UVRMS':'μV','PCT':'%','%':'%'}
                        y_unit_display = unit_map.get(yu, std_unit_raw.strip())
            except Exception:
                pass

            # Build / reuse popup window
            import tkinter as _tk
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure

            # Destroy previous plot window if still open
            if hasattr(self, '_sweep_plot_win') and self._sweep_plot_win is not None:
                try:
                    self._sweep_plot_win.destroy()
                except Exception:
                    pass
            self._sweep_plot_win = _tk.Toplevel(self.master)
            self._sweep_plot_win.title("Sweep Display")
            self._sweep_plot_win.geometry("700x450")
            # Figure
            fig = Figure(figsize=(7, 4.2), dpi=100)
            ax = fig.add_subplot(111)
            ax.semilogx(x_vals, y_vals)
            ax.set_xlabel('Frequency (Hz)')
            ax.set_ylabel(f'Level ({y_unit_display})')
            ax.set_title('Sweep Trace')
            ax.grid(True, which='both', ls='--', linewidth=0.5)
            # Force refresh of axis limits for explicit display request
            self._force_freq_limit_refresh = True
            self._apply_fixed_freq_and_auto_level(ax, x_vals, y_vals)
            fig.tight_layout()

            canvas = FigureCanvasTkAgg(fig, master=self._sweep_plot_win)
            canvas.draw()
            canvas.get_tk_widget().pack(fill='both', expand=True)

            self.update_status("Sweep display updated.")
        except Exception as e:
            messagebox.showerror("Display Error", f"Failed to show sweep: {e}")
            self.update_status("Failed to show sweep", color="red")

    # ---------------- Live Sweep Display (Auto Refresh) -----------------
    def _init_live_sweep_display(self):
        """Setup (or reuse) live sweep window and start background acquisition & GUI consumer."""
        if self.upv is None:
            return
        import tkinter as _tk
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure
        create_new = False
        if not hasattr(self, '_sweep_plot_win') or self._sweep_plot_win is None or not self._sweep_plot_win.winfo_exists():
            create_new = True
        if create_new:
            try:
                self._sweep_plot_win = _tk.Toplevel(self.master)
                self._sweep_plot_win.title("Live Sweep")
                self._sweep_plot_win.geometry("700x450")
                fig = Figure(figsize=(7, 4.2), dpi=100)
                ax = fig.add_subplot(111)
                ax.set_xscale('log')
                ax.set_xlabel('Frequency (Hz)')
                ax.set_ylabel(f'Level ({self._resolve_y_unit_from_settings()})')
                ax.set_title('Live Sweep Trace')
                ax.grid(True, which='both', ls='--', linewidth=0.5)
                try:
                    ax.set_xlim(100, 12000)
                except Exception:
                    pass
                fig.tight_layout()
                canvas = FigureCanvasTkAgg(fig, master=self._sweep_plot_win)
                canvas.draw()
                canvas.get_tk_widget().pack(fill='both', expand=True)
                self._live_fig = fig
                self._live_ax = ax
                self._live_canvas = canvas
                try:
                    (self._live_line,) = ax.semilogx([], [], color='C0')
                except Exception:
                    self._live_line = None
                def _on_close():
                    try:
                        self._live_consumer_started = False
                        self._stop_acquisition_thread()
                    except Exception:
                        pass
                    try:
                        self._sweep_plot_win.destroy()
                    except Exception:
                        pass
                self._sweep_plot_win.protocol("WM_DELETE_WINDOW", _on_close)
            except Exception:
                return
        # Start acquisition thread if needed
        if self._acq_thread is None or not self._acq_thread.is_alive():
            self._start_acquisition_thread()
        # Start consumer loop once
        if not self._live_consumer_started:
            self._live_consumer_started = True
            self.after(120, self._poll_live_sweep)

    def _poll_live_sweep(self):
        """GUI consumer: apply latest queued data to plot (non-blocking)."""
        try:
            single_active = getattr(self, '_single_sweep_in_progress', False)
            if self.upv is None or (not self._continuous_active and not single_active):
                # Still reschedule to detect restart
                self.after(300, self._poll_live_sweep)
                return
            latest = None
            while True:
                try:
                    latest = self._data_queue.get_nowait()
                except queue.Empty:
                    break
            if latest and hasattr(self, '_live_ax'):
                x_vals, y_vals = latest
                unit_display = self._resolve_y_unit_from_settings()
                ax = self._live_ax
                try:
                    if getattr(self, '_live_line', None) is not None:
                        self._live_line.set_data(x_vals, y_vals)
                    else:
                        (self._live_line,) = ax.semilogx(x_vals, y_vals, color='C0')
                    ax.set_ylabel(f'Level ({unit_display})')
                    self._apply_fixed_freq_and_auto_level(ax, x_vals, y_vals)
                except Exception:
                    pass
                try:
                    self._live_canvas.draw_idle()
                except Exception:
                    pass
        finally:
            if hasattr(self, '_sweep_plot_win') and self._sweep_plot_win and self._sweep_plot_win.winfo_exists() and self._live_consumer_started:
                self.after(120, self._poll_live_sweep)

    # ---------------- Acquisition Thread Management -----------------
    def _start_acquisition_thread(self):
        self._stop_acquisition_thread()
        self._acq_stop_event.clear()
        t = threading.Thread(target=self._acquisition_loop, name="UPVAcq", daemon=True)
        self._acq_thread = t
        t.start()

    def _stop_acquisition_thread(self):
        if self._acq_thread and self._acq_thread.is_alive():
            self._acq_stop_event.set()
            try:
                self._acq_thread.join(timeout=1.2)
            except Exception:
                pass
        self._acq_thread = None

    def _acquisition_loop(self):
        prev_point_count = None
        idle_cycles = 0
        while not self._acq_stop_event.is_set():
            active = (self._continuous_active or getattr(self, '_single_sweep_in_progress', False)) and self.upv is not None
            if not active:
                # If single sweep finished and not continuous, we can slow down / exit thread if window closed
                if not self._continuous_active and not getattr(self, '_single_sweep_in_progress', False):
                    if not hasattr(self, '_sweep_plot_win') or not (self._sweep_plot_win and self._sweep_plot_win.winfo_exists()):
                        break  # no need to keep thread alive
                time.sleep(0.25)
                continue
            x_raw = self._safe_query("TRAC:SWE1:LOAD:AX?", timeout_ms=2500)
            y_raw = self._safe_query("TRAC:SWE1:LOAD:AY?", timeout_ms=2500)
            if x_raw is None or y_raw is None:
                self._acq_fail_count += 1
                if self._acq_fail_count == 5:
                    self._thread_safe_status("Comm timeouts (5) – continuing", color="red")
                time.sleep(0.35)
                continue
            self._acq_fail_count = 0
            try:
                x_vals = [float(v) for v in x_raw.split(',') if v.strip()]
                y_vals = [float(v) for v in y_raw.split(',') if v.strip()]
            except Exception:
                time.sleep(0.18)
                continue
            if len(x_vals) != len(y_vals):
                m = min(len(x_vals), len(y_vals))
                x_vals = x_vals[:m]
                y_vals = y_vals[:m]
            if x_vals:
                if self._data_queue.full():
                    try:
                        self._data_queue.get_nowait()
                    except Exception:
                        pass
                try:
                    self._data_queue.put_nowait((x_vals, y_vals))
                except Exception:
                    pass
            pc = len(x_vals)
            if prev_point_count is not None and pc == prev_point_count:
                idle_cycles += 1
            else:
                idle_cycles = 0
            prev_point_count = pc
            if idle_cycles < 3:
                time.sleep(0.12)
            elif idle_cycles < 10:
                time.sleep(0.22)
            else:
                time.sleep(0.4)
            # Single sweep completion detection via ESR bit 0
            if getattr(self, '_single_sweep_in_progress', False) and not self._continuous_active:
                esr = self._safe_query("*ESR?", timeout_ms=600)
                if esr is not None:
                    try:
                        esr_val = int(float(esr))
                    except Exception:
                        esr_val = 0
                    if esr_val & 0x01:
                        try:
                            self._thread_safe_status("Single sweep complete", color="green")
                        except Exception:
                            pass
                        try:
                            self.after(0, lambda: self._on_single_sweep_complete(True))
                        except Exception:
                            pass
                        continue
                # If acquisition seems stalled for extended time (idle_cycles high) mark as timeout
                if idle_cycles > 200:  # ~ >60s of no change at slowest loop
                    try:
                        self.after(0, lambda: self._on_single_sweep_complete(False))
                    except Exception:
                        pass
                    continue
        # exiting

    def destroy(self):  # override
        try:
            self._stop_acquisition_thread()
        except Exception:
            pass
        return super().destroy()

    def _is_continuous_sweep_enabled(self):
        """Determine if preset/settings JSON requests continuous sweep (INIT:CONT ON).

        Priority order / accepted forms (case-insensitive):
          1. Top-level key "INIT:CONT": "ON" | "OFF"
          2. Top-level key "SweepMode": "CONT" / "CONTINUOUS" / "ON" (anything else = single)
          3. Top-level key "ContinuousSweep": true/false

        Example additions to preset JSON (any ONE of these):
          { "INIT:CONT": "ON" }
          { "SweepMode": "CONT" }
          { "ContinuousSweep": true }

        Returns True if continuous sweep requested, False otherwise.
        """
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return False

        # 1. Explicit SCPI style key
        init_cont = data.get("INIT:CONT")
        if isinstance(init_cont, str) and init_cont.strip().upper() == "ON":
            return True
        if isinstance(init_cont, str) and init_cont.strip().upper() == "OFF":
            return False

        # 2. Mode key
        sweep_mode = data.get("SweepMode")
        if isinstance(sweep_mode, str) and sweep_mode.strip().upper() in {"CONT", "CONTINUOUS", "ON"}:
            return True

        # 3. Boolean helper key
        cont_flag = data.get("ContinuousSweep")
        if isinstance(cont_flag, bool):
            return cont_flag

        return False

    def _activate_scroll(self, canvas):
        self.active_scroll_canvas = canvas

    def _on_global_mousewheel(self, event):
        if self._suspend_global_scroll:
            return
        if self.active_scroll_canvas is not None:
            delta = event.delta
            # Windows gives multiples of 120
            steps = int(-delta/120) if delta != 0 else 0
            if steps != 0:
                self.active_scroll_canvas.yview_scroll(steps, 'units')

    def _on_button4(self, event):  # Linux scroll up
        if self._suspend_global_scroll:
            return
        if self.active_scroll_canvas is not None:
            self.active_scroll_canvas.yview_scroll(-1, 'units')

    def _on_button5(self, event):  # Linux scroll down
        if self._suspend_global_scroll:
            return
        if self.active_scroll_canvas is not None:
            self.active_scroll_canvas.yview_scroll(1, 'units')

    def bind_combobox_mousewheel(self, combo):
        """Allow scrolling the parent panel even while mouse is over a readonly Combobox.

        Previous implementation suspended global scroll to avoid accidental panel movement while
        the user intended to use the combobox. However, since all comboboxes are readonly and we
        also block their own default mousewheel behavior, it's more user-friendly to keep panel
        scrolling active. We intercept the wheel event, manually scroll the active canvas, then
        return 'break' so the combobox selection doesn't change.
        """

        def on_mousewheel(event):
            # Ensure we have an active canvas (should be set when entering panel/inner frame)
            if self.active_scroll_canvas is not None:
                delta = event.delta
                steps = int(-delta/120) if delta != 0 else 0
                if steps != 0:
                    self.active_scroll_canvas.yview_scroll(steps, 'units')
            return 'break'  # Prevent combobox value cycling

        combo.bind('<MouseWheel>', on_mousewheel, add='+')

    def _update_sweep_ctrl_visibility(self):
        """Show only Frequency when Sweep Ctrl == OFF; otherwise hide Frequency and show other sweep controls.

        Sweep Ctrl combobox contains human-readable values; we map back to code via display_map if needed.
        We rely on the stored widget registry self._gen_func_widgets built in load_settings.
        """
        try:
            sc_widget = self.entries[("Generator Function", "Sweep Ctrl")]
        except KeyError:
            return

        current_display = sc_widget.get().strip()
        # Determine if OFF; fetch mapping
        try:
            from gui.display_map import SWEEP_CTRL_OPTIONS
            reverse_map = {v: k for k, v in SWEEP_CTRL_OPTIONS.items()}
            code = reverse_map.get(current_display, current_display)
        except Exception:
            code = current_display

        # Determine OFF state robustly (previous bug: comparing upper() to mixed-case string always False)
        is_off = str(code).strip().lower() == "off"
        # Determine Auto List state (various possible display forms)
        code_norm = str(code).strip().lower()
        is_auto_list = code_norm in {"alis", "auto list", "auto_list", "autolist"}

        # If registry missing OR any expected dynamic label missing, rebuild dynamically by scanning grid
        expected_dynamic = ["Frequency", "Next Step", "X Axis", "Z Axis", "Spacing", "Start", "Stop", "Points", "Halt"]
        if (not hasattr(self, '_gen_func_widgets') or
            any(lbl not in getattr(self, '_gen_func_widgets', {}) for lbl in expected_dynamic)):
            try:
                inner_frame, _canvas = self._panel_frames.get("Generator Function", (None, None))
                if inner_frame is not None:
                    dynamic_labels = set(expected_dynamic)
                    row_map = {}
                    for child in inner_frame.winfo_children():
                        try:
                            info = child.grid_info()
                        except Exception:
                            continue
                        if not info:
                            continue
                        r = info.get('row')
                        c = info.get('column')
                        if r is None or c is None:
                            continue
                        row_map.setdefault(r, {})[c] = child
                    rebuilt = {}
                    for r, cols in row_map.items():
                        label_w = cols.get(0)
                        control_w = cols.get(1)
                        if label_w is not None:
                            try:
                                text = label_w.cget('text')
                            except Exception:
                                text = None
                            if text in dynamic_labels:
                                rebuilt.setdefault(text, []).append(label_w)
                                if control_w is not None:
                                    rebuilt[text].append(control_w)
                    if rebuilt:
                        self._gen_func_widgets = rebuilt
            except Exception:
                pass

        # Frequency widgets: match loosely (case-insensitive, allow colon, partial 'freq')
        other_norm_labels = {lbl.replace(':','').strip().lower() for lbl in expected_dynamic if lbl != 'Frequency'}
        for label_text, widgets in getattr(self, '_gen_func_widgets', {}).items():
            norm = label_text.replace(':', '').strip().lower()
            is_frequency_label = norm.startswith('frequency') or 'freq' in norm
            if is_frequency_label:
                # Frequency only shown when Sweep Ctrl == OFF
                show = is_off
            elif norm in other_norm_labels:
                # Base visibility for non-frequency dynamic labels is the inverse of OFF
                if is_off:
                    show = False
                else:
                    # Additional rule: when Auto List (ALIS) is chosen, hide Spacing/Start/Stop/Points
                    hide_for_auto_list = {"spacing", "start", "stop", "points"}
                    if is_auto_list and norm in hide_for_auto_list:
                        show = False
                    else:
                        show = True
            else:
                # Not a managed dynamic label; leave as-is
                continue
            for w in widgets:
                try:
                    if show:
                        if hasattr(w, 'grid'):
                            w.grid()
                    else:
                        if hasattr(w, 'grid_remove'):
                            w.grid_remove()
                except Exception:
                    continue

    def _update_sn_sequence_visibility(self):
        # Backwards compatibility: delegate to unified analyzer function visibility handler
        self._update_analyzer_function_visibility()

    def _update_analyzer_function_visibility(self):
        """Unified visibility control for Analyzer Function dependent rows.

        Rules:
          - Hide 'S/N Sequence' when Function Analyzer == 'RMS Selective' (RMSS)
          - Hide 'Bandwidth Analyzer Config', 'Sweep Ctrl Analyzer Config', and 'Freq Mode' when Function Analyzer == 'RMS'
        """
        try:
            fa_widget = self.entries.get(("Analyzer Function", "Function Analyzer"))
            if not fa_widget:
                return
            current_display = fa_widget.get().strip()
            from gui.display_map import FUNCTION_ANALYZER_OPTIONS
            reverse_map = {v: k for k, v in FUNCTION_ANALYZER_OPTIONS.items()}
            code = reverse_map.get(current_display, current_display)

            # S/N Sequence handling (hide if RMSS)
            widgets = getattr(self, '_sn_sequence_widgets', None)
            if widgets:
                hide_sn = (code == 'RMSS')
                any_visible = any(w.winfo_manager() == 'grid' for w, _ in widgets)
                if hide_sn and any_visible:
                    for w, _info in widgets:
                        try:
                            w.grid_remove()
                        except Exception:
                            pass
                elif not hide_sn and not any_visible:
                    for w, info in widgets:
                        try:
                            grid_kwargs = {k: v for k, v in info.items() if k in ('row','column','sticky','padx','pady','columnspan','rowspan')}
                            w.grid(**grid_kwargs)
                        except Exception:
                            pass

            # RMS hide set
            hide_when_rms = ['Bandwidth Analyzer Config', 'Sweep Ctrl Analyzer Config', 'Freq Mode', 'Factor']
            rows = getattr(self, '_an_func_hidden_rows', {})

            # Ensure RMS-only labels (Tolerance, Resolution, Timeout) are captured if missing
            try:
                rms_only_capture_labels = ['Tolerance', 'Resolution', 'Timeout']
                missing_capture = [lbl for lbl in rms_only_capture_labels if lbl not in rows]
                if missing_capture:
                    panel_tuple = self._panel_frames.get("Analyzer Function") if hasattr(self, '_panel_frames') else None
                    if panel_tuple:
                        inner_frame = panel_tuple[0]
                        # Build row map of all widgets by grid row
                        row_map = {}
                        for child in inner_frame.winfo_children():
                            try:
                                gi = child.grid_info()
                            except Exception:
                                continue
                            if not gi:
                                continue
                            r = gi.get('row')
                            if r is None:
                                continue
                            row_map.setdefault(r, []).append(child)
                        # Search for labels matching our targets
                        for r, widgets_in_row in row_map.items():
                            # Find any Label widget whose text (stripped, without colon) matches one of the missing labels
                            label_texts = {}
                            for w in widgets_in_row:
                                try:
                                    if isinstance(w, Label):
                                        txt = w.cget('text')
                                        if isinstance(txt, str):
                                            norm = txt.replace(':', '').strip()
                                            label_texts[norm] = True
                                except Exception:
                                    continue
                            intersect = [lbl for lbl in missing_capture if lbl in label_texts]
                            if not intersect:
                                continue
                            # Capture entire row for each matching label (usually one)
                            for target in intersect:
                                captured = []
                                for w in widgets_in_row:
                                    try:
                                        gi = w.grid_info()
                                        # Store minimal grid params we rely on elsewhere
                                        grid_kwargs = {k: v for k, v in gi.items() if k in ('row','column','sticky','padx','pady','columnspan','rowspan')}
                                        captured.append((w, grid_kwargs))
                                    except Exception:
                                        continue
                                if captured:
                                    rows[target] = captured
                    # Reassign back to attribute (rows is a reference but ensure attr exists)
                    self._an_func_hidden_rows = rows
            except Exception:
                pass
            for label in hide_when_rms:
                row_widgets = rows.get(label, [])
                if not row_widgets:
                    continue
                hide_row = (code == 'RMS')
                any_visible = any(w.winfo_manager() == 'grid' for w, _ in row_widgets)
                if hide_row and any_visible:
                    for w, _info in row_widgets:
                        try:
                            w.grid_remove()
                        except Exception:
                            pass
                elif not hide_row and not any_visible:
                    for w, info in row_widgets:
                        try:
                            grid_kwargs = {k: v for k, v in info.items() if k in ('row','column','sticky','padx','pady','columnspan','rowspan')}
                            w.grid(**grid_kwargs)
                        except Exception:
                            pass

            # RMSS-specific hide set (Filter1 and Filter3)
            hide_when_rmss = ['Filter1', 'Filter3']
            for label in hide_when_rmss:
                row_widgets = rows.get(label, [])
                if not row_widgets:
                    continue
                # Fallback: also treat display text containing 'RMS Selective' as RMSS in case mapping failed
                hide_row = (code == 'RMSS') or (isinstance(current_display, str) and current_display.lower().startswith('rms') and 'select' in current_display.lower())
                any_visible = any(w.winfo_manager() == 'grid' for w, _ in row_widgets)
                if hide_row and any_visible:
                    for w, _info in row_widgets:
                        try:
                            w.grid_remove()
                        except Exception:
                            pass
                elif not hide_row and not any_visible:
                    for w, info in row_widgets:
                        try:
                            grid_kwargs = {k: v for k, v in info.items() if k in ('row','column','sticky','padx','pady','columnspan','rowspan')}
                            w.grid(**grid_kwargs)
                        except Exception:
                            pass

            # Samples: show only when Function Analyzer == RMS
            try:
                samples_widgets = rows.get('Samples', [])
                if samples_widgets:
                    should_show_samples = (code == 'RMS')
                    any_visible = any(w.winfo_manager() == 'grid' for w, _ in samples_widgets)
                    if should_show_samples and not any_visible:
                        for w, info in samples_widgets:
                            try:
                                grid_kwargs = {k: v for k, v in info.items() if k in ('row','column','sticky','padx','pady','columnspan','rowspan')}
                                w.grid(**grid_kwargs)
                            except Exception:
                                pass
                    elif not should_show_samples and any_visible:
                        for w, _info in samples_widgets:
                            try:
                                w.grid_remove()
                            except Exception:
                                pass
            except Exception:
                pass

            # Additional dependency: Factor only visible when Freq Mode == GENT (Gen Track)
            try:
                freq_widget = self.entries.get(("Analyzer Function", "Freq Mode"))
                if freq_widget:
                    from gui.display_map import FREQ_MODE_OPTIONS
                    rev_freq = {v: k for k, v in FREQ_MODE_OPTIONS.items()}
                    freq_code = rev_freq.get(freq_widget.get().strip(), freq_widget.get().strip())
                    factor_widgets = rows.get('Factor', [])
                    if factor_widgets:
                        should_show = (code != 'RMS') and (freq_code == 'GENT')  # hide under RMS anyway; show only if Gen Track
                        any_visible = any(w.winfo_manager() == 'grid' for w, _ in factor_widgets)
                        if should_show and not any_visible:
                            for w, info in factor_widgets:
                                try:
                                    grid_kwargs = {k: v for k, v in info.items() if k in ('row','column','sticky','padx','pady','columnspan','rowspan')}
                                    w.grid(**grid_kwargs)
                                except Exception:
                                    pass
                        elif not should_show and any_visible:
                            for w, _info in factor_widgets:
                                try:
                                    w.grid_remove()
                                except Exception:
                                    pass
            except Exception:
                pass

            # Tolerance / Resolution / Timeout: only show when Function Analyzer == RMS
            try:
                rms_only = ['Tolerance', 'Resolution', 'Timeout']
                for label in rms_only:
                    row_widgets = rows.get(label, [])
                    if not row_widgets:
                        continue
                    show = (code == 'RMS')
                    any_visible = any(w.winfo_manager() == 'grid' for w, _ in row_widgets)
                    if show and not any_visible:
                        for w, info in row_widgets:
                            try:
                                grid_kwargs = {k: v for k, v in info.items() if k in ('row','column','sticky','padx','pady','columnspan','rowspan')}
                                w.grid(**grid_kwargs)
                            except Exception:
                                pass
                    elif not show and any_visible:
                        for w, _info in row_widgets:
                            try:
                                w.grid_remove()
                            except Exception:
                                pass
            except Exception:
                pass
        except Exception:
            pass

    def _reset_all_panel_views(self):
        """Ensure each panel canvas shows content at the top and has proper scrollregion.

        Some platforms create the canvas before children sizes are final; this forces an
        update so the widgets are visible immediately without needing an initial scroll.
        """
        frames = getattr(self, '_panel_frames', {})
        for section, (inner_frame, canvas) in frames.items():
            try:
                if hasattr(canvas, '_recalc'):
                    canvas._recalc()
                canvas.update_idletasks()
                bbox = canvas.bbox("all")
                if bbox:
                    canvas.configure(scrollregion=bbox)
                canvas.yview_moveto(0)
            except Exception:
                continue

    def save_preset(self):
        import json
        from tkinter import filedialog, messagebox

        # Ask user where to save the preset
        preset_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="Save Preset As"
        )
        if not preset_path:
            return

        mode_continuous = messagebox.askyesno(
            "Sweep Mode",
            "Save preset as continuous sweep?\nYes = Continuous\nNo = Single"
        )

        # Read current settings from settings.json
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            current_settings = json.load(f)

        current_settings["INIT:CONT"] = "ON" if mode_continuous else "OFF"

        # Save to the chosen preset file
        with open(preset_path, "w", encoding="utf-8") as f:
            json.dump(current_settings, f, indent=2, ensure_ascii=False)

        messagebox.showinfo(
            "Preset Saved",
            f"Preset saved to {preset_path}\nSweep Mode: {'Continuous' if mode_continuous else 'Single'}"
        )
    
    def load_preset(self):
        import json
        from tkinter import filedialog, messagebox
        from pathlib import Path as _Path

        # Ask user to select a preset file
        preset_path = filedialog.askopenfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="Load Preset"
        )
        if not preset_path:
            return

        try:
            # Load the selected preset file
            with open(preset_path, "r", encoding="utf-8") as f:
                preset_settings = json.load(f)

            # Overwrite the current settings.json with the preset
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(preset_settings, f, indent=2, ensure_ascii=False)

            # Reload the GUI to reflect the loaded preset
            self.load_settings()
            # Record preset base name for future exports (WorkingTitle / CurveDataName), but allow default to override
            try:
                stem = _Path(preset_path).stem
                if stem.lower() == DEFAULT_PRESET_NAME.lower():
                    self._current_preset_name = DEFAULT_PRESET_NAME
                else:
                    self._current_preset_name = stem
            except Exception:
                self._current_preset_name = DEFAULT_PRESET_NAME
            # Update preset label display (always show something; default if None)
            try:
                display_name = self._current_preset_name or DEFAULT_PRESET_NAME
                self.preset_label.config(text=f"Preset: {display_name}")
            except Exception:
                pass
            messagebox.showinfo("Preset Loaded", f"Preset loaded from {preset_path}")
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load preset: {e}")

    def update_status(self, msg, color="green"):
        self.status_label.config(text=msg, fg=color)
        self.status_label.update_idletasks()
        # Keep preset label visible; optionally append to status text if desired (disabled by default)