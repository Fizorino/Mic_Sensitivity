import pyvisa
import json
import time
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox
import datetime

CONFIG_FILE = "config.json"
SETTINGS_FILE = "settings.json"

# SCPI command groups for each section
command_groups = {
    "Generator Config": {
        "Instrument Generator"      : "INST1",
        "Channel Generator"         : "OUTP:CHAN",
        "Output Type (Unbal/Bal)"   : "OUTP:TYPE",
        "Impedance"                 : "OUTP:IMP",
        "Common (Float/Ground)"     : "OUTP:LOW",
        "Bandwidth Generator"       : "OUTP:BAND:MODE",
        "Volt Range (Auto/Fix)"     : "SOUR:VOLT:RANG",
        "Max Voltage"               : "SOUR:VOLT:MAX",
        "Ref Voltage"               : "SOUR:VOLT:REF",
        "Ref Frequency"             : "SOUR:FREQ:REF",
    },
    "Generator Function": {
        "Function Generator"        : "SOUR:FUNC",
        "Low Dist"                  : "SOUR:LOWD",
        "Sweep Ctrl"                : "SOUR:SWE:CONT",
        "Frequency"                 : "SOUR:FREQ",
        "Next Step"                 : "SOUR:SWE:NEXT",
        "X Axis"                    : "SOUR:SWE:XAX",
        "Z Axis"                    : "SOUR:SWE:ZAX",
        "Spacing"                   : "SOUR:SWE:FREQ:SPAC",
        "Start"                     : "SOUR:SWE:FREQ:STAR",
        "Stop"                      : "SOUR:SWE:FREQ:STOP",
        "Points"                    : "SOUR:SWE:FREQ:POIN",
        "Halt"                      : "SOUR:SWE:FREQ:HALT",
        "Voltage"                   : "SOUR:VOLT",
        "Filter"                    : "SOUR:FILT",
        "Equalizer"                 : "SOUR:VOLT:EQU",
        "DC Offset"                 : "SOUR:VOLT:OFFS:STAT",
    },
    "Analyzer Config": {
        "Instrument Analyzer"       : "INST2",
        "Channel Analyzer"          : "INP1:CHAN",
        "CH1 Coupling"              : "INP1:COUP",
        "Bandwidth Analyzer"        : "INP1:BAND:MODE",
        "Pre Filter"                : "INP1:FILT",
        "CH1 Input"                 : "INP1:TYPE",
        "CH1 Impedance"             : "INP1:IMP",
        "CH1 Ground/Common"         : "INP1:COMM",
        "CH1 Range"                 : "SENS:VOLT:RANG1:MODE",
        "Ref Imped"                 : "SENS1:POW:REF:RES",
        "Start Cond"                : "TRIG:SOUR",
        "Delay"                     : "TRIG:DEL",
        "MAX FFT Size"              : "SENS1:MAX:FFT:SIZE",
    },
    "Analyzer Function": {
        "Function Analyzer"         : "SENS1:FUNC",
        "S/N Sequence"              : "SENS1:FUNC:SNS",
        "Meas Time"                 : "SENS1:FUNC:APER:MODE",
        "Bandwidth Analyzer Config" : "SENS1:BAND:MODE",
        "Sweep Ctrl Analyzer Config" : "SENS1:SWE:CONT",
        "Freq Mode"                 : "SENS1:FREQ:SEL",
        "Factor"                    : "SENS1:FREQ:FACT",
        "Notch(Gain)"               : "SENS1:NOTC",
        "Filter1"                   : "SENS1:FILT1",
        "Filter2"                   : "SENS1:FILT2",
        "Filter3"                   : "SENS1:FILT3",
        "Fnct Settling"             : "SENS1:FUNC:SETT:MODE",
        "Samples"                   : "SENS1:FUNC:SETT:COUN",
        "Tolerance"                 : "SENS1:FUNC:SETT:TOL",
        "Resolution"                : "SENS1:FUNC:SETT:RES",
        "Timeout"                   : "SENS1:FUNC:SETT:TOUT",
        "Bargraph"                  : "SENS1:FUNC:BARG",
        "POST FFT"                  : "SENS1:FUNC:FFT:STAT",
        "Level Monitor"             : "SENSE6:FUNC",
        "Second Monitor"            : "SENSE2:FUNC:SNDM",
        "Input Monitor"             : "SENSE2:FUNCtion",
        "Freq/Phase"                : "SENSE3:FUNCtion",
        "Waveform"                  : "SENSE7:FUNCtion",
    }
}

# --- Utility Functions ---

def find_upv_ip(status_callback=None):
    """Scan VISA resources for UPV via LAN or USB and return its address."""
    def log(msg):
        if status_callback:
            status_callback(msg)
        else:
            print(msg)
    rm = pyvisa.ResourceManager()
    log("🔍 Scanning VISA resources for UPV (LAN/USB)...")
    found = []
    for res in rm.list_resources():
        try:
            inst = rm.open_resource(res)
            idn = inst.query("*IDN?").strip()
            if "UPV" in idn:
                if "TCPIP" in res:
                    log(f"✅ Found UPV via LAN: {idn} ({res})")
                elif "USB" in res:
                    log(f"✅ Found UPV via USB: {idn} ({res})")
                else:
                    log(f"✅ Found UPV: {idn} ({res})")
                found.append(res)
        except Exception:
            pass
    if found:
        save_config(found[0])
        return found[0]
    log("❌ UPV not found on LAN or USB.")
    return None

def save_config(visa_address):
    """Save the VISA address to config file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump({"visa_address": visa_address}, f)

def load_config():
    """Load the VISA address from config file."""
    if Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f).get("visa_address")
    return None

def get_save_path_from_dialog():
    """Show a file dialog to get the export path for .hxml file."""
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.asksaveasfilename(
        title="Save .hxml File As",
        defaultextension=".hxml",
        filetypes=[("HXML files", "*.hxml"), ("All files", "*.*")],
        initialfile=""
    )
    return file_path

def apply_grouped_settings(upv, data=None, config_file=SETTINGS_FILE, status_callback=None):
    """Apply grouped settings from JSON to the UPV instrument."""
    def log(msg):
        if status_callback:
            status_callback(msg)
        else:
            print(msg)
    if data is None:
        if not Path(config_file).exists():
            log(f"⚠️ Settings file '{config_file}' not found.")
            return
        with open(config_file, "r") as f:
            data = json.load(f)

    for section, settings_map in command_groups.items():
        if section in data:
            log(f"\n➡️ Applying {section}")
            settings = data[section]
            for label, value in settings.items():
                scpi = settings_map.get(label)
                if scpi:
                    try:
                        upv.write(f"{scpi} {value}")
                        log(f"   ✓ {label}: {value}")
                    except Exception as e:
                        log(f"   ❌ Failed to apply {label}: {e}")
                else:
                    log(f"   ⚠️ Unknown setting label: {label}")
        else:
            log(f"⚠️ Section '{section}' not found in settings.")

    # --- Raw / Ungrouped SCPI keys ---
    # Some presets may include additional top-level SCPI commands (e.g., "SENS:UNIT", "DISP:SWE1:A:UNIT:TRAC", "INIT:CONT").
    # These are not part of the GUI's grouped sections but the user expects them to be applied automatically.
    # Send any top-level key that:
    #   * is not one of the defined section names
    #   * has a non-dict value
    #   * contains at least one colon (heuristic for SCPI command)
    # Skip keys we intentionally interpret elsewhere (e.g., INIT:CONT used later to decide sweep mode).
    RAW_EXCLUDE = {"INIT:CONT", "SweepMode", "ContinuousSweep"}  # handled in runtime logic
    try:
        for key, value in data.items():
            if key in command_groups:  # section dicts already processed
                continue
            if isinstance(value, dict):  # only leaf values
                continue
            if key in RAW_EXCLUDE:
                continue
            if ':' in key:
                try:
                    upv.write(f"{key} {value}")
                    log(f"   ✓ (raw) {key}: {value}")
                except Exception as e:
                    log(f"   ❌ (raw) Failed {key}: {e}")
    except Exception as e:
        log(f"⚠️ Raw SCPI application phase encountered an error: {e}")

def fetch_and_plot_trace(upv, export_path="sweep_trace.hxml", working_title=None):
    """Fetch sweep trace data from UPV, save as .hxml, and plot.

    Parameters:
        upv: VISA instrument handle
        export_path (str|Path): destination .hxml path (user-chosen file name)
        working_title (str|None): preset file stem to use for dataset WorkingTitle. If None, falls back to export file stem.

    Behavior change:
        - WorkingTitle attribute: based on preset (working_title param) if provided
        - CurveDataName attribute: always based on the user-typed export file name stem
    """
    try:
        print("📊 Fetching Sweep trace data directly from UPV...")

        x_raw = upv.query("TRAC:SWE1:LOAD:AX?")
        y_raw = upv.query("TRAC:SWE1:LOAD:AY?")
        x_vals = np.fromstring(x_raw, sep=',')
        y_vals = np.fromstring(y_raw, sep=',')

        if len(x_vals) != len(y_vals) or len(x_vals) == 0:
            raise ValueError("Empty or mismatched sweep data.")

        now = datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")

        # Derive dynamic dataset WorkingTitle (preset focused):
        # Priority: explicit working_title (preset stem) > export file stem > default fallback
        if isinstance(working_title, str) and working_title.strip():
            working_title_raw = working_title.strip()
        else:
            try:
                working_title_raw = Path(export_path).stem if export_path else "Mic Sensitivity"
                if not working_title_raw:
                    working_title_raw = "Mic Sensitivity"
            except Exception:
                working_title_raw = "Mic Sensitivity"

        # Simple XML escape for attribute context
        def _xml_escape(s: str) -> str:
            return (s.replace('&', '&amp;')
                     .replace('"', '&quot;')
                     .replace("'", '&apos;')
                     .replace('<', '&lt;')
                     .replace('>', '&gt;'))

        working_title_xml = _xml_escape(working_title_raw)

        # CurveDataName must always reflect exactly the user-chosen export file name (file name with extension)
        try:
            curve_data_name_raw = Path(export_path).name if export_path else "sweep_trace.hxml"
            if not curve_data_name_raw:
                curve_data_name_raw = "sweep_trace.hxml"
        except Exception:
            curve_data_name_raw = "sweep_trace.hxml"
        curve_data_name_xml = _xml_escape(curve_data_name_raw)

        # Determine Y-axis / magnitude units from current settings.
        # Priority:
        #   1. SENS:USER (user-defined textual unit) -> sanitized (strip quotes)
        #   2. SENS:UNIT (standard unit selection)
        #   3. SENS1:UNIT (legacy / alternative key)
        # Fallback: dBV
        try:
            y_unit_display = 'dBV'
            if Path(SETTINGS_FILE).exists():
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as sf:
                    settings_data = json.load(sf)
                user_unit_raw = settings_data.get('SENS:USER')
                std_unit_raw = settings_data.get('SENS:UNIT') or settings_data.get('SENS1:UNIT')

                def _sanitize_user_unit(s: str) -> str:
                    if not isinstance(s, str):
                        return ''
                    # Strip surrounding quotes (single or double)
                    s2 = s.strip().strip('"').strip('\'')
                    # Common normalization: 'db spl' -> 'dB SPL'
                    low = s2.lower()
                    if low.startswith('db'):
                        # split after 'db'
                        rest = s2[2:].lstrip()
                        # Uppercase SPL token if present
                        tokens = rest.split()
                        tokens = [t.upper() if t.lower() == 'spl' else t for t in tokens]
                        if tokens:
                            return 'dB ' + ' '.join(tokens)
                        return 'dB'
                    return s2

                if isinstance(user_unit_raw, str) and user_unit_raw.strip():
                    candidate = _sanitize_user_unit(user_unit_raw)
                    if candidate:
                        y_unit_display = candidate
                    else:
                        # fall back to std unit if user unit empty after sanitize
                        if isinstance(std_unit_raw, str):
                            yu = std_unit_raw.strip().upper()
                            unit_map = {
                                'DBR': 'dBr',
                                'DBV': 'dBV',
                                'DBU': 'dBu',
                                'DBM': 'dBm',
                                'V': 'V',
                                'MV': 'mV',
                                'UV': 'μV',
                                'UVR': 'μV',
                                'UV RMS': 'μV',
                                'UVRMS': 'μV',
                                'PCT': '%',
                                '%': '%'
                            }
                            y_unit_display = unit_map.get(yu, std_unit_raw.strip())
                elif isinstance(std_unit_raw, str):
                    yu = std_unit_raw.strip().upper()
                    unit_map = {
                        'DBR': 'dBr',
                        'DBV': 'dBV',
                        'DBU': 'dBu',
                        'DBM': 'dBm',
                        'V': 'V',
                        'MV': 'mV',
                        'UV': 'μV',
                        'UVR': 'μV',
                        'UV RMS': 'μV',
                        'UVRMS': 'μV',
                        'PCT': '%',
                        '%': '%'
                    }
                    y_unit_display = unit_map.get(yu, std_unit_raw.strip())
        except Exception:
            y_unit_display = 'dBV'

        # For HXML attribute, use the same token (without spaces)
        hxml_y_unit = y_unit_display.replace(' ', '')

        with open(export_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>\n')
            f.write("<hxml>\n")
            f.write("  <head>\n")
            f.write("    <Document>\n")
            f.write("      <DataVersion XsdVersion=\"0.0.0.1\">0.0.0.1</DataVersion>\n")
            f.write("      <DataType>hiCurve</DataType>\n")
            f.write("      <LDocNode>//hxml/data</LDocNode>\n")
            f.write("      <PlatformVersion>n.a.</PlatformVersion>\n")
            f.write("    </Document>\n")
            f.write("  </head>\n")
            f.write("  <data>\n")
            f.write(f"    <dataset WorkingTitle=\"{working_title_xml}\">\n")
            f.write("      <longDataSetDesc/>\n")
            f.write("      <shortDataSetDesc/>\n")
            f.write("      <acpEarhookType/>\n")
            f.write("      <v-curvedata>\n")
            # CurveDataName now strictly equals the saved file name (may differ from WorkingTitle/preset)
            f.write(f"        <curvedata CurveDataName=\"{curve_data_name_xml}\" MeasurementDate=\"{now}\"\n")
            f.write("                   TestEquipmentNr=\"UPV_Audio_Analyzer\"\n")
            f.write("                   Tester=\"PythonApp\">\n")
            f.write("          <longCurveDesc/>\n")
            f.write("          <shortCurveDesc/>\n")
            f.write("          <curve name=\"frequency\" unit=\"Hz\">[" + " ".join(f"{x:.6f}" for x in x_vals) + "]</curve>\n")
            f.write(f"          <curve name=\"magnitude\" unit=\"{hxml_y_unit}\">[" + " ".join(f"{y:.6f}" for y in y_vals) + "]</curve>\n")
            f.write("        </curvedata>\n")
            f.write("      </v-curvedata>\n")
            f.write("    </dataset>\n")
            f.write("  </data>\n")
            f.write("</hxml>\n")

        print(f"✅ File saved to '{export_path}'")

        # Plot (Logarithmic X-Axis)
        plt.figure(figsize=(10, 6))
        plt.semilogx(x_vals, y_vals)
        # Use the saved file's base name (without extension) as the plot title
        try:
            file_title = Path(export_path).stem if export_path else "Sweep Measurement Result"
            if not file_title:
                file_title = "Sweep Measurement Result"
        except Exception:
            file_title = "Sweep Measurement Result"
        plt.title(file_title)
        plt.xlabel("Frequency (Hz)")
        plt.ylabel(f"Level ({y_unit_display})")
        plt.grid(True, which="both", ls="--", linewidth=0.5)
        plt.tight_layout()
        plt.show()

    except Exception as e:
        print(f"❌ Failed to fetch or plot trace: {e}")

# --- Main Routine ---

def main():
    rm = pyvisa.ResourceManager()
    visa_address = load_config()
    upv = None

    # STEP 1: Connect to UPV
    if visa_address:
        for attempt in range(2):
            try:
                print(f"🔌 Trying saved UPV address: {visa_address}")
                upv = rm.open_resource(visa_address)
                upv.timeout = 5000
                print("✅ Connected to:", upv.query("*IDN?").strip())
                break
            except Exception as e:
                print(f"⚠️ Attempt {attempt+1} failed: {e}")
                if attempt == 0:
                    print("🔁 Retrying in 1.5 seconds...")
                    time.sleep(1.5)
                else:
                    print("❌ Saved address failed. Searching for a new UPV (LAN/USB)...")
                    visa_address = None

    if not visa_address:
        visa_address = find_upv_ip()
        if not visa_address:
            print("❌ No UPV found. Please check LAN/USB connection and power.")
            return
        try:
            upv = rm.open_resource(visa_address)
            upv.timeout = 5000
            print("✅ Connected to new UPV:", upv.query("*IDN?").strip())
            save_config(visa_address)
        except Exception as e:
            print("❌ Failed to connect to newly found UPV:", e)
            return

    # STEP 2: Apply grouped settings
    apply_grouped_settings(upv)

    # STEP 3: Setup for single sweep
    print("\n⚙️ Preparing for single sweep...")
    upv.write("OUTP ON")
    upv.write("INIT:CONT OFF")

    # STEP 4: Start sweep
    print("▶️ Starting single sweep...")
    upv.write("INIT")

    # STEP 5: Wait for completion
    print("⏳ Waiting for sweep to complete test...")
    upv.timeout = 20000
    try:
        upv.query("*OPC?")
        print("✔️ Sweep completed successfully.")
    except Exception as e:
        print(f"❌ Failed while waiting for sweep: {e}")
        return

    # STEP 6: Save As dialog
    export_path = get_save_path_from_dialog()
    if not export_path:
        print("❌ Save cancelled. No file selected.")
        return

    # STEP 7: Fetch and plot
    fetch_and_plot_trace(upv, export_path)

if __name__ == "__main__":
    main()