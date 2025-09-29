"""UPV settings read-back utility.

This module queries the connected UPV audio analyzer for the current values
of all settings defined in `command_groups` (imported from `upv_auto_config`)
and writes them into a JSON file matching the same hierarchical structure
used by the GUI application (sections: Generator Config, Generator Function,
Analyzer Config, Analyzer Function).

The JSON that is produced is directly compatible with the existing
`settings.json` / preset load logic (it stores the raw *code* values
returned by the instrument, not the human-friendly display strings).

Limitations / Notes:
- Query strategy: for each SCPI base command we attempt a "?" form
  (e.g. SENS1:FUNC -> SENS1:FUNC?). If the command already ends with "?"
  we send it as-is.
- Some selector/style commands like INST1 / INST2 used to switch context
  may not respond directly to adding a '?'. If a query fails, we skip that
  item and continue.
- No attempt is made to convert units; the raw response is stored.
- You can post-process or map display labels later if needed.

Example CLI usage (after configuring VISA address with the GUI or config):

    python -m upv.upv_readback --output current_settings_dump.json

or simply:

    python mic-sensitivity-gui/src/upv/upv_readback.py -o snapshot.json

If no output path is provided, a timestamped file is created next to
`settings.json`.
"""
from __future__ import annotations

import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any

import pyvisa

from .upv_auto_config import (
    command_groups,
    load_config,
    find_upv_ip,
    save_config,
)

DEFAULT_SETTINGS_FILE = "readback.json"

# Commands that require a different query form than simply appending '?'
# Map label -> explicit query command
SPECIAL_QUERY_COMMANDS = {
    # Instrument selection: we query current instrument with INST?
    "Instrument Generator": "INST?",   # Will return 1 or 2 typically
    "Instrument Analyzer": "INST?",    # We still record the numeric result
}

# Labels we should skip entirely (rare / not readable)
SKIP_LABELS = set()


def _derive_query(scpi: str, label: str) -> str | None:
    """Return the SCPI query form for a given base command.

    If the label is in SPECIAL_QUERY_COMMANDS we return that.
    If the command already ends with '?' return unchanged.
    Else append '?' to base command.
    Returns None if the label is to be skipped.
    """
    if label in SKIP_LABELS:
        return None
    if label in SPECIAL_QUERY_COMMANDS:
        return SPECIAL_QUERY_COMMANDS[label]
    if scpi.endswith('?'):
        return scpi
    return f"{scpi}?"


def read_current_settings(upv) -> Dict[str, Dict[str, Any]]:
    """Query the UPV for all known settings and return a nested dict.

    Structure:
    {
        "Generator Config": { label: value, ... },
        ...
    }

    Query failures are logged (printed) and the offending label omitted.
    """
    snapshot: Dict[str, Dict[str, Any]] = {}
    for section, mapping in command_groups.items():
        section_out: Dict[str, Any] = {}
        for label, scpi in mapping.items():
            q = _derive_query(scpi, label)
            if q is None:
                continue
            try:
                resp = upv.query(q).strip()
                # Basic normalization: remove enclosing quotes if any
                if resp.startswith('"') and resp.endswith('"') and len(resp) >= 2:
                    resp = resp[1:-1]
                section_out[label] = resp
            except Exception as e:
                print(f"⚠️ Query failed for {section}/{label} ({q}): {e}")
                continue
        snapshot[section] = section_out
    return snapshot


def save_settings_snapshot(upv, output_path: Path | None = None) -> Path:
    """Create a settings snapshot JSON file and return its path."""
    if output_path is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"upv_snapshot_{ts}.json")
    data = read_current_settings(upv)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Settings snapshot written to {output_path}")
    return output_path


def connect_upv() -> Any:
    """Connect to the UPV using stored config or discovery."""
    rm = pyvisa.ResourceManager()
    visa_address = load_config()
    upv = None

    if visa_address:
        try:
            print(f"🔌 Trying saved UPV address: {visa_address}")
            upv = rm.open_resource(visa_address)
            upv.timeout = 5000
            print("✅ Connected to:", upv.query("*IDN?").strip())
            return upv
        except Exception as e:
            print(f"❌ Saved address failed: {e} -> searching...")

    visa_address = find_upv_ip()
    if not visa_address:
        raise RuntimeError("No UPV found (LAN/USB).")
    upv = rm.open_resource(visa_address)
    upv.timeout = 5000
    print("✅ Connected to:", upv.query("*IDN?").strip())
    save_config(visa_address)
    return upv


def main():
    parser = argparse.ArgumentParser(description="Read current UPV settings and save to JSON.")
    parser.add_argument("-o", "--output", help="Output JSON file path (default: auto timestamp)")
    args = parser.parse_args()

    try:
        upv = connect_upv()
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return 1

    try:
        out_path = Path(args.output) if args.output else None
        save_settings_snapshot(upv, out_path)
    except Exception as e:
        print(f"❌ Failed to create snapshot: {e}")
        return 2
    finally:
        try:
            upv.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
