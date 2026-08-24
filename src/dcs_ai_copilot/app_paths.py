from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DIR_NAME = "DCS AI Copilot"


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def config_root() -> Path:
    if getattr(sys, "frozen", False):
        appdata = Path(os.environ.get("APPDATA", str(Path.home())))
        return appdata / APP_DIR_NAME
    return runtime_root()


def ensure_config_root() -> Path:
    root = config_root()
    root.mkdir(parents=True, exist_ok=True)
    return root
