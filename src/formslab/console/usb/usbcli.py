#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path

from formslab.config import usbmap_path
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from formslab.console.sessions.base import CLIResult
from formslab.console.style import (
    console,
    BG,
    TEXT,
    HEADER,
    ERROR,
    NUMBER,
    ACCENT1,
    ACCENT2,
    PANEL_BORDER,
    PANEL_PADDING,
    PROMPT_SUFFIX,
)

BASE = Path(__file__).parent
# Resolved per call: this module both reads and *writes* the map (`map_slta`
# records a discovered serial number), so it must reach the live copy in the
# config directory, never the read-only packaged default. The path it used to
# build -- `console/lab/usbmap.json` -- never existed after the extraction.


def load_map():
    try:
        with open(usbmap_path()) as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"Failed to load usbmap.json: {e}")


def help_panel():
    txt = Text(style=TEXT)
    txt.append("USB CLI Commands\n", HEADER)
    txt.append("(Commands work with or without -- prefix)\n\n", TEXT)
    commands = [
        ("list", "Show mapped USB devices"),
        ("scan", "Scan USB ports and show TTY devices"),
        ("map-slta [label]", "Auto-detect sLTA hub/port and update map"),
        ("reset <label>", "Run usbreset on mapped port"),
        ("poweron <label>", "Power ON the USB port via uhubctl"),
        ("poweroff <label>", "Power OFF the USB port via uhubctl"),
        ("help", "Show this help message"),
    ]
    for cmd, desc in commands:
        txt.append(f"  {cmd:<20}", HEADER)
        txt.append(desc + "\n", TEXT)
    return CLIResult(Panel(txt, title="USB CLI Help", border_style=PANEL_BORDER, style=BG, padding=PANEL_PADDING))


def list_devices(usbmap):
    table = Table(title="USB Device Mapping", header_style=HEADER, style=TEXT)
    table.add_column("Label", style=HEADER)
    table.add_column("Description", style=TEXT)
    table.add_column("Hub", justify="right", style=NUMBER)
    table.add_column("Port", justify="right", style=NUMBER)
    for label, dev in usbmap.items():
        table.add_row(
            label,
            dev.get("description", ""),
            dev.get("hub_location", "—"),
            str(dev.get("hub_port", "—")),
        )
    return CLIResult(table)


def reset_device(usbmap, label):
    entry = usbmap.get(label)
    if not entry:
        return CLIResult(Text(f"✗ No device labeled '{label}'", style=ERROR))
    port = entry.get("port")
    if not port:
        return CLIResult(Text("✗ 'port' not found in map entry", style=ERROR))
    try:
        from usbreset import run_usbreset
        success = run_usbreset(port)
        if success:
            return CLIResult(Text(f"✔ usbreset sent to port {port}", style=ACCENT2))
        else:
            return CLIResult(Text(f"✗ usbreset failed on port {port}", style=ERROR))
    except ImportError:
        return CLIResult(Text("✗ usbreset module not found", style=ERROR))


def power_device(usbmap, label, state):
    entry = usbmap.get(label)
    if not entry:
        return CLIResult(Text(f"✗ No device labeled '{label}'", style=ERROR))
    loc = entry.get("hub_location")
    port = entry.get("hub_port")
    if not loc or not port:
        return CLIResult(Text("✗ 'hub_location' or 'hub_port' missing", style=ERROR))
    try:
        subprocess.run(["sudo", "uhubctl", "-l", loc, "-p", str(port), "-a", "1" if state == "on" else "0"], check=True)
        return CLIResult(Text(f"✔ Power {state} sent to {label}", style=ACCENT2))
    except subprocess.CalledProcessError as e:
        return CLIResult(Text(f"✗ uhubctl command failed: {e}", style=ERROR))


def scan_ports(usbmap):
    try:
        output = subprocess.check_output(["uhubctl"], text=True)
    except subprocess.CalledProcessError as e:
        return CLIResult(Text(f"✗ uhubctl failed: {e}", style=ERROR))

    current_hub = None
    table = Table(title="Live USB Port Scan", header_style=ACCENT1, style=TEXT)
    table.add_column("Hub", justify="right", style=NUMBER)
    table.add_column("Port", justify="right", style=NUMBER)
    table.add_column("Status", style=ACCENT1)
    table.add_column("Device", style=TEXT)
    table.add_column("Mapped Label", style=ACCENT2)
    table.add_column("TTY", style=NUMBER)

    for line in output.splitlines():
        if line.startswith("Current status for hub"):
            parts = line.split()
            current_hub = parts[4]
        elif line.strip().startswith("Port"):
            parts = line.strip().split()
            port = parts[1].strip(":")
            status = parts[2]
            device_info = " ".join(parts[6:]) if len(parts) > 6 else "—"
            label = next((k for k, v in usbmap.items()
                          if v.get("hub_location") == current_hub and str(v.get("hub_port")) == port), None)
            tty = Path(f"/sys/bus/usb/devices/{current_hub}.{port}").glob("ttyUSB*")
            tty_name = next(tty, None)
            table.add_row(
                current_hub,
                port,
                status,
                device_info,
                label if label else "unmapped",
                tty_name.name if tty_name else "—"
            )
    return CLIResult(table)


def map_slta(usbmap, label="slta"):
    entry = usbmap.get(label)
    if not entry:
        return CLIResult(Text(f"✗ No device labeled '{label}'", style=ERROR))
    mac = entry.get("mac_address")
    if not mac:
        return CLIResult(Text(f"✗ '{label}' missing 'mac_address'", style=ERROR))

    # mock detection
    entry.update({"hub_location": "detected_loc", "hub_port": 1, "port": "detected_port"})
    usbmap[label] = entry
    try:
        with open(usbmap_path(), "w") as f:
            json.dump(usbmap, f, indent=2)
        return CLIResult(Text(f"✔ {label} mapped to {entry['hub_location']} port {entry['hub_port']}", style=ACCENT2))
    except Exception as e:
        return CLIResult(Text(f"✗ Failed to save usbmap.json: {e}", style=ERROR))


def run_command(args):
    try:
        usbmap = load_map()
    except RuntimeError as e:
        return CLIResult(Text(str(e), style=ERROR))

    if not args:
        return help_panel()

    # Standardize: strip -- prefix to match other CLI modules
    cmd = args[0].lstrip("-").lower()

    if cmd == "help":
        return help_panel()
    if cmd == "list":
        return list_devices(usbmap)
    if cmd == "scan":
        return scan_ports(usbmap)
    if cmd == "map-slta":
        lbl = args[1] if len(args) > 1 else "slta"
        return map_slta(usbmap, lbl)
    if cmd == "reset":
        if len(args) < 2:
            return CLIResult(Text("✗ Missing device label. Usage: reset <label>", style=ERROR))
        return reset_device(usbmap, args[1])
    if cmd == "poweron":
        if len(args) < 2:
            return CLIResult(Text("✗ Missing device label. Usage: poweron <label>", style=ERROR))
        return power_device(usbmap, args[1], "on")
    if cmd == "poweroff":
        if len(args) < 2:
            return CLIResult(Text("✗ Missing device label. Usage: poweroff <label>", style=ERROR))
        return power_device(usbmap, args[1], "off")

    return CLIResult(Text(f"✗ Unknown command: {' '.join(args)}. Type 'help' for available commands.", style=ERROR))


def main():
    result = run_command(["--help"])
    console.print(result.content)
    while True:
        raw = input(f"usbcli{PROMPT_SUFFIX} ").strip()
        if raw in ("exit", "quit"):
            break
        result = run_command(raw.split())
        console.print(result.content)

if __name__ == "__main__":
    main()
