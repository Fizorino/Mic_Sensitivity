# DISPLAY_MAP = {
#     #Generator Config
#     "ANLG": "Analog",
#     "DIG": "Digital",
#     "I2SB": "I2S Board",
#     "IMPairment": "Digital Impairment",
#     "U2Channel": "USI Dual Chan",

#     "A8CHannel": "Analog 8 Chan",
#     "A16CHannel": "Analog 16 Chan",
#     "U8CHannel": "USI 8 Chan",
#     "DIGBitstream": "Dig Bitstream",

#     "OFF": "Off",
#     "CH1": "1",
#     "CH2": "2",
#     "CH2Is1": "2 = 1",

#     "UNB": "Unbal",
#     "BAL": "Bal",

#     "R5": "5 Ω",
#     "R10": "10 Ω",
#     "R200": "200 Ω",
#     "R600": "600 Ω",

#     "GRO": "Ground",
#     "FLO": "Float",

#     "B22": "22 kHz",
#     "B40": "40 kHz",
#     "B80": "80 kHz",
#     "AUTO": "Play Auto",
#     "SIN185": "Sine 185 kHz",

#     "AUTO": "Auto",
#     "FIX": "Fix",

#     #Generator Function
#     "SIN": "Sine",
#     "STER": "Stereo Sine",
#     "MULTI": "Multisine",
#     "BURST": "Sine Burst",
#     "S2Pulse": "Sine² Pulse",
#     "MDISt": "Mod Dist",
#     "DFD": "DFD",
#     "DIM": "DIM",
#     "RANDom": "Random",
#     "ARB": "Arbitrary",
#     "PLAY": "Play",
#     "PLYA": "Play+Anlr",
#     "POL": "Polarity",
#     "MOD": "Modulation",
#     "DC": "DC",
#     "SQU": "Square",
#     "CHIR": "Chirp",

#     "OFF": "Off",
#     "ON": "On",

#     "ASW": "Auto Sweep",
#     "ALIS": "Auto List",

#     "DWELl": "Dwell Value",
#     "ASYNc": "Anlr Sync",
#     "LIST": "Dwell File",

#     "VOLT": "Voltage",
#     "FREQ": "Frequency",

#     "LINPoints": "Lin Points",
#     "LINSteps": "Lin Steps",
#     "LOGPoints": "Log Points",
#     "LOGP": "Log Steps",

#     "OFF": "Off",
#     "UFIL1":"Filter 1",
#     "UFIL2":"Filter 2",
#     "UFIL3":"Filter 3",
#     "UFIL4":"Filter 4",
#     "UFIL5":"Filter 5",
#     "UFIL6":"Filter 6",
#     "UFIL7":"Filter 7",
#     "UFIL8":"Filter 8",
#     "UFIL9":"Filter 9",
#     "AWE":"A Weighting",
#     "CARM":"CCIR 2k wtd",
#     "CCIU":"CCIR unwtd",
#     "CCIR":"CCIR 1k wtd",
#     "CCIT": "CCITT",
#     "CMES":"C Message",
#     "DEMP17":"Deemph J.17",
#     "DCN":"DC Noise HP",
#     "DEMP5015":"Deemph 50/15",
#     "DEMP75":"Deemph 75",
#     "IECT":"IEC Tuner",
#     "JITT":"Jitter wtd",
#     "PEMP17":"Preemp J.17",
#     "PEMP50":"Preemp 50",
#     "PEMP5015":"Preemp 50/15",
#     "PEMP75":"Preemp 75",
#     "HP22":"High-pass 22 Hz",
#     "HP400":"High-pass 400 Hz",
#     "LP22":"Low-pass 22 kHz",
#     "LP30":"Low-pass 30 kHz",
#     "LP80":"Low-pass 80 kHz",
#     "AES17":"AES 17",
#     "CWE":"C Weighting",
#     "URUM":"Rumble unwtd",
#     "WRUM":"Rumble wtd",

#     "VALUE":"Value",
#     "MUTE": "Mute",

#     #Analyzer Config
#     "CH1Is2": "1 = 2",
#     "CH1And2": "1 & 2",

#     "AC": "AC",
#     "DC": "DC",


# }


#Generator Config
INSTRUMENT_GENERATOR_OPTIONS = {
    "ANLG": "Analog",
    "DIG": "Digital",
    "I2S": "I2S Board",
    "IMPairment": "Digital Impairment",
    "U2Channel": "USI Dual Chan"
}

CHANNEL_GENERATOR_OPTIONS = {
    "OFF": "Off",
    "CH1": "1",
    "CH2": "2",
    "CH2Is1": "2 = 1"
}

OUTPUT_TYPE_OPTIONS = {
    "UNB": "Unbal",
    "UNBalanced": "Unbal",
    
    "BALanced": "Bal"
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
    "SINusoid": "Sine",
    "STEReo": "Stereo Sine",
    "MULTI": "Multisine",
    "BURST": "Sine Burst",
    "S2Pulse": "Sine² Pulse",
    "MDISt": "Mod Dist",
    "DFD": "DFD",
    "DIM": "DIM",
    "RANDom": "Random",
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
    "ASWeep": "Auto Sweep",
    "ALIS": "Auto List"
}

NEXT_STEP_OPTIONS = {
    "ASYNc": "Anlr Sync",
    "LIST": "Dwell File",
    "DWELl": "Dwell Value",    
}

X_AXIS_OPTIONS = {
    "VOLTage": "Voltage",
    "FREQuency": "Frequency"
}

Z_AXIS_OPTIONS = {
    "OFF": "Off",
    "VOLTage": "Voltage",
    "FREQuency": "Frequency"
}

SPACING_OPTIONS = {
    "LINPoints": "Lin Points",
    "LINSteps": "Lin Steps",
    "LOGPoints": "Log Points",
    "LOGSteps": "Log Steps"
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

EQUALIZER_OPTIONS = {
    "OFF": "Off",
    "ON": "On"
}

DC_OFFSET_OPTIONS = {
    "OFF": "Off",
    "ON": "On"
}

#Analyzer Config
INSTRUMENT_ANALYZER_OPTIONS = {
    "ANLG": "Analog",
    "A8CHannel": "Analog 8 Chan",
    "A16CHannel": "Analog 16 Chan",
    "DIG": "Digital",
    "I2S": "I2S Board",
    "U2Channel": "USI Dual Chan",
    "U8CHannel": "USI 8 Chan",
    "DIGBitstream": "Dig Bitstream",
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
    "BALanced": "BAL",
    "GEN1": "GEN CH1",
    "GEN2": "GEN CH2"
}

CH1_IMPEDANCE_OPTIONS = {
    "R300": "300 Ω",
    "R600": "600 Ω",
    "R200K": "200 KΩ"
}

CH1_COMMON_OPTIONS = {
    "FLOat": "Float",
    "GROund": "Ground",
}

CH1_RANGE_OPTIONS = {
    "AUTO": "Auto",
    "FIXed": "Fixed",
    "LOWer": "Lower"
}

START_COND_OPTIONS = {
    "AUTO": "Auto",
    "TIMer": "Time Tick",
    "TCHart": "Time Chart",
    "CH1Freq": "Freq Ch1",
    "CH1Rapidfreq": "Freq Fast Ch1",
    "CH1Level" : "Volt Ch1",
    "CH1Trigger": "Lev Trig Ch1",
    "CH1Edgetrigger": "Edge Trig Ch1"
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
    "RMSSelect": "RMS Selective",
    "PEAK": "Peak",
    "QPEak": "Quasi Peak",
    "SN": "S/N",
    "DC": "DC",
    "FFT": "FFT",
    "THD": "THD",
    "THDNsndr": "THD+N SINAD",
    "MDISt": "Mod DIst",
    "DFD": "DFD",
    "DIM": "DIM",
    "POLarity": "Polarity",
    "RUBBuzz": "RUB Buzz",
    "RECord": "Record",
    "NOCTave": "1/n Octave",
    "PESQ": "PESQ",
    "PLUGin": "PLUGin",
    "PEAQ": "PEAQ",
    "COHerence": "Transfer Co",
    "POLQa": "POLQA",
    "CHIRpbased": "Chirpbased Meas"
}

MEAS_TIME_OPTIONS = {
    "AFASt": "Auto Fast",
    "AUTO": "Auto",
    "VALue": "Value",
    "GENTrack": "Gen Track"
}

NOTCH_OPTIONS = {
    "OFF": "Off",
    "DB0": "0 dB",
    "DB12": "12 dB Auto",
    "DB30": "30 dB Auto"
}

FILTER1_OPTIONS = {
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

FILTER2_OPTIONS = {
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
FILTER3_OPTIONS = {
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

FNCT_SETTLING_OPTIONS = {
    "OFF": "Off",
    "EXPonential": "Exponential",
    "FLAT": "Flat",
    "AVERage": "Average"
}
LEVEL_MONITOR_OPTIONS = {
    "OFF": "Off",
    "LRMS": "RMS",
    "DC": "DC",
    "PEAK": "Peak"
}

SECOND_MONITOR_OPTIONS = {
    "OFF": "Off",
    "INPut": "Input Monitor",
    "LEVel": "Level Monitor"
}
INPUT_MONITOR_OPTIONS = {
    "OFF": "Off",
    "PEAK": "Peak"
}
FREQ_OPTIONS = {
    "OFF": "Off",
    "FREQuency": "Frequency"
}