import pyvisa
import json
import time
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import filedialog
import datetime

CONFIG_FILE = "config.json"
SETTINGS_FILE = "settings.json"

# SCPI command groups for each section
command_groups = {fig": {
    "Generator Config": {ator"      : "INST1",
        "Instrument Generator": "INST1",AN",
        "Channel Generator": "OUTP:CHAN",
        "Output Type (Unbal/Bal)": "OUTP:TYPE",B?",
        "Impedance": "OUTP:IMP:UNB?",
        "Common (Float/Ground)": "OUTP:LOW",MODE",
        "Bandwidth Generator": "OUTP:BAND:MODE",
        "Volt Range (Auto/Fix)": "SOUR:VOLT:RANG",
        "Max Voltage": "SOUR:VOLT:MAX",
        "Ref Voltage": "SOUR:VOLT:REF",
        "Ref Frequency": "SOUR:FREQ:REF",
    },enerator Function": {
    "Generator Function": {"        : "SOUR:FUNC",
        "Function Generator": "SOUR:FUNC",
        "Low Dist": "SOUR:LOWD",NT",
        "Sweep Ctrl": "SOUR:SWE:CONT",
        "Next Step": "SOUR:SWE:NEXT",
        "X Axis": "SOUR:SWE:XAX",
        "Z Axis": "SOUR:SWE:ZAX",SPAC",
        "Frequency": "SOUR:SWE:FREQ:SPAC",
        "Start": "SOUR:SWE:FREQ:STAR",
        "Stop": "SOUR:SWE:FREQ:STOP",
        "Points": "SOUR:SWE:FREQ:POIN",
        "Halt": "SOUR:SWE:FREQ:HALT",
        "Voltage": "SOUR:VOLT",
        "Filter": "SOUR:FILT",QU",
        "Equalizer": "SOUR:VOLT:EQU",STAT",
        "DC Offset": "SOUR:VOLT:OFFS:STAT",
    },nalyzer Config": {
    "Analyzer Config": {yzer"       : "INST2",
        "Instrument Analyzer": "INST2",AN",
        "Channel Analyzer": "INP1:CHAN",
        "CH1 Coupling": "INP1:COUP",ODE",
        "Bandwidth Analyzer": "INP1:BAND:MODE",
        "Pre Filter": "INP1:FILT",
        "CH1 Input": "INP1:TYPE",
        "CH1 Impedance": "INP1:IMP",,
        "CH1 Ground/Common": "INP1:COMM",ANG1:MODE",
        "CH1 Range": "SENS:VOLT:RANG1:MODE",
        "Ref Imped": "SENS1:POW:REF:RES",
        "Start Cond": "TRIG:SOUR",
        "Delay": "TRIG:DEL",,
        "Play bef.Meas": "TRIG:PLAY",FT:SIZE",
        "MAX FFT Size": "SENS1:MAX:FFT:SIZE",
    },nalyzer Function": {
    "Analyzer Function": {"         : "SENS:FUNC",
        "Function Analyzer": "SENS:FUNC",SNS",
        "S/N Sequence": "SENS1:FUNC:SNS",MODE",
        "Meas Time": "SENS1:FUNC:APER:MODE",
        "Notch(Gain)": "SENS1:NOTCh",
        "Filter1": "SENS1:FILT1",
        "Filter2": "SENS1:FILT2",
        "Filter3": "SENS1:FILT3",TT:MODE",
        "Fnct Setting": "SENS1:FUNC:SETT:MODE",
        "Samples": "SENS1:FUNC:SETT:COUN",
        "Tolerance": "SENS1:FUNC:SETT:TOL",
        "Resolution": "SENS1:FUNC:SETT:RES",,
        "Timeout": "SENS1:FUNC:SETT:TOUT",
        "Bargraph": "SENS1:FUNC:BARG",AT",
        "POST FFT": "SENS1:FUNC:FFT:STAT",
        "Level Monitor": "SENSE6:FUNC",NDM",
        "2nd Monitor": "SENSE2:FUNC:SNDM",
        "Input Monitor": "SENSE2:FUNCtion",
        "Freq/Phase": "SENSE3:FUNCtion",
        "Waveform": "SENSE7:FUNCtion",
    }
}

# --- Utility Functions ---    rm = pyvisa.ResourceManager()
.list_resources()
def find_upv_ip():rces for UPV...")
    """Scan VISA resources for UPV and return its address."""
    rm = pyvisa.ResourceManager()
    print("🔍 Scanning VISA resources for UPV...")        try:
    for res in rm.list_resources():n_resource(res)
        try:idn = inst.query("*IDN?").strip()
            inst = rm.open_resource(res)
            idn = inst.query("*IDN?").strip()
            if "UPV" in idn:res)
                print(f"✅ Found UPV: {idn}")
                save_config(res)
                return res
        except Exception:
            pass not found on the network.")
    print("❌ UPV not found on the network.")    return None
    return None
(visa_address):
def save_config(visa_address):    with open(CONFIG_FILE, "w") as f:
    """Save the VISA address to config file."""ss": visa_address}, f)
    with open(CONFIG_FILE, "w") as f:
        json.dump({"visa_address": visa_address}, f)
    if Path(CONFIG_FILE).exists():
def load_config():CONFIG_FILE, "r") as f:
    """Load the VISA address from config file."""t("visa_address")
    if Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f).get("visa_address")th_from_dialog():
    return None    root = tk.Tk()
empty main window
def get_save_path_from_dialog():ledialog.asksaveasfilename(
    """Show a file dialog to get the export path for .hxml file."""
    root = tk.Tk()
    root.withdraw()*.hxml"), ("All files", "*.*")],
    file_path = filedialog.asksaveasfilename(
        title="Save .hxml File As",
        defaultextension=".hxml",
        filetypes=[("HXML files", "*.hxml"), ("All files", "*.*")],
        initialfile=""
    )def apply_grouped_settings(upv, config_file=SETTINGS_FILE):
    return file_path    if not Path(config_file).exists():
")
def apply_grouped_settings(upv, config_file=SETTINGS_FILE):
    """Apply grouped settings from JSON to the UPV instrument."""
    if not Path(config_file).exists():config_file, "r") as f:
        print(f"⚠️ Settings file '{config_file}' not found.")        data = json.load(f)
        return
ap in command_groups.items():
    with open(config_file, "r") as f:        if section in data:
        data = json.load(f)
[section]
    for section, settings_map in command_groups.items():s():
        if section in data:get(label)
            print(f"\n➡️ Applying {section}")
            settings = data[section]
            for label, value in settings.items():upv.write(f"{scpi} {value}")
                scpi = settings_map.get(label)print(f"   ✓ {label}: {value}")
                if scpi:
                    try:abel}: {e}")
                        upv.write(f"{scpi} {value}")
                        print(f"   ✓ {label}: {value}")
                    except Exception as e:
                        print(f"   ❌ Failed to apply {label}: {e}"))
                else:
                    print(f"   ⚠️ Unknown setting label: {label}")
        else:    try:
            print(f"⚠️ Section '{section}' not found in settings.")..")

def fetch_and_plot_trace(upv, export_path="sweep_trace.hxml"):
    """Fetch sweep trace data from UPV, save as .hxml, and plot."""        y_raw = upv.query("TRAC:SWE1:LOAD:AY?")
    try:
        print("📊 Fetching Sweep trace data directly from UPV...")

        x_raw = upv.query("TRAC:SWE1:LOAD:AX?")_vals) == 0:
        y_raw = upv.query("TRAC:SWE1:LOAD:AY?")            raise ValueError("Empty or mismatched sweep data.")
        x_vals = np.fromstring(x_raw, sep=',')
        y_vals = np.fromstring(y_raw, sep=',')%S")

        if len(x_vals) != len(y_vals) or len(x_vals) == 0:
            raise ValueError("Empty or mismatched sweep data.")            f.write('<?xml version="1.0" encoding="utf-8"?>\n')

        now = datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")
ent>\n")
        with open(export_path, "w", encoding="utf-8") as f:ersion XsdVersion=\"0.0.0.1\">0.0.0.1</DataVersion>\n")
            f.write('<?xml version="1.0" encoding="utf-8"?>\n')Curve</DataType>\n")
            f.write("<hxml>\n")
            f.write("  <head>\n")ersion>\n")
            f.write("    <Document>\n")
            f.write("      <DataVersion XsdVersion=\"0.0.0.1\">0.0.0.1</DataVersion>\n")
            f.write("      <DataType>hiCurve</DataType>\n")
            f.write("      <LDocNode>//hxml/data</LDocNode>\n")WorkingTitle=\"Mic Sensitivity\">\n")
            f.write("      <PlatformVersion>n.a.</PlatformVersion>\n")ataSetDesc/>\n")
            f.write("    </Document>\n")
            f.write("  </head>\n")
            f.write("  <data>\n")
            f.write("    <dataset WorkingTitle=\"Mic Sensitivity\">\n")taName=\"Mic_Sensitivity\" MeasurementDate=\"{now}\"\n")
            f.write("      <longDataSetDesc/>\n")EquipmentNr=\"UPV_Audio_Analyzer\"\n")
            f.write("      <shortDataSetDesc/>\n")
            f.write("      <acpEarhookType/>\n")
            f.write("      <v-curvedata>\n")
            f.write(f"        <curvedata CurveDataName=\"Mic_Sensitivity\" MeasurementDate=\"{now}\"\n")ncy\" unit=\"Hz\">[" + " ".join(f"{x:.6f}" for x in x_vals) + "]</curve>\n")
            f.write("                   TestEquipmentNr=\"UPV_Audio_Analyzer\"\n")de\" unit=\"dBV\">[" + " ".join(f"{y:.6f}" for y in y_vals) + "]</curve>\n")
            f.write("                   Tester=\"PythonApp\">\n")
            f.write("          <longCurveDesc/>\n")
            f.write("          <shortCurveDesc/>\n")
            f.write("          <curve name=\"frequency\" unit=\"Hz\">[" + " ".join(f"{x:.6f}" for x in x_vals) + "]</curve>\n")
            f.write("          <curve name=\"magnitude\" unit=\"dBV\">[" + " ".join(f"{y:.6f}" for y in y_vals) + "]</curve>\n")
            f.write("        </curvedata>\n")
            f.write("      </v-curvedata>\n")'{export_path}'")
            f.write("    </dataset>\n")
            f.write("  </data>\n")
            f.write("</hxml>\n")        plt.figure(figsize=(10, 6))
 Use semilogx for log-scaled frequency
        print(f"✅ File saved to '{export_path}'")t Result")

        # Plot (Logarithmic X-Axis)
        plt.figure(figsize=(10, 6)) ls="--", linewidth=0.5)
        plt.semilogx(x_vals, y_vals)
        plt.title("Sweep Measurement Result")
        plt.xlabel("Frequency (Hz)")
        plt.ylabel("Level (dBV)")
        plt.grid(True, which="both", ls="--", linewidth=0.5)    except Exception as e:
        plt.tight_layout()        print(f"❌ Failed to fetch or plot trace: {e}")
        plt.show()

    except Exception as e:    rm = pyvisa.ResourceManager()
        print(f"❌ Failed to fetch or plot trace: {e}")dress = load_config()

# --- Main Routine ---
Connect to UPV
def main():    if visa_address:
    rm = pyvisa.ResourceManager()(2):
    visa_address = load_config()
    upv = Noneg saved UPV address: {visa_address}")
upv = rm.open_resource(visa_address)
    # STEP 1: Connect to UPV
    if visa_address:*IDN?").strip())
        for attempt in range(2):
            try:
                print(f"🔌 Trying saved UPV address: {visa_address}")(f"⚠️ Attempt {attempt+1} failed: {e}")
                upv = rm.open_resource(visa_address)
                upv.timeout = 5000
                print("✅ Connected to:", upv.query("*IDN?").strip()).5)
                break
            except Exception as e:address failed. Searching for a new UPV...")
                print(f"⚠️ Attempt {attempt+1} failed: {e}")isa_address = None
                if attempt == 0:
                    print("🔁 Retrying in 1.5 seconds...")
                    time.sleep(1.5)        visa_address = find_upv_ip()
                else:ess:
                    print("❌ Saved address failed. Searching for a new UPV...")
                    visa_address = None
rm.open_resource(visa_address)
    if not visa_address:upv.timeout = 5000
        visa_address = find_upv_ip().query("*IDN?").strip())
        if not visa_address:ddress)
            return
        try:t to newly found UPV:", e)
            upv = rm.open_resource(visa_address)
            upv.timeout = 5000
            print("✅ Connected to new UPV:", upv.query("*IDN?").strip())y grouped settings
            save_config(visa_address)    apply_grouped_settings(upv)
        except Exception as e:
            print("❌ Failed to connect to newly found UPV:", e)sweep
            return    print("\n⚙️ Preparing for single sweep...")

    # STEP 2: Apply grouped settings
    apply_grouped_settings(upv)

    # STEP 3: Setup for single sweep    print("▶️ Starting single sweep...")
    print("\n⚙️ Preparing for single sweep...")
    upv.write("OUTP ON")
    upv.write("INIT:CONT OFF")r completion
    print("⏳ Waiting for sweep to complete test...")
    # STEP 4: Start sweep
    print("▶️ Starting single sweep...")
    upv.write("INIT")?")
print("✔️ Sweep completed successfully.")
    # STEP 5: Wait for completion
    print("⏳ Waiting for sweep to complete test...") {e}")
    upv.timeout = 20000
    try:
        upv.query("*OPC?")Save As dialog
        print("✔️ Sweep completed successfully.")    export_path = get_save_path_from_dialog()
    except Exception as e:
        print(f"❌ Failed while waiting for sweep: {e}")cted.")
        return

    # STEP 6: Save As dialogFetch and plot
    export_path = get_save_path_from_dialog()    fetch_and_plot_trace(upv, export_path)
    if not export_path:
        print("❌ Save cancelled. No file selected.")
        returnif __name__ == "__main__":
    main()    # STEP 7: Fetch and plot    fetch_and_plot_trace(upv, export_path)

if __name__ == "__main__":
    main()