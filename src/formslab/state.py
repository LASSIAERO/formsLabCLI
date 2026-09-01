from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from formslab.devices.cryo_config import (
    CRYO_PSU_CHANNEL,
    CRYO_PSU_LABEL,
    CRYO_SUPPLY_CURRENT_A,
    CRYO_SUPPLY_VOLTAGE_V,
)


# Where the console's mutable runtime state lives. Still inside the package,
# as it was inside the checkout before the extraction -- Phase 2 moves it to a
# real per-user config directory ($FORMSLAB_CONFIG_DIR / ~/.formslab), which is
# what makes an installed console writable on a lab machine.
PACKAGE_ROOT = Path(__file__).resolve().parent
CAST_STATE_PATH = PACKAGE_ROOT / "console" / "cast" / "castfile.json"
CTRL_STATE_PATH = PACKAGE_ROOT / "console" / "ctrl" / "ctrlfile.json"


def build_default_ctrl_commands() -> dict:
    return {
        "missions": {
            "key": None,
            "processed": True,
            "desc": "List available .zen missions and operational modes",
        },
        "run": {
            "key": None,
            "processed": True,
            "desc": (
                "Launch a mission by name, index, or 'tvac'. "
                "Usage: run <name|#|tvac> (e.g. 'run darkness', 'run 1', 'run tvac')"
            ),
        },
        "pause": {"key": None, "processed": True, "desc": "Pause the running sequence"},
        "resume": {"key": None, "processed": True, "desc": "Resume a paused sequence"},
        "reset": {"key": None, "processed": True, "desc": "Reset control state"},
        "end": {"key": None, "processed": True, "desc": "Terminate the running sequence"},
        "stream": {
            "key": None,
            "processed": True,
            "desc": "Set the GUI telemetry rate in Hz (0 = off when no window is open)",
        },
        "status": {
            "key": None,
            "processed": True,
            "desc": "Check if sequence.py is running",
        },
        "ps": {
            "key": None,
            "processed": True,
            "desc": "List all sequence.py processes",
        },
        "help": {
            "key": None,
            "processed": True,
            "desc": "Display help panel for available commands",
        },
        "exit": {
            "key": None,
            "processed": True,
            "desc": "Exit the forms console",
        },
    }


def build_default_cast_state(now: float | None = None) -> dict:
    timestamp = time.time() if now is None else now
    return {
        "psu1": {
            "timestamp": timestamp,
            "processed": True,
            "request": {},
            "status": {
                "1": {"on": False, "vset": 0.0, "cset": 0.0, "vmeas": 0.0, "cmeas": 0.0},
                "2": {"on": False, "vset": 0.0, "cset": 0.0, "vmeas": 0.0, "cmeas": 0.0},
                "3": {"on": False, "vset": 0.0, "cset": 0.0, "vmeas": 0.0, "cmeas": 0.0},
            },
        },
        "psu2": {
            "timestamp": timestamp,
            "processed": True,
            "request": {},
            "status": {
                "1": {"on": False, "vset": 0.0, "cset": 0.0, "vmeas": 0.0, "cmeas": 0.0},
                "2": {"on": False, "vset": 0.0, "cset": 0.0, "vmeas": 0.0, "cmeas": 0.0},
                "3": {"on": False, "vset": 0.0, "cset": 0.0, "vmeas": 0.0, "cmeas": 0.0},
            },
        },
        "slta": {
            "timestamp": timestamp,
            "processed": True,
            "request": {},
            "status": {
                "SLTARUN": False,
                "running": False,
                "in_umbra": False,
                "mode": "E",
                "exposure": 600,
                "idle": 30,
                "token": None,
                "IMAGEDIR": "default",
            },
        },
        "tvac": {
            "timestamp": timestamp,
            "processed": True,
            "request": {},
            "status": {
                "target PY Shroud": 240,
                "target MY Shroud": 240,
                "PYsT": 0.0,
                "MYsT": 0.0,
                "TC08": [0.0] * 8,
            },
        },
        "cryo": {
            "timestamp": timestamp,
            "processed": True,
            "request": {},
            "status": {
                "LINK": False,
                "ON": False,
                "PSU": f"{CRYO_PSU_LABEL.upper()} CH{CRYO_PSU_CHANNEL}",
                "PSUON": False,
                "CCVIN": CRYO_SUPPLY_VOLTAGE_V,
                "CCIIN": CRYO_SUPPLY_CURRENT_A,
                "CCVINM": None,
                "CCIINM": None,
                "CCV": None,
                "CCVRES": None,
                "CCVRES#": None,
            },
        },
    }


def ensure_json_file(path: Path, factory: Callable[[], dict]) -> Path:
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(factory(), indent=2) + "\n", encoding="utf-8")
    return path


def ensure_runtime_files() -> None:
    ensure_json_file(CAST_STATE_PATH, build_default_cast_state)
    ensure_json_file(CTRL_STATE_PATH, build_default_ctrl_commands)
