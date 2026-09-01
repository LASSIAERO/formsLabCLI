"""
Command file utilities for interactive REPL.

Same IPC pattern as console/ctrl/ctrlutils.py — reads and writes
cmdfile.json so the GUI (via Tauri) can send eval/exec commands
to the running Python process.

Protocol:
  command:  { id, type, payload, processed }
  response: { id, result, error }
"""

import json
from pathlib import Path
from typing import Dict, Optional

from formslab import config

# Resolved per call from the config directory. This was a *relative* path
# (`cli/cmd/cmdfile.json`), which only ever resolved because `setenv.py` chdir'd
# into the FORMS checkout first -- from any other working directory it silently
# read and wrote the wrong file, or none.
def _cmdfile() -> Path:
    return config.state_path("cmdfile.json")


def _load() -> Dict:
    """Load the command file, returning default if missing."""
    try:
        with open(_cmdfile(), "r") as f:
            return json.load(f)
    except Exception:
        return {"command": None, "response": None}


def _save(data: Dict):
    """Atomically write the command file."""
    with open(_cmdfile(), "w") as f:
        json.dump(data, f, indent=2)


def read_cmd() -> Optional[Dict]:
    """
    Read a pending command if one exists and hasn't been processed.

    Returns the command dict or None.
    """
    data = _load()
    cmd = data.get("command")
    if not isinstance(cmd, dict):
        return None
    if cmd.get("processed", True):
        return None
    return cmd


def write_response(cmd_id: str, result=None, error=None):
    """
    Write a response to a processed command and clear the command slot.
    """
    data = _load()

    # Mark command as processed
    if isinstance(data.get("command"), dict):
        data["command"]["processed"] = True

    data["response"] = {
        "id": cmd_id,
        "result": result,
        "error": error,
    }
    _save(data)


def reset_cmd_state():
    """Reset the command file to empty state."""
    _save({"command": None, "response": None})
