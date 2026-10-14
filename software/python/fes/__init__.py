"""
fes — Camera-assisted FES control: mapping, safety, simulation, calibration.

The vision layer (software/python/vision) turns a webcam frame into per-finger
flexion. This package turns that into safe electrical stimulation, and simulates
the whole loop with no hardware attached.

Modules:
    channels     StimParams + anatomical channel/recruitment model
    mapping      pose error -> per-channel stimulation commands
    safety       stimulation bounds checking + runtime force-gradient governors
    simulator    hardware-free stimulator, biomechanical hand, ASCII viz
    calibration  per-user threshold/comfort/recruitment calibration workflow
    pipeline     the closed-loop controller wiring it all together
"""
from .channels import (
    Finger, StimParams, StimDirection, Channel, ChannelBank, MAX_FLEXION_DEG,
)
from .mapping import FESMapper, RecruitmentCurve, REST_FLEXION_DEG
from .safety import SafetyGuard, SafetyDecision, SafetyViolation, Severity
from .simulator import SimulatedStimulator, SimulatedHand, visualize_frame
from .calibration import (
    UserProfile, CalibrationConfig, SimulatedProbe, run_calibration,
    calibrate_channel,
)
from .pipeline import CameraFESPipeline, FrameResult, build_sim_pipeline

__all__ = [
    "Finger", "StimParams", "StimDirection", "Channel", "ChannelBank",
    "MAX_FLEXION_DEG", "FESMapper", "RecruitmentCurve", "REST_FLEXION_DEG",
    "SafetyGuard", "SafetyDecision", "SafetyViolation", "Severity",
    "SimulatedStimulator", "SimulatedHand", "visualize_frame",
    "UserProfile", "CalibrationConfig", "SimulatedProbe", "run_calibration",
    "calibrate_channel", "CameraFESPipeline", "FrameResult", "build_sim_pipeline",
]
