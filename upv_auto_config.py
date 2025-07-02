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
    print("\n📋 UPV Configuration:")

    grouped_commands = {
        "🔧 Generator Config": {
            "Generator Instrument"     : "SOUR:INP:SEL <type>",
            "Generator Channel"        : "SOUR:CHAN?",
            "Output Impedance"         : "OUTP:IMP:UNB?",
            "Output Type (Unbal/Bal)"  : "OUTP:TYPE",
            "Generator Bandwidth"      : "SOUR:BAND?",
            "Generator Voltage Range"  : "SOUR:VOLT:RANG?",
        },

        "🎵 Generator Function": {
            "Waveform Function"        : "SOUR:FUNC:SHAP?",
            "Frequency"                : "SOUR:FREQ?",
            "Sweep Mode"               : "SOUR:SWE:STAT?",
            "Sweep Type"               : "SOUR:SWE:TYPE?",
        },

        "🎧 Analyzer Config": {
            "Analyzer Instrument"      : "CALC:INP:SEL?",
            "CH1 Coupling"             : "INP1:COUP?",
            "CH1 Bandwidth"            : "INP1:BAND?",
            "Pre Filter"               : "INP1:FILT?",
            "CH1 Input Type"           : "INP1:TYPE?",
            "CH1 Impedance"            : "INP1:IMP?",
            "CH1 Ground/Common"        : "INP1:COMM?",
        },

        "📐 Analyzer Function": {
            "Measurement Function"     : "CALC:FUNC:TYPE?",
            "S/N Sequence"             : "CALC:SEQ?",
            "Meas Time Mode"           : "CALC:TIME:MODE?",
            "Notch Filter"             : "CALC:NOTC:STAT?",
            "Filter"                   : "CALC:FILT:STAT?",
            "Avg Type"                 : "CALC:AVER:TYPE?",
            "Avg Count"                : "CALC:AVER:COUN?",
        }
    }

    for section, cmds in grouped_commands.items():
        print(f"\n{section}")
        print("-" * len(section))
        for label, cmd in cmds.items():
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
