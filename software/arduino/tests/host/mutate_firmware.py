#!/usr/bin/env python3
"""Break the stimulator wrapper on purpose, one way at a time, and confirm a named host test fails.

    python3 mutate_firmware.py            exit 0 only if the baseline passes and every mutant is killed
    python3 mutate_firmware.py --list
    python3 mutate_firmware.py --only F0  mutants whose names start with this

A mutant counts as killed only when it compiles and the test binary exits 1 naming a failing test. One that does
not compile is an error, not a kill. Every anchor must match exactly once.

Mutants left out as equivalent (no test can tell them apart, because another guard covers the same case):
- resetAfterStop() clearing _paramsValid: emergencyStop() already clears it, and setParams() refuses while latched.
- stopChannel() returning false when the board sends nothing: read() then returns -1, which is not "stopped" either.
- calibrateThreshold() returning at once on a latch: the next setParams() refuses while latched and returns -1.
- startStim() refusing while latched: an emergency stop also disables the output and drops the parameters, and
  setOutputEnabled(true) and setParams() both refuse while latched, so startStim() already refuses. Kept as a
  second guard.
- pulsePattern() returning at once on a latch: the next setParams() refuses while latched; the only difference is
  one gap of delay.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOST = Path(__file__).resolve().parent
ARDUINO = HOST.parents[1]
HDR = "stimulation_control/neurostimduino.h"

MUTANTS = [
    ("F01 above the absolute limit is an emergency stop", HDR,
     '      emergencyStop();\n      _lastError = "Current exceeds absolute maximum',
     '      _lastError = "Current exceeds absolute maximum'),
    ("F02 the absolute limit is checked before the working limit (the 2026-02 bug)", HDR,
     "    if (params.current_ua > ABSOLUTE_MAX_UA || params.current_ua < -ABSOLUTE_MAX_UA) {",
     '    if (params.current_ua > MAX_CURRENT_UA || params.current_ua < 0) { _lastError = "x"; return false; }\n'
     "    if (params.current_ua > ABSOLUTE_MAX_UA || params.current_ua < -ABSOLUTE_MAX_UA) {"),
    ("F03 a large negative current is an emergency stop", HDR,
     " || params.current_ua < -ABSOLUTE_MAX_UA) {", ") {"),
    ("F04 above the working limit is refused", HDR,
     "    if (params.current_ua < 0 || params.current_ua > MAX_CURRENT_UA) {", "    if (params.current_ua < 0) {"),
    ("F05 a negative current is refused", HDR,
     "    if (params.current_ua < 0 || params.current_ua > MAX_CURRENT_UA) {",
     "    if (params.current_ua > MAX_CURRENT_UA) {"),
    ("F06 the pulse width ceiling", HDR, " || params.pulse_width_us > MAX_PULSE_WIDTH_US) {", ") {"),
    ("F07 the pulse width floor", HDR, "params.pulse_width_us < MIN_PULSE_WIDTH_US || ", ""),
    ("F08 the frequency ceiling", HDR, " || params.frequency_hz > MAX_FREQUENCY_HZ) {", ") {"),
    ("F09 a duration of 0 is refused", HDR, "params.duration_ms == 0 || ", ""),
    ("F10 the duration ceiling", HDR, " || params.duration_ms > MAX_STIM_DURATION_MS) {", ") {"),
    ("F11 biphasic only", HDR, "    if (!params.biphasic) {", "    if (false) {"),
    ("F12 two channels only", HDR, "    if (params.channel > 1) {", "    if (params.channel > 2) {"),
    ("F13 a refused set leaves nothing to start", HDR,
     "    _paramsValid = false;                  // whatever happens next", "    // removed"),
    ("F14 start needs accepted parameters", HDR, "    if (!_paramsValid) {", "    if (false) {"),
    ("F15 start needs enabled output", HDR,
     '    if (!_enabled) {\n      _lastError = "Output not enabled";', '    if (false) {\n      _lastError = "Output not enabled";'),
    ("F17 setParams refuses while latched", HDR,
     '    if (_latched) {\n      _lastError = "Latched by an emergency stop";\n      return false;\n    }\n    if (!validateParams',
     "    if (!validateParams"),
    ("F18 enabling refuses while latched", HDR, "    if (enabled && _latched) {", "    if (false) {"),
    ("F19 the emergency stop sends EOFF first", HDR,
     "    send1(NSD_CMD_EOFF);\n    send2(NSD_CMD_STOP, 1);", "    send2(NSD_CMD_STOP, 1);"),
    ("F20 the emergency stop latches", HDR,
     '    _latched = true;\n    _lastError = "Emergency stop activated";', '    _lastError = "Emergency stop activated";'),
    ("F21 a stop counts only when the board confirms it", HDR,
     "    return NSD_WIRE.read() == NSD_STOP_CONFIRMED;", "    return true;"),
    ("F22 a stop whose write is not acknowledged does not count", HDR,
     "    if (send2(NSD_CMD_STOP, ch) != 0) return false;", "    send2(NSD_CMD_STOP, ch);"),
    ("F23 an unconfirmed stop is escalated", HDR,
     '      emergencyStop();\n      _lastError = "The board did not confirm', '      _lastError = "The board did not confirm'),
    ("F24 the lease covers the whole duration (rounds up)", HDR,
     "(uint8_t)((_currentParams.duration_ms + 999) / 1000)", "(uint8_t)(_currentParams.duration_ms / 1000)"),
    ("F25 the continuous flag is never set", HDR,
     "    send4(NSD_CMD_STIM, _currentParams.channel + 1, lease_s, 0);",
     "    send4(NSD_CMD_STIM, _currentParams.channel + 1, lease_s, 1);"),
    ("F26 API channel n is wire channel n+1 (parameters)", HDR,
     "    uint8_t ch = params.channel + 1;", "    uint8_t ch = params.channel;"),
    ("F27 API channel n is wire channel n+1 (stim)", HDR,
     "    send4(NSD_CMD_STIM, _currentParams.channel + 1,", "    send4(NSD_CMD_STIM, _currentParams.channel,"),
    ("F28 current rounds down to the board's steps", HDR,
     "(uint8_t)(params.current_ua / NSD_UA_PER_STEP)",
     "(uint8_t)((params.current_ua + NSD_UA_PER_STEP - 1) / NSD_UA_PER_STEP)"),
    ("F29 the Due uses Wire1", HDR, "  #define NSD_WIRE Wire1", "  #define NSD_WIRE Wire"),
    ("F30 stimulation stops at the end of its duration", HDR,
     "    if (_stimulating && millis() - _stimStartTime >= _currentParams.duration_ms) {", "    if (false) {"),
    ("F31 running past the maximum is an emergency stop", HDR,
     "    if (_stimulating && millis() - _stimStartTime > MAX_STIM_DURATION_MS) {", "    if (false) {"),
    ("F32 safety is not ok while latched", HDR, "    return !_latched;", "    return true;"),
    ("F33 disabling the output stops a running stimulation", HDR,
     "    if (!enabled) {\n      stopStim();\n    }\n", ""),
    ("F35 calibration climbs one step at a time", HDR,
     "      p.current_ua += NSD_UA_PER_STEP;", "      p.current_ua += 2 * NSD_UA_PER_STEP;"),
    ("F36 calibration stops on any other key", HDR,
     "        return -1;                           // any other key stops the search", ""),
    ("F37 every write waits for the board", HDR, "    delay(NSD_WRITE_SETTLE_MS);\n", ""),
    ("F38 begin stops both channels", HDR,
     "    stopChannel(1);\n    stopChannel(2);\n    enableChannels(false);", "    enableChannels(false);"),
    ("F39 begin turns ramping on", HDR, "    send3(NSD_CMD_RAMP, 0xFF, 1);", "    send3(NSD_CMD_RAMP, 0xFF, 0);"),
    ("F40 begin fails when no board answers", HDR,
     '    if (!isConnected()) {\n      _lastError = "Device not found', '    if (false) {\n      _lastError = "Device not found'),
    ("F41 the pulse width goes low byte first", HDR,
     "params.pulse_width_us & 0xFF, (params.pulse_width_us >> 8) & 0xFF",
     "(params.pulse_width_us >> 8) & 0xFF, params.pulse_width_us & 0xFF"),
    ("F42 disabling the output disables both channels", HDR,
     "    send3(NSD_CMD_ENAB, 2, on ? 1 : 0);\n", ""),
]


def build_and_run(root: Path):
    host = root / "tests" / "host"
    b = subprocess.run(["make", "-s", "-C", str(host), "test_neurostimduino"], capture_output=True, text=True)
    if b.returncode != 0:
        return "ERROR(build)", b.stderr.strip().splitlines()[-1:] if b.stderr else ""
    r = subprocess.run([str(host / "test_neurostimduino")], capture_output=True, text=True, timeout=60)
    failed = re.findall(r"^FAIL (\S+):", r.stdout, re.M)
    if r.returncode == 0:
        return "SURVIVED", ""
    if r.returncode == 1 and failed:
        return "killed", failed[0]
    return f"ERROR({r.returncode})", "no named failing test"


def copy(dst: Path):
    shutil.copytree(ARDUINO / "stimulation_control", dst / "stimulation_control")
    shutil.copytree(HOST, dst / "tests" / "host", ignore=shutil.ignore_patterns("test_neurostimduino", "__pycache__"))


def main():
    if "--list" in sys.argv:
        for m in MUTANTS:
            print(m[0])
        return 0
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    chosen = [m for m in MUTANTS if m[0].startswith(tuple(only.split(",")))] if only else MUTANTS
    with tempfile.TemporaryDirectory() as t:
        copy(Path(t))
        verdict, why = build_and_run(Path(t))
        if verdict != "SURVIVED":
            print(f"baseline FAILED: {verdict} {why}")
            return 1
    bad = 0
    for name, rel, old, new in chosen:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            copy(root)
            f = root / rel
            src = f.read_text()
            n = src.count(old)
            if n != 1:
                print(f"ANCHOR     {name}: found {n}x")
                bad += 1
                continue
            f.write_text(src.replace(old, new))
            verdict, why = build_and_run(root)
            print(f"{verdict:<10} {name}" + (f"  <- {why}" if why else ""))
            bad += verdict != "killed"
    print(f"\nbaseline ok; {len(chosen)} mutants run, {bad} survived, errored or unanchored")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
