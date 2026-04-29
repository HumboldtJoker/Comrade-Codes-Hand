"""
test_integration.py — End-to-end pipeline integration tests.

Tests the full signal flow:
  Synthetic EMG → onset detection → gesture classification →
  target pose → error computation → FES channel output

Also tests safety layers for edge cases:
  - Sudden signal loss
  - Sensor saturation
  - Camera loss mid-loop
  - Divergence safety limits
  - Emergency stop conditions
  - Fatigue detection response

All test data is synthetic and marked with TEST_DATA prefix
for cleanup. No real EMG or hardware required.

Run: python -m pytest software/python/tests/test_integration.py -v
"""
import numpy as np
import time
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from software.python.signal_processing.emg_processor import EMGProcessor, EMGSample, EMGFeatures
from software.python.signal_processing.onset_detector import OnsetDetector, OnsetEvent
from software.python.gesture_recognition.gesture_model import GestureClassifier, Gesture
from software.python.vision.hand_tracker import HandPose, FingerAngles, Finger
from software.python.vision.error_computer import (
    ErrorComputer, CorrectionSignal, Direction, GESTURE_TARGETS,
)

# ── TEST DATA MARKER ──
# All synthetic data in this file is prefixed TEST_DATA_ or created
# within test functions. No persistent files are written.
# To clean up any artifacts: find . -name "TEST_DATA_*" -delete
TEST_DATA_PREFIX = "TEST_DATA_"


def _make_synthetic_emg(gesture: str, duration_ms: int = 200,
                        sample_rate: int = 1000, noise: float = 0.01,
                        seed: int = 42) -> np.ndarray:
    """Generate synthetic EMG for a gesture.

    Returns (4, n_samples) array of filtered-like EMG signals.
    Marked as TEST_DATA for cleanup.
    """
    rng = np.random.RandomState(seed)
    n_samples = int(duration_ms * sample_rate / 1000)
    base = rng.randn(4, n_samples) * noise

    profiles = {
        "RELAX": np.array([0.01, 0.01, 0.01, 0.01]),
        "FIST":  np.array([0.15, 0.05, 0.12, 0.04]),
        "OPEN":  np.array([0.04, 0.12, 0.05, 0.14]),
        "POINT": np.array([0.08, 0.10, 0.03, 0.06]),
        "WAVE":  np.array([0.06, 0.06, 0.06, 0.06]),
    }
    amplitude = profiles.get(gesture, profiles["RELAX"])

    for ch in range(4):
        envelope = np.linspace(0, amplitude[ch], n_samples)
        base[ch] += envelope * np.sin(2 * np.pi * 80 * np.arange(n_samples) / sample_rate)

    return base


def _make_fake_pose(angles: FingerAngles) -> HandPose:
    """Create a fake HandPose for testing."""
    return HandPose(
        landmarks=np.zeros((21, 3)),
        finger_angles=angles,
        handedness="Right",
        confidence=0.95,
        timestamp=time.perf_counter(),
    )


# ════════════════════════════════════════════════════════════════
# PIPELINE INTEGRATION TESTS
# ════════════════════════════════════════════════════════════════

class TestFullPipeline:
    """Test the complete EMG → classification → error → FES flow."""

    def test_onset_to_feature_vector(self):
        """Onset detector produces a 24-element feature vector."""
        detector = OnsetDetector(onset_threshold=3.0, onset_window_ms=50)
        rest = _make_synthetic_emg("RELAX", duration_ms=500)
        detector.calibrate_baseline(rest)

        emg = _make_synthetic_emg("FIST", duration_ms=100)
        event = None
        for t in range(emg.shape[1]):
            event = detector.process_sample(emg[:, t])
            if event:
                break

        assert event is not None, "Onset should be detected for FIST gesture"
        vec = event.feature_vector()
        assert vec.shape == (24,), f"Expected 24 features, got {vec.shape}"
        assert not np.any(np.isnan(vec)), "Feature vector should not contain NaN"

    def test_feature_vector_to_classification(self):
        """24-element onset features can be classified by the gesture model."""
        classifier = GestureClassifier(input_size=24)

        event = OnsetEvent(
            timestamp=time.perf_counter(),
            channel_order=np.array([2, 0, 3, 1]),
            onset_rms=np.array([0.1, 0.05, 0.15, 0.04]),
            dmav_dt=np.array([0.5, 0.2, 0.8, 0.1]),
            early_mav=np.array([0.12, 0.04, 0.10, 0.03]),
            early_zc=np.array([15, 8, 12, 6]),
            early_wl=np.array([1.2, 0.3, 0.9, 0.2]),
            early_ssc=np.array([10, 5, 8, 3]),
        )

        vec = event.feature_vector()
        prediction = classifier.predict(vec)
        assert prediction.gesture in Gesture
        assert 0.0 <= prediction.confidence <= 1.0
        assert prediction.latency_ms >= 0

    def test_classification_to_error_signal(self):
        """Gesture classification produces usable error signals."""
        error_comp = ErrorComputer(smoothing=0.0)

        actual = _make_fake_pose(FingerAngles(
            thumb=20, index=30, middle=25, ring=40, pinky=50,
        ))

        correction = error_comp.compute("FIST", actual)
        assert correction.tracking_valid
        assert len(correction.fingers) == 5

        for finger in Finger:
            fc = correction[finger]
            assert fc.direction in Direction
            assert 0.0 <= fc.magnitude <= 1.0

    def test_full_loop_latency(self):
        """Full pipeline completes within the 100ms EMD budget."""
        detector = OnsetDetector(onset_threshold=3.0, onset_window_ms=50)
        rest = _make_synthetic_emg("RELAX", duration_ms=500)
        detector.calibrate_baseline(rest)

        classifier = GestureClassifier(input_size=24)
        error_comp = ErrorComputer(smoothing=0.0)

        emg = _make_synthetic_emg("FIST", duration_ms=100)

        t_start = time.perf_counter()

        event = None
        for t in range(emg.shape[1]):
            event = detector.process_sample(emg[:, t])
            if event:
                break

        if event:
            vec = event.feature_vector()
            prediction = classifier.predict(vec)
            actual = _make_fake_pose(FingerAngles(20, 30, 25, 40, 50))
            correction = error_comp.compute(prediction.gesture.name, actual)

        t_end = time.perf_counter()
        total_ms = (t_end - t_start) * 1000

        # The PROCESSING time (not including the 50ms onset window)
        # should be well under 50ms, leaving margin in the 100ms EMD
        processing_ms = total_ms - 50  # subtract onset window wait
        assert processing_ms < 50, f"Processing took {processing_ms:.1f}ms, budget is 50ms"

    def test_error_to_fes_channels(self):
        """Error signal produces per-finger FES correction values."""
        error_comp = ErrorComputer(smoothing=0.0, gain=1.0)
        actual = _make_fake_pose(FingerAngles(20, 30, 25, 40, 50))
        correction = error_comp.compute("FIST", actual)

        fes_output = correction.as_array()
        assert fes_output.shape == (5,), f"Expected 5 FES channels, got {fes_output.shape}"

        # FIST target has high flexion, actual is low → expect positive (FLEX)
        assert fes_output[1] > 0, "Index should need more flexion for FIST"


# ════════════════════════════════════════════════════════════════
# SAFETY EDGE CASE TESTS
# ════════════════════════════════════════════════════════════════

class TestSafetyLayers:
    """Test safety behavior under edge conditions."""

    def test_camera_loss_produces_zero_correction(self):
        """When camera tracking is lost, all corrections go to zero."""
        error_comp = ErrorComputer(smoothing=0.0)

        # Normal operation
        actual = _make_fake_pose(FingerAngles(20, 30, 25, 40, 50))
        normal = error_comp.compute("FIST", actual)
        assert normal.tracking_valid

        # Camera loss
        lost = error_comp.compute("FIST", None)
        assert not lost.tracking_valid
        for finger in Finger:
            assert lost[finger].magnitude == 0.0, \
                f"{finger.name} should be zero on camera loss"
            assert lost[finger].direction == Direction.HOLD

    def test_divergence_flags_safety(self):
        """Large error between target and actual triggers safety flag."""
        error_comp = ErrorComputer(divergence_limit_deg=45.0, smoothing=0.0)

        # Massive divergence: target FIST (85°) vs actual fully open (5°)
        actual = _make_fake_pose(FingerAngles(5, 5, 5, 5, 5))
        correction = error_comp.compute("FIST", actual)
        assert correction.safety_limited, \
            "Should flag safety when error exceeds divergence limit"

    def test_divergence_within_limit_no_flag(self):
        """Small error does not trigger safety flag."""
        error_comp = ErrorComputer(divergence_limit_deg=45.0, smoothing=0.0)
        actual = _make_fake_pose(FingerAngles(60, 70, 70, 70, 70))
        correction = error_comp.compute("FIST", actual)
        assert not correction.safety_limited

    def test_deadzone_prevents_oscillation(self):
        """Small errors within deadzone produce HOLD, not corrections."""
        error_comp = ErrorComputer(deadzone_deg=5.0, smoothing=0.0)
        target = GESTURE_TARGETS["FIST"]
        close = FingerAngles(
            thumb=target.thumb - 3,
            index=target.index - 2,
            middle=target.middle + 4,
            ring=target.ring - 1,
            pinky=target.pinky + 2,
        )
        actual = _make_fake_pose(close)
        correction = error_comp.compute("FIST", actual)
        for finger in Finger:
            assert correction[finger].direction == Direction.HOLD, \
                f"{finger.name} should HOLD within deadzone"

    def test_max_error_clamp(self):
        """Corrections are clamped to max magnitude even with extreme error."""
        error_comp = ErrorComputer(max_error_deg=45.0, gain=1.0, smoothing=0.0)

        # Extreme case: target 85° flexion, actual 0°
        actual = _make_fake_pose(FingerAngles(0, 0, 0, 0, 0))
        correction = error_comp.compute("FIST", actual)
        for finger in Finger:
            assert correction[finger].magnitude <= 1.0, \
                f"{finger.name} magnitude should be clamped to 1.0"

    def test_emg_saturation_handling(self):
        """Onset detector handles saturated EMG without crashing."""
        detector = OnsetDetector(onset_threshold=3.0, onset_window_ms=50)
        rest = _make_synthetic_emg("RELAX", duration_ms=500)
        detector.calibrate_baseline(rest)

        # Saturated signal (max ADC value)
        for t in range(100):
            sample = np.ones(4) * 3.3
            event = detector.process_sample(sample)
            # Should trigger onset but not crash

    def test_zero_signal_handling(self):
        """Pipeline handles zero/dead signal gracefully."""
        detector = OnsetDetector(onset_threshold=3.0, onset_window_ms=50)
        rest = _make_synthetic_emg("RELAX", duration_ms=500)
        detector.calibrate_baseline(rest)

        # Dead signal (all zeros)
        for t in range(200):
            sample = np.zeros(4)
            event = detector.process_sample(sample)
        # No onset should fire on zero signal
        assert event is None, "Dead signal should not trigger onset"

    def test_nan_signal_handling(self):
        """Pipeline handles NaN values without crashing."""
        error_comp = ErrorComputer(smoothing=0.0)

        # NaN in finger angles
        nan_angles = FingerAngles(float('nan'), 30, 25, 40, 50)
        pose = _make_fake_pose(nan_angles)
        correction = error_comp.compute("FIST", pose)
        # Should not crash — NaN propagation is acceptable, crash is not

    def test_rapid_onset_refractory(self):
        """Refractory period prevents rapid re-triggering."""
        detector = OnsetDetector(
            onset_threshold=3.0, onset_window_ms=50, refractory_ms=300,
        )
        rest = _make_synthetic_emg("RELAX", duration_ms=500)
        detector.calibrate_baseline(rest)

        events = []
        # Rapid repeated bursts
        for burst in range(5):
            emg = _make_synthetic_emg("FIST", duration_ms=100,
                                       seed=42 + burst)
            for t in range(emg.shape[1]):
                event = detector.process_sample(emg[:, t])
                if event:
                    events.append(event)

        # With 300ms refractory and 500ms total (5 x 100ms bursts),
        # should get at most 2 events
        assert len(events) <= 2, \
            f"Refractory should limit to ≤2 events, got {len(events)}"

    def test_smoothing_prevents_jitter(self):
        """Exponential smoothing prevents rapid magnitude changes."""
        error_comp = ErrorComputer(smoothing=0.7)

        # Alternating between two poses rapidly
        for i in range(10):
            if i % 2 == 0:
                pose = _make_fake_pose(FingerAngles(20, 30, 25, 40, 50))
            else:
                pose = _make_fake_pose(FingerAngles(70, 80, 75, 80, 80))
            correction = error_comp.compute("FIST", pose)

        # With heavy smoothing, magnitudes should be moderate, not extreme
        for finger in Finger:
            mag = correction[finger].magnitude
            assert mag < 0.9, \
                f"{finger.name} magnitude {mag:.2f} should be smoothed"

    def test_camera_recovery_after_loss(self):
        """System recovers gracefully when camera tracking returns."""
        error_comp = ErrorComputer(smoothing=0.3)
        actual = _make_fake_pose(FingerAngles(20, 30, 25, 40, 50))

        # Normal → camera loss → recovery
        c1 = error_comp.compute("FIST", actual)
        assert c1.tracking_valid

        c2 = error_comp.compute("FIST", None)
        assert not c2.tracking_valid

        error_comp.reset()
        c3 = error_comp.compute("FIST", actual)
        assert c3.tracking_valid
        assert c3.max_error > 0


# ════════════════════════════════════════════════════════════════
# LATENCY BENCHMARK
# ════════════════════════════════════════════════════════════════

class TestLatencyBenchmark:
    """Benchmark pipeline component latencies."""

    def test_onset_detection_latency(self):
        """Onset feature extraction completes in <5ms."""
        detector = OnsetDetector(onset_threshold=3.0, onset_window_ms=50)
        rest = _make_synthetic_emg("RELAX", duration_ms=500)
        detector.calibrate_baseline(rest)

        emg = _make_synthetic_emg("FIST", duration_ms=100)
        event = None
        for t in range(emg.shape[1]):
            event = detector.process_sample(emg[:, t])
            if event:
                break

        assert event is not None
        assert event.latency_ms < 5.0, \
            f"Onset extraction took {event.latency_ms:.1f}ms, budget is 5ms"

    def test_classification_latency(self):
        """Gesture classification completes in <10ms."""
        classifier = GestureClassifier(input_size=24)
        vec = np.random.randn(24)

        t0 = time.perf_counter()
        prediction = classifier.predict(vec)
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000

        assert latency_ms < 10.0, \
            f"Classification took {latency_ms:.1f}ms, budget is 10ms"

    def test_error_computation_latency(self):
        """Error computation completes in <1ms."""
        error_comp = ErrorComputer(smoothing=0.0)
        actual = _make_fake_pose(FingerAngles(20, 30, 25, 40, 50))

        t0 = time.perf_counter()
        correction = error_comp.compute("FIST", actual)
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000

        assert latency_ms < 1.0, \
            f"Error computation took {latency_ms:.1f}ms, budget is 1ms"


if __name__ == "__main__":
    print("=" * 60)
    print("HAND PROJECT — Integration & Safety Tests")
    print("All data is synthetic (TEST_DATA_). No hardware required.")
    print("=" * 60)
    print()

    passed = 0
    failed = 0
    errors = []

    # Collect all test classes and methods
    test_classes = [TestFullPipeline, TestSafetyLayers, TestLatencyBenchmark]

    for cls in test_classes:
        print(f"\n{cls.__name__}:")
        instance = cls()
        for method_name in sorted(dir(instance)):
            if not method_name.startswith("test_"):
                continue
            method = getattr(instance, method_name)
            try:
                method()
                print(f"  PASS  {method_name}")
                passed += 1
            except AssertionError as e:
                print(f"  FAIL  {method_name}: {e}")
                failed += 1
                errors.append((cls.__name__, method_name, str(e)))
            except Exception as e:
                print(f"  ERR   {method_name}: {type(e).__name__}: {e}")
                failed += 1
                errors.append((cls.__name__, method_name, f"{type(e).__name__}: {e}"))

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    if errors:
        print("\nFailures:")
        for cls_name, method, msg in errors:
            print(f"  {cls_name}.{method}: {msg}")
    print(f"{'=' * 60}")
