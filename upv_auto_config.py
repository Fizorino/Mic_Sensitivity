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
        "Input Range"        : "INP1:RANG?",
        "Measurement Type"   : "CALC:FUNC:TYPE?",
        "Input Coupling"     : "INP1:COUP?",
        "Trigger Source"     : "TRIG:SOUR?",
        "Mic Sensitivity"    : "SENS:MIC:SENS?",
        "Input Impedance"    : "INP1:IMP?",
        "Sampling Rate"      : "SENS:RATE?",
        "Averaging Count"    : "CALC:AVER:COUN?",
        "Frequency"          : "SOUR:FREQ?",
        "Level"              : "SOUR:LEV?"
    }

    for label, cmd in commands.items():
        try:
            response = upv.query(cmd).strip()
        except Exception as e:
            response = f"Unavailable ({e})"
        print(f"{label:20}: {response}")

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

        # Load the .SET file
        print(f"📂 Loading setup file: {SET_FILE_PATH}")
        upv.write(f"MMEM:LOAD:STAT '{SET_FILE_PATH}'")

        # Display config
        display_upv_settings(upv)

    except Exception as e:
        print("❌ Error communicating with UPV:", e)

if __name__ == "__main__":
    main()
