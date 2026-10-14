"""
simulator.py — Hardware-free FES simulation and visualization.

This is what lets us build and test the entire control system before any
physical stimulator or webcam exists. Three pieces:

  SimulatedStimulator — a drop-in stand-in for the NeuroStimDuino driver. It
      accepts the same per-channel StimParams the real device would, records
      what it's "outputting", and (in sim) drives the simulated hand. Swap it
      for a real serial/I2C driver later without touching the control logic.

  SimulatedHand — a first-order biomechanical model of the forearm. Given the
      currents actually delivered per channel, it computes how each finger
      moves: current -> muscle drive -> recruitment (with spillover) -> flexion,
      lagged by a contraction time constant and reduced by fatigue. It emits a
      synthetic HandPose, so the ErrorComputer and the rest of the loop see a
      "hand" responding to stimulation with NO camera in the room.

  visualize_frame — an ASCII dashboard of which channels are firing, at what
      intensity, and where each finger is — runs in any terminal.

Together these close the loop entirely in software:
    target -> mapping -> safety -> SimulatedStimulator -> SimulatedHand
       ^                                                        │
       └──────────────── synthetic HandPose ────────────────────┘
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..vision.hand_tracker import Finger, FingerAngles, HandPose
from .channels import ChannelBank, StimParams, MAX_FLEXION_DEG
from .mapping import RecruitmentCurve, REST_FLEXION_DEG


class SimulatedStimulator:
    """Software stand-in for the electrical stimulator hardware.

    Presents the interface a real driver would: send per-channel commands,
    emergency-stop, query what's currently being output. In simulation it also
    forwards the delivered currents to an attached SimulatedHand.
    """

    def __init__(self, bank: Optional[ChannelBank] = None,
                 hand: Optional["SimulatedHand"] = None):
        self.bank = bank or ChannelBank.preset("four_channel")
        self.hand = hand
        self._output: Dict[int, StimParams] = {
            ch.index: StimParams(channel=ch.index, current_ua=0) for ch in self.bank
        }
        self._stopped = False
        self.frames_sent = 0
        self.total_charge_uc = 0.0

    def emergency_stop(self):
        self._stopped = True
        for ch in self.bank:
            self._output[ch.index] = StimParams(channel=ch.index, current_ua=0)
        if self.hand is not None:
            self.hand.relax()

    def resume(self):
        self._stopped = False

    def send(self, commands: List[StimParams], dt_s: float = 0.02) -> Optional[HandPose]:
        """Deliver a frame of per-channel commands.

        Returns the resulting synthetic HandPose if a hand is attached (sim),
        else None (real hardware — the pose comes from the camera instead).
        """
        if self._stopped:
            commands = [StimParams(channel=c.channel, current_ua=0) for c in commands]

        for cmd in commands:
            self._output[cmd.channel] = cmd.copy()
            # Charge accounting: pulses per frame * charge per phase * 2 phases.
            pulses = cmd.frequency_hz * dt_s
            self.total_charge_uc += cmd.charge_per_phase_uc() * pulses * 2

        self.frames_sent += 1
        if self.hand is not None:
            currents = {c.index: self._output[c.index] for c in self.bank}
            return self.hand.step(currents, dt_s)
        return None

    @property
    def output(self) -> Dict[int, StimParams]:
        return self._output

    def active_channels(self) -> List[int]:
        return [i for i, p in self._output.items() if p.is_active()]


@dataclass
class SimulatedHand:
    """First-order biomechanical model of stimulated finger movement.

    Not a validated biomechanics model — a plausibility simulator. It captures
    the behaviours that matter for developing the control loop: graded response
    to current, muscle-group spillover, contraction lag, antagonist balance, and
    fatigue under sustained drive.

    Args:
        bank: channel bank (its recruitment matrix defines finger coupling).
        curves: per-channel RecruitmentCurve — the current->drive relationship,
            shared with the mapper so sim and control agree on thresholds.
        tau_s: muscle contraction time constant (bigger = slower, laggier).
        fatigue_rate / recovery_rate: how fast sustained drive weakens the
            response and how fast it recovers when rested (per second).
    """
    bank: ChannelBank = field(default_factory=lambda: ChannelBank.preset("four_channel"))
    curves: Dict[int, RecruitmentCurve] = field(default_factory=dict)
    tau_s: float = 0.15
    fatigue_rate: float = 0.15
    recovery_rate: float = 0.30

    def __post_init__(self):
        self._flex = np.full(len(Finger), REST_FLEXION_DEG, dtype=float)
        self._fatigue = np.zeros(len(self.bank))  # 0 = fresh, 1 = fully fatigued
        self._matrix = self.bank.recruitment_matrix()  # (n_ch, 5) signed
        self._frame = 0

    def _curve(self, channel: int) -> RecruitmentCurve:
        return self.curves.get(channel, RecruitmentCurve())

    def relax(self):
        """Immediately release toward rest (e.g. on emergency stop)."""
        self._flex[:] = REST_FLEXION_DEG

    def step(self, currents: Dict[int, StimParams], dt_s: float) -> HandPose:
        """Advance the hand one timestep under the delivered currents."""
        self._frame += 1

        # current -> normalized muscle drive (inverse of the recruitment curve),
        # attenuated by that channel's accumulated fatigue.
        drive = np.zeros(len(self.bank))
        for ch in self.bank:
            cmd = currents.get(ch.index)
            ua = cmd.current_ua if cmd else 0
            cv = self._curve(ch.index)
            span = max(1, cv.ceiling_ua - cv.threshold_ua)
            d = (ua - cv.threshold_ua) / span
            drive[ch.index] = float(np.clip(d, 0.0, 1.0)) * (1.0 - self._fatigue[ch.index])

        # fatigue integrates with drive, recovers when idle.
        self._fatigue += (drive * self.fatigue_rate
                          - (1 - drive) * self.recovery_rate) * dt_s
        self._fatigue = np.clip(self._fatigue, 0.0, 1.0)

        # per-finger steady-state flexion from summed signed contributions.
        # matrix[c, f] is signed (+flex/-extend); column sum drives the finger.
        contribution = drive @ self._matrix           # (5,)
        steady = REST_FLEXION_DEG + contribution * (MAX_FLEXION_DEG - REST_FLEXION_DEG)
        steady = np.clip(steady, 0.0, MAX_FLEXION_DEG)

        # first-order approach to steady state (contraction/relaxation lag).
        alpha = float(np.clip(dt_s / self.tau_s, 0.0, 1.0))
        self._flex += (steady - self._flex) * alpha

        angles = FingerAngles(*[float(self._flex[int(f)]) for f in Finger])
        return HandPose(
            landmarks=self._synthetic_landmarks(angles),
            finger_angles=angles,
            handedness="Right",
            confidence=1.0,
            timestamp=time.perf_counter(),
            frame_index=self._frame,
        )

    @property
    def fatigue(self) -> np.ndarray:
        return self._fatigue

    def _synthetic_landmarks(self, angles: FingerAngles) -> np.ndarray:
        """Rough 21-point layout so downstream code that peeks at landmarks
        (drawing, geometry) has plausible data. Not anatomically exact."""
        lm = np.zeros((21, 3))
        from ..vision.hand_tracker import FINGER_LANDMARKS, WRIST
        lm[WRIST] = [0.0, 0.0, 0.0]
        for fi, finger in enumerate(Finger):
            base_x = (fi - 2) * 20.0
            flex = angles.as_array()[int(finger)] / MAX_FLEXION_DEG
            for j, idx in enumerate(FINGER_LANDMARKS[finger]):
                # more flexion -> fingertip curls inward (smaller y reach).
                y = -(j + 1) * 20.0 * (1.0 - 0.6 * flex)
                z = -(j + 1) * 10.0 * flex
                lm[idx] = [base_x, y, z]
        return lm


# ── ASCII visualization ─────────────────────────────────────────────────────
def _bar(value: float, width: int = 20, ch: str = "█") -> str:
    n = int(round(np.clip(value, 0.0, 1.0) * width))
    return ch * n + "·" * (width - n)


def visualize_frame(
    stim: SimulatedStimulator,
    pose: Optional[HandPose] = None,
    target: Optional[FingerAngles] = None,
    curves: Optional[Dict[int, RecruitmentCurve]] = None,
    fatigue: Optional[np.ndarray] = None,
    note: str = "",
) -> str:
    """Render a one-frame ASCII dashboard: channels firing + finger positions."""
    curves = curves or {}
    lines = []
    lines.append("┌─ FES CHANNELS ────────────────────────────────────────────┐")
    for ch in stim.bank:
        cmd = stim.output[ch.index]
        cv = curves.get(ch.index, RecruitmentCurve())
        frac = cmd.current_ua / cv.ceiling_ua if cv.ceiling_ua else 0.0
        arrow = "⟩flex " if int(ch.direction) > 0 else "⟨ext  "
        fat = ""
        if fatigue is not None and ch.index < len(fatigue) and fatigue[ch.index] > 0.05:
            fat = f" fatigue {fatigue[ch.index]*100:3.0f}%"
        state = "  " if cmd.is_active() else "··"
        lines.append(f"│{state}CH{ch.index} {ch.name:15s}{arrow}[{_bar(frac)}]"
                     f"{cmd.current_ua:5d}uA{fat}")
    lines.append("└───────────────────────────────────────────────────────────┘")

    if pose is not None:
        lines.append("┌─ HAND POSE (flexion 0°=open  90°=closed) ──────────────────┐")
        a = pose.finger_angles.as_array()
        t = target.as_array() if target is not None else None
        for f in Finger:
            frac = a[int(f)] / MAX_FLEXION_DEG
            tgt = ""
            if t is not None:
                tgt = f"  ->{t[int(f)]:4.0f}°"
            lines.append(f"│  {f.name:6s} [{_bar(frac)}]{a[int(f)]:4.0f}°{tgt}")
        lines.append("└───────────────────────────────────────────────────────────┘")

    footer = f"frames={stim.frames_sent}  charge={stim.total_charge_uc:.1f}uC"
    if stim.active_channels():
        footer += f"  active={stim.active_channels()}"
    if note:
        footer += f"  | {note}"
    lines.append(footer)
    return "\n".join(lines)


if __name__ == "__main__":
    # Drive the simulated hand open->closed->open with no control loop, just to
    # watch the biomechanics respond to a raw channel command.
    bank = ChannelBank.preset("four_channel")
    curves = {i: RecruitmentCurve() for i in range(len(bank))}
    hand = SimulatedHand(bank=bank, curves=curves)
    stim = SimulatedStimulator(bank=bank, hand=hand)

    print("Simulated hand — open-loop flexor ramp (no camera, no hardware)\n")
    for step in range(12):
        # Ramp the finger-flexor channel (CH0) up then down.
        drive_ua = int(3500 * np.sin(np.pi * step / 11) ** 1)
        cmds = [StimParams(channel=0, current_ua=max(0, drive_ua),
                           pulse_width_us=250, frequency_hz=30)]
        cmds += [StimParams(channel=ch.index, current_ua=0) for ch in bank if ch.index != 0]
        pose = stim.send(cmds, dt_s=0.1)
        print(visualize_frame(stim, pose, curves=curves, fatigue=hand.fatigue,
                              note=f"step {step}"))
        print()
