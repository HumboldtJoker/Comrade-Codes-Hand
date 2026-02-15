"""
EMG Signal Processing Pipeline

Reads EMG data from Arduino, applies filtering, extracts features.
This is the core signal processing for the hand project.

Author: CC (Coalition Code)
Date: 2026-02-14
"""

import numpy as np
from scipy import signal
from collections import deque
from dataclasses import dataclass
from typing import Optional, List, Tuple
import time


@dataclass
class EMGSample:
    """Single EMG sample with all channels"""
    raw: np.ndarray  # Raw ADC values (4 channels)
    mav: np.ndarray  # Mean Absolute Value from Arduino
    timestamp: float  # Microseconds from Arduino


@dataclass
class EMGFeatures:
    """Complete feature set for gesture recognition"""
    mav: np.ndarray      # Mean Absolute Value (4 channels)
    zc: np.ndarray       # Zero Crossings (4 channels)
    wl: np.ndarray       # Waveform Length (4 channels)
    ssc: np.ndarray      # Slope Sign Changes (4 channels)
    rms: np.ndarray      # Root Mean Square (4 channels)
    mnf: np.ndarray      # Mean Frequency (4 channels) - for fatigue detection
    timestamp: float


class EMGProcessor:
    """
    Real-time EMG signal processor.

    Features:
    - Bandpass filtering (20-450 Hz for EMG)
    - Notch filter for powerline (60 Hz)
    - Sliding window feature extraction
    - Fatigue detection via frequency analysis
    """

    def __init__(
        self,
        sample_rate: int = 1000,
        num_channels: int = 4,
        window_size: int = 200,  # 200ms at 1kHz
        adc_resolution: int = 12,
        adc_voltage: float = 3.3
    ):
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.window_size = window_size
        self.adc_resolution = adc_resolution
        self.adc_max = 2 ** adc_resolution
        self.adc_voltage = adc_voltage

        # Circular buffers for each channel
        self.buffers = [deque(maxlen=window_size) for _ in range(num_channels)]

        # Design filters
        self._design_filters()

        # Baseline calibration (updated during calibration phase)
        self.baselines = np.array([self.adc_max / 2] * num_channels)

        # Feature history for temporal smoothing
        self.feature_history = deque(maxlen=5)

    def _design_filters(self):
        """Design bandpass and notch filters for EMG"""

        # Bandpass filter: 20-450 Hz (typical EMG frequency range)
        # Using Butterworth filter for flat passband
        nyquist = self.sample_rate / 2
        low_cut = 20 / nyquist
        high_cut = min(450 / nyquist, 0.99)  # Stay below Nyquist

        self.bandpass_b, self.bandpass_a = signal.butter(
            4,  # 4th order
            [low_cut, high_cut],
            btype='band'
        )

        # Notch filter: 60 Hz (US powerline frequency)
        # Q factor of 30 gives narrow notch
        notch_freq = 60 / nyquist
        if notch_freq < 1.0:  # Only if below Nyquist
            self.notch_b, self.notch_a = signal.iirnotch(
                notch_freq,
                Q=30
            )
        else:
            self.notch_b, self.notch_a = [1], [1]  # Pass-through

        # Initialize filter states for real-time filtering
        self.bandpass_zi = [
            signal.lfilter_zi(self.bandpass_b, self.bandpass_a)
            for _ in range(self.num_channels)
        ]
        self.notch_zi = [
            signal.lfilter_zi(self.notch_b, self.notch_a)
            for _ in range(self.num_channels)
        ]

    def add_sample(self, sample: EMGSample) -> bool:
        """
        Add a new sample to the processor.

        Returns True if buffer is full and features can be extracted.
        """
        for ch in range(self.num_channels):
            # Convert to voltage
            voltage = (sample.raw[ch] / self.adc_max) * self.adc_voltage

            # Apply bandpass filter (real-time)
            filtered, self.bandpass_zi[ch] = signal.lfilter(
                self.bandpass_b, self.bandpass_a,
                [voltage],
                zi=self.bandpass_zi[ch]
            )

            # Apply notch filter
            filtered, self.notch_zi[ch] = signal.lfilter(
                self.notch_b, self.notch_a,
                filtered,
                zi=self.notch_zi[ch]
            )

            self.buffers[ch].append(filtered[0])

        return len(self.buffers[0]) == self.window_size

    def extract_features(self) -> Optional[EMGFeatures]:
        """
        Extract complete feature set from current window.

        Returns None if buffer not full.
        """
        if len(self.buffers[0]) < self.window_size:
            return None

        # Convert buffers to arrays
        signals = np.array([list(buf) for buf in self.buffers])

        # Time-domain features
        mav = self._calc_mav(signals)
        zc = self._calc_zero_crossings(signals)
        wl = self._calc_waveform_length(signals)
        ssc = self._calc_slope_sign_changes(signals)
        rms = self._calc_rms(signals)

        # Frequency-domain features (for fatigue detection)
        mnf = self._calc_mean_frequency(signals)

        features = EMGFeatures(
            mav=mav,
            zc=zc,
            wl=wl,
            ssc=ssc,
            rms=rms,
            mnf=mnf,
            timestamp=time.time()
        )

        self.feature_history.append(features)
        return features

    def _calc_mav(self, signals: np.ndarray) -> np.ndarray:
        """Mean Absolute Value - most common EMG amplitude feature"""
        return np.mean(np.abs(signals), axis=1)

    def _calc_zero_crossings(
        self,
        signals: np.ndarray,
        threshold: float = 0.01
    ) -> np.ndarray:
        """
        Zero Crossings - related to frequency content.
        Threshold prevents noise from causing false crossings.
        """
        zc = np.zeros(self.num_channels)
        for ch in range(self.num_channels):
            sig = signals[ch]
            crossings = np.where(
                (np.abs(sig[:-1]) > threshold) &
                (np.abs(sig[1:]) > threshold) &
                (np.sign(sig[:-1]) != np.sign(sig[1:]))
            )[0]
            zc[ch] = len(crossings)
        return zc

    def _calc_waveform_length(self, signals: np.ndarray) -> np.ndarray:
        """Waveform Length - cumulative signal change"""
        return np.sum(np.abs(np.diff(signals, axis=1)), axis=1)

    def _calc_slope_sign_changes(
        self,
        signals: np.ndarray,
        threshold: float = 0.01
    ) -> np.ndarray:
        """Slope Sign Changes - related to frequency content"""
        ssc = np.zeros(self.num_channels)
        for ch in range(self.num_channels):
            diff = np.diff(signals[ch])
            changes = np.where(
                (np.abs(diff[:-1]) > threshold) &
                (np.abs(diff[1:]) > threshold) &
                (np.sign(diff[:-1]) != np.sign(diff[1:]))
            )[0]
            ssc[ch] = len(changes)
        return ssc

    def _calc_rms(self, signals: np.ndarray) -> np.ndarray:
        """Root Mean Square - another amplitude measure"""
        return np.sqrt(np.mean(signals ** 2, axis=1))

    def _calc_mean_frequency(self, signals: np.ndarray) -> np.ndarray:
        """
        Mean Frequency - shifts down during muscle fatigue.
        Key feature for fatigue detection.
        """
        mnf = np.zeros(self.num_channels)
        for ch in range(self.num_channels):
            # Compute power spectral density
            freqs, psd = signal.welch(
                signals[ch],
                fs=self.sample_rate,
                nperseg=min(256, len(signals[ch]))
            )

            # Mean frequency = weighted average
            if np.sum(psd) > 0:
                mnf[ch] = np.sum(freqs * psd) / np.sum(psd)
            else:
                mnf[ch] = 0

        return mnf

    def get_feature_vector(self) -> Optional[np.ndarray]:
        """
        Get flattened feature vector for ML classification.

        Returns 16-element vector: [mav(4), zc(4), wl(4), ssc(4)]
        """
        features = self.extract_features()
        if features is None:
            return None

        return np.concatenate([
            features.mav,
            features.zc,
            features.wl,
            features.ssc
        ])

    def calibrate_baseline(self, duration_sec: float = 2.0) -> np.ndarray:
        """
        Calibrate baseline during rest.
        Should be called with muscles relaxed.

        Returns the calculated baseline for each channel.
        """
        # This would be called from the calibration script
        # Accumulates samples and calculates mean
        pass

    def detect_fatigue(self, threshold_drop: float = 0.15) -> List[bool]:
        """
        Detect muscle fatigue based on mean frequency drop.

        Returns list of booleans, one per channel.
        True means fatigue detected.
        """
        if len(self.feature_history) < 2:
            return [False] * self.num_channels

        # Compare recent MNF to historical average
        recent = self.feature_history[-1].mnf
        historical = np.mean([f.mnf for f in list(self.feature_history)[:-1]], axis=0)

        fatigue = []
        for ch in range(self.num_channels):
            if historical[ch] > 0:
                drop = (historical[ch] - recent[ch]) / historical[ch]
                fatigue.append(drop > threshold_drop)
            else:
                fatigue.append(False)

        return fatigue


class EMGStreamReader:
    """
    Reads EMG data from Arduino serial connection.
    """

    def __init__(self, port: str, baud_rate: int = 115200):
        import serial
        self.serial = serial.Serial(port, baud_rate, timeout=1)
        self.connected = False

    def connect(self) -> bool:
        """Wait for Arduino to be ready"""
        print(f"Connecting to Arduino...")
        for _ in range(50):  # 5 second timeout
            line = self.serial.readline().decode('utf-8', errors='ignore').strip()
            if line == "READY":
                self.connected = True
                print("Connected!")
                return True
            time.sleep(0.1)
        return False

    def start_streaming(self):
        """Enable data streaming"""
        self.serial.write(b"START\n")

    def stop_streaming(self):
        """Disable data streaming"""
        self.serial.write(b"STOP\n")

    def read_sample(self) -> Optional[EMGSample]:
        """Read one EMG sample from serial"""
        try:
            line = self.serial.readline().decode('utf-8', errors='ignore').strip()
            if line.startswith("EMG,"):
                parts = line.split(",")
                if len(parts) >= 10:
                    raw = np.array([int(parts[i]) for i in range(1, 5)])
                    mav = np.array([float(parts[i]) for i in range(5, 9)])
                    timestamp = float(parts[9])
                    return EMGSample(raw=raw, mav=mav, timestamp=timestamp)
        except (ValueError, IndexError):
            pass
        return None

    def close(self):
        """Clean up serial connection"""
        self.serial.close()


# Quick test
if __name__ == "__main__":
    # Test without hardware using synthetic data
    print("Testing EMG Processor with synthetic data...")

    processor = EMGProcessor(sample_rate=1000, num_channels=4)

    # Generate synthetic EMG-like signal
    np.random.seed(42)
    for i in range(300):  # 300ms of data
        # Simulate 4-channel EMG with different activation patterns
        raw = np.array([
            2048 + int(500 * np.sin(2 * np.pi * 50 * i / 1000) + np.random.randn() * 100),
            2048 + int(300 * np.sin(2 * np.pi * 80 * i / 1000) + np.random.randn() * 80),
            2048 + int(400 * np.sin(2 * np.pi * 60 * i / 1000) + np.random.randn() * 90),
            2048 + int(200 * np.sin(2 * np.pi * 100 * i / 1000) + np.random.randn() * 70),
        ])

        sample = EMGSample(
            raw=raw,
            mav=np.zeros(4),  # Would come from Arduino
            timestamp=i * 1000
        )

        buffer_full = processor.add_sample(sample)

        if buffer_full and i % 50 == 0:
            features = processor.extract_features()
            if features:
                print(f"\nSample {i}:")
                print(f"  MAV: {features.mav}")
                print(f"  ZC:  {features.zc}")
                print(f"  MNF: {features.mnf}")

    # Test feature vector
    vec = processor.get_feature_vector()
    print(f"\nFeature vector shape: {vec.shape}")
    print(f"Feature vector: {vec}")

    print("\nProcessor test complete!")
