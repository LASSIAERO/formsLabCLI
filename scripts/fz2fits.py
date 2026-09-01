#!/usr/bin/env python3
import sys
import os
from astropy.io import fits

def convert_fz_to_fits(fz_path):
    if not fz_path.endswith(".fz"):
        print(f"❌ Not an .fz file: {fz_path}")
        return

    fits_path = fz_path[:-3] + ".fits"
    if os.path.exists(fits_path):
        print(f"⚠️ Output already exists: {fits_path}")
        return

    try:
        with fits.open(fz_path) as hdul:
            hdul.writeto(fits_path)
        print(f"✅ Converted: {fz_path} → {fits_path}")
    except Exception as e:
        print(f"❌ Failed to convert {fz_path}: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: fz2fits.py file1.fz [file2.fz ...]")
        sys.exit(1)

    for fz_file in sys.argv[1:]:
        convert_fz_to_fits(fz_file)

if __name__ == "__main__":
    main()
