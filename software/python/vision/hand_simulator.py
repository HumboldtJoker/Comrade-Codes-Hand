"""
hand_simulator.py — Synthetic hand pose generation for testing without hardware.

Generates MediaPipe-compatible 21-landmark hand poses from per-finger
flexion angles. Enables full closed-loop testing: EMG intent → gesture
classifier → target pose → simulated hand → error computer → FES mapper
→ update simulated hand → repeat.

The simulator models:
- Anatomically plausible finger kinematics (3-joint chain per finger)
- Gradual movement with configurable speed (not teleporting)
- Optional noise (simulating tracking jitter)
- FES response (current → muscle activation → joint angle change)

Usage:
    sim = HandSimulator()
    sim.set_target_pose("FIST", speed=0.1)
    for _ in range(100):
        sim.step()
        pose = sim.get_pose()  # HandPose with 21 landmarks
        # feed to error_computer, get correction, apply FES...
        sim.apply_fes_response(correction)
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .hand_tracker import (
    HandPose, FingerAngles, Finger, FINGER_LANDMARKS, WRIST,
)
from .error_computer import GESTURE_TARGETS

# Anatomical segment lengths (mm, approximate adult hand)
SEGMENT_LENGTHS = {
    Finger.THUMB:  [40, 30, 25],   # metacarpal, proximal, distal
    Finger.INDEX:  [70, 40, 25],   # metacarpal, proximal+middle, distal
    Finger.MIDDLE: [65, 45, 28],
    Finger.RING:   [60, 40, 25],
    Finger.PINKY:  [55, 30, 20],
}

# MCP positions relative to wrist (mm, palm-up view)
MCP_OFFSETS = {
    Finger.THUMB:  np.array([-35, 20, 0]),
    Finger.INDEX:  np.array([-15, 75, 0]),
    Finger.MIDDLE: np.array([0, 80, 0]),
    Finger.RING:   np.array([15, 75, 0]),
    Finger.PINKY:  np.array([30, 65, 0]),
}

# Joint angle distribution: how total flexion splits across joints
# [MCP fraction, PIP fraction, DIP fraction]
JOINT_DISTRIBUTION = {
    Finger.THUMB:  [0.4, 0.35, 0.25],
    Finger.INDEX:  [0.35, 0.40, 0.25],
    Finger.MIDDLE: [0.35, 0.40, 0.25],
    Finger.RING:   [0.35, 0.40, 0.25],
    Finger.PINKY:  [0.35, 0.40, 0.25],
}

MAX_SPEED_DEG_PER_STEP = 5.0
FES_GAIN_DEG_PER_UA = 0.008
TRACKING_NOISE_STD = 0.002


@dataclass
class SimulatedFinger:
    """State of one simulated finger."""
    finger: Finger
    current_angle: float = 15.0  # current flexion (degrees)
    target_angle: float = 15.0
    speed: float = 1.0  # fraction of MAX_SPEED per step


class HandSimulator:
    """Synthetic hand that responds to FES and generates MediaPipe poses."""

    def __init__(
        self,
        noise: float = TRACKING_NOISE_STD,
        handedness: str = "Right",
    ):
        self.noise = noise
        self.handedness = handedness
        self.frame_index = 0

        self.fingers = {
            f: SimulatedFinger(finger=f)
            for f in Finger
        }

    @property
    def angles(self) -> FingerAngles:
        return FingerAngles(
            thumb=self.fingers[Finger.THUMB].current_angle,
            index=self.fingers[Finger.INDEX].current_angle,
            middle=self.fingers[Finger.MIDDLE].current_angle,
            ring=self.fingers[Finger.RING].current_angle,
            pinky=self.fingers[Finger.PINKY].current_angle,
        )

    def set_target_pose(self, gesture: str, speed: float = 1.0):
        target = GESTURE_TARGETS.get(gesture)
        if target is None:
            raise ValueError(f"Unknown gesture: {gesture}. "
                             f"Available: {list(GESTURE_TARGETS.keys())}")
        targets = target.as_array()
        for f in Finger:
            self.fingers[f].target_angle = targets[int(f)]
            self.fingers[f].speed = speed

    def set_finger_target(self, finger: Finger, angle_deg: float,
                          speed: float = 1.0):
        self.fingers[finger].target_angle = angle_deg
        self.fingers[finger].speed = speed

    def apply_fes_response(self, channel_commands: list, dt: float = 0.02):
        """Apply FES stimulation effect — current drives finger movement.

        This models the actual physics: electrical current causes muscle
        contraction, which changes joint angles. The relationship is
        nonlinear (recruitment curve) but we linearize for simulation.
        """
        from .hand_tracker import Finger as F
        from ..fes.channels import ChannelBank

        bank = ChannelBank.preset("four_channel")
        for cmd in channel_commands:
            ch = bank[cmd.channel]
            if cmd.current_ua <= 0:
                continue
            for f in F:
                w = ch.weight(f)
                if w <= 0:
                    continue
                delta = cmd.current_ua * FES_GAIN_DEG_PER_UA * w * dt * 50
                if ch.direction.name == "FLEX":
                    self.fingers[f].current_angle += delta
                else:
                    self.fingers[f].current_angle -= delta
                self.fingers[f].current_angle = np.clip(
                    self.fingers[f].current_angle, 0, 90
                )

    def step(self):
        """Advance one timestep — fingers move toward targets."""
        for sf in self.fingers.values():
            error = sf.target_angle - sf.current_angle
            max_step = MAX_SPEED_DEG_PER_STEP * sf.speed
            step = np.clip(error, -max_step, max_step)
            sf.current_angle += step
            sf.current_angle = np.clip(sf.current_angle, 0, 90)
        self.frame_index += 1

    def get_pose(self) -> HandPose:
        """Generate a MediaPipe-compatible HandPose from current state."""
        landmarks = self._compute_landmarks()
        if self.noise > 0:
            landmarks += np.random.normal(0, self.noise, landmarks.shape)
        return HandPose(
            landmarks=landmarks,
            finger_angles=self.angles,
            handedness=self.handedness,
            confidence=0.95,
            timestamp=time.perf_counter(),
            frame_index=self.frame_index,
        )

    def _compute_landmarks(self) -> np.ndarray:
        """Build 21 landmark positions from current finger angles."""
        pts = np.zeros((21, 3))
        pts[WRIST] = np.array([0, 0, 0])

        for finger in Finger:
            lm_indices = FINGER_LANDMARKS[finger]
            segments = SEGMENT_LENGTHS[finger]
            joint_frac = JOINT_DISTRIBUTION[finger]
            mcp_offset = MCP_OFFSETS[finger]

            total_flex = self.fingers[finger].current_angle
            joint_angles = [total_flex * f for f in joint_frac]

            pos = pts[WRIST] + mcp_offset
            cumulative_angle = 0.0

            for i, (seg_len, joint_angle) in enumerate(
                zip(segments, joint_angles)
            ):
                cumulative_angle += math.radians(joint_angle)
                dx = 0
                dy = seg_len * math.cos(cumulative_angle)
                dz = -seg_len * math.sin(cumulative_angle)
                pos = pos + np.array([dx, dy, dz])
                # Normalize to MediaPipe coordinate space (0-1 range)
                pts[lm_indices[i]] = pos / 200.0

            if len(lm_indices) > len(segments):
                pts[lm_indices[-1]] = pos / 200.0

        return pts

    def reset(self, gesture: str = "RELAX"):
        """Reset to a named pose instantly (no animation)."""
        target = GESTURE_TARGETS.get(gesture, GESTURE_TARGETS["RELAX"])
        angles = target.as_array()
        for f in Finger:
            self.fingers[f].current_angle = angles[int(f)]
            self.fingers[f].target_angle = angles[int(f)]
        self.frame_index = 0

    def describe(self) -> str:
        parts = []
        for f in Finger:
            sf = self.fingers[f]
            parts.append(f"{f.name}:{sf.current_angle:.0f}/{sf.target_angle:.0f}")
        return "  ".join(parts)


if __name__ == "__main__":
    sim = HandSimulator(noise=0.0)

    print("=== Hand Simulator Self-Test ===\n")

    print("Starting pose (RELAX):")
    sim.reset("RELAX")
    print(f"  {sim.describe()}")
    pose = sim.get_pose()
    print(f"  Landmarks shape: {pose.landmarks.shape}")
    print(f"  Confidence: {pose.confidence}")

    print("\nAnimating to FIST (20 steps):")
    sim.set_target_pose("FIST", speed=0.5)
    for i in range(20):
        sim.step()
        if i % 5 == 0:
            print(f"  Step {i:2d}: {sim.describe()}")

    print(f"\nFinal pose:")
    print(f"  {sim.describe()}")
    final = sim.get_pose()
    print(f"  Angles: {final.finger_angles}")

    print("\nAnimating to OPEN (20 steps):")
    sim.set_target_pose("OPEN", speed=0.8)
    for i in range(20):
        sim.step()
        if i % 5 == 0:
            print(f"  Step {i:2d}: {sim.describe()}")

    print(f"\nFinal: {sim.describe()}")
    print("\nSelf-test passed.")
