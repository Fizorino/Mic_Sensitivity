from __future__ import annotations

import sys
from pathlib import Path


def get_app_base_dir() -> Path:
    """Return the directory that should contain app data files.

    - When packaged (PyInstaller), this is the folder containing the .exe.
    - When running from source, this is the repository root (3 levels up from src/...).
      If that cannot be derived, fall back to the current working directory.
    """
    # PyInstaller frozen app
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    # Running from source: try to locate repo root based on this file location.
    # paths.py -> utils -> src -> mic-sensitivity-gui -> repo_root
    try:
        return Path(__file__).resolve().parents[3]
    except Exception:
        return Path.cwd().resolve()


def data_path(*parts: str) -> Path:
    """Build an absolute path to a data file that lives next to the exe (packaged) or in repo root (dev)."""
    return get_app_base_dir().joinpath(*parts)
