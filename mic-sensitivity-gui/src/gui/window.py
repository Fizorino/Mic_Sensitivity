import pyvisa
import json
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

        self.frame = Frame(self.master)
        self.frame.pack(pady=20)
        Label(self.frame, text="Mic Sensitivity Control", font=("Helvetica", 16)).pack(pady=10)
        Button(self.frame, text="Connect to UPV", command=self.connect_to_upv).pack(pady=5)
        Button(self.frame, text="Apply Settings", command=self.apply_settings).pack(pady=5)
        Button(self.frame, text="Start Sweep", command=self.start_sweep).pack(pady=5)
        self.status_label = Label(self.frame, text="", fg="green")
        self.status_label.pack(pady=10)

        # Centered container for settings tables
        self.center_frame = Frame(self.master)
        self.center_frame.pack(expand=True, fill="both")

        # Scrollable area
        canvas = Canvas(self.center_frame)
        scrollbar = Scrollbar(self.center_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.settings_frame = Frame(canvas)
        window_id = canvas.create_window((0, 0), window=self.settings_frame, anchor="n")

        def center_table(event):
            canvas_width = event.width
            canvas.coords(window_id, canvas_width // 2, 0)
        canvas.bind("<Configure>", center_table)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.settings_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        self.entries = {}
        self.load_settings()
        self.upv = None

    def load_settings(self):
        for widget in self.settings_frame.winfo_children():
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

            self.settings_frame.grid_columnconfigure(0, weight=1, uniform="col")
            self.settings_frame.grid_columnconfigure(1, weight=1, uniform="col")
            self.settings_frame.grid_rowconfigure(0, weight=1, uniform="row")
            self.settings_frame.grid_rowconfigure(1, weight=1, uniform="row")

            frames = {}
            for section, row, col in sections:
                frame = Frame(self.settings_frame, bd=2, relief="groove", padx=16, pady=12)
                frame.grid(row=row, column=col, sticky="nsew", padx=32, pady=24)
                frames[section] = frame

            for section, row, col in sections:
                frame = frames[section]
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
                            self.entries[("Generator Config", label)] = combo
                        elif section == "Generator Config" and label == "Channel Generator":
                            display_values = list(CHANNEL_GENERATOR_OPTIONS.values())
                            current_display = CHANNEL_GENERATOR_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[("Generator Config", label)] = combo
                        elif section == "Generator Config" and label == "Output Type (Unbal/Bal)":
                            display_values = list(OUTPUT_TYPE_OPTIONS.values())
                            current_display = OUTPUT_TYPE_OPTIONS.get(value, value)
                            self.output_type_combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            self.output_type_combo.set(current_display)
                            self.output_type_combo.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[("Generator Config", label)] = self.output_type_combo
                            output_type_row = i
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
                            self.prevent_combobox_scroll(combo)
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
                            self.prevent_combobox_scroll(combo)
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
                            self.prevent_combobox_scroll(combo)
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
                            self.entries[(section, label)] = combo
                        elif section == "Generator Function" and label == "Sweep Ctrl":
                            from gui.display_map import SWEEP_CTRL_OPTIONS
                            display_values = list(SWEEP_CTRL_OPTIONS.values())
                            reverse_map = {v: k for k, v in SWEEP_CTRL_OPTIONS.items()}
                            current_display = SWEEP_CTRL_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = combo
                        elif section == "Generator Function" and label == "Next Step":
                            from gui.display_map import NEXT_STEP_OPTIONS
                            display_values = list(NEXT_STEP_OPTIONS.values())
                            reverse_map = {v: k for k, v in NEXT_STEP_OPTIONS.items()}
                            current_display = NEXT_STEP_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = combo
                        elif section == "Generator Function" and label == "X Axis":
                            from gui.display_map import X_AXIS_OPTIONS
                            display_values = list(X_AXIS_OPTIONS.values())
                            reverse_map = {v: k for k, v in X_AXIS_OPTIONS.items()}
                            current_display = X_AXIS_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = combo
                        elif section == "Generator Function" and label == "Z Axis":
                            from gui.display_map import Z_AXIS_OPTIONS
                            display_values = list(Z_AXIS_OPTIONS.values())
                            reverse_map = {v: k for k, v in Z_AXIS_OPTIONS.items()}
                            current_display = Z_AXIS_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = combo
                        elif section == "Generator Function" and label == "Spacing":
                            from gui.display_map import SPACING_OPTIONS
                            display_values = list(SPACING_OPTIONS.values())
                            reverse_map = {v: k for k, v in SPACING_OPTIONS.items()}
                            current_display = SPACING_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
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
                            self.prevent_combobox_scroll(combo)
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
                            self.prevent_combobox_scroll(combo)
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
                            combo = ttk.Combobox(frame, values=filter_values, width=18, state="readonly")
                            combo.set(display_val)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            
                            # Store both the combobox and the key list for saving
                            self.entries[(section, label)] = (combo, filter_keys, filter_values)
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
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=2)
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

            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=2)

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
        try:
            self.upv.timeout = 30000  # Increase timeout to 30 seconds
            self.upv.write("OUTP ON")
            self.upv.write("INIT:CONT OFF")
            self.upv.write("INIT")
            self.upv.query("*OPC?")
            messagebox.showinfo("Sweep", "Single sweep started and completed!")
            self.fetch_data()
        except Exception as e:
            messagebox.showerror("Sweep Error", f"Failed to start sweep: {e}")

    def prevent_combobox_scroll(self, combo):
        def stop_scroll(event):
            return "break"
        combo.bind("<MouseWheel>", stop_scroll)
        combo.bind("<Button-4>", stop_scroll)
        combo.bind("<Button-5>", stop_scroll)
