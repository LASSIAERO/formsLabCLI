#!/usr/bin/env python3
import sys
import os
# Ensure project root is on sys.path (if RTD16.py lives elsewhere)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from formslab.devices.RTD16 import RTD16


def main():
    # Instantiate for label "RTD1" (must exist in usbmap.json)
    rtd = RTD16("RTD1")
    rtd.read_serial()
    print(rtd.temps)

if __name__ == '__main__':
    main()

