from cProfile import label
import pyvisa
import json
import math
from tkinter import Tk, Frame, Button, Label, filedialog, messagebox, Canvas, Scrollbar
from upv.upv_auto_config import find_upv_ip, apply_grouped_settings, fetch_and_plot_trace, load_config, save_config
from tkinter import ttk, Entry
from gui.display_map import (
    INSTRUMENT_GENERATOR_OPTIONS,
    CHANNEL_GENERATOR_OPTIONS,
    OUTPUT_TYPE_OPTIONS,
    IMPEDANCE_OPTIONS_BAL,
    IMPEDANCE_OPTIONS_UNBAL
)

SETTINGS_FILE = r"c:\Users\AU001A0W\OneDrive - WSA\Documents\Mic_Sensitivity\settings.json"

reverse_output_type_map = {v: k for k, v in OUTPUT_TYPE_OPTIONS.items()}

class MainWindow(Frame):
    def __init__(self, master, run_upv_callback):
        super().__init__(master)
        self.run_upv_callback = run_upv_callback
        self.master = master
        self.master.title("Mic Sensitivity GUI")
        self.master.geometry("1200x700")  # Wider window for all sections

        self.top_frame = Frame(self.master)
        self.top_frame.pack(pady=20, fill="x")

        # Left spacer
        self.left_spacer = Frame(self.top_frame)
        self.left_spacer.pack(side="left", expand=True)

        # Left column for main controls
        self.left_frame = Frame(self.top_frame)
        self.left_frame.pack(side="left", padx=(0, 20), anchor="n")

        Label(self.left_frame, text="Mic Sensitivity Control", font=("Helvetica", 16)).pack(pady=10)

        # Use grid for button rows to prevent shifting
        btn_width = 18
        button_row1 = Frame(self.left_frame)
        button_row1.pack(pady=5)
        btn1 = Button(button_row1, text="Connect to UPV", command=self.connect_to_upv, width=btn_width)
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

        # Right spacer
        self.right_spacer = Frame(self.top_frame)
        self.right_spacer.pack(side="left", expand=True)

        self.status_label = Label(self.left_frame, text="", fg="green")
        self.status_label.pack(pady=10)

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

    def load_settings(self):
        # Clear existing panel containers (if any)
        for widget in self.grid_frame.winfo_children():
            widget.destroy()
        self.entries.clear()

        try:
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)

            sections = [
                ("Generator Config", 0, 0),
                ("Analyzer Config", 0, 1),
                ("Generator Function", 1, 0),
                ("Analyzer Function", 1, 1)
            ]

            frames = {}
            # Build four scrollable panels
            for section, row, col in sections:
                # Outer container cell
                cell = Frame(self.grid_frame, bd=0)
                cell.grid(row=row, column=col, sticky="nsew", padx=12, pady=12)
                cell.grid_rowconfigure(0, weight=1)
                cell.grid_columnconfigure(0, weight=1)

                panel_canvas = Canvas(cell, highlightthickness=0, bd=1, relief="solid")
                vscroll = Scrollbar(cell, orient="vertical", command=panel_canvas.yview)
                panel_canvas.configure(yscrollcommand=vscroll.set)
                panel_canvas.grid(row=0, column=0, sticky="nsew")
                vscroll.grid(row=0, column=1, sticky="ns")

                inner_frame = Frame(panel_canvas, bd=2, relief="groove", padx=16, pady=12)
                window_id = panel_canvas.create_window((0, 0), window=inner_frame, anchor="nw")

                def _make_configure_callback(pc=panel_canvas, fr=inner_frame, wid=window_id):
                    def _on_configure(event):
                        pc.itemconfig(wid, width=pc.winfo_width())
                        pc.configure(scrollregion=pc.bbox("all"))
                    return _on_configure
                inner_frame.bind("<Configure>", _make_configure_callback())

                # Activate scroll focus when pointer enters this panel
                panel_canvas.bind("<Enter>", lambda e, pc=panel_canvas: self._activate_scroll(pc))
                inner_frame.bind("<Enter>", lambda e, pc=panel_canvas: self._activate_scroll(pc))

                frames[section] = (inner_frame, panel_canvas)

            for section, row, col in sections:
                frame, frame_canvas = frames[section]
                Label(frame, text=section, font=("Helvetica", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0,8))
                if section in settings:
                    impedance_row = None
                    impedance_frame = None
                    impedance_value = None
                    if section == "Generator Config":
                        self.output_type_combo = None  # <-- Only reset for Generator Config

                    for i, (label, value) in enumerate(settings[section].items(), start=1):
                        Label(frame, text=label, anchor="w", width=22).grid(row=i, column=0, sticky="w", padx=(0,8), pady=2)
                        if section == "Generator Config" and label == "Instrument Generator":
                            display_values = list(INSTRUMENT_GENERATOR_OPTIONS.values())
                            current_display = INSTRUMENT_GENERATOR_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[("Generator Config", label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Generator Config" and label == "Channel Generator":
                            display_values = list(CHANNEL_GENERATOR_OPTIONS.values())
                            current_display = CHANNEL_GENERATOR_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[("Generator Config", label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Generator Config" and label == "Output Type (Unbal/Bal)":
                            display_values = list(OUTPUT_TYPE_OPTIONS.values())
                            current_display = OUTPUT_TYPE_OPTIONS.get(value, value)
                            self.output_type_combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            self.output_type_combo.set(current_display)
                            self.output_type_combo.grid(row=i, column=1, sticky="w", pady=2)
                            self.output_type_combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[("Generator Config", label)] = self.output_type_combo
                            output_type_row = i
                            self.bind_combobox_mousewheel(self.output_type_combo)
                        elif section == "Generator Config" and label == "Common (Float/Ground)":
                            # Use Radiobuttons for GRO/FLO
                            from gui.display_map import COMMON_OPTIONS
                            import tkinter as tk
                            self.common_var = tk.StringVar()
                            self.common_var.set(value if value in COMMON_OPTIONS else "GRO")
                            radio_frame = Frame(frame)
                            radio_frame.grid(row=i, column=1, sticky="w", pady=2)
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
                            # Try to get display value from code, else use as is
                            current_display = BANDWIDTH_GENERATOR_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[("Generator Config", label)] = combo
                        elif section == "Generator Config" and label == "Volt Range (Auto/Fix)":
                            from gui.display_map import VOLT_RANGE_OPTIONS
                            import tkinter as tk
                            self.volt_range_var = tk.StringVar()
                            self.volt_range_var.set(value if value in VOLT_RANGE_OPTIONS else "AUTO")
                            radio_frame = Frame(frame)
                            radio_frame.grid(row=i, column=1, sticky="w", pady=2)
                            for code, display in VOLT_RANGE_OPTIONS.items():
                                rb = ttk.Radiobutton(radio_frame, text=display, variable=self.volt_range_var, value=code)
                                rb.pack(side="left", padx=5)
                            self.entries[("Generator Config", label)] = self.volt_range_var
                        elif section == "Generator Config" and label == "Max Voltage":
                            # Split value and unit if possible
                            import re
                            unit_options = ["V", "mV", "μV", "dBV", "dBu", "dBm"]
                            val_str = str(value)
                            match = re.match(r"^([\-\d\.]+)\s*([a-zA-Zμ]+)?$", val_str)
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
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = (entry, combo)
                        elif section == "Generator Config" and label == "Ref Voltage":
                            # Same as Max Voltage: value + unit
                            import re
                            unit_options = ["V", "mV", "μV", "dBV", "dBu", "dBm"]
                            val_str = str(value)
                            match = re.match(r"^([\-\d\.]+)\s*([a-zA-Zμ]+)?$", val_str)
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
                            combo.bind("<MouseWheel>", lambda e: "break")
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
                            combo.bind("<MouseWheel>", lambda e: "break")
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
                            reverse_map = {v: k for k, v in FUNCTION_GENERATOR_OPTIONS.items()}
                            current_display = FUNCTION_GENERATOR_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                        elif section == "Generator Function" and label == "Sweep Ctrl":
                            from gui.display_map import SWEEP_CTRL_OPTIONS
                            display_values = list(SWEEP_CTRL_OPTIONS.values())
                            reverse_map = {v: k for k, v in SWEEP_CTRL_OPTIONS.items()}
                            current_display = SWEEP_CTRL_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                        elif section == "Generator Function" and label == "Next Step":
                            from gui.display_map import NEXT_STEP_OPTIONS
                            display_values = list(NEXT_STEP_OPTIONS.values())
                            reverse_map = {v: k for k, v in NEXT_STEP_OPTIONS.items()}
                            current_display = NEXT_STEP_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                        elif section == "Generator Function" and label == "X Axis":
                            from gui.display_map import X_AXIS_OPTIONS
                            display_values = list(X_AXIS_OPTIONS.values())
                            reverse_map = {v: k for k, v in X_AXIS_OPTIONS.items()}
                            current_display = X_AXIS_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                        elif section == "Generator Function" and label == "Z Axis":
                            from gui.display_map import Z_AXIS_OPTIONS
                            display_values = list(Z_AXIS_OPTIONS.values())
                            reverse_map = {v: k for k, v in Z_AXIS_OPTIONS.items()}
                            current_display = Z_AXIS_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                        elif section == "Generator Function" and label == "Spacing":
                            from gui.display_map import SPACING_OPTIONS
                            display_values = list(SPACING_OPTIONS.values())
                            reverse_map = {v: k for k, v in SPACING_OPTIONS.items()}
                            current_display = SPACING_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
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
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = (entry, combo)
                        elif section == "Generator Function" and label == "Voltage":
                            # Same as Max Voltage: value + unit
                            import re
                            unit_options = ["V", "mV", "μV", "dBV", "dBu", "dBm", "dBr"]
                            val_str = str(value)
                            match = re.match(r"^([\-\d\.]+)\s*([a-zA-Zμ]+)?$", val_str)
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
                            combo.bind("<MouseWheel>", lambda e: "break")
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
                            combo.bind("<MouseWheel>", lambda e: "break")
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
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
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
                            reverse_map = {v: k for k, v in INSTRUMENT_ANALYZER_OPTIONS.items()}
                            current_display = INSTRUMENT_ANALYZER_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Config" and label == "Channel Analyzer":
                            from gui.display_map import CHANNEL_ANALYZER_OPTIONS
                            display_values = list(CHANNEL_ANALYZER_OPTIONS.values())
                            reverse_map = {v: k for k, v in CHANNEL_ANALYZER_OPTIONS.items()}
                            current_display = CHANNEL_ANALYZER_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
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
                            reverse_map = {v: k for k, v in BANDWIDTH_ANALYZER_OPTIONS.items()}
                            current_display = BANDWIDTH_ANALYZER_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Config" and label == "Pre Filter":
                            from gui.display_map import PRE_FILTER_OPTIONS
                            display_values = list(PRE_FILTER_OPTIONS.values())
                            reverse_map = {v: k for k, v in PRE_FILTER_OPTIONS.items()}
                            current_display = PRE_FILTER_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Config" and label == "CH1 Input":
                            from gui.display_map import CH1_INPUT_OPTIONS
                            display_values = list(CH1_INPUT_OPTIONS.values())
                            reverse_map = {v: k for k, v in CH1_INPUT_OPTIONS.items()}
                            current_display = CH1_INPUT_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Config" and label == "CH1 Impedance":
                            from gui.display_map import CH1_IMPEDANCE_OPTIONS
                            display_values = list(CH1_IMPEDANCE_OPTIONS.values())
                            reverse_map = {v: k for k, v in CH1_IMPEDANCE_OPTIONS.items()}
                            current_display = CH1_IMPEDANCE_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
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
                            reverse_map = {v: k for k, v in CH1_RANGE_OPTIONS.items()}
                            current_display = CH1_RANGE_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
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
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = (entry, combo)
                        elif section == "Analyzer Config" and label == "Start Cond":
                            from gui.display_map import START_COND_OPTIONS
                            display_values = list(START_COND_OPTIONS.values())
                            reverse_map = {v: k for k, v in START_COND_OPTIONS.items()}
                            current_display = START_COND_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
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
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = (entry, combo)
                        elif section == "Analyzer Config" and label == "MAX FFT Size":
                            from gui.display_map import MAX_FFT_SIZE_OPTIONS
                            display_values = list(MAX_FFT_SIZE_OPTIONS.values())
                            reverse_map = {v: k for k, v in MAX_FFT_SIZE_OPTIONS.items()}
                            current_display = MAX_FFT_SIZE_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Function" and label == "Function Analyzer":
                            from gui.display_map import FUNCTION_ANALYZER_OPTIONS
                            display_values = list(FUNCTION_ANALYZER_OPTIONS.values())
                            reverse_map = {v: k for k, v in FUNCTION_ANALYZER_OPTIONS.items()}
                            current_display = FUNCTION_ANALYZER_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=24, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Function" and label == "S/N Sequence":
                            import tkinter as tk
                            var = tk.BooleanVar()
                            var.set(str(value).upper() == "ON")
                            chk = tk.Checkbutton(frame, variable=var)
                            chk.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = var
                        elif section == "Analyzer Function" and label == "Meas Time":
                            from gui.display_map import MEAS_TIME_OPTIONS
                            display_values = list(MEAS_TIME_OPTIONS.values())
                            reverse_map = {v: k for k, v in MEAS_TIME_OPTIONS.items()}
                            current_display = MEAS_TIME_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Function" and label == "Notch(Gain)":
                            from gui.display_map import NOTCH_OPTIONS
                            display_values = list(NOTCH_OPTIONS.values())
                            reverse_map = {v: k for k, v in NOTCH_OPTIONS.items()}
                            current_display = NOTCH_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Function" and label == "Filter1":
                            from gui.display_map import FILTER1_OPTIONS
                            display_values = list(FILTER1_OPTIONS.values())
                            reverse_map = {v: k for k, v in FILTER1_OPTIONS.items()}
                            current_display = FILTER1_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Function" and label == "Filter2":
                            from gui.display_map import FILTER2_OPTIONS
                            display_values = list(FILTER2_OPTIONS.values())
                            reverse_map = {v: k for k, v in FILTER2_OPTIONS.items()}
                            current_display = FILTER2_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Function" and label == "Filter3":
                            from gui.display_map import FILTER3_OPTIONS
                            display_values = list(FILTER3_OPTIONS.values())
                            reverse_map = {v: k for k, v in FILTER3_OPTIONS.items()}
                            current_display = FILTER3_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Function" and label == "Fnct Settling":
                            from gui.display_map import FNCT_SETTLING_OPTIONS
                            display_values = list(FNCT_SETTLING_OPTIONS.values())
                            reverse_map = {v: k for k, v in FNCT_SETTLING_OPTIONS.items()}
                            current_display = FNCT_SETTLING_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
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
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = (entry, combo)
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
                            combo.bind("<MouseWheel>", lambda e: "break")
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
                            combo.bind("<MouseWheel>", lambda e: "break")
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
                            reverse_map = {v: k for k, v in LEVEL_MONITOR_OPTIONS.items()}
                            current_display = LEVEL_MONITOR_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Function" and label == "Second Monitor":
                            from gui.display_map import SECOND_MONITOR_OPTIONS
                            display_values = list(SECOND_MONITOR_OPTIONS.values())
                            reverse_map = {v: k for k, v in SECOND_MONITOR_OPTIONS.items()}
                            current_display = SECOND_MONITOR_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Function" and label == "Input Monitor":
                            from gui.display_map import INPUT_MONITOR_OPTIONS
                            display_values = list(INPUT_MONITOR_OPTIONS.values())
                            reverse_map = {v: k for k, v in INPUT_MONITOR_OPTIONS.items()}
                            current_display = INPUT_MONITOR_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
                        elif section == "Analyzer Function" and label == "Freq/Phase":
                            from gui.display_map import FREQ_OPTIONS
                            display_values = list(FREQ_OPTIONS.values())
                            reverse_map = {v: k for k, v in FREQ_OPTIONS.items()}
                            current_display = FREQ_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[(section, label)] = combo
                            self.bind_combobox_mousewheel(combo)
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
                            combo.bind("<MouseWheel>", lambda e: "break")
                            self.entries[("Generator Config", "Impedance")] = combo

                    # Initial setup for Impedance widget
                    if self.output_type_combo:
                        selected_output_type = self.output_type_combo.get()
                        set_impedance_widget(selected_output_type, selected_code=impedance_value)

                        # Bind event to Output Type combobox to update Impedance field
                        def on_output_type_change(event):
                            selected_display = self.output_type_combo.get()
                            set_impedance_widget(selected_display)
                        self.output_type_combo.bind("<<ComboboxSelected>>", on_output_type_change)

        except Exception as e:
            messagebox.showerror("Settings Error", f"Could not load settings.json: {e}")

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
                upv.timeout = 5000
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
                    settings[section][label] = f"{val} {unit_ascii}" if val else ""
                elif section == "Generator Config" and label == "Ref Voltage":
                    entry, combo = widget
                    val = entry.get().strip()
                    unit = combo.get().strip()
                    if unit == "μV":
                        unit_ascii = "uV"
                    else:
                        unit_ascii = unit
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

    def fetch_data(self):
        if self.upv:
            export_path = filedialog.asksaveasfilename(defaultextension=".hxml",
                                                       filetypes=[("HXML files", "*.hxml"), ("All files", "*.*")])
            if export_path:
                fetch_and_plot_trace(self.upv, export_path)
        else:
            messagebox.showwarning("Warning", "Not connected to UPV.")

    def start_sweep(self):
        if self.upv is None:
            messagebox.showerror("Sweep Error", "UPV is not connected.")
            return

        def status_callback(msg):
            self.update_status(msg)

        try:
            self.upv.timeout = 30000  # Increase timeout to 30 seconds
            status_callback("⚙️ Preparing for single sweep...")
            self.upv.write("OUTP ON")
            self.upv.write("INIT:CONT OFF")

            status_callback("▶️ Starting single sweep...")
            self.upv.write("INIT")

            status_callback("⏳ Waiting for sweep to complete test...")
            self.upv.timeout = 20000
            self.upv.query("*OPC?")
            status_callback("✔️ Sweep completed successfully.")
            messagebox.showinfo("Sweep", "Single sweep started and completed!")
            self.fetch_data()
        except Exception as e:
            status_callback(f"❌ Failed to start sweep: {e}")
            messagebox.showerror("Sweep Error", f"Failed to start sweep: {e}")

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
        # Temporarily suspend panel scrolling when hovering over combobox to prevent panel jump
        def on_enter(event):
            self._suspend_global_scroll = True
        def on_leave(event):
            self._suspend_global_scroll = False
        combo.bind("<Enter>", on_enter)
        combo.bind("<Leave>", on_leave)

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

        # Read current settings from settings.json
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            current_settings = json.load(f)

        # Save to the chosen preset file
        with open(preset_path, "w", encoding="utf-8") as f:
            json.dump(current_settings, f, indent=2, ensure_ascii=False)

        messagebox.showinfo("Preset Saved", f"Preset saved to {preset_path}")
    
    def load_preset(self):
        import json
        from tkinter import filedialog, messagebox

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
            messagebox.showinfo("Preset Loaded", f"Preset loaded from {preset_path}")
        except Exception as e:
            messagebox.showerror("Load Error", f"Could not load preset: {e}")

    def update_status(self, msg, color="green"):
        self.status_label.config(text=msg, fg=color)
        self.status_label.update_idletasks()