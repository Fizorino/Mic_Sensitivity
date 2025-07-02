import pyvisa
import json
from pathlib import Path

CONFIG_FILE = "config.json"
SETTINGS_FILE = "settings.json"
SET_FILE_PATH = "C:\Documents and Settings\instrument\Desktop\COP_Sensitivity.set"

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

def apply_grouped_settings(upv, config_file=SETTINGS_FILE):
    with open(config_file, "r") as f:
        data = json.load(f)

    command_map = {
        "Instrument"               : "SOUR:INP:SEL",
        "Channel"                  : "SOUR:CHAN",
        "Output Type (Unbal/Bal)"  : "OUTP:TYPE",
        "Impedance"                : "OUTP:IMP:UNB",
        "Bandwidth"                : "SOUR:BAND",
        "Generator Voltage Range"  : "SOUR:VOLT:RANG",

        "Waveform Function"        : "SOUR:FUNC:SHAP",
        "Frequency"                : "SOUR:FREQ",
        "Sweep Mode"               : "SOUR:SWE:STAT",
        "Sweep Type"               : "SOUR:SWE:TYPE",

        "Analyzer Instrument"      : "CALC:INP:SEL",
        "CH1 Coupling"             : "INP1:COUP",
        "CH1 Bandwidth"            : "INP1:BAND",
        "Pre Filter"               : "INP1:FILT",
        "CH1 Input Type"           : "INP1:TYPE",
        "CH1 Impedance"            : "INP1:IMP",
        "CH1 Ground/Common"        : "INP1:COMM",

        "Measurement Function"     : "CALC:FUNC:TYPE",
        "S/N Sequence"             : "CALC:SEQ",
        "Meas Time Mode"           : "CALC:TIME:MODE",
        "Notch Filter"             : "CALC:NOTC:STAT",
        "Filter"                   : "CALC:FILT:STAT",
        "Avg Type"                 : "CALC:AVER:TYPE",
        "Avg Count"                : "CALC:AVER:COUN"
    }

    for section, settings in data.items():
        print(f"\n➡️ Applying {section}")
        for label, value in settings.items():
            scpi = command_map.get(label)
            if scpi:
                try:
                    upv.write(f"{scpi} {value}")
                    print(f"   ✓ {label}: {value}")
                except Exception as e:
                    print(f"   ❌ Failed to apply {label}: {e}")
            else:
                print(f"   ⚠️ Unknown setting label: {label}")

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
        upv.timeout = 3000  # Timeout in milliseconds
        print("✅ Connected to:", upv.query("*IDN?").strip())

        # Load setup file if it exists
        if Path(SET_FILE_PATH).exists():
            safe_path = SET_FILE_PATH.replace("\\", "/")
            print(f"📂 Loading setup file: {SET_FILE_PATH}")
            upv.write(f"MMEM:LOAD:STAT '{safe_path}'")
        else:
            print("⚠️ SET file not found. Skipping setup load.")

        # Apply settings from JSON
        apply_grouped_settings(upv)

    except Exception as e:
        print("❌ Error communicating with UPV:", e)

if __name__ == "__main__":
    main()
