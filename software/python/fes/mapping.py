"""
mapping.py — Hand landmarks / pose error -> per-channel FES commands.

This is the translation layer between the vision world (per-finger flexion in
degrees) and the electrical world (per-channel current in microamps).

Because surface FES produces grasp patterns, not per-finger control
(docs/TARGETING_AND_SELECTIVITY.md), we cannot simply assign one finger to one
channel. Instead we PROJECT the desired per-finger movement onto the channels
that can produce it, using the channel bank's recruitment weights:

    desired signed flexion per finger  (+ = flex more, - = extend more)
        │
        │  for each channel, gather the demand of the fingers it recruits,
        │  in that channel's direction, weighted by recruitment strength
        ▼
    per-channel activation  (0..1)
        │
        │  recruitment curve: activation below the motor threshold produces
        │  nothing; above it, current scales up to the user's comfort ceiling
        ▼
    per-channel StimParams (current in uA)

Two entry points:
  - from_correction():  closed-loop. Consumes the ErrorComputer's per-finger
                        correction (target-minus-actual) — the camera is in the
                        loop, driving the hand toward the intended pose.
  - from_target_pose(): open-loop / feed-forward. Consumes a desired pose
                        directly, for when no camera correction is available.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from ..vision.hand_tracker import Finger, FingerAngles
from ..vision.error_computer import CorrectionSignal, Direction
from .channels import (
    ChannelBank, Channel, StimParams, StimDirection, MAX_FLEXION_DEG,
)

# Neutral resting flexion (deg). A relaxed hand sits slightly flexed, not at 0.
REST_FLEXION_DEG = 10.0


@dataclass
class RecruitmentCurve:
    """Maps a channel's activation (0..1) to a stimulation current.

    Below `threshold_ua` a muscle does not visibly respond, so any activation
    maps into [threshold_ua, ceiling_ua] — there is no point commanding current
    the muscle can't feel, nor above what the user tolerates. Produced per
    channel by the calibration workflow (see calibration.py); sensible defaults
    let the mapper run before calibration.
    """
    threshold_ua: int = 1500     # motor threshold: first visible movement
    ceiling_ua: int = 4000       # comfort ceiling: strongest tolerated
    pulse_width_us: int = 250
    frequency_hz: int = 30
    # Activation below this is treated as "off" (deadband against jitter).
    activation_deadband: float = 0.05

    def current_for(self, activation: float) -> int:
        a = float(np.clip(activation, 0.0, 1.0))
        if a < self.activation_deadband:
            return 0
        span = self.ceiling_ua - self.threshold_ua
        return int(round(self.threshold_ua + a * span))


class FESMapper:
    """Turns desired hand movement into per-channel stimulation commands.

    Args:
        bank: the channel bank (default 4-channel preset).
        curves: per-channel RecruitmentCurve (from calibration). Channels
            without an entry use a default curve.
        gain: scales activation before the recruitment curve. >1 reaches the
            ceiling sooner (more aggressive); <1 is gentler.
    """

    def __init__(
        self,
        bank: Optional[ChannelBank] = None,
        curves: Optional[Dict[int, RecruitmentCurve]] = None,
        gain: float = 1.0,
    ):
        self.bank = bank or ChannelBank.preset("four_channel")
        self.curves = dict(curves or {})
        self.gain = gain

    def curve(self, channel: int) -> RecruitmentCurve:
        return self.curves.get(channel, RecruitmentCurve())

    # ── core projection ─────────────────────────────────────────────────
    def _activations(self, signed_demand: np.ndarray) -> np.ndarray:
        """Project per-finger signed demand onto per-channel activations.

        signed_demand: (5,) array, + = flex the finger, - = extend it, |.|<=1.
        Returns: (n_channels,) activations in 0..1.
        """
        acts = np.zeros(len(self.bank))
        for ch in self.bank:
            want_flex = ch.direction == StimDirection.FLEX
            num = 0.0
            den = 0.0
            for f in Finger:
                w = ch.weight(f)
                if w <= 0.0:
                    continue
                d = signed_demand[int(f)]
                # Only the component in this channel's direction counts.
                demand = max(0.0, d) if want_flex else max(0.0, -d)
                num += w * demand
                den += w
            acts[ch.index] = (num / den) if den > 0 else 0.0
        return np.clip(acts * self.gain, 0.0, 1.0)

    def _commands(self, activations: np.ndarray) -> List[StimParams]:
        out = []
        for ch in self.bank:
            c = self.curve(ch.index)
            out.append(StimParams(
                channel=ch.index,
                current_ua=c.current_for(activations[ch.index]),
                pulse_width_us=c.pulse_width_us,
                frequency_hz=c.frequency_hz,
                duration_ms=0,
                biphasic=True,
            ))
        return out

    # ── entry points ────────────────────────────────────────────────────
    def from_correction(self, correction: CorrectionSignal) -> List[StimParams]:
        """Closed-loop: map the camera-derived pose error to channel commands.

        If tracking is invalid (camera lost), returns all-zero commands — the
        system must not stimulate blind.
        """
        if not correction.tracking_valid:
            return [StimParams(channel=ch.index, current_ua=0) for ch in self.bank]
        # correction.as_array(): per-finger magnitude*direction, + = FLEX.
        signed_demand = correction.as_array()
        return self._commands(self._activations(signed_demand))

    def from_target_pose(
        self,
        target: FingerAngles,
        actual: Optional[FingerAngles] = None,
    ) -> List[StimParams]:
        """Feed-forward: map a desired pose (optionally relative to the actual
        pose) directly to channel commands.

        With `actual` given, demand is the normalized error (drive toward
        target). Without it, demand is the target's displacement from the
        neutral resting posture (pure open-loop pose command).
        """
        t = target.as_array()
        if actual is not None:
            signed_demand = (t - actual.as_array()) / MAX_FLEXION_DEG
        else:
            signed_demand = (t - REST_FLEXION_DEG) / (MAX_FLEXION_DEG - REST_FLEXION_DEG)
        signed_demand = np.clip(signed_demand, -1.0, 1.0)
        return self._commands(self._activations(signed_demand))

    def describe(self, commands: List[StimParams]) -> str:
        parts = []
        for ch in self.bank:
            cmd = commands[ch.index]
            parts.append(f"CH{ch.index}:{ch.name}={cmd.current_ua}uA")
        return "  ".join(parts)


if __name__ == "__main__":
    from ..vision.error_computer import ErrorComputer

    mapper = FESMapper()
    print("FESMapper self-test\n" + "=" * 60)

    # Closed loop: target FIST, hand currently open -> expect flexor channels hot.
    ec = ErrorComputer(smoothing=0.0)
    actual = FingerAngles(thumb=10, index=15, middle=15, ring=15, pinky=15)
    from ..vision.hand_tracker import HandPose
    import time as _t
    pose = HandPose(landmarks=np.zeros((21, 3)), finger_angles=actual,
                    handedness="Right", confidence=0.95, timestamp=_t.perf_counter())
    corr = ec.compute("FIST", pose)
    cmds = mapper.from_correction(corr)
    print("Target FIST, hand open (closed-loop correction):")
    print("  " + mapper.describe(cmds))

    # Open loop: command an OPEN pose directly -> expect extensor channels hot.
    cmds2 = mapper.from_target_pose(FingerAngles(5, 5, 5, 5, 5))
    print("\nCommand OPEN pose (feed-forward):")
    print("  " + mapper.describe(cmds2))
