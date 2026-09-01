#!/usr/bin/env python3
"""
usbreset.py: selectively unbind PSU USB ports, reload FTDI modules,
then trigger udev to recreate /dev/psu1 and /dev/psu2.
"""
import time
import subprocess
import sys
import os
import psutil
from pathlib import Path

# Safe target ports for PSU1 and PSU2
PORTS = ["1-4.1", "1-4.2"]

# Paths
UNBIND = Path('/sys/bus/usb/drivers/usb/unbind')
BIND   = Path('/sys/bus/usb/drivers/usb/bind')


def write_sysfs(path: Path, text: str):
    if not path.exists():
        print(f"✗ Path {path} does not exist", file=sys.stderr)
        sys.exit(1)
    try:
        path.write_text(text)
        print(f"→ Wrote '{text}' to {path}")
    except Exception as e:
        print(f"✗ ERROR writing {path}: {e}", file=sys.stderr)
        sys.exit(1)


def run(cmd):
    print(f"→ Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def main():
    if os.geteuid() != 0:
        print("✗ ERROR: must run as root", file=sys.stderr)
        sys.exit(1)

    # 1) Unbind PSU ports
    for port in PORTS:
        write_sysfs(UNBIND, port)

    time.sleep(2)

    for port in PORTS:
        write_sysfs(BIND, port)

    time.sleep(5)  # allow USB stack to re-enumerate

    # 2) Kill processes using ttyUSB
    for proc in psutil.process_iter(['pid', 'name', 'open_files']):
        try:
            for f in proc.info['open_files'] or []:
                if f.path.startswith('/dev/ttyUSB'):
                    print(f"⚠ Killing PID {proc.pid} ({proc.name()}) using {f.path}")
                    proc.terminate()
                    proc.wait(timeout=2)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 3) Reload FTDI drivers
    run(['modprobe', '-r', 'ftdi_sio', 'usbserial'])
    time.sleep(2)
    run(['modprobe', 'usbserial'])
    run(['modprobe', 'ftdi_sio'])
    time.sleep(5)

    # 4) Trigger udev
    run(['udevadm', 'trigger', '--action=add', '--attr-match=subsystem=tty'])
    print("→ Reset complete. /dev/psu1 & /dev/psu2 should be restored.")

if __name__ == '__main__':
    main()
