"""
onset_detector.py — Predictive EMG onset detection and early classification.

Detects muscle activation onset 50-100ms before visible hand movement
by exploiting the electromechanical delay (EMD). Extracts early features
(activation sequence, dMAV/dt) that enable gesture classification from
the first 50ms of EMG onset.

Based on: Gandolla et al. 2017 (76% accuracy, 100ms EMD window),
Frontiers in Neurorobotics 2023 (activation sequence features).

Author: CC (Coalition Code)
Date: April 2026
"""
import numpy as np
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, List
import time


@dataclass
class OnsetEvent:
    """Detected EMG onset with early features for predictive classification."""
    timestamp: float
    channel_order: np.ndarray  # rank-order of channel activation (e.g., [2,0,3,1])
    onset_rms: np.ndarray     # per-channel RMS at onset (4,)
    dmav_dt: np.ndarray       # rate of change of MAV in early window (4,)
    early_mav: np.ndarray     # MAV from the short onset window (4,)
    early_zc: np.ndarray      # zero crossings from onset window (4,)
    early_wl: np.ndarray      # waveform length from onset window (4,)
    early_ssc: np.ndarray     # slope sign changes from onset window (4,)
    latency_ms: float = 0.0

    def feature_vector(self) -> np.ndarray:
        """24-element vector: 16 standard + 4 activation rank + 4 dMAV/dt."""
        return np.concatenate([
            self.early_mav,
            self.early_zc,
            self.early_wl,
            self.early_ssc,
            self.channel_order.astype(float),
            self.dmav_dt,
        ])

    @property
    def feature_names(self) -> List[str]:
        channels = ['ch0', 'ch1', 'ch2', 'ch3']
        names = []
        for feat in ['mav', 'zc', 'wl', 'ssc', 'rank', 'dmav']:
            for ch in channels:
                names.append(f"{feat}_{ch}")
        return names


class OnsetDetector:
    """Real-time EMG onset detector with predictive feature extraction.

    Monitors per-channel RMS and triggers when any channel exceeds a
    threshold relative to the calibrated baseline. Once triggered,
    captures a short window of data for early feature extraction.

    Args:
        num_channels: Number of EMG channels.
        sample_rate: Samples per second.
        baseline_window: Samples used for running baseline estimate.
        onset_threshold: Multiplier of baseline RMS to trigger onset.
        onset_window_ms: Duration (ms) of the early feature window
            after onset is detected. Shorter = more predictive,
            less accurate. 50ms is the sweet spot.
        refractory_ms: Minimum time between onset events (prevents
            re-triggering during sustained contraction).
    """

    def __init__(
        self,
        num_channels: int = 4,
        sample_rate: int = 1000,
        baseline_window: int = 500,
        onset_threshold: float = 3.0,
        onset_window_ms: float = 50.0,
        refractory_ms: float = 300.0,
    ):
        self.num_channels = num_channels
        self.sample_rate = sample_rate
        self.onset_threshold = onset_threshold
        self.onset_window_samples = int(onset_window_ms * sample_rate / 1000)
        self.refractory_samples = int(refractory_ms * sample_rate / 1000)

        self._baseline_buf = [deque(maxlen=baseline_window) for _ in range(num_channels)]
        self._baseline_rms = np.zeros(num_channels)
        self._calibrated = False

        self._onset_active = False
        self._onset_start_sample = 0
        self._onset_buffers = [[] for _ in range(num_channels)]
        self._channel_onset_times = np.full(num_channels, -1, dtype=int)
        self._last_onset_sample = -self.refractory_samples
        self._sample_count = 0

        self._onset_start_time = 0.0

    def calibrate_baseline(self, resting_data: np.ndarray):
        """Set baseline from resting EMG data.

        Args:
            resting_data: (num_channels, num_samples) of filtered EMG
                recorded during rest.
        """
        for ch in range(self.num_channels):
            self._baseline_rms[ch] = np.sqrt(np.mean(resting_data[ch] ** 2))
        self._calibrated = True

    def update_baseline_sample(self, sample: np.ndarray):
        """Update running baseline estimate from a single sample (4,).
        Call this during detected rest periods."""
        for ch in range(self.num_channels):
            self._baseline_buf[ch].append(sample[ch])
            if len(self._baseline_buf[ch]) >= 50:
                buf = np.array(self._baseline_buf[ch])
                self._baseline_rms[ch] = np.sqrt(np.mean(buf ** 2))
                self._calibrated = True

    def process_sample(self, sample: np.ndarray) -> Optional[OnsetEvent]:
        """Process a single filtered EMG sample (num_channels,).

        Returns an OnsetEvent when the early feature window completes
        after an onset is detected. Returns None otherwise.

        Call this at sample_rate Hz with filtered EMG data.
        """
        self._sample_count += 1

        if not self._calibrated:
            self.update_baseline_sample(sample)
            return None

        if not self._onset_active:
            in_refractory = (self._sample_count - self._last_onset_sample) < self.refractory_samples
            if in_refractory:
                return None

            thresholds = self._baseline_rms * self.onset_threshold
            for ch in range(self.num_channels):
                if abs(sample[ch]) > thresholds[ch] and thresholds[ch] > 1e-8:
                    self._onset_active = True
                    self._onset_start_sample = self._sample_count
                    self._onset_start_time = time.perf_counter()
                    self._onset_buffers = [[] for _ in range(self.num_channels)]
                    self._channel_onset_times = np.full(self.num_channels, -1, dtype=int)
                    self._channel_onset_times[ch] = 0
                    break

            if not self._onset_active:
                return None

        for ch in range(self.num_channels):
            self._onset_buffers[ch].append(sample[ch])

        samples_since_onset = self._sample_count - self._onset_start_sample

        thresholds = self._baseline_rms * self.onset_threshold
        for ch in range(self.num_channels):
            if self._channel_onset_times[ch] < 0 and abs(sample[ch]) > thresholds[ch]:
                self._channel_onset_times[ch] = samples_since_onset

        if samples_since_onset >= self.onset_window_samples:
            event = self._extract_onset_features()
            self._onset_active = False
            self._last_onset_sample = self._sample_count
            return event

        return None

    def _extract_onset_features(self) -> OnsetEvent:
        """Extract predictive features from the onset window."""
        t0 = time.perf_counter()

        signals = np.array([np.array(buf) for buf in self._onset_buffers])
        n_samples = signals.shape[1]

        # Activation sequence: rank channels by onset time
        onset_times = self._channel_onset_times.copy()
        not_fired = onset_times < 0
        onset_times[not_fired] = n_samples + 1
        channel_order = np.argsort(onset_times)

        # RMS at onset
        onset_rms = np.sqrt(np.mean(signals ** 2, axis=1))

        # dMAV/dt: slope of MAV over the onset window
        half = max(n_samples // 2, 1)
        mav_first = np.mean(np.abs(signals[:, :half]), axis=1)
        mav_second = np.mean(np.abs(signals[:, half:]), axis=1)
        dt = (n_samples / 2) / self.sample_rate
        dmav_dt = (mav_second - mav_first) / max(dt, 1e-6)

        # Standard features from the short window
        early_mav = np.mean(np.abs(signals), axis=1)

        early_zc = np.zeros(self.num_channels)
        for ch in range(self.num_channels):
            sig = signals[ch]
            if len(sig) > 1:
                threshold = self._baseline_rms[ch] * 0.5
                crossings = np.where(
                    (np.abs(sig[:-1]) > threshold) &
                    (np.abs(sig[1:]) > threshold) &
                    (np.sign(sig[:-1]) != np.sign(sig[1:]))
                )[0]
                early_zc[ch] = len(crossings)

        early_wl = np.sum(np.abs(np.diff(signals, axis=1)), axis=1) if n_samples > 1 else np.zeros(self.num_channels)

        early_ssc = np.zeros(self.num_channels)
        for ch in range(self.num_channels):
            if n_samples > 2:
                diff = np.diff(signals[ch])
                threshold = self._baseline_rms[ch] * 0.3
                changes = np.where(
                    (np.abs(diff[:-1]) > threshold) &
                    (np.abs(diff[1:]) > threshold) &
                    (np.sign(diff[:-1]) != np.sign(diff[1:]))
                )[0]
                early_ssc[ch] = len(changes)

        latency = (time.perf_counter() - t0) * 1000

        return OnsetEvent(
            timestamp=self._onset_start_time,
            channel_order=channel_order,
            onset_rms=onset_rms,
            dmav_dt=dmav_dt,
            early_mav=early_mav,
            early_zc=early_zc,
            early_wl=early_wl,
            early_ssc=early_ssc,
            latency_ms=latency,
        )

    @property
    def is_onset_active(self) -> bool:
        return self._onset_active

    @property
    def is_calibrated(self) -> bool:
        return self._calibrated


if __name__ == "__main__":
    print("OnsetDetector — standalone test with synthetic EMG")
    print("=" * 50)

    np.random.seed(42)
    sample_rate = 1000
    detector = OnsetDetector(sample_rate=sample_rate, onset_threshold=3.0,
                             onset_window_ms=50)

    # Simulate 500ms of rest (baseline calibration)
    rest_data = np.random.randn(4, 500) * 0.01
    detector.calibrate_baseline(rest_data)
    print(f"Baseline RMS: {detector._baseline_rms}")

    # Simulate rest → onset → sustained contraction
    events = []
    for t in range(1000):
        if t < 200:
            # Rest
            sample = np.random.randn(4) * 0.01
        elif t == 200:
            # Onset: channel 2 fires first (simulate flexor)
            sample = np.random.randn(4) * 0.01
            sample[2] = 0.15
        elif t == 210:
            # Channel 0 fires second
            sample = np.random.randn(4) * 0.01
            sample[2] = 0.15
            sample[0] = 0.12
        elif t >= 220:
            # All channels active (sustained contraction)
            sample = np.random.randn(4) * 0.05 + np.array([0.1, 0.08, 0.15, 0.06])
        else:
            sample = np.random.randn(4) * 0.01
            sample[2] = 0.12 + np.random.randn() * 0.02

        event = detector.process_sample(sample)
        if event:
            events.append(event)

    print(f"\nDetected {len(events)} onset event(s)")
    for e in events:
        print(f"  Activation order: ch{e.channel_order[0]} → ch{e.channel_order[1]} → "
              f"ch{e.channel_order[2]} → ch{e.channel_order[3]}")
        print(f"  dMAV/dt: {e.dmav_dt}")
        print(f"  Feature vector shape: {e.feature_vector().shape}")
        print(f"  Extraction latency: {e.latency_ms:.3f}ms")
        print(f"  Feature names: {e.feature_names[:4]}...{e.feature_names[-4:]}")
