"""Display option maps used by the GUI.

De-duplicated and pruned for clarity:
 - Removed large commented legacy DISPLAY_MAP block.
 - Unified identical filter dictionaries (FILTER1/2/3) by aliasing to FILTER_OPTIONS.
 - Removed unused EQUALIZER_OPTIONS and DC_OFFSET_OPTIONS (not referenced in window.py).
"""

# Friendly display label overrides (UI label -> shorter label) while keeping internal JSON keys
DISPLAY_LABEL_OVERRIDES = {
    "Bandwidth Analyzer Config": "Bandwidth",
    "Sweep Ctrl Analyzer Config": "Sweep Ctrl",
    "Filter1": "Filter",
    "Filter2": "Filter",
    "Filter3": "Filter",
}

#Generator Config
INSTRUMENT_GENERATOR_OPTIONS = {
    "ANLG": "Analog",
    "DIG": "Digital",
    "I2S": "I2S Board",
    "IMP": "Digital Impairment",
    "U2C": "USI Dual Chan"
}

CHANNEL_GENERATOR_OPTIONS = {
    "OFF": "Off",
    "CH1": "1",
    "CH2": "2",
    "CH2Is1": "2 = 1"
}

OUTPUT_TYPE_OPTIONS = {
    "UNB": "Unbal",
    "BAL": "Bal"
}
IMPEDANCE_OPTIONS_BAL = {
    "R10": "10 Ω",
    "R200": "200 Ω",
    "R600": "600 Ω"
}
IMPEDANCE_OPTIONS_UNBAL = {
    "R5": "5 Ω"
}

COMMON_OPTIONS = {
    "FLO": "Float",
    "GRO": "Ground",    
}

BANDWIDTH_GENERATOR_OPTIONS = {
    "B22": "22 kHz",
    "B40": "40 kHz",
    "B80": "80 kHz",
    "AUTO": "Play Auto",
    "SIN185": "Sine 185 kHz",
}

VOLT_RANGE_OPTIONS = {
    "AUTO": "Auto",
    "FIX": "Fix",
}

#Generator Function
FUNCTION_GENERATOR_OPTIONS = {
    "SIN": "Sine",
    "STER": "Stereo Sine",
    "MULTI": "Multisine",
    "BURST": "Sine Burst",
    "S2P": "Sine² Pulse",
    "MDIS": "Mod Dist",
    "DFD": "DFD",
    "DIM": "DIM",
    "RAND": "Random",
    "ARB": "Arbitrary",
    "PLAY": "Play",
    "PLYA": "Play+Anlr",
    "POL": "Polarity",
    "MOD": "Modulation",
    "DC": "DC",
    "SQU": "Square",
    "CHIR": "Chirp"
}

LOW_DIST_OPTIONS = {
    "OFF": "Off",
    "ON": "On"
}

SWEEP_CTRL_OPTIONS = {
    "OFF": "Off",
    "ASW": "Auto Sweep",
    "ALIS": "Auto List"
}

NEXT_STEP_OPTIONS = {
    "ASYN": "Anlr Sync",
    "LIST": "Dwell File",
    "DWELl": "Dwell Value",    
}

X_AXIS_OPTIONS = {
    "VOLT": "Voltage",
    "FREQ": "Frequency"
}

Z_AXIS_OPTIONS = {
    "OFF": "Off",
    "VOLT": "Voltage",
    "FREQ": "Frequency"
}

SPACING_OPTIONS = {
    "LINP": "Lin Points",
    "LINS": "Lin Steps",
    "LOGP": "Log Points",
    "LOGS": "Log Steps"
}

FILTER_OPTIONS = {
    "OFF": "Off",
    "UFIL1":"Filter 1",
    "UFIL2":"Filter 2",
    "UFIL3":"Filter 3",
    "UFIL4":"Filter 4",
    "UFIL5":"Filter 5",
    "UFIL6":"Filter 6",
    "UFIL7":"Filter 7",
    "UFIL8":"Filter 8",
    "UFIL9":"Filter 9",
    "AWE":"A Weighting",
    "CARM":"CCIR 2k wtd",
    "CCIU":"CCIR unwtd",
    "CCIR":"CCIR 1k wtd",
    "CCIT": "CCITT",
    "CMES":"C Message",
    "DEMP17":"Deemph J.17",
    "DCN":"DC Noise HP",
    "DEMP5015":"Deemph 50/15",
    "DEMP75":"Deemph 75",
    "IECT":"IEC Tuner",
    "JITT":"Jitter wtd",
    "PEMP17":"Preemp J.17",
    "PEMP50":"Preemp 50",
    "PEMP5015":"Preemp 50/15",
    "PEMP75":"Preemp 75",
    "HP22":"High-pass 22 Hz",
    "HP400":"High-pass 400 Hz",
    "LP22":"Low-pass 22 kHz",
    "LP30":"Low-pass 30 kHz",
    "LP80":"Low-pass 80 kHz",
    "AES17":"AES 17",
    "CWE":"C Weighting",
    "URUM":"Rumble unwtd",
    "WRUM":"Rumble wtd",
}

HALT_OPTIONS = {
    "STARt": "Start",
    "VALue":"Value",
    "MUTE": "Mute"
}

# (Unused option sets removed: EQUALIZER_OPTIONS, DC_OFFSET_OPTIONS)

#Analyzer Config
INSTRUMENT_ANALYZER_OPTIONS = {
    "ANLG": "Analog",
    "A8CH": "Analog 8 Chan",
    "A16CH": "Analog 16 Chan",
    "DIG": "Digital",
    "I2S": "I2S Board",
    "U2CH": "USI Dual Chan",
    "U8CH": "USI 8 Chan",
    "DIGB": "Dig Bitstream",
}

CHANNEL_ANALYZER_OPTIONS = {
    "CH1": "1",
    "CH2": "2",
    "CH1And2": "1 & 2",
    "CH1Is2": "1 = 2",
    "CH2Is1": "2 = 1"
}

CH1_COUPLING_OPTIONS = {
    "AC": "AC",
    "DC": "DC",
}

BANDWIDTH_ANALYZER_OPTIONS = {
    "B22": "22 kHz",
    "B40": "40 kHz",
    "B80": "80 kHz",
    "B250": "250 kHz"
}

PRE_FILTER_OPTIONS = {
    "OFF": "Off",
    "UFIL1":"Filter 1",
    "UFIL2":"Filter 2",
    "UFIL3":"Filter 3",
    "UFIL4":"Filter 4",
    "UFIL5":"Filter 5",
    "UFIL6":"Filter 6",
    "UFIL7":"Filter 7",
    "UFIL8":"Filter 8",
    "UFIL9":"Filter 9",
    "AWE":"A Weighting",
    "CARM":"CCIR 2k wtd",
    "CCIU":"CCIR unwtd",
    "CCIR":"CCIR 1k wtd",
    "CCIT": "CCITT",
    "CMES":"C Message",
    "DEMP17":"Deemph J.17",
    "DCN":"DC Noise HP",
    "DEMP5015":"Deemph 50/15",
    "DEMP75":"Deemph 75",
    "IECT":"IEC Tuner",
    "JITT":"Jitter wtd",
    "PEMP17":"Preemp J.17",
    "PEMP50":"Preemp 50",
    "PEMP5015":"Preemp 50/15",
    "PEMP75":"Preemp 75",
    "HP22":"High-pass 22 Hz",
    "HP400":"High-pass 400 Hz",
    "LP22":"Low-pass 22 kHz",
    "LP30":"Low-pass 30 kHz",
    "LP80":"Low-pass 80 kHz",
    "AES17":"AES 17",
    "CWE":"C Weighting",
    "URUM":"Rumble unwtd",
    "WRUM":"Rumble wtd",
}

CH1_INPUT_OPTIONS = {
    "BAL": "Bal",
    "GEN1": "GEN CH1",
    "GEN2": "GEN CH2"
}

CH1_IMPEDANCE_OPTIONS = {
    "R300": "300 Ω",
    "R600": "600 Ω",
    "R200K": "200 KΩ"
}

CH1_COMMON_OPTIONS = {
    "FLO": "Float",
    "GRO": "Ground",
}

CH1_RANGE_OPTIONS = {
    "AUTO": "Auto",
    "FIXed": "Fixed",
    "LOWer": "Lower"
}

START_COND_OPTIONS = {
    "AUTO": "Auto",
    "TIM": "Time Tick",
    "TCH": "Time Chart",
    "CH1F": "Freq Ch1",
    "CH1R": "Freq Fast Ch1",
    "CH1L" : "Volt Ch1",
    "CH1T": "Lev Trig Ch1",
    "CH1E": "Edge Trig Ch1"
}

MAX_FFT_SIZE_OPTIONS = {
    "S512": "0.5 k",
    "S1K": "1 k",
    "S2K": "2 k",
    "S4K": "4 k",
    "S8K": "8 k",
    "S16K": "16 k",
    "S32K": "32 k",
    "S64K": "64 k",
    "S128K": "128 k",
    "S256K": "256 k"
}

FUNCTION_ANALYZER_OPTIONS = {
    "OFF": "Off",
    "RMS": "RMS",
    "RMSS": "RMS Selective",
    "PEAK": "Peak",
    "QPE": "Quasi Peak",
    "SN": "S/N",
    "DC": "DC",
    "FFT": "FFT",
    "THD": "THD",
    "THDN": "THD+N SINAD",
    "MDIS": "Mod DIst",
    "DFD": "DFD",
    "DIM": "DIM",
    "POL": "Polarity",
    "RUBB": "RUB Buzz",
    "REC": "Record",
    "NOCT": "1/n Octave",
    "PESQ": "PESQ",
    "PLUG": "PLUGin",
    "PEAQ": "PEAQ",
    "COH": "Transfer Co",
    "POLQ": "POLQA",
    "CHIR": "Chirpbased Meas"
}

MEAS_TIME_OPTIONS = {
    "AFASt": "Auto Fast",
    "AUTO": "Auto",
    "VALue": "Value",
    "GENT": "Gen Track"
}

NOTCH_OPTIONS = {
    "OFF": "Off",
    "DB0": "0 dB",
    "DB12": "12 dB Auto",
    "DB30": "30 dB Auto"
}

FILTER1_OPTIONS = FILTER_OPTIONS
FILTER2_OPTIONS = FILTER_OPTIONS
FILTER3_OPTIONS = FILTER_OPTIONS

FNCT_SETTLING_OPTIONS = {
    "OFF": "Off",
    "EXP": "Exponential",
    "FLAT": "Flat",
    "AVER": "Average"
}
LEVEL_MONITOR_OPTIONS = {
    "OFF": "Off",
    "LRMS": "RMS",
    "DC": "DC",
    "PEAK": "Peak"
}

SECOND_MONITOR_OPTIONS = {
    "OFF": "Off",
    "INP": "Input Monitor",
    "LEV": "Level Monitor"
}
INPUT_MONITOR_OPTIONS = {
    "OFF": "Off",
    "PEAK": "Peak"
}
FREQ_OPTIONS = {
    "OFF": "Off",
    "FREQ": "Frequency"
}

BANDWIDTH_ANALYZER_CONFIG_OPTIONS = {
    "PPCT1": "BP 1 %",
    "PPCT3": "BP 3 %",
    "POCT12": "BP 1/12 Oct",
    "PTOC": "BP 1/3 Oct",
    "PFAS": "BP 1/3 Oct Fast",
    "PFIXED": "BP Fixed",
    "SPCT1": "BS 1 %",
    "SPCT3": "BS 3 %",
    "SOCT12": "BS 1/12 Oct",
    "STOC": "BS 1/3 Oct",
    "SFAS": "BS 1/3 Oct Fast",
    "SFIX": "BS Fixed"
    }

FREQ_MODE_OPTIONS = {
    "FIXed": "Fixed",
    "GENT": "Gen Track",
    "CH1F": "Freq Ch1",
}