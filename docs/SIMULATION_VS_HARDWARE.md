# Simulation vs. Hardware — What Runs Today, What Needs a Body

**Last verified:** 2026-07-07 (worktree merge + re-verification session)

This is the honest boundary line for the Hand project: which parts of the stack
are actually exercised and passing in software right now, and which parts are
architecturally complete but have never touched physical reality. It exists so
nobody mistakes "the simulation converges" for "this is safe on a real arm."

**Rule that governs everything below:** simulation success is necessary, not
sufficient. Every current value, threshold, and recruitment weight in the
software is a *design estimate*. None of it has been validated on tissue. The
one question that matters most — is AI-initiated stimulation tolerable and safe
on a real body — cannot be answered by any test in this repo.

---

## Runs fully in software (verified this session, no hardware, numpy+scipy only)

| Component | Entry point | Verified behavior |
|---|---|---|
| EMG signal simulation | `python software/emg_simulator.py` | 8 synthetic channels, gesture-keyed activation, MAV/RMS features; classifies rest/fist/open/pinch/solidarity_fist. numpy only. |
| Phase-0 bidirectional control loop | `python software/control_loop.py` | Collaborative / autonomous / hybrid modes; AI initiates a gesture from a relaxed hand in sim. Toy-grade (see safety caveat below). |
| FES channel + recruitment model | `python -m python.fes.channels` (from `software/`) | 4-channel bank, signed recruitment matrix modeling surface-FES spillover. |
| **FES safety guard** | `python -m python.fes.safety` (from `software/`) | Every documented behavior fired: working-max clamp, comfort-ceiling clamp, non-biphasic rejection, absolute-max→e-stop latch, post-e-stop blocking, manual reset, ramp limiting, duty-cycle rest. |
| Per-user calibration workflow | `python -m python.fes.calibration` (from `software/`) | Ramps each channel to motor threshold + comfort ceiling against a simulated user, writes/reloads `models/profile_thomas_sim.json` (gitignored, regenerable). |
| **Closed-loop FES pipeline** | `python -m python.fes.pipeline` (from `software/`) | Drives RELAX→FIST; error converges 360°→~107° over 25 frames; FES commands fire on channels [0,2]; safety guard visibly clamps during ramp then passes (`sev=clamped`→`sev=ok`). Final pose T=57° I=67° M=65° R=60° P=54°. |
| Integration test suite | `python -m pytest software/python/tests/test_integration.py` | **19/19 passing** (~36 s) under normal load. Full synthetic chain + latency budgets + safety edge cases. |
| Onset detector, error computer | via tests / standalone | Predictive onset features, per-finger error with deadzone/clamp/tracking-loss handling. |

**Note on the latency tests:** three of the 19 tests are wall-clock latency
assertions (e.g. error computation < 1 ms). They pass under normal load but
flake under heavy system load — observed failing at ~7.6 ms with the box at load
average 24, then passing cleanly in isolation. They measure timing, not
correctness; treat a latency failure as "re-run on an idle machine" before
treating it as a regression.

---

## Runs in software but needs installed vision deps (needs a real webcam to be *useful*)

| Component | Needs | Status |
|---|---|---|
| `vision/error_computer.py` | numpy only | Fully testable headless; consumes tracker output but doesn't need the camera to unit-test. |
| `vision/hand_tracker.py` | `mediapipe`, `opencv-python` | Imports are guarded (try/except), so the FES package imports fine without them. The tracker only does anything against a **real webcam frame** — there is no synthetic-landmark path. A venv for these lives at `software/python/.venv`. **See the version pin caveat below.** |

Installing mediapipe/opencv makes the code *importable*, but it cannot be
*validated* without an actual camera pointed at an actual hand across real
lighting, skin tone, occlusion, and motion blur. That is a hardware-adjacent
milestone, not a simulation one.

> **⚠️ mediapipe version pin required.** `requirements.txt` specifies
> `mediapipe>=0.10.0`, which currently resolves to **mediapipe 0.10.35** (pulled
> alongside opencv 5.0.0). That build has **removed the legacy
> `mp.solutions.hands` API** that `hand_tracker.py:142` calls
> (`mp.solutions.hands.Hands(...)`) — `mediapipe.python` no longer exists, so
> constructing a `HandTracker` fails with `AttributeError: module 'mediapipe'
> has no attribute 'solutions'`. Before the camera phase, either **pin mediapipe
> to a `solutions`-era release** (e.g. `mediapipe==0.10.9`) or **migrate
> `hand_tracker.py` to the new MediaPipe Tasks API** (`mp.tasks.vision.HandLandmarker`).
> This does not affect any simulation path — the FES stack never imports the tracker.

---

## Needs real hardware to validate (unverified against physical reality)

- **EMG acquisition (BioAmp Candy ×4).** No real muscle signal has ever entered
  this codebase. `emg_processor.py`'s Butterworth bandpass + 60 Hz notch have
  correct coefficients but have only filtered synthetic sine+noise. The 60 Hz
  notch in particular can't be honestly validated without real mains artifact.
- **FES stimulation (NeuroStimDuino v3.0).** `neurostimduino.h`'s I2C driver has
  never talked to the device. Every current/threshold/recruitment number is a
  design estimate pending real per-user calibration.
- **Camera hand tracking.** Flexion-angle-from-landmark math is standard, but
  landmark noise / occlusion / lighting robustness is completely unknown here.
- **Arduino firmware.** `emg_acquisition.ino`, `stimulation_control/`,
  `closed_loop/closed_loop.ino` have not been compiled or flashed. The on-device
  MLP inference path (generated C header → `closed_loop.ino`) is unverified
  end-to-end. Firmware safety constants *do* match the Python `safety.py`
  numbers by inspection, but that consistency is unexercised.
- **The core research question.** Whether AI-initiated stimulation produces
  movement a real person experiences as tolerable, and whether the 10-week
  force-gradient progression in `safety/FORCE_GRADIENT_SAFETY.md` is actually
  safe on a real body. This is the one that matters and it cannot be simulated.

---

## ⚠️ Safety-consistency gap between the two software layers

The repo contains **two** stimulation-command generators with **different**
safety limits. This is an architecture hazard to resolve before any hardware
wiring:

- **Mature FES stack** (`software/python/fes/safety.py`) — the researched limits,
  grounded in `FORCE_GRADIENT_SAFETY.md`:
  - working max **5 mA**, absolute max **15 mA** (exceeding it *trips the e-stop*),
    500 µs pulse width, 3–50 Hz, 5 s max continuous, charge-per-phase ceiling,
    ramp limiting, mandatory duty-cycle rest, biphasic-only.
- **Phase-0 toy** (`software/ai_controller.py`, `MotorCommandGenerator`) — its own
  ad-hoc limits: `max_current = 25 mA` labeled "safe FES limit," with gesture
  patterns commanding **up to 20 mA per channel**. It does **not** route through
  `safety.py` at all.

**Consequence:** the Phase-0 loop's own numbers exceed the researched absolute
maximum. On the current mature stack those commands would be rejected and
e-stopped. The Phase-0 layer is a pure software toy and never reaches hardware
today, so this is not an *active* hazard — but the two layers must be reconciled
(Phase-0 either retired or forced through `safety.py`) before any code path can
command a real stimulator.

**Invariant to preserve:** no stimulation command should ever reach hardware
except through `fes/safety.py`.

---

## How to reproduce the software verification

```bash
# Phase-0 toy (numpy only)
python3 software/emg_simulator.py
python3 software/control_loop.py

# Mature FES stack — run as a package from the software/ directory
cd software
python3 -m python.fes.safety        # safety guard self-test
python3 -m python.fes.channels      # channel/recruitment model
python3 -m python.fes.calibration   # regenerates models/profile_thomas_sim.json
python3 -m python.fes.pipeline      # closed-loop RELAX->FIST convergence
python3 -m pytest python/tests/test_integration.py -q   # 19 tests (idle machine)

# Vision layer (needs the venv with mediapipe/opencv + a real camera)
software/python/.venv/bin/python -m python.vision.hand_tracker
```
