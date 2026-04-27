"""
error_computer.py — Per-finger error signals for FES correction.

Takes a target pose (from gesture classifier) and actual pose (from
hand tracker) and produces per-finger correction signals that drive
FES channel adjustment.

Phase 2 deliverable per docs/CAMERA_INTEGRATION.md.

Usage:
    error_comp = ErrorComputer()
    correction = error_comp.compute(target_gesture, actual_pose)
    for finger, signal in correction.items():
        fes.adjust(finger, signal.magnitude, signal.direction)
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import IntEnum

import numpy as np

from .hand_tracker import HandPose, FingerAngles, Finger


# Target finger angles per gesture (degrees of flexion, 0=extended, 90=flexed)
GESTURE_TARGETS: Dict[str, FingerAngles] = {
    "RELAX": FingerAngles(thumb=10.0, index=15.0, middle=15.0, ring=15.0, pinky=15.0),
    "FIST":  FingerAngles(thumb=70.0, index=85.0, middle=85.0, ring=85.0, pinky=85.0),
    "OPEN":  FingerAngles(thumb=5.0,  index=5.0,  middle=5.0,  ring=5.0,  pinky=5.0),
    "POINT": FingerAngles(thumb=60.0, index=5.0,  middle=80.0, ring=80.0, pinky=80.0),
    "WAVE":  FingerAngles(thumb=10.0, index=10.0, middle=10.0, ring=10.0, pinky=10.0),
}


class Direction(IntEnum):
    EXTEND = -1
    HOLD = 0
    FLEX = 1


@dataclass
class FingerCorrection:
    """Correction signal for a single finger."""
    finger: Finger
    error_deg: float
    direction: Direction
    magnitude: float  # 0.0 to 1.0, normalized correction strength
    raw_error: float


@dataclass
class CorrectionSignal:
    """Complete per-finger correction signal for FES adjustment."""
    fingers: Dict[Finger, FingerCorrection]
    gesture: str
    timestamp: float
    tracking_valid: bool = True
    safety_limited: bool = False

    def __getitem__(self, finger: Finger) -> FingerCorrection:
        return self.fingers[finger]

    def items(self):
        return self.fingers.items()

    @property
    def max_error(self) -> float:
        if not self.fingers:
            return 0.0
        return max(abs(fc.error_deg) for fc in self.fingers.values())

    @property
    def total_error(self) -> float:
        return sum(abs(fc.error_deg) for fc in self.fingers.values())

    def as_array(self) -> np.ndarray:
        return np.array([self.fingers[f].magnitude * self.fingers[f].direction
                         for f in Finger])


class ErrorComputer:
    """Computes per-finger error signals between target and actual poses.

    Args:
        deadzone_deg: Ignore errors smaller than this (prevents oscillation).
        max_error_deg: Clamp errors above this (safety limit).
        divergence_limit_deg: If any finger error exceeds this, flag safety.
        gain: Proportional gain applied to normalized error.
        smoothing: Exponential smoothing factor (0=no smoothing, 0.9=heavy).
    """

    def __init__(
        self,
        deadzone_deg: float = 5.0,
        max_error_deg: float = 45.0,
        divergence_limit_deg: float = 45.0,
        gain: float = 1.0,
        smoothing: float = 0.3,
    ):
        self.deadzone = deadzone_deg
        self.max_error = max_error_deg
        self.divergence_limit = divergence_limit_deg
        self.gain = gain
        self.smoothing = smoothing
        self._prev_magnitudes: Dict[Finger, float] = {f: 0.0 for f in Finger}
        self._custom_targets: Dict[str, FingerAngles] = {}

    def set_target(self, gesture_name: str, angles: FingerAngles):
        """Override or add a gesture target (from calibration)."""
        self._custom_targets[gesture_name] = angles

    def get_target(self, gesture_name: str) -> Optional[FingerAngles]:
        if gesture_name in self._custom_targets:
            return self._custom_targets[gesture_name]
        return GESTURE_TARGETS.get(gesture_name)

    def compute(
        self,
        gesture: str,
        actual_pose: Optional[HandPose],
    ) -> CorrectionSignal:
        """Compute per-finger correction signals.

        Args:
            gesture: Name of the target gesture (e.g. "FIST", "OPEN").
            actual_pose: Current hand pose from HandTracker, or None if lost.

        Returns:
            CorrectionSignal with per-finger corrections.
        """
        target = self.get_target(gesture)
        if target is None:
            target = FingerAngles()

        if actual_pose is None:
            return CorrectionSignal(
                fingers={f: FingerCorrection(f, 0.0, Direction.HOLD, 0.0, 0.0)
                         for f in Finger},
                gesture=gesture,
                timestamp=time.perf_counter(),
                tracking_valid=False,
            )

        actual = actual_pose.finger_angles
        target_arr = target.as_array()
        actual_arr = actual.as_array()
        errors = target_arr - actual_arr

        safety_limited = False
        fingers = {}

        for finger in Finger:
            raw_error = errors[finger]

            if abs(raw_error) > self.divergence_limit:
                safety_limited = True

            if abs(raw_error) < self.deadzone:
                direction = Direction.HOLD
                magnitude = 0.0
            else:
                direction = Direction.FLEX if raw_error > 0 else Direction.EXTEND
                clamped = min(abs(raw_error), self.max_error)
                magnitude = (clamped / self.max_error) * self.gain
                magnitude = min(magnitude, 1.0)

            prev = self._prev_magnitudes[finger]
            magnitude = prev * self.smoothing + magnitude * (1.0 - self.smoothing)
            self._prev_magnitudes[finger] = magnitude

            fingers[finger] = FingerCorrection(
                finger=finger,
                error_deg=raw_error,
                direction=direction,
                magnitude=magnitude,
                raw_error=raw_error,
            )

        return CorrectionSignal(
            fingers=fingers,
            gesture=gesture,
            timestamp=time.perf_counter(),
            tracking_valid=True,
            safety_limited=safety_limited,
        )

    def reset(self):
        """Reset smoothing state (e.g. after camera re-acquisition)."""
        self._prev_magnitudes = {f: 0.0 for f in Finger}


if __name__ == "__main__":
    print("ErrorComputer — standalone test with simulated data")
    print("=" * 50)

    ec = ErrorComputer(deadzone_deg=5.0, max_error_deg=45.0)

    # Simulate: target is FIST, actual hand is mostly open
    target_gesture = "FIST"
    target = GESTURE_TARGETS[target_gesture]

    simulated_actual = FingerAngles(
        thumb=20.0, index=30.0, middle=25.0, ring=40.0, pinky=50.0,
    )

    fake_pose = HandPose(
        landmarks=np.zeros((21, 3)),
        finger_angles=simulated_actual,
        handedness="Right",
        confidence=0.95,
        timestamp=time.perf_counter(),
    )

    print(f"Target gesture: {target_gesture}")
    print(f"Target angles:  T={target.thumb:.0f} I={target.index:.0f} "
          f"M={target.middle:.0f} R={target.ring:.0f} P={target.pinky:.0f}")
    print(f"Actual angles:  T={simulated_actual.thumb:.0f} I={simulated_actual.index:.0f} "
          f"M={simulated_actual.middle:.0f} R={simulated_actual.ring:.0f} "
          f"P={simulated_actual.pinky:.0f}")
    print()

    correction = ec.compute(target_gesture, fake_pose)

    print(f"Tracking valid: {correction.tracking_valid}")
    print(f"Safety limited: {correction.safety_limited}")
    print(f"Max error:      {correction.max_error:.1f} deg")
    print(f"Total error:    {correction.total_error:.1f} deg")
    print()
    print(f"{'Finger':>8s}  {'Error':>7s}  {'Dir':>6s}  {'Mag':>5s}")
    print("-" * 35)
    for finger, fc in correction.items():
        dir_name = {Direction.FLEX: "FLEX", Direction.EXTEND: "EXT",
                    Direction.HOLD: "HOLD"}[fc.direction]
        print(f"{finger.name:>8s}  {fc.error_deg:>+6.1f}°  {dir_name:>6s}  {fc.magnitude:>5.3f}")

    # Simulate camera loss
    print("\nSimulating camera loss...")
    lost = ec.compute("FIST", None)
    print(f"Tracking valid: {lost.tracking_valid}")
    print(f"All magnitudes zero: {all(fc.magnitude == 0 for fc in lost.fingers.values())}")
