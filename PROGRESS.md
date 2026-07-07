# Hand Project — Progress Report

**Reviewed:** 2026-07-07
**Scope:** Everything built in worktree `cc-hand-fes` (branch `feature/camera-fes-simulation`), now committed to git (previously untracked — see the 2026-07-07 merge session log at the bottom).
**Bottom line:** Software stack for a camera-corrected, EMG-driven FES hand controller is complete and internally consistent, down to a simulated closed loop that converges on target gestures with no hardware attached. Nothing has touched real hardware yet. One real bug was found and fixed during this review (see below).

---

## What was built

### 1. Phase 0 — EMG/AI control simulation (Oct 2025, `software/*.py`)
The original proof-of-concept, hand-rolled and simple:
- `emg_simulator.py` — `EMGSimulator` (8 synthetic channels, gesture-keyed activation patterns, MAV/RMS/WL/ZC/SSC feature extraction) + `HandState` (joint-angle biomechanics, rule-based gesture classification).
- `ai_controller.py` — `GestureClassifier` (nearest-prototype classifier over 8 gestures including `solidarity_fist`) + `MotorCommandGenerator` (gesture → 8-channel stimulation pattern) + `AIController` with three control modes: **collaborative** (assist high-confidence human intent), **autonomous** (AI initiates when human is at rest), **hybrid** (switches between the two).
- `control_loop.py` — wires the above into a full bidirectional loop and runs three demo scenarios, including the key test: can the AI initiate movement from a relaxed hand with zero human input? (Answer, in simulation: yes.)
- `gesture_trainer.py` — synthetic dataset generator + ASCII pattern visualizer + a `LearningSimulator` that narrates, epoch by epoch, what learning to recognize gestures would "feel like" (this is exploratory/reflective writing, not a real training algorithm).

This layer works standalone (`python control_loop.py`) and needs no dependencies beyond numpy. It's a toy relative to the FES module below, but it's what proved the core idea was worth building further.

### 2. Signal processing & gesture recognition (Feb–Apr 2026, `software/python/signal_processing/`, `gesture_recognition/`)
- `emg_processor.py` — real filtering pipeline: 4th-order Butterworth bandpass (20–450Hz) + 60Hz notch (via scipy), sliding-window MAV/ZC/WL/SSC/RMS + mean-frequency (fatigue proxy) feature extraction, plus `EMGStreamReader` for the Arduino serial protocol (`EMG,ch0..ch3,mav0..mav3,timestamp`). **This is real DSP**, not a toy — it will work against actual Arduino serial data once hardware exists.
- `onset_detector.py` — predictive onset detection exploiting electromechanical delay: triggers on 3× baseline RMS, captures a 50ms post-onset window, extracts activation-order + dMAV/dt features so classification can happen ~50-100ms before visible movement (research-grounded: Gandolla et al. 2017). Fully self-contained, no hardware needed to exercise it.
- `gesture_model.py` — from-scratch NumPy MLP (16→32→16→5, manual forward/backprop, softmax + cross-entropy), 5-gesture vocabulary (RELAX/FIST/OPEN/POINT/WAVE), plus `export_arduino()` which serializes trained weights to a C header for on-device inference. This is legitimate hand-rolled ML — no numpy autograd shortcuts.
- `pretrain/emg2pose_pipeline.py` — downloads Meta's emg2pose dataset (193 users, 370 hours, 16-channel wristband), reduces to 4 channels (max-energy channel per group), extracts matching MAV/ZC/WL/SSC features, pretrains the MLP above, and exports both a `.npz` and an Arduino header. `calibrate.py` automatically loads these pretrained weights if present and fine-tunes in ~30 epochs instead of ~150 — the stated goal is cutting live calibration time from scratch-training to 2-3 minutes. **Note:** the 10-recording mini dataset (`data/emg2pose/emg2pose_dataset_mini/`) is downloaded and present, and `software/python/pretrain/weights/pretrained_emg2pose.npz` exists, so a real pretrain pass has been run at least once — but with only ~10 recordings this is closer to plumbing verification than a genuinely useful pretrained prior.

### 3. Camera vision layer (Apr 2026, `software/python/vision/`)
- `hand_tracker.py` — wraps MediaPipe Hands: 21-landmark extraction, per-finger flexion angle from the PIP joint angle (0°=extended, 90°=flexed), `HandTracker` context manager, `draw_hand()` for skeleton overlay, and a CLI standalone test mode with CSV logging. **MediaPipe and opencv-python are not installed in this environment** (verified: `pip show` reports both absent) — this module is architecturally complete but has never actually been run against a real camera in this workspace.
- `error_computer.py` — per-finger error signal: target pose (from a `GESTURE_TARGETS` table: RELAX/FIST/OPEN/POINT/WAVE, in degrees) minus actual pose from the tracker, with deadzone, max-error clamp, divergence-safety flagging, and exponential smoothing. Explicitly handles tracking loss (returns all-zero, `tracking_valid=False`) rather than guessing. This one is thoroughly unit-tested and runs standalone with no camera.

### 4. FES control stack (Apr 2026, `software/python/fes/` — the newest and most substantial layer)
This is the module that existed only as **untracked files in the worktree** and has now been copied into the main repo (`software/python/fes/{__init__,channels,mapping,safety,simulator,calibration,pipeline}.py`). It is the most mature part of the codebase:

- `channels.py` — `StimParams` (mirrors the Arduino `StimParams` struct exactly — current/pulse-width/frequency/duration/biphasic, so Python and firmware never disagree about safety numbers) and `ChannelBank`, an anatomical model of which stimulation channel recruits which fingers, with signed recruitment weights modeling the real spillover of surface FES (a flexor channel doesn't move "the index finger," it moves all fingers with tapering weight). Two presets: `two_channel` (what the $260 NeuroStimDuino can do today) and `four_channel` (adds thumb flex/extend for pinch/opposition).
- `mapping.py` — `FESMapper` projects desired per-finger movement onto channel activations using the recruitment matrix (since surface FES can't address individual fingers — this is physics, not a control-software gap, per `docs/TARGETING_AND_SELECTIVITY.md`), then a per-channel `RecruitmentCurve` maps activation → actual microamps between motor threshold and comfort ceiling. Two entry points: closed-loop (`from_correction`, consumes the vision layer's error signal) and open-loop (`from_target_pose`, for when there's no camera).
- `safety.py` — the software half of an explicitly-designed 8-layer safety system. Static hard limits mirror `neurostimduino.h` exactly (5mA working max, 15mA absolute max — trips e-stop, not just rejection). Runtime governors implement `safety/FORCE_GRADIENT_SAFETY.md`'s force-gradient requirement in code: ramp-rate limiting (current can't rise faster than 4000µA/s), per-user comfort ceiling from calibration, charge-per-phase ceiling (tissue safety, computed as clamping pulse width rather than current), duty-cycle/mandatory-rest tracking, and a manual-reset-only emergency-stop latch. Every clamp/rejection is reported as a structured `SafetyViolation`. This is a serious, stateful implementation, not a stub.
- `simulator.py` — `SimulatedStimulator` (drop-in stand-in for the real NeuroStimDuino driver interface) + `SimulatedHand` (first-order biomechanical model: current → recruitment-weighted drive → per-finger flexion, with a contraction time-constant lag and per-channel fatigue that accumulates under sustained drive and recovers at rest) + an ASCII terminal dashboard (`visualize_frame`) showing live channel currents and finger positions. Lets the whole loop run and be watched with zero hardware.
- `calibration.py` — per-user calibration workflow: ramps each channel's current to find motor threshold (first visible movement) and comfort ceiling (capped by a 5-phase training-progression schedule matching the safety doc's 10-week plan, from 30% to 70% of working max), records observed per-finger recruitment at the ceiling to refine the design-estimate weights in `channels.py`, and produces a JSON-serializable `UserProfile` that feeds both the mapper and the safety guard. `SimulatedProbe` runs this against `SimulatedHand` with per-channel discomfort thresholds, so the whole ramp-and-discover workflow is testable with no hardware.
- `pipeline.py` — `CameraFESPipeline`, the actual closed loop: observe pose → compute error → map to channel commands → gate through the safety guard → deliver via the stimulator → (in sim) get the resulting pose back and repeat. `build_sim_pipeline()` wires up a complete no-hardware instance, optionally seeded with a calibrated `UserProfile`.

### 5. Integration tests (`software/python/tests/test_integration.py`)
19 tests, **all passing** (`python -m pytest software/python/tests/test_integration.py -v` — 19 passed in ~6-18s). Covers the full synthetic signal chain (EMG → onset detection → classification → error → FES output), latency budgets (onset extraction <5ms, classification <10ms, error computation <1ms, full pipeline processing under the 50ms EMD budget), and safety edge cases: camera loss, sensor saturation, dead/zero signal, NaN handling, divergence flagging, deadzone, max-error clamping, rapid-onset refractory period, smoothing, camera-loss recovery. This is a genuinely useful regression net for a hardware-less phase.

### 6. Arduino firmware (`software/arduino/`)
- `emg_acquisition.ino` — 4-channel EMG read + MAV + serial protocol out.
- `stimulation_control/neurostimduino.h` — I2C driver for the NeuroStimDuino with the same hard safety limits as the Python `safety.py` (5mA/15mA/500µs/3-50Hz/5s), biphasic-only enforcement.
- `closed_loop/closed_loop.ino` — the on-device integration of EMG read + (auto-generated) gesture model + stimulation output, with a physical e-stop pin and confidence-threshold/debounce gating.
- **Not verified in this review** — no Arduino toolchain here to compile/flash. These are architecturally consistent with the Python safety numbers (same constants) but unexercised.

### 7. Docs
- `docs/CAMERA_INTEGRATION.md` — the architecture doc the vision + FES layers were built from (4-phase plan; phases 1-2 done in code, phase 3-4 partially done via `pipeline.py`/`calibration.py`).
- `docs/TARGETING_AND_SELECTIVITY.md` — grounds the whole recruitment-matrix design in the real physics of surface FES (why per-finger selectivity is a hard physical limit, not a software gap) and documents a genuine research stretch-goal (Temporal Interference Stimulation) that isn't implemented.
- `safety/FORCE_GRADIENT_SAFETY.md` — the safety protocol `safety.py`'s runtime governors and `calibration.py`'s phase-ceiling schedule directly implement.
- `hardware/SHOPPING_LIST.md` — current BOM ~$390-400 (BioAmp Candy ×4 EMG sensors $40, NeuroStimDuino v3.0 $260, Arduino Due $40, electrodes/mounts ~$50-60).
- `hardware/3d_models/*.scad` — OpenSCAD mounts (electrode clip, cable clip, electronics box, stim guide) — not verified to actually print/fit anything, just present.

---

## What works (verified this session)

- All 19 integration tests pass against the current code.
- The full simulated closed loop (`build_sim_pipeline()` → repeated `.step("FIST")`) actually converges: starting from rest, error drops from 360° to ~107° over 25 frames and finger flexion approaches the FIST target (measured T=57° I=67° M=65° R=60° P=54° against a ~70-85° target band) — with the safety guard visibly clamping/ramping in the process (`sev=clamped` → `sev=ok`).
- The safety guard's self-test demonstrates every documented behavior: normal pass-through, working-max clamp, comfort-ceiling clamp, non-biphasic rejection, absolute-max → e-stop latch, post-e-stop blocking, and manual reset.
- Calibration's self-test produces sensible per-channel thresholds/ceilings against a simulated user with per-channel tolerances, and round-trips through JSON save/load correctly.
- The onset detector correctly extracts a 24-feature vector within its 50ms window and stays under its 5ms extraction-latency budget.

## Bug found and fixed during this review

`software/python/fes/simulator.py`, `SimulatedStimulator.send()` (was line 84): iterated `for c in self.bank` (yielding `Channel` objects, which have `.index`) but indexed with `c.channel`, an attribute that doesn't exist on `Channel`. This meant **any use of the simulator with a hand attached crashed immediately** — including `pipeline.py`'s own `if __name__ == "__main__"` demo and, by extension, `build_sim_pipeline()` in general. The unit test suite didn't catch this because it exercises components individually rather than the wired-up `CameraFESPipeline`. Fixed to `c.index`; confirmed the pipeline demo now runs and converges (see above). This fix has been applied to the copy now living in the main repo; it was **not** applied back to the original untracked files in the worktree.

## What's stubbed / incomplete

- `emg_processor.py`'s `calibrate_baseline()` is a `pass`-only stub — the real baseline calibration logic referenced by its docstring was never written (a duplicate, working baseline mechanism does exist in `onset_detector.py` via `update_baseline_sample`, so this isn't blocking, but the two modules disagree on how baseline gets set).
- `gesture_trainer.py`'s "learning simulator" is explicitly narrative/reflective, not a real training loop — it interpolates a canned accuracy curve and prints hand-written prose about what each accuracy band "feels like." Fun to read, not functional ML.
- Temporal Interference Stimulation (docs/TARGETING_AND_SELECTIVITY.md's "mad science stretch goal") is documented as a research direction only — no code.
- The emg2pose pretraining has apparently only been run against the *mini* dataset (10 recordings, not the full 193-user corpus), so the "pretrained weights give a massive head start" claim in `calibrate.py`'s comments is aspirational relative to what's actually in `pretrained_emg2pose.npz` right now.
- No CI config anywhere in the repo — the 19-test suite is real but only runs when someone remembers to invoke pytest manually.

## What needs hardware to validate

Everything past the simulation boundary is unverified against physical reality:
- **EMG sensors** (BioAmp Candy) haven't been used to acquire a single real muscle signal in this codebase — `emg_processor.py`'s bandpass/notch filters have real coefficients but have only ever filtered synthetic sine+noise.
- **NeuroStimDuino stimulation** — `neurostimduino.h`'s I2C driver has never talked to real hardware; all current numbers (motor threshold, comfort ceiling, recruitment weights) in `channels.py`/`calibration.py` are design estimates pending real per-user calibration.
- **Camera tracking** — MediaPipe isn't even installed in this environment; `hand_tracker.py` has never processed a real webcam frame here. Flexion-angle-from-landmark math is standard and should work, but landmark noise/occlusion/lighting robustness is completely unknown.
- **The core research question** — whether AI-initiated stimulation produces movement Thomas experiences as tolerable, and whether the 10-week force-gradient progression in `FORCE_GRADIENT_SAFETY.md` is actually safe on a real body — is entirely untested. This is the one that matters most and it can't be simulated away.
- **Arduino firmware** hasn't been compiled or flashed; the on-device MLP inference path (`export_arduino()`'s generated C header, consumed by `closed_loop.ino`) is unverified end-to-end.

## Next steps (in likely priority order)

1. **Hardware acquisition** — BOM is well-researched and priced (~$390-400); this is a funding/ordering blocker, not a technical one.
2. **First real EMG signal** — get BioAmp Candy sensors on forearm, confirm `emg_processor.py`'s filters behave sensibly on real muscle noise (60Hz notch especially, since that's a real-world artifact the simulator doesn't reproduce authentically).
3. **Camera-only phase** (Phase 1 per `docs/CAMERA_INTEGRATION.md`) — install mediapipe/opencv, mount a webcam, verify `hand_tracker.py`'s flexion angles against a real hand across lighting/skin-tone/angle before any stimulation is involved. Zero risk, high information value.
4. **NeuroStimDuino bench test** — verify the I2C driver against the real device with a dummy/resistive load before any human contact, per `hardware/SHOPPING_LIST.md`'s own safety notes.
5. **Real per-user calibration run** — once hardware exists, run `calibration.py`'s `run_calibration()` against a real `MovementProbe` (not `SimulatedProbe`) to get Thomas's actual thresholds/ceilings, replacing the design-estimate weights in `channels.py`.
6. **Phase 1 of `FORCE_GRADIENT_SAFETY.md`'s 10-week progression** — single-finger twitch at 10% of voluntary baseline, only after 1-5 are solid.
7. Consider wiring the 19-test suite into a pre-commit hook or CI, since it's currently the only thing preventing silent regressions like the `simulator.py` bug found above.

---

## Session log — 2026-07-07: worktree merge + re-verification

The prior review (above) had left the whole FES stack as **untracked files** —
present in the working checkout but never committed. `git ls-files
software/python/fes/` returned nothing; the module existed only on disk. This
session put it into git and independently re-verified the simulation.

**Merge.** The `software/python/fes/` module (`__init__`, `channels`, `mapping`,
`safety`, `simulator`, `calibration`, `pipeline`) is now committed. The version
committed is the **corrected** one (`simulator.py` line 84 uses `c.index`, the
attribute `Channel` actually has). Note: the original `cc-hand-fes` worktree
still holds the **buggy** pre-fix copy (`c.channel`); it was deliberately not the
source. `models/profile_thomas_sim.json` is gitignored generated output and is
**not** committed — it regenerates from `python -m python.fes.calibration`
(verified: reproduces thresholds 1500/1750/2000/2250 µA, ceilings all 2750 µA).

**Re-verification (this session, independent of the prior review):**
- `software/emg_simulator.py` — runs, produces MAV/RMS features, classifies all
  five demo gestures. numpy only.
- `software/control_loop.py` — runs all three Phase-0 scenarios to completion
  (collaborative / autonomous / hybrid), exit 0.
- `python -m python.fes.safety` — self-test exercises every safety behavior
  (clamp, comfort-ceiling, non-biphasic reject, absolute-max→e-stop, post-e-stop
  block, reset).
- `python -m python.fes.pipeline` — closed loop drives RELAX→FIST, error
  converges 360°→~107° over 25 frames, FES fires on channels [0,2], safety
  guard transitions `sev=clamped`→`sev=ok`. Final pose T=57° I=67° M=65° R=60°
  P=54°.
- `python -m python.fes.calibration` — full ramp-and-discover workflow, JSON
  save/reload round-trip OK.
- `pytest python/tests/test_integration.py` — **19/19 pass** under normal load.

**New findings this session:**
1. **The FES stack was never committed** (fixed by this session's commit). The
   previous PROGRESS.md said "merged into the main checkout," but that only meant
   copied to the working tree, not tracked. Now genuinely in git.
2. **Safety-consistency gap between the two software layers** — documented in
   full in `docs/SIMULATION_VS_HARDWARE.md`. Short version: the Phase-0 toy
   (`ai_controller.py`) uses a 25 mA "safe limit" and commands up to 20 mA/channel
   without routing through `safety.py`, while the researched mature stack caps at
   5 mA working / 15 mA absolute (e-stop). The Phase-0 layer never reaches
   hardware, so it's not an active hazard, but the two must be reconciled before
   any hardware wiring. Invariant to hold: **nothing commands a real stimulator
   except through `fes/safety.py`.**
3. **Latency tests are load-sensitive.** Three of the 19 tests are wall-clock
   timing assertions; they failed at ~7.6 ms (budget 1 ms) with the box at load
   average 24 during a heavy dependency install, then passed in isolation. Not a
   regression — but reinforces next-step #7 (CI should run them on an idle
   runner, or convert them to relative/statistical budgets).
4. **mediapipe version break in the vision layer.** `requirements.txt`'s
   `mediapipe>=0.10.0` resolves to 0.10.35 (with opencv 5.0.0), which removed the
   legacy `mp.solutions.hands` API that `hand_tracker.py:142` uses — constructing
   a `HandTracker` raises `AttributeError: module 'mediapipe' has no attribute
   'solutions'`. Simulation is unaffected (the FES stack never imports the
   tracker). Fix before the camera phase: pin mediapipe to a `solutions`-era
   release (~0.10.9) or migrate to the MediaPipe Tasks API. Documented in
   `docs/SIMULATION_VS_HARDWARE.md`.

**Environment note.** This box is PEP 668 externally-managed; numpy/scipy are
system packages. mediapipe/opencv (vision layer only) were installed into a
dedicated venv at `software/python/.venv` — the simulation path above needs
none of them.

**New doc:** `docs/SIMULATION_VS_HARDWARE.md` — the explicit software/hardware
boundary and the safety-layer reconciliation requirement.
