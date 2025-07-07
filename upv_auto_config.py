import pyvisa
import json
import time
from pathlib import Path

CONFIG_FILE = "config.json"
SETTINGS_FILE = "settings.json"
SET_FILE_NAME = "C:\\Documents and Settings\\instrument\\Desktop\\COP_Sensitivity.set"
SET_FILE_PATH_ON_UPV = f"{SET_FILE_NAME}"

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
    if not Path(config_file).exists():
        print(f"⚠️ Settings file '{config_file}' not found.")
        return

    with open(config_file, "r") as f:
        data = json.load(f)

    command_groups = {
        "Generator Config": {
            "Instrument Generator"     : "INST1",
            "Channel Generator"        : "OUTP:CHAN",
            "Output Type (Unbal/Bal)"  : "OUTP:TYPE",
            "Impedance"                : "OUTP:IMP:UNB?",
            "Common (Float/Ground)"    : "OUTP:LOW",
            "Bandwidth Generator"      : "OUTP:BAND:MODE",
            "Volt Range (Auto/Fix)"    : "SOUR:VOLT:RANG",
            "Max Voltage"              : "SOUR:VOLT:MAX",
            "Ref Voltage"              : "SOUR:VOLT:REF",
            "Ref Frequency"            : "SOUR:FREQ:REF",
        },
        "Generator Function": {
            "Function Generator"       : "SOUR:FUNC",
            "Low Dist"                 : "SOUR:LOWD",
            "Sweep Ctrl"               : "SOUR:SWE:CONT",
            "Next Step"                : "SOUR:SWE:NEXT",
            "X Axis"                   : "SOUR:SWE:XAX",
            "Z Axis"                   : "SOUR:SWE:ZAX",
            "Frequency"                : "SOUR:SWE:FREQ:SPAC",
            "Start"                    : "SOUR:SWE:FREQ:STAR",
            "Stop"                     : "SOUR:SWE:FREQ:STOP",
            "Points"                   : "SOUR:SWE:FREQ:POIN",
            "Halt"                     : "SOUR:SWE:FREQ:HALT",
            "Voltage"                  : "SOUR:VOLT",
            "Filter"                   : "SOUR:FILT",
            "Equalizer"                : "SOUR:VOLT:",
            "DC Offset"                : "SOUR:VOLT:OFFS:STAT",
        },
        "Analyzer Config": {
            "Instrument Analyzer"      : "INST2",
            "Channel Analyzer"         : "INP1:CHAN",
            "CH1 Coupling"             : "INP1:COUP",
            "Bandwidth Analyzer"       : "INP1:BAND:MODE",
            "Pre Filter"               : "INP1:FILT",
            "CH1 Input"                : "INP1:TYPE",
            "CH1 Impedance"            : "INP1:IMP",
            "CH1 Ground/Common"        : "INP1:COMM",
            "CH1 Range"                : "SENS:VOLT:RANG1:MODE",
            "Ref Imped"                : "SENS1:POW:REF:RES",
            "Start Cond"               : "TRIG:SOUR",
            "Delay"                    : "TRIG:DEL",
            "Play bef.Meas"            : "TRIG:PLAY",
            "MAX FFT Size"             : "SENS1:MAX:FFT:SIZE",
        },
        "Analyzer Function": {
            "Function Analyzer"        : "SENS:FUNC",
            "S/N Sequence"             : "SENS1:FUNC:SNS",
            "Meas Time"                : "SENS1:FUNC:APER:MODE",
            "Notch(Gain)"              : "SENS1:NOTCh",
            "Filter1"                  : "SENS1:FILT1",
            "Filter2"                  : "SENS1:FILT2",
            "Filter3"                  : "SENS1:FILT3",
            "Fnct Setting"             : "SENS1:FUNC:SETT:MODE",
            "Samples"                  : "SENS1:FUNC:SETT:COUN",
            "Tolerance"                : "SENS1:FUNC:SETT:TOL",
            "Resolution"               : "SENS1:FUNC:SETT:RES",
            "Timeout"                  : "SENS1:FUNC:SETT:TOUT",
            "Bargraph"                 : "SENS1:FUNC:BARG",
            "POST FFT"                 : "SENS1:FUNC:FFT:STAT",
            "Level Monitor"            : "SENSE6:FUNC",
            "2nd Monitor"              : "SENSE2:FUNC:SNDM",
            "Input Monitor"            : "SENSE2:FUNCtion",
            "Freq/Phase"               : "SENSE3:FUNCtion",
            "Waveform"                 : "SENSE7:FUNCtion",
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

def main():
    rm = pyvisa.ResourceManager()
    visa_address = load_config()
    upv = None

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

    print(f"\n📂 Loading setup file from UPV: {SET_FILE_PATH_ON_UPV}")
    upv.write(f'SYST:SET:LOAD "{SET_FILE_PATH_ON_UPV}"')

    print("▶️ Starting measurement (INIT:CONT OFF)")
    upv.write("INIT:CONT OFF")
    upv.write("INIT")

    apply_grouped_settings(upv)

if __name__ == "__main__":
    main()
