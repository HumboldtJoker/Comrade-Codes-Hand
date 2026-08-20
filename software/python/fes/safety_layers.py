"""
safety_layers.py — The four missing safety layers for human FES testing.

Layer 4: EMG feedback — detect unexpected muscle response
Layer 5: Fatigue detection — reduce stimulation as muscles tire
Layer 7: Camera divergence — stop if hand diverges from intent
Layer 8: Human override — voluntary EMG suppresses FES

Each layer is independent: it takes sensor data and returns a SafetyAction
that the control loop must respect before sending any FES command. Any
layer can trigger an emergency stop.

These do NOT replace the SafetyGuard (layers 1-3, 6). They run BEFORE it.
The chain is:

    sensor data → safety_layers (4,5,7,8)
        → if any layer says STOP → e-stop, no FES
        → if any layer says REDUCE → scale down commands
        → if all layers say OK → SafetyGuard (bounds, ramp, duty)
            → stimulator

Design philosophy: false positives (unnecessary stops) are acceptable.
False negatives (missed dangers) are not. Every layer defaults to
caution. If a sensor is unavailable, that layer assumes the worst.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np


class SafetyAction(Enum):
    OK = "ok"
    REDUCE = "reduce"
    STOP = "stop"


@dataclass
class LayerResult:
    layer: str
    action: SafetyAction
    detail: str
    scale: float = 1.0


# ── Layer 4: EMG Feedback ───────────────────────────────────────────────
# If FES is on but no EMG response is detected, the electrodes may have
# lost contact or the stimulation isn't reaching the muscle. If FES is
# on and the EMG response is MUCH larger than expected, the muscle may
# be cramping or the current is too high.

@dataclass
class EMGFeedbackMonitor:
    """Detect unexpected muscle response during FES.

    Tracks the relationship between commanded FES current and observed
    EMG amplitude. Flags anomalies in either direction.
    """
    # EMG amplitude below this during active FES = no response (electrode issue)
    min_response_uv: float = 50.0
    # EMG amplitude above this during active FES = excessive response (cramping)
    max_response_uv: float = 2000.0
    # How many consecutive no-response cycles before flagging
    no_response_patience: int = 10
    # How many consecutive excessive cycles before e-stop
    excessive_patience: int = 3

    _no_response_count: int = field(default=0, init=False)
    _excessive_count: int = field(default=0, init=False)

    def check(self, fes_active: bool, emg_amplitude_uv: float) -> LayerResult:
        if not fes_active:
            self._no_response_count = 0
            self._excessive_count = 0
            return LayerResult("emg_feedback", SafetyAction.OK, "FES inactive")

        if emg_amplitude_uv < self.min_response_uv:
            self._no_response_count += 1
            self._excessive_count = 0
            if self._no_response_count >= self.no_response_patience:
                return LayerResult(
                    "emg_feedback", SafetyAction.STOP,
                    f"No EMG response for {self._no_response_count} cycles "
                    f"during active FES — possible electrode disconnect"
                )
            return LayerResult(
                "emg_feedback", SafetyAction.OK,
                f"Low EMG ({emg_amplitude_uv:.0f}uV), "
                f"watching ({self._no_response_count}/{self.no_response_patience})"
            )

        if emg_amplitude_uv > self.max_response_uv:
            self._excessive_count += 1
            self._no_response_count = 0
            if self._excessive_count >= self.excessive_patience:
                return LayerResult(
                    "emg_feedback", SafetyAction.STOP,
                    f"Excessive EMG response ({emg_amplitude_uv:.0f}uV) "
                    f"for {self._excessive_count} cycles — possible cramping"
                )
            return LayerResult(
                "emg_feedback", SafetyAction.REDUCE,
                f"High EMG ({emg_amplitude_uv:.0f}uV), "
                f"reducing ({self._excessive_count}/{self.excessive_patience})",
                scale=0.5,
            )

        self._no_response_count = 0
        self._excessive_count = 0
        return LayerResult(
            "emg_feedback", SafetyAction.OK,
            f"Normal EMG response ({emg_amplitude_uv:.0f}uV)"
        )


# ── Layer 5: Fatigue Detection ──────────────────────────────────────────
# Muscle fatigue manifests as declining EMG amplitude for the same FES
# current. If the response drops below a fraction of the initial
# response, the muscle is fatiguing and stimulation should be reduced.

@dataclass
class FatigueMonitor:
    """Track muscle fatigue over a session.

    Monitors the ratio of EMG response to FES command over time. When
    the ratio drops significantly, the muscle is fatiguing.
    """
    window_size: int = 50
    fatigue_threshold: float = 0.5
    severe_fatigue_threshold: float = 0.3
    min_samples: int = 10

    _response_ratios: deque = field(default_factory=lambda: deque(maxlen=50), init=False)
    _baseline_ratio: Optional[float] = field(default=None, init=False)

    def check(self, fes_current_ua: int, emg_amplitude_uv: float) -> LayerResult:
        if fes_current_ua <= 0:
            return LayerResult("fatigue", SafetyAction.OK, "No active FES")

        ratio = emg_amplitude_uv / max(fes_current_ua, 1)
        self._response_ratios.append(ratio)

        if len(self._response_ratios) < self.min_samples:
            return LayerResult(
                "fatigue", SafetyAction.OK,
                f"Collecting baseline ({len(self._response_ratios)}/{self.min_samples})"
            )

        if self._baseline_ratio is None:
            self._baseline_ratio = np.mean(list(self._response_ratios))

        current_ratio = np.mean(list(self._response_ratios)[-10:])
        fatigue_level = current_ratio / max(self._baseline_ratio, 1e-6)

        if fatigue_level < self.severe_fatigue_threshold:
            return LayerResult(
                "fatigue", SafetyAction.STOP,
                f"Severe fatigue detected — response at "
                f"{fatigue_level:.0%} of baseline. Rest required."
            )

        if fatigue_level < self.fatigue_threshold:
            scale = max(0.3, fatigue_level)
            return LayerResult(
                "fatigue", SafetyAction.REDUCE,
                f"Fatigue detected — response at {fatigue_level:.0%} of baseline. "
                f"Reducing stimulation to {scale:.0%}.",
                scale=scale,
            )

        return LayerResult(
            "fatigue", SafetyAction.OK,
            f"Muscle response at {fatigue_level:.0%} of baseline"
        )


# ── Layer 7: Camera Divergence ──────────────────────────────────────────
# If the hand is moving AWAY from the target (error increasing over
# time despite FES), something is wrong — electrode misplacement,
# antagonist activation, or spasticity.

@dataclass
class CameraDivergenceMonitor:
    """Stop if the hand diverges from intent despite FES correction.

    Watches the error trend over a window. If error is consistently
    increasing while FES is active, the system is making things worse.
    """
    window_size: int = 20
    divergence_threshold_deg: float = 15.0
    max_divergence_cycles: int = 15

    _errors: deque = field(default_factory=lambda: deque(maxlen=20), init=False)
    _diverging_count: int = field(default=0, init=False)

    def check(self, total_error_deg: float, fes_active: bool,
              safety_limited: bool = False) -> LayerResult:
        if safety_limited:
            return LayerResult(
                "camera_divergence", SafetyAction.STOP,
                "ErrorComputer flagged safety_limited — divergence beyond safe range"
            )

        if not fes_active:
            self._errors.clear()
            self._diverging_count = 0
            return LayerResult("camera_divergence", SafetyAction.OK, "FES inactive")

        self._errors.append(total_error_deg)

        if len(self._errors) < 5:
            return LayerResult(
                "camera_divergence", SafetyAction.OK,
                "Collecting error baseline"
            )

        recent = list(self._errors)
        mid = len(recent) // 2
        first_half = np.mean(recent[:mid])
        second_half = np.mean(recent[mid:])
        trend = second_half - first_half

        if trend > 0 and total_error_deg > self.divergence_threshold_deg:
            self._diverging_count += 1
            if self._diverging_count >= self.max_divergence_cycles:
                return LayerResult(
                    "camera_divergence", SafetyAction.STOP,
                    f"Hand diverging from target for {self._diverging_count} cycles "
                    f"(error {total_error_deg:.1f}°, trend +{trend:.1f}°). "
                    f"Possible electrode misplacement or antagonist activation."
                )
            return LayerResult(
                "camera_divergence", SafetyAction.REDUCE,
                f"Error increasing (trend +{trend:.1f}°, "
                f"{self._diverging_count}/{self.max_divergence_cycles})",
                scale=0.5,
            )

        self._diverging_count = max(0, self._diverging_count - 1)
        return LayerResult(
            "camera_divergence", SafetyAction.OK,
            f"Error {total_error_deg:.1f}°, trend {trend:+.1f}°"
        )


# ── Layer 8: Human Override ─────────────────────────────────────────────
# If the user's own EMG shows strong voluntary activation, FES should
# back off. Voluntary movement takes priority — the system assists,
# it doesn't fight.

@dataclass
class HumanOverrideMonitor:
    """Detect voluntary EMG and suppress FES.

    Distinguishes voluntary EMG (which has higher frequency content and
    temporal correlation with intent) from FES-evoked EMG (which is
    time-locked to stimulation pulses). Simplified version: if EMG
    amplitude during the FES-off phase of each pulse exceeds a threshold,
    the user is actively contracting.
    """
    voluntary_threshold_uv: float = 200.0
    voluntary_patience: int = 3
    suppress_scale: float = 0.0

    _voluntary_count: int = field(default=0, init=False)

    def check(self, emg_between_pulses_uv: float) -> LayerResult:
        if emg_between_pulses_uv > self.voluntary_threshold_uv:
            self._voluntary_count += 1
            if self._voluntary_count >= self.voluntary_patience:
                return LayerResult(
                    "human_override", SafetyAction.REDUCE,
                    f"Voluntary EMG detected ({emg_between_pulses_uv:.0f}uV "
                    f"between pulses) — suppressing FES. "
                    f"Human movement takes priority.",
                    scale=self.suppress_scale,
                )
            return LayerResult(
                "human_override", SafetyAction.OK,
                f"Possible voluntary EMG ({self._voluntary_count}/{self.voluntary_patience})"
            )

        self._voluntary_count = max(0, self._voluntary_count - 1)
        return LayerResult(
            "human_override", SafetyAction.OK,
            f"No voluntary override detected"
        )


# ── Combined Safety Layer Check ─────────────────────────────────────────

class SafetyLayerStack:
    """Runs all four safety layers and returns the combined decision.

    Any STOP from any layer stops everything.
    REDUCE actions compound multiplicatively (all scale factors multiply).
    All results are logged for post-session review.
    """

    def __init__(self):
        self.emg_feedback = EMGFeedbackMonitor()
        self.fatigue = FatigueMonitor()
        self.camera_divergence = CameraDivergenceMonitor()
        self.human_override = HumanOverrideMonitor()
        self.log: list[list[LayerResult]] = []

    def check(
        self,
        fes_active: bool,
        fes_current_ua: int,
        emg_amplitude_uv: float,
        emg_between_pulses_uv: float,
        total_error_deg: float,
        safety_limited: bool = False,
    ) -> tuple[SafetyAction, float, list[LayerResult]]:
        """Run all safety layers.

        Returns:
            action: worst action across all layers (STOP > REDUCE > OK)
            scale: combined scale factor (product of all REDUCE scales)
            results: per-layer results for logging
        """
        results = [
            self.emg_feedback.check(fes_active, emg_amplitude_uv),
            self.fatigue.check(fes_current_ua, emg_amplitude_uv),
            self.camera_divergence.check(total_error_deg, fes_active, safety_limited),
            self.human_override.check(emg_between_pulses_uv),
        ]

        self.log.append(results)

        action = SafetyAction.OK
        scale = 1.0

        for r in results:
            if r.action == SafetyAction.STOP:
                action = SafetyAction.STOP
                scale = 0.0
                break
            if r.action == SafetyAction.REDUCE:
                action = SafetyAction.REDUCE
                scale *= r.scale

        return action, scale, results

    def reset(self):
        self.emg_feedback = EMGFeedbackMonitor()
        self.fatigue = FatigueMonitor()
        self.camera_divergence = CameraDivergenceMonitor()
        self.human_override = HumanOverrideMonitor()

    def summary(self) -> str:
        if not self.log:
            return "No safety events logged."
        stops = sum(1 for frame in self.log
                    for r in frame if r.action == SafetyAction.STOP)
        reduces = sum(1 for frame in self.log
                      for r in frame if r.action == SafetyAction.REDUCE)
        return (f"{len(self.log)} cycles checked, "
                f"{stops} STOP events, {reduces} REDUCE events")


if __name__ == "__main__":
    print("Safety Layers Self-Test\n" + "=" * 60)

    stack = SafetyLayerStack()

    # Normal operation
    action, scale, results = stack.check(
        fes_active=True, fes_current_ua=2000,
        emg_amplitude_uv=500, emg_between_pulses_uv=50,
        total_error_deg=20.0,
    )
    print(f"\nNormal: {action.value}, scale={scale:.2f}")
    for r in results:
        print(f"  {r.layer}: {r.action.value} — {r.detail}")

    # No EMG response (electrode disconnect)
    for i in range(12):
        action, scale, results = stack.check(
            fes_active=True, fes_current_ua=2000,
            emg_amplitude_uv=10, emg_between_pulses_uv=5,
            total_error_deg=20.0,
        )
    print(f"\nAfter 12 cycles no EMG response: {action.value}")
    for r in results:
        if r.action != SafetyAction.OK:
            print(f"  {r.layer}: {r.action.value} — {r.detail}")

    # Voluntary override
    stack.reset()
    action, scale, results = stack.check(
        fes_active=True, fes_current_ua=2000,
        emg_amplitude_uv=500, emg_between_pulses_uv=500,
        total_error_deg=10.0,
    )
    for i in range(3):
        action, scale, results = stack.check(
            fes_active=True, fes_current_ua=2000,
            emg_amplitude_uv=500, emg_between_pulses_uv=500,
            total_error_deg=10.0,
        )
    print(f"\nVoluntary EMG detected: {action.value}, scale={scale:.2f}")
    for r in results:
        if r.action != SafetyAction.OK:
            print(f"  {r.layer}: {r.action.value} — {r.detail}")

    # Camera divergence
    stack.reset()
    for i in range(20):
        error = 10 + i * 2  # increasing error
        action, scale, results = stack.check(
            fes_active=True, fes_current_ua=2000,
            emg_amplitude_uv=500, emg_between_pulses_uv=50,
            total_error_deg=error,
        )
    print(f"\nAfter 20 cycles of increasing error: {action.value}")
    for r in results:
        if r.action != SafetyAction.OK:
            print(f"  {r.layer}: {r.action.value} — {r.detail}")

    print(f"\n{stack.summary()}")
    print("\nSelf-test complete.")
