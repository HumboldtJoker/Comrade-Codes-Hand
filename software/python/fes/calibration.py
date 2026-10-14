"""
calibration.py — User-specific FES calibration workflow.

Every body responds differently to stimulation: electrode placement, skin
impedance, muscle depth, and tolerance all vary. The control system is only as
good as its per-user map, so before any functional use we calibrate each
channel to the individual.

For each channel we ramp current upward in small steps and watch what the hand
actually does (camera ground truth, per docs/CAMERA_INTEGRATION.md Phase 4). We
find two currents that define that channel's recruitment curve:

  motor threshold — the first current that produces visible finger movement.
                    Below it, stimulation is wasted (and just uncomfortable).
  comfort ceiling — the strongest current the user tolerates, hard-capped by
                    the force-gradient PHASE limit (safety/FORCE_GRADIENT_SAFETY.md):
                    early phases never let the ceiling rise near the muscle's
                    true maximum. Progression is earned session by session.

We also record the OBSERVED per-finger response at the ceiling, which refines
the channel's recruitment weights for this user (the design-estimate weights in
channels.py are just a starting point).

The ramp needs to observe movement. `MovementProbe` abstracts that: `SimulatedProbe`
drives a SimulatedHand (no hardware), while a hardware probe would stimulate and
read the MediaPipe HandTracker. Same workflow either way.

Output is a `UserProfile` (JSON-serializable) that feeds directly into the
FESMapper (recruitment curves) and the SafetyGuard (comfort ceilings).
"""
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Tuple

import numpy as np

from ..vision.hand_tracker import Finger, FingerAngles
from .channels import ChannelBank, StimParams, MAX_FLEXION_DEG
from .mapping import RecruitmentCurve, REST_FLEXION_DEG
from .safety import MAX_CURRENT_UA
from .simulator import SimulatedHand


# Force-gradient progression: the comfort ceiling for each channel is capped at
# this fraction of the conservative working maximum, by training phase. Start
# low, expand only as safety is confirmed (FORCE_GRADIENT_SAFETY.md §4).
PHASE_CEILING_FRACTION = {1: 0.30, 2: 0.45, 3: 0.55, 4: 0.65, 5: 0.70}

# A finger is "moving" once its flexion changes this many degrees from rest.
MOVEMENT_THRESHOLD_DEG = 6.0


@dataclass
class CalibrationConfig:
    start_ua: int = 500
    step_ua: int = 250
    settle_frames: int = 6      # timesteps to let the muscle reach steady state
    dt_s: float = 0.05
    phase: int = 1              # training phase -> ceiling cap
    movement_threshold_deg: float = MOVEMENT_THRESHOLD_DEG

    def phase_ceiling_ua(self) -> int:
        frac = PHASE_CEILING_FRACTION.get(self.phase, 0.30)
        return int(frac * MAX_CURRENT_UA)


class MovementProbe(Protocol):
    """Stimulates one channel and reports the resulting hand movement."""

    def probe(self, channel: int, current_ua: int,
              settle_frames: int, dt_s: float) -> Tuple[FingerAngles, bool]:
        """Return (finger flexion delta from rest, user_discomfort_flag)."""
        ...


@dataclass
class SimulatedProbe:
    """MovementProbe backed by a SimulatedHand — calibration with no hardware.

    `tolerance_ua` models where the simulated user reports discomfort per
    channel, so the ceiling search terminates realistically rather than always
    hitting the phase cap.
    """
    hand: SimulatedHand
    tolerance_ua: Dict[int, int] = field(default_factory=dict)
    default_tolerance_ua: int = 4200

    def probe(self, channel: int, current_ua: int,
              settle_frames: int, dt_s: float) -> Tuple[FingerAngles, bool]:
        self.hand.relax()
        pose = None
        cmd = {channel: StimParams(channel=channel, current_ua=current_ua,
                                   pulse_width_us=250, frequency_hz=30)}
        # Zero the other channels for a clean single-channel measurement.
        for ch in self.hand.bank:
            cmd.setdefault(ch.index, StimParams(channel=ch.index, current_ua=0))
        for _ in range(settle_frames):
            pose = self.hand.step(cmd, dt_s)
        delta = FingerAngles(*[
            float(pose.finger_angles.as_array()[int(f)] - REST_FLEXION_DEG)
            for f in Finger
        ])
        tol = self.tolerance_ua.get(channel, self.default_tolerance_ua)
        return delta, current_ua > tol


@dataclass
class UserProfile:
    """Per-user calibration result. JSON-serializable.

    Feeds the FESMapper (`recruitment_curves`) and the SafetyGuard
    (`comfort_ceilings`). `observed_recruitment[channel][finger_name]` is the
    measured per-finger response used to refine the mapping for this user.
    """
    user_id: str
    channel_names: Dict[int, str]
    thresholds_ua: Dict[int, int]
    ceilings_ua: Dict[int, int]
    pulse_width_us: int
    frequency_hz: int
    phase: int
    observed_recruitment: Dict[int, Dict[str, float]] = field(default_factory=dict)
    timestamp: str = ""
    notes: str = ""

    def recruitment_curves(self) -> Dict[int, RecruitmentCurve]:
        return {
            ch: RecruitmentCurve(
                threshold_ua=self.thresholds_ua[ch],
                ceiling_ua=self.ceilings_ua[ch],
                pulse_width_us=self.pulse_width_us,
                frequency_hz=self.frequency_hz,
            )
            for ch in self.thresholds_ua
        }

    def comfort_ceilings(self) -> Dict[int, int]:
        return dict(self.ceilings_ua)

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)
        return path

    @classmethod
    def load(cls, path: Path) -> "UserProfile":
        with open(path) as f:
            data = json.load(f)
        # JSON keys are strings; restore int channel keys.
        for key in ("channel_names", "thresholds_ua", "ceilings_ua",
                    "observed_recruitment"):
            data[key] = {int(k): v for k, v in data[key].items()}
        return cls(**data)


def calibrate_channel(
    probe: MovementProbe,
    channel: int,
    config: CalibrationConfig,
    verbose: bool = True,
) -> Optional[Dict]:
    """Ramp one channel to find its motor threshold and comfort ceiling.

    Returns a dict with threshold_ua, ceiling_ua, and observed per-finger
    response at the ceiling — or None if no movement was ever elicited within
    the phase cap (e.g. bad electrode contact).
    """
    phase_cap = config.phase_ceiling_ua()
    threshold: Optional[int] = None
    ceiling: Optional[int] = None
    last_delta: Optional[FingerAngles] = None

    current = config.start_ua
    while current <= phase_cap:
        delta, discomfort = probe.probe(channel, current,
                                        config.settle_frames, config.dt_s)
        max_move = float(np.max(np.abs(delta.as_array())))

        if threshold is None and max_move >= config.movement_threshold_deg:
            threshold = current
            if verbose:
                print(f"    motor threshold: {current}uA (moved {max_move:.1f}°)")

        if discomfort:
            # Back off one step: the ceiling is the last comfortable current.
            ceiling = max(threshold or config.start_ua, current - config.step_ua)
            if verbose:
                print(f"    discomfort at {current}uA -> ceiling {ceiling}uA")
            break

        last_delta = delta
        ceiling = current
        current += config.step_ua

    if threshold is None:
        if verbose:
            print(f"    no movement up to phase cap {phase_cap}uA — check electrodes")
        return None

    # Ensure a usable span even if discomfort came right after threshold.
    ceiling = max(ceiling or threshold, threshold + config.step_ua)
    ceiling = min(ceiling, phase_cap)

    observed = {}
    if last_delta is not None:
        # Normalize the observed movement into 0..1 recruitment weights.
        arr = np.clip(last_delta.as_array() / (MAX_FLEXION_DEG - REST_FLEXION_DEG), 0, 1)
        observed = {f.name: round(float(arr[int(f)]), 3) for f in Finger}

    if verbose:
        print(f"    ceiling: {ceiling}uA (phase {config.phase} cap {phase_cap}uA)")

    return {"threshold_ua": threshold, "ceiling_ua": ceiling,
            "observed_recruitment": observed}


def run_calibration(
    probe: MovementProbe,
    bank: ChannelBank,
    user_id: str = "thomas",
    config: Optional[CalibrationConfig] = None,
    verbose: bool = True,
) -> UserProfile:
    """Calibrate every channel in the bank and build a UserProfile."""
    config = config or CalibrationConfig()
    thresholds, ceilings, observed, names = {}, {}, {}, {}

    if verbose:
        print(f"Calibration — user '{user_id}', training phase {config.phase}")
        print(f"Phase ceiling cap: {config.phase_ceiling_ua()}uA "
              f"({PHASE_CEILING_FRACTION.get(config.phase, 0.3)*100:.0f}% of working max)\n")

    for ch in bank:
        names[ch.index] = ch.name
        if verbose:
            print(f"  CH{ch.index} {ch.name} [{ch.electrode_site}]")
        result = calibrate_channel(probe, ch.index, config, verbose)
        if result is None:
            # Fall back to conservative defaults so the channel is at least safe.
            thresholds[ch.index] = config.phase_ceiling_ua()
            ceilings[ch.index] = config.phase_ceiling_ua()
            observed[ch.index] = {}
            continue
        thresholds[ch.index] = result["threshold_ua"]
        ceilings[ch.index] = result["ceiling_ua"]
        observed[ch.index] = result["observed_recruitment"]

    return UserProfile(
        user_id=user_id,
        channel_names=names,
        thresholds_ua=thresholds,
        ceilings_ua=ceilings,
        pulse_width_us=250,
        frequency_hz=30,
        phase=config.phase,
        observed_recruitment=observed,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        notes="simulated calibration" if isinstance(probe, SimulatedProbe) else "",
    )


if __name__ == "__main__":
    bank = ChannelBank.preset("four_channel")
    # Simulated user: give channels slightly different thresholds/tolerances so
    # the calibration has something real to discover.
    curves = {i: RecruitmentCurve(threshold_ua=1200 + 200 * i, ceiling_ua=4500)
              for i in range(len(bank))}
    hand = SimulatedHand(bank=bank, curves=curves)
    probe = SimulatedProbe(hand=hand,
                           tolerance_ua={0: 3800, 1: 3600, 2: 3200, 3: 3000})

    profile = run_calibration(probe, bank, user_id="thomas_sim",
                              config=CalibrationConfig(phase=3))

    print("\nResulting profile:")
    for ch in bank:
        print(f"  CH{ch.index} {ch.name:16s} "
              f"threshold={profile.thresholds_ua[ch.index]}uA  "
              f"ceiling={profile.ceilings_ua[ch.index]}uA")

    out = Path(__file__).resolve().parents[2] / "models" / "profile_thomas_sim.json"
    saved = profile.save(out)
    print(f"\nSaved profile -> {saved}")
    reloaded = UserProfile.load(saved)
    print(f"Reload check: user={reloaded.user_id}, "
          f"{len(reloaded.recruitment_curves())} curves, phase {reloaded.phase}")
