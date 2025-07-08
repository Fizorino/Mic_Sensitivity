import pyvisa
import json
import time
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import filedialog
import datetime

CONFIG_FILE = "config.json"
SETTINGS_FILE = "settings.json"
# SET_FILE_NAME = "C:\\Documents and Settings\\instrument\\Desktop\\COP_Sensitivity.set"

#EXPORT_FILE = "sweep_trace.hxml"

def find_upv_ip():
    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()
    print("🔍 Scanning VISA resources for UPV...")

    for res in resources:
        try:
            inst = rm.open_resource(res)
            idn = inst.query("*IDN?").strip()
            if "UPV" in idn:
                print(f"✅ Found UPV: {idn}")
                save_config(res)
                return res
        except Exception:
            pass

    print("❌ UPV not found on the network.")
    return None

def save_config(visa_address):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"visa_address": visa_address}, f)

def load_config():
    if Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f).get("visa_address")
    return None

def get_save_path_from_dialog():
    root = tk.Tk()
    root.withdraw()  # Hide the empty main window
    file_path = filedialog.asksaveasfilename(
        title="Save .hxml File As",
        defaultextension=".hxml",
        filetypes=[("HXML files", "*.hxml"), ("All files", "*.*")],
        initialfile=""
    )
    return file_path


def apply_grouped_settings(upv, config_file=SETTINGS_FILE):
    if not Path(config_file).exists():
        print(f"⚠️ Settings file '{config_file}' not found.")
        return

    with open(config_file, "r") as f:
        data = json.load(f)

    command_groups = {
        "Generator Config": {
            "Instrument Generator"      : "INST1",
            "Channel Generator"         : "OUTP:CHAN",
            "Output Type (Unbal/Bal)"   : "OUTP:TYPE",
            "Impedance"                 : "OUTP:IMP:UNB?",
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
            "Next Step"                 : "SOUR:SWE:NEXT",
            "X Axis"                    : "SOUR:SWE:XAX",
            "Z Axis"                    : "SOUR:SWE:ZAX",
            "Frequency"                 : "SOUR:SWE:FREQ:SPAC",
            "Start"                     : "SOUR:SWE:FREQ:STAR",
            "Stop"                      : "SOUR:SWE:FREQ:STOP",
            "Points"                    : "SOUR:SWE:FREQ:POIN",
            "Halt"                      : "SOUR:SWE:FREQ:HALT",
            "Voltage"                   : "SOUR:VOLT",
            "Filter"                    : "SOUR:FILT",
            "Equalizer"                 : "SOUR:VOLT:",
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
            "Play bef.Meas"             : "TRIG:PLAY",
            "MAX FFT Size"              : "SENS1:MAX:FFT:SIZE",
        },
        "Analyzer Function": {
            "Function Analyzer"         : "SENS:FUNC",
            "S/N Sequence"              : "SENS1:FUNC:SNS",
            "Meas Time"                 : "SENS1:FUNC:APER:MODE",
            "Notch(Gain)"               : "SENS1:NOTCh",
            "Filter1"                   : "SENS1:FILT1",
            "Filter2"                   : "SENS1:FILT2",
            "Filter3"                   : "SENS1:FILT3",
            "Fnct Setting"              : "SENS1:FUNC:SETT:MODE",
            "Samples"                   : "SENS1:FUNC:SETT:COUN",
            "Tolerance"                 : "SENS1:FUNC:SETT:TOL",
            "Resolution"                : "SENS1:FUNC:SETT:RES",
            "Timeout"                   : "SENS1:FUNC:SETT:TOUT",
            "Bargraph"                  : "SENS1:FUNC:BARG",
            "POST FFT"                  : "SENS1:FUNC:FFT:STAT",
            "Level Monitor"             : "SENSE6:FUNC",
            "2nd Monitor"               : "SENSE2:FUNC:SNDM",
            "Input Monitor"             : "SENSE2:FUNCtion",
            "Freq/Phase"                : "SENSE3:FUNCtion",
            "Waveform"                  : "SENSE7:FUNCtion",
        }
    }

    for section, settings_map in command_groups.items():
        if section in data:
            print(f"\n➡️ Applying {section}")
            settings = data[section]
            for label, value in settings.items():
                scpi = settings_map.get(label)
                if scpi:
                    try:
                        upv.write(f"{scpi} {value}")
                        print(f"   ✓ {label}: {value}")
                    except Exception as e:
                        print(f"   ❌ Failed to apply {label}: {e}")
                else:
                    print(f"   ⚠️ Unknown setting label: {label}")
        else:
            print(f"⚠️ Section '{section}' not found in settings.")

def fetch_and_plot_trace(upv, export_path="sweep_trace.hxml"):
    try:
        print("📊 Fetching Sweep trace data directly from UPV...")

        x_raw = upv.query("TRAC:SWE1:LOAD:AX?")
        y_raw = upv.query("TRAC:SWE1:LOAD:AY?")
        x_vals = np.fromstring(x_raw, sep=',')
        y_vals = np.fromstring(y_raw, sep=',')

        if len(x_vals) != len(y_vals) or len(x_vals) == 0:
            raise ValueError("Empty or mismatched sweep data.")

        now = datetime.datetime.now().strftime("%d-%b-%Y %H:%M:%S")

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
            f.write("    <dataset WorkingTitle=\"Mic Sensitivity\">\n")
            f.write("      <longDataSetDesc/>\n")
            f.write("      <shortDataSetDesc/>\n")
            f.write("      <acpEarhookType/>\n")
            f.write("      <v-curvedata>\n")
            f.write(f"        <curvedata CurveDataName=\"Mic_Sensitivity\" MeasurementDate=\"{now}\"\n")
            f.write("                   TestEquipmentNr=\"UPV_Audio_Analyzer\"\n")
            f.write("                   Tester=\"PythonApp\">\n")
            f.write("          <longCurveDesc/>\n")
            f.write("          <shortCurveDesc/>\n")
            f.write("          <curve name=\"frequency\" unit=\"Hz\">[" + " ".join(f"{x:.6f}" for x in x_vals) + "]</curve>\n")
            f.write("          <curve name=\"magnitude\" unit=\"dBV\">[" + " ".join(f"{y:.6f}" for y in y_vals) + "]</curve>\n")
            f.write("        </curvedata>\n")
            f.write("      </v-curvedata>\n")
            f.write("    </dataset>\n")
            f.write("  </data>\n")
            f.write("</hxml>\n")

        print(f"✅ File saved to '{export_path}'")

        # Step 2: Plot
        plt.figure(figsize=(10, 6))
        plt.plot(x_vals, y_vals)
        plt.title("Sweep Measurement Result")
        plt.xlabel("Frequency (Hz)")
        plt.ylabel("Level (dBV)")
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    except Exception as e:
        print(f"❌ Failed to fetch or plot trace: {e}")

def check_upv_status(upv):
    print("\n🛠 Checking UPV status...")

    try:
        oper = int(upv.query("STAT:OPER:COND?"))
        ques = int(upv.query("STAT:QUES:COND?"))
        over = int(upv.query("STAT:QUES:OVER:COND?"))
        under = int(upv.query("STAT:QUES:UND:COND?"))

        print(f"📟 Operation Status: {oper}")
        print(f"⚠️ Questionable Status: {ques}")
        print(f"🚨 Overrange (Overload): {over}")
        print(f"📉 Underrange: {under}")

        if over != 0:
            print("❗ Overrange detected — generator likely overloaded. Try reducing output voltage.")
        elif under != 0:
            print("❗ Underrange detected — signal level may be too low.")
        elif ques != 0:
            print("⚠️ Other questionable condition detected. Inspect individual status bits.")
        else:
            print("✅ UPV reports normal status.")
    except Exception as e:
        print(f"❌ Failed to query UPV status: {e}")


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
                    print("❌ Saved address failed. Searching for a new UPV...")
                    visa_address = None

    if not visa_address:
        visa_address = find_upv_ip()
        if not visa_address:
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
    # print("🧹 Old sweep data cleared.")

    # STEP 4: Start sweep
    print("▶️ Starting single sweep...")
    upv.write("INIT")

    # STEP 5: Wait for completion
    print("⏳ Waiting for sweep to complete (using *OPC?)...")
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
    
    # STEP 7: Check status
    check_upv_status(upv)

    # STEP 7: Fetch and plot
    fetch_and_plot_trace(upv, export_path)


if __name__ == "__main__":
    main()