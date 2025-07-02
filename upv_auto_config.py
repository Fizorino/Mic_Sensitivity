import pyvisa
import json
from pathlib import Path

CONFIG_FILE = "config.json"
SET_FILE_PATH = "C:/Documents and Settings/instrument/Desktop/COP_Sensitivity.set"

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

def display_upv_settings(upv):
    print("\n📋 UPV Configuration:\n")

    commands = {
        # --- Generator Config ---
        "Generator Instrument"     : "SOUR:INP:SEL?",         # Might return 'ANALOG'
        "Generator Channel"        : "SOUR:CHAN?",            # May not apply directly
        "Output Impedance"         : "OUTP:IMP?",             # e.g. 5 ohm
        "Output Type (Unbal/Bal)"  : "OUTP:COUP?",            # May need interpretation
        "Generator Bandwidth"      : "SOUR:BAND?",            # If supported
        "Generator Voltage Range"  : "SOUR:VOLT:RANG?",       # Or SENS:RANG?

        # --- Generator Function ---
        "Waveform Function"        : "SOUR:FUNC:SHAP?",       # e.g. SINE
        "Frequency"                : "SOUR:FREQ?",            # e.g. 1 kHz
        "Sweep Mode"               : "SOUR:SWE:STAT?",        # ON/OFF
        "Sweep Type"               : "SOUR:SWE:TYPE?",        # e.g. LIN

        # --- Analyzer Config ---
        "Analyzer Instrument"      : "CALC:INP:SEL?",         # e.g. ANALOG
        "CH1 Coupling"             : "INP1:COUP?",
        "CH1 Bandwidth"            : "INP1:BAND?",            # or LPAS?
        "Pre Filter"               : "INP1:FILT?",            # Try filter settings
        "CH1 Input Type"           : "INP1:TYPE?",            # e.g. BAL
        "CH1 Impedance"            : "INP1:IMP?",
        "CH1 Ground/Common"        : "INP1:COMM?",            # FLOAT/GND

        # --- Analyzer Function ---
        "Measurement Function"     : "CALC:FUNC:TYPE?",       # e.g. RMS
        "S/N Sequence"             : "CALC:SEQ?",             # If supported
        "Meas Time Mode"           : "CALC:TIME:MODE?",       # e.g. GEN or AUTO
        "Notch Filter"             : "CALC:NOTC:STAT?",       # ON/OFF
        "Filter"                   : "CALC:FILT:STAT?",       # ON/OFF
        "Avg Type"                 : "CALC:AVER:TYPE?",
        "Avg Count"                : "CALC:AVER:COUN?",
    }

    for label, cmd in commands.items():
        try:
            response = upv.query(cmd).strip()
        except Exception as e:
            response = f"Unavailable ({e})"
        print(f"{label:30}: {response}")


def main():
    rm = pyvisa.ResourceManager()
    
    # Try loading from config first
    visa_address = load_config()
    if visa_address:
        print(f"📁 Using saved VISA address: {visa_address}")
    else:
        visa_address = find_upv_ip()

    if not visa_address:
        return

    try:
        upv = rm.open_resource(visa_address)
        print("✅ Connected to:", upv.query("*IDN?").strip())

        # 🔽 Place it here
        print(f"📂 Loading setup file: {SET_FILE_PATH}")
        upv.write(f"MMEM:LOAD:STAT '{SET_FILE_PATH}'")

        # 🔽 Then display settings from that .SET config
        display_upv_settings(upv)

    except Exception as e:
        print("❌ Error communicating with UPV:", e)

if __name__ == "__main__":
    main()
