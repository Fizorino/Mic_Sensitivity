import pyvisa
import json
from tkinter import Tk, Frame, Button, Label, Entry, filedialog, messagebox, Canvas, Scrollbar
from pathlib import Path
from upv.upv_auto_config import find_upv_ip, apply_grouped_settings, fetch_and_plot_trace, load_config, save_config, command_groups
from tkinter import ttk
from gui.display_map import INSTRUMENT_GENERATOR_OPTIONS, CHANNEL_GENERATOR_OPTIONS

SETTINGS_FILE = r"c:\Users\AU001A0W\OneDrive - WSA\Documents\Mic_Sensitivity\settings.json"

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

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.settings_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
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

            # Section order and layout
            sections = [
                ("Generator Config", 0, 0),
                ("Analyzer Config", 0, 1),
                ("Generator Function", 1, 0),
                ("Analyzer Function", 1, 1)
            ]

            # Configure grid for equal spacing
            self.settings_frame.grid_columnconfigure(0, weight=1, uniform="col")
            self.settings_frame.grid_columnconfigure(1, weight=1, uniform="col")
            self.settings_frame.grid_rowconfigure(0, weight=1, uniform="row")
            self.settings_frame.grid_rowconfigure(1, weight=1, uniform="row")

            frames = {}
            for section, row, col in sections:
                frame = Frame(self.settings_frame, bd=2, relief="groove", padx=16, pady=12)
                frame.grid(row=row, column=col, sticky="nsew", padx=32, pady=24)
                frames[section] = frame

            # Fill each section
            for section, row, col in sections:
                frame = frames[section]
                Label(frame, text=section, font=("Helvetica", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0,8))
                if section in settings:
                    for i, (label, value) in enumerate(settings[section].items(), start=1):
                        Label(frame, text=label, anchor="w", width=22).grid(row=i, column=0, sticky="w", padx=(0,8), pady=2)

                        # Dropdown for Instrument Generator
                        if section == "Generator Config" and label == "Instrument Generator":
                            display_values = list(INSTRUMENT_GENERATOR_OPTIONS.values())
                            current_display = INSTRUMENT_GENERATOR_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = combo

                        # Dropdown for Channel Generator
                        elif section == "Generator Config" and label == "Channel Generator":
                            display_values = list(CHANNEL_GENERATOR_OPTIONS.values())
                            current_display = CHANNEL_GENERATOR_OPTIONS.get(value, value)
                            combo = ttk.Combobox(frame, values=display_values, width=20, state="readonly")
                            combo.set(current_display)
                            combo.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = combo

                        # Regular Entry for other fields
                        else:
                            entry = Entry(frame, width=22)
                            entry.insert(0, str(value))
                            entry.grid(row=i, column=1, sticky="w", pady=2)
                            self.entries[(section, label)] = entry

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
        if visa_address:
            try:
                rm = pyvisa.ResourceManager()
                self.upv = rm.open_resource(visa_address)
                self.upv.timeout = 5000
                self.status_label.config(text=f"Connected to: {self.upv.query('*IDN?').strip()}")
            except Exception as e:
                messagebox.showerror("Connection Error", str(e))
                self.upv = None
        else:
            visa_address = find_upv_ip()
            if visa_address:
                try:
                    rm = pyvisa.ResourceManager()
                    self.upv = rm.open_resource(visa_address)
                    self.upv.timeout = 5000
                    save_config(visa_address)
                    self.status_label.config(text=f"Connected to: {self.upv.query('*IDN?').strip()}")
                except Exception as e:
                    messagebox.showerror("Connection Error", str(e))
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
                else:
                    settings[section][label] = widget.get()

            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f, indent=2)

        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save settings: {e}")
            return

        if self.upv:
            apply_grouped_settings(self.upv)
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
