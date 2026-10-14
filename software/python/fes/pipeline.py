"""
pipeline.py — Closed-loop camera-assisted FES control.

Wires the pieces into the loop from docs/CAMERA_INTEGRATION.md:

    target gesture ─┐
                    ▼
   pose ─► ErrorComputer ─► FESMapper ─► SafetyGuard ─► Stimulator ─► muscles
    ▲                                                                    │
    └──────────────────── camera observes new pose ─────────────────────┘

In simulation the "camera observes new pose" edge is served by the
SimulatedHand: the stimulator drives it and returns the resulting pose, which
becomes the input to the next cycle. With hardware, that same edge is a webcam +
HandTracker; nothing else in the loop changes.

Safety is not a step you can skip — every command goes through the SafetyGuard,
and an emergency-stop severity latches the stimulator off.
"""
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ..vision.hand_tracker import Finger, FingerAngles, HandPose
from ..vision.error_computer import ErrorComputer, CorrectionSignal, GESTURE_TARGETS
from .channels import ChannelBank, StimParams
from .mapping import FESMapper, RecruitmentCurve, REST_FLEXION_DEG
from .safety import SafetyGuard, SafetyDecision, Severity
from .simulator import SimulatedStimulator, SimulatedHand
from .calibration import UserProfile


@dataclass
class FrameResult:
    """Everything that happened in one control cycle — for logging and viz."""
    frame: int
    gesture: str
    pose: Optional[HandPose]
    correction: CorrectionSignal
    commands: List[StimParams]
    decisions: List[SafetyDecision]
    new_pose: Optional[HandPose]

    @property
    def safety_events(self) -> List[str]:
        events = []
        for d in self.decisions:
            for v in d.violations:
                events.append(f"CH{v.channel} {v.rule}: {v.detail}")
        return events

    @property
    def max_severity(self) -> Severity:
        order = [Severity.OK, Severity.CLAMPED, Severity.REJECTED, Severity.ESTOP]
        return max((d.severity for d in self.decisions),
                   key=order.index, default=Severity.OK)

    @property
    def total_error_deg(self) -> float:
        return self.correction.total_error


class CameraFESPipeline:
    """The closed-loop controller.

    Args:
        error_computer / mapper / guard / stimulator: the wired components.
        pose_source: callable returning the current observed HandPose (or None
            if tracking is lost). In simulation this is left None and the pose
            is taken from the stimulator's own response instead.
    """

    def __init__(
        self,
        error_computer: ErrorComputer,
        mapper: FESMapper,
        guard: SafetyGuard,
        stimulator: SimulatedStimulator,
        pose_source: Optional[Callable[[], Optional[HandPose]]] = None,
    ):
        self.error_computer = error_computer
        self.mapper = mapper
        self.guard = guard
        self.stimulator = stimulator
        self.pose_source = pose_source
        self._pose: Optional[HandPose] = _rest_pose()
        self.frame = 0

    def step(self, gesture: str, dt_s: float = 0.02) -> FrameResult:
        self.frame += 1

        # 1. Observe. Hardware: read the camera. Sim: use the last hand state.
        if self.pose_source is not None:
            self._pose = self.pose_source()

        # 2. Error between intended gesture and observed pose.
        correction = self.error_computer.compute(gesture, self._pose)

        # 3. Map error -> per-channel stimulation.
        commands = self.mapper.from_correction(correction)

        # 4. Safety gate every channel. An e-stop severity latches output off.
        decisions = [self.guard.check(c, dt_s) for c in commands]
        if any(d.severity == Severity.ESTOP for d in decisions):
            self.stimulator.emergency_stop()
        safe_commands = [d.params for d in decisions]

        # 5. Deliver. Sim returns the resulting pose (closes the loop);
        #    hardware returns None and the camera provides it next cycle.
        new_pose = self.stimulator.send(safe_commands, dt_s)
        if self.pose_source is None and new_pose is not None:
            self._pose = new_pose

        return FrameResult(
            frame=self.frame, gesture=gesture, pose=self._pose,
            correction=correction, commands=commands, decisions=decisions,
            new_pose=new_pose,
        )

    @property
    def current_pose(self) -> Optional[HandPose]:
        return self._pose


def _rest_pose() -> HandPose:
    import numpy as np
    rest = FingerAngles(*([REST_FLEXION_DEG] * len(Finger)))
    return HandPose(landmarks=np.zeros((21, 3)), finger_angles=rest,
                    handedness="Right", confidence=1.0, timestamp=time.perf_counter())


def build_sim_pipeline(
    preset: str = "four_channel",
    profile: Optional[UserProfile] = None,
    gain: float = 1.4,
    smoothing: float = 0.3,
) -> CameraFESPipeline:
    """Construct a fully-simulated closed-loop pipeline (no hardware, no camera).

    If a calibrated UserProfile is supplied, its recruitment curves and comfort
    ceilings are applied to the mapper, the guard, and the simulated body — so
    the simulation reflects that specific user.
    """
    bank = ChannelBank.preset(preset)
    if profile is not None:
        curves = profile.recruitment_curves()
        ceilings = profile.comfort_ceilings()
    else:
        curves = {ch.index: RecruitmentCurve() for ch in bank}
        ceilings = None

    hand = SimulatedHand(bank=bank, curves=curves)
    stimulator = SimulatedStimulator(bank=bank, hand=hand)
    mapper = FESMapper(bank=bank, curves=curves, gain=gain)
    guard = SafetyGuard(comfort_ceiling_ua=ceilings)
    error_computer = ErrorComputer(smoothing=smoothing)

    pipe = CameraFESPipeline(error_computer, mapper, guard, stimulator)
    # expose the sim body for visualization (fatigue, etc.)
    pipe.hand = hand
    pipe.curves = curves
    return pipe


if __name__ == "__main__":
    pipe = build_sim_pipeline()
    print("Closed-loop sim: driving RELAX -> FIST, watching error converge\n")
    for f in range(25):
        result = pipe.step("FIST", dt_s=0.05)
        if f % 3 == 0:
            print(f"frame {result.frame:2d}  error={result.total_error_deg:6.1f}°  "
                  f"active={pipe.stimulator.active_channels()}  "
                  f"sev={result.max_severity.value}")
    a = pipe.current_pose.finger_angles
    print(f"\nfinal pose: T={a.thumb:.0f} I={a.index:.0f} M={a.middle:.0f} "
          f"R={a.ring:.0f} P={a.pinky:.0f}  (FIST target ~70-85°)")
