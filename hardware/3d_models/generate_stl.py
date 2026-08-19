#!/usr/bin/env python3
"""Generate STL files from OpenSCAD sources.

Requires OpenSCAD installed (brew install openscad / apt install openscad).
If OpenSCAD is not available, the .scad files can be loaded directly by
most fab labs or slicers (PrusaSlicer, Cura, BambuStudio).

Usage:
    python generate_stl.py              # Generate all STLs
    python generate_stl.py emg_clip     # Generate one part
    python generate_stl.py --check      # Verify .scad files parse cleanly
"""
import os
import subprocess
import sys
from pathlib import Path

SCAD_DIR = Path(__file__).parent
STL_DIR = SCAD_DIR / "stl"

PARTS = {
    "emg_clip": {"file": "emg_clip.scad", "copies": 4},
    "stim_guide": {"file": "stim_guide.scad", "copies": 2},
    "electronics_box": {"file": "electronics_box.scad", "copies": 1},
    "cable_clip": {"file": "cable_clip.scad", "copies": 2},
}


def find_openscad():
    """Find the OpenSCAD binary."""
    for name in ["openscad", "OpenSCAD"]:
        for path in [
            f"/usr/bin/{name}",
            f"/usr/local/bin/{name}",
            f"/opt/homebrew/bin/{name}",
            f"/Applications/OpenSCAD.app/Contents/MacOS/{name}",
            os.path.expanduser(f"~/Applications/OpenSCAD.app/Contents/MacOS/{name}"),
        ]:
            if os.path.isfile(path):
                return path

    import shutil
    return shutil.which("openscad")


def generate_stl(scad_file, stl_file, openscad_bin):
    """Render a .scad file to .stl."""
    cmd = [openscad_bin, "-o", str(stl_file), str(scad_file)]
    print(f"  Rendering {scad_file.name} -> {stl_file.name}...", end=" ", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode == 0:
        size_kb = stl_file.stat().st_size / 1024
        print(f"OK ({size_kb:.0f} KB)")
        return True
    else:
        print(f"FAILED")
        print(f"    stderr: {result.stderr[:200]}")
        return False


def check_scad(scad_file, openscad_bin):
    """Check if a .scad file parses without errors."""
    cmd = [openscad_bin, "-o", "/dev/null", "--export-format", "echo", str(scad_file)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode == 0


def main():
    args = sys.argv[1:]

    openscad = find_openscad()
    if not openscad:
        print("OpenSCAD not found.")
        print()
        print("Install it:")
        print("  macOS:  brew install openscad")
        print("  Ubuntu: sudo apt install openscad")
        print("  Or download from https://openscad.org/downloads.html")
        print()
        print("Alternatively, load the .scad files directly into your slicer")
        print("or bring them to the fab lab — most can render .scad natively.")
        sys.exit(1)

    print(f"Using OpenSCAD: {openscad}")

    if "--check" in args:
        print("\nChecking .scad files...")
        all_ok = True
        for name, info in PARTS.items():
            scad = SCAD_DIR / info["file"]
            ok = check_scad(scad, openscad)
            status = "OK" if ok else "PARSE ERROR"
            print(f"  {info['file']}: {status}")
            if not ok:
                all_ok = False
        sys.exit(0 if all_ok else 1)

    # Filter to requested parts
    if args:
        parts = {k: v for k, v in PARTS.items() if k in args}
        if not parts:
            print(f"Unknown part(s): {args}. Available: {list(PARTS.keys())}")
            sys.exit(1)
    else:
        parts = PARTS

    STL_DIR.mkdir(exist_ok=True)
    print(f"\nGenerating STL files to {STL_DIR}/\n")

    success = 0
    failed = 0
    for name, info in parts.items():
        scad = SCAD_DIR / info["file"]
        stl = STL_DIR / f"{name}.stl"
        if generate_stl(scad, stl, openscad):
            success += 1
        else:
            failed += 1

    print(f"\nDone: {success} generated, {failed} failed")

    if success > 0:
        print(f"\nPrint summary:")
        total_copies = 0
        for name, info in parts.items():
            stl = STL_DIR / f"{name}.stl"
            if stl.exists():
                print(f"  {name}.stl x{info['copies']}")
                total_copies += info["copies"]
        print(f"  Total parts: {total_copies}")
        print(f"\nBring the stl/ folder to the fab lab.")
        print(f"Settings: PLA, 0.2mm layers, 20-30% infill, no supports.")


if __name__ == "__main__":
    main()
