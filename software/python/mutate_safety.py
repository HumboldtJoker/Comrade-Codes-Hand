#!/usr/bin/env python3
"""Break the Hand's software safety gates on purpose, one at a time, and confirm a named test fails.

    python3 python/mutate_safety.py            (from software/) exit 0 only if every mutant is killed
    python3 python/mutate_safety.py --only S1  mutants whose names start with this

Rules, as in the firmware harness (software/arduino/tests/host/mutate_firmware.py): the unmutated suite must pass
first; a mutant counts as killed only when pytest exits 1 and names a failing test; every anchor matches once.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SOFTWARE = Path(__file__).resolve().parents[1]
G, L = "python/fes/safety.py", "python/fes/safety_layers.py"
TESTS = ["python/tests/test_safety_guard.py", "python/tests/test_safety_layers.py"]

MUTANTS = [
    # ---- the guard (safety.py) -------------------------------------------------------------------------------------
    ("S01 the latch zeroes everything", G, "        if self._estopped:\n", "        if False:\n"),
    ("S02 biphasic only", G, "        if not p.biphasic:\n", "        if False:\n"),
    ("S03 above the absolute limit latches the stop", G,
     '            self.emergency_stop("current exceeded absolute maximum")\n', ""),
    ("S04 the absolute check runs before the working clamp", G,
     "        if abs(p.current_ua) > ABSOLUTE_MAX_UA:",
     "        if p.current_ua > MAX_CURRENT_UA:\n            p.current_ua = MAX_CURRENT_UA\n"
     "        if abs(p.current_ua) > ABSOLUTE_MAX_UA:"),
    ("S05 the absolute check covers negative currents", G,
     "        if abs(p.current_ua) > ABSOLUTE_MAX_UA:", "        if p.current_ua > ABSOLUTE_MAX_UA:"),
    ("S06 negative current is refused", G, "        if p.current_ua < 0:\n", "        if False:\n"),
    ("S07 the working clamp", G, "        if p.current_ua > MAX_CURRENT_UA:\n", "        if False:\n"),
    ("S08 the comfort ceiling", G, "        if p.current_ua > ceiling:\n", "        if False:\n"),
    ("S09 the pulse width clamp", G, "        if p.pulse_width_us > MAX_PULSE_WIDTH_US:\n", "        if False:\n"),
    ("S10 the frequency range", G,
     "        if p.is_active() and not (MIN_FREQUENCY_HZ <= p.frequency_hz <= MAX_FREQUENCY_HZ):",
     "        if p.is_active() and not (MIN_FREQUENCY_HZ <= p.frequency_hz):"),
    ("S11 the duration clamp", G, "        if p.duration_ms > MAX_STIM_DURATION_MS:\n", "        if False:\n"),
    ("S12 the charge ceiling", G,
     "        if p.charge_per_phase_uc() > self.max_charge_per_phase_uc and p.current_ua > 0:",
     "        if False:"),
    ("S13 the ramp limit", G, "        if rise > max_step:\n", "        if False:\n"),
    ("S14 the forced rest", G,
     "        if st.continuous_on_s >= self.max_continuous_on_s - _TIME_EPS and p.is_active():", "        if False:"),
    ("S15 the forced rest counts the last tick (time drift)", G,
     "        if st.continuous_on_s >= self.max_continuous_on_s - _TIME_EPS and p.is_active():",
     "        if st.continuous_on_s >= self.max_continuous_on_s and p.is_active():"),
    ("S16 a rest restores the duty budget only when long enough", G,
     "            if st.resting_s >= self.min_rest_after_on_s - _TIME_EPS:", "            if True:"),
    ("S17 a field that is not a finite number is refused", G,
     '        if not all(_is_number(getattr(p, f)) for f in ("current_ua", "pulse_width_us", "frequency_hz", "duration_ms")) \\\n'
     "                or not isinstance(p.current_ua, numbers.Integral):",
     "        if not isinstance(p.current_ua, numbers.Integral):"),
    ("S18 the current is a whole number", G,
     "                or not isinstance(p.current_ua, numbers.Integral):", "                or False:"),
    ("S19 a bool is not a number", G, "    return not isinstance(x, bool) and isinstance(x, numbers.Real)",
     "    return isinstance(x, numbers.Real)"),
    ("S20 reset clears the latch", G, "Deliberately manual per protocol.\"\"\"\n        self._estopped = False\n",
     "Deliberately manual per protocol.\"\"\"\n"),
    # ---- the layers (safety_layers.py) ------------------------------------------------------------------------------
    ("L01 a missing reading is unavailable", L,
     "        if isinstance(x, bool) or not isinstance(x, numbers.Real) or not math.isfinite(x):",
     "        if not isinstance(x, numbers.Real) or not math.isfinite(x):"),
    ("L02 a non-finite reading is unavailable", L,
     "        if isinstance(x, bool) or not isinstance(x, numbers.Real) or not math.isfinite(x):",
     "        if isinstance(x, bool) or not isinstance(x, numbers.Real):"),
    ("L03 layer 4 stops on an unavailable reading", L,
     '        if _unavailable(emg_amplitude_uv):\n            return _stop_unavailable("emg_feedback")', ""),
    ("L04 layer 5 stops on an unavailable current", L,
     '        if _unavailable(fes_current_ua):\n            return _stop_unavailable("fatigue")\n', ""),
    ("L05 layer 7 stops on an unavailable error", L,
     '        if _unavailable(total_error_deg):\n            return _stop_unavailable("camera_divergence")', ""),
    ("L06 layer 8 stops on an unavailable reading", L,
     '        if _unavailable(emg_between_pulses_uv):\n            return _stop_unavailable("human_override")', ""),
    ("L07 layer 4: no response stops at the patience limit", L,
     "            if self._no_response_count >= self.no_response_patience:", "            if False:"),
    ("L08 layer 4: an excessive response stops", L,
     "            if self._excessive_count >= self.excessive_patience:", "            if False:"),
    ("L09 layer 4: an excessive response halves first", L, "                scale=0.5,\n            )\n\n        self._no_response_count = 0",
     "                scale=1.0,\n            )\n\n        self._no_response_count = 0"),
    ("L10 layer 5: severe fatigue stops", L, "        if fatigue_level < self.severe_fatigue_threshold:", "        if False:"),
    ("L11 layer 5: fatigue reduces", L, "        if fatigue_level < self.fatigue_threshold:", "        if False:"),
    ("L12 layer 5: the reduction has a floor", L, "            scale = max(0.3, fatigue_level)", "            scale = fatigue_level"),
    ("L13 layer 7: the error computer's flag stops", L, "        if safety_limited:\n", "        if False:\n"),
    ("L14 layer 7: divergence stops at the cycle limit", L,
     "            if self._diverging_count >= self.max_divergence_cycles:", "            if False:"),
    ("L15 layer 7: only a growing error counts", L,
     "        if trend > 0 and total_error_deg > self.divergence_threshold_deg:",
     "        if total_error_deg > self.divergence_threshold_deg:"),
    ("L16 layer 8: voluntary effort suppresses completely", L, "    suppress_scale: float = 0.0", "    suppress_scale: float = 0.5"),
    ("L17 the stack: one stop stops everything", L, "            if r.action == SafetyAction.STOP:", "            if False:"),
    ("L18 the stack: reductions multiply", L, "                scale *= r.scale", "                scale = min(scale, 1.0)"),
]


def run_suite(cwd: Path):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS], cwd=cwd,
                       capture_output=True, text=True, timeout=300)
    failed = re.findall(r"^FAILED (\S+)", r.stdout, re.M)
    errored = bool(re.search(r"^ERROR ", r.stdout, re.M) or re.search(r"errors? during collection", r.stdout))
    if r.returncode == 0:
        return "SURVIVED", ""
    if r.returncode == 1 and failed and not errored:
        return "killed", failed[0].split("::")[-1]
    return f"ERROR({r.returncode})", "collection error" if errored else "no named failing test"


def copy(dst: Path):
    shutil.copytree(SOFTWARE / "python", dst / "python", ignore=shutil.ignore_patterns("__pycache__", ".venv", "*.npz"))
    shutil.copytree(SOFTWARE / "arduino" / "stimulation_control", dst / "arduino" / "stimulation_control")


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
    chosen = [m for m in MUTANTS if m[0].startswith(tuple(only.split(",")))] if only else MUTANTS
    with tempfile.TemporaryDirectory() as t:
        copy(Path(t))
        v, why = run_suite(Path(t))
        if v != "SURVIVED":
            print(f"baseline FAILED: {v} {why}")
            return 1
    bad = 0
    for name, rel, old, new in chosen:
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            copy(root)
            f = root / rel
            src = f.read_text()
            if src.count(old) != 1:
                print(f"ANCHOR     {name}: found {src.count(old)}x")
                bad += 1
                continue
            f.write_text(src.replace(old, new))
            v, why = run_suite(root)
            print(f"{v:<10} {name}" + (f"  <- {why}" if why else ""))
            bad += v != "killed"
    print(f"\nbaseline ok; {len(chosen)} mutants run, {bad} survived, errored or unanchored")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
