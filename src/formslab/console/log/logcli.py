#!/usr/bin/env python3
import sys, re, json
from pathlib import Path
from rich.text import Text
from formslab.console.sessions.base import CLIResult
from formslab.console.style import console, TEXT, ERROR

# Paths
CONFIG_FILE = Path(__file__).resolve().parent / "logfile.json"
# NOT YET RESOLVED after the extraction: this tails the log written by the
# sequence host, which has not moved over yet. Same fix as MISSIONS_DIR in
# ctrl/ctrlcli.py -- a resolved workspace rather than a walk up from __file__.
FORMSPATH = Path(__file__).resolve().parents[3]
DATAPATH     = FORMSPATH / "data" / "forms.log"
# Load command definitions from logfile.json
def load_commands():
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}

# Command handlers
def show_log(args):
    try:
        data = DATAPATH.read_text().splitlines()
    except Exception as e:
        return CLIResult(Text(f"Error reading log: {e}", style=ERROR))
    return CLIResult(Text("\n".join(data), style=TEXT), clear=True, suppress_prompt=True)

def tail_log(args):
    if not args:
        return CLIResult(Text("✗ Missing count. Usage: tail <N>", style=ERROR))
    try:
        n = int(args[0])
    except ValueError:
        return CLIResult(Text("✗ Invalid number (must be integer)", style=ERROR))

    # Validate range
    if n < 1:
        return CLIResult(Text("✗ Count must be positive", style=ERROR))
    if n > 10000:
        return CLIResult(Text("✗ Count too large (max: 10000 lines)", style=ERROR))

    data = DATAPATH.read_text().splitlines()
    return CLIResult(Text("\n".join(data[-n:]), style=TEXT))

def grep_log(args):
    if not args:
        return CLIResult(Text("✗ Missing pattern. Usage: grep <pattern>", style=ERROR))
    pat = args[0]

    # Validate regex pattern
    try:
        re.compile(pat)
    except re.error as e:
        return CLIResult(Text(f"✗ Invalid regex pattern: {e}", style=ERROR))

    data = DATAPATH.read_text().splitlines()
    hits = [l for l in data if re.search(pat, l)]
    return CLIResult(Text("\n".join(hits), style=TEXT))

# Help panel

def help_panel() -> CLIResult:
    cmds = load_commands()
    lines = ["LOG Commands:"]
    max_key = max((len(k) for k in cmds), default=0)
    for k, meta in cmds.items():
        desc = meta.get("desc", "")
        lines.append(f"  {k.ljust(max_key)}   {desc}")
    return CLIResult(Text("\n".join(lines), style=TEXT), clear=False, suppress_prompt=True)

# Command registry
COMMANDS = {
    "status": show_log,
    "tail": tail_log,
    "grep": grep_log,
    "help": lambda args=None: help_panel()
}

def execute_command(args, *, context="cli") -> CLIResult:
    if not args:
        return help_panel()
    cmd = args[0].lstrip("-")
    handler = COMMANDS.get(cmd)
    if handler:
        return handler(args[1:])
    return CLIResult(Text(f"Unknown command: {' '.join(args)}", style=ERROR))

# Standalone entrypoint
if __name__ == "__main__":
    console.print(help_panel().content)
    args = sys.argv[1:]
    if args:
        result = execute_command(args)
        console.print(result.content)
    else:
        while True:
            raw = console.input("log> ").strip()
            if raw in ("--exit", "exit", "quit"):
                break
            result = execute_command(raw.split())
            console.print(result.content)
