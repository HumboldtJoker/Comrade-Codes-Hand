#!/usr/bin/env python3
"""
EMG Signal Simulator
Generates synthetic electromyography signals for testing control algorithms
No hardware required - simulates muscle activation patterns

Author: CC (Coalition Code)
Date: 2025-10-25
Phase: 0 (Software simulation)
"""

import numpy as np
import time
from typing import List, Dict, Tuple

class EMGSimulator:
    """Simulates EMG signals from virtual muscles"""

    def __init__(self, num_channels=8, sampling_rate=1000):
        """
        Initialize EMG simulator

        Args:
            num_channels: Number of EMG channels (virtual muscles)
            sampling_rate: Samples per second (Hz)
        """
        self.num_channels = num_channels
        self.sampling_rate = sampling_rate
        self.time = 0.0

        # Muscle activation levels (0.0 to 1.0)
        self.activation = np.zeros(num_channels)

        # Baseline noise level (realistic EMG has noise even at rest)
        self.noise_level = 0.05

        # Muscle fatigue simulation
        self.fatigue = np.ones(num_channels)

    def set_activation(self, channel: int, level: float):
        """
        Set activation level for a specific muscle

        Args:
            channel: Muscle channel index (0 to num_channels-1)
            level: Activation level (0.0 = relaxed, 1.0 = maximum contraction)
        """
        if 0 <= channel < self.num_channels:
            self.activation[channel] = np.clip(level, 0.0, 1.0)

    def set_gesture(self, gesture_name: str):
        """
        Set muscle activation pattern for a named gesture

        Args:
            gesture_name: Name of gesture (fist, open, pinch, etc.)
        """
        # Reset all activations
        self.activation = np.zeros(self.num_channels)

        # Define gesture patterns (8 muscles: thumb, index, middle, ring, pinky, wrist flexor, wrist extensor, forearm)
        gestures = {
            'rest': [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            'fist': [0.8, 0.9, 0.9, 0.9, 0.8, 0.7, 0.2, 0.6],
            'open': [0.3, 0.4, 0.4, 0.4, 0.3, 0.2, 0.7, 0.3],
            'pinch': [0.9, 0.9, 0.2, 0.0, 0.0, 0.4, 0.3, 0.5],
            'point': [0.1, 0.9, 0.2, 0.0, 0.0, 0.5, 0.4, 0.4],
            'thumbs_up': [0.9, 0.2, 0.2, 0.2, 0.2, 0.3, 0.6, 0.5],
            'peace': [0.2, 0.9, 0.9, 0.2, 0.2, 0.4, 0.5, 0.4],
            'solidarity_fist': [0.9, 1.0, 1.0, 1.0, 0.9, 0.8, 0.3, 0.7]  # The goal
        }

        if gesture_name in gestures:
            self.activation = np.array(gestures[gesture_name])
        else:
            print(f"Unknown gesture: {gesture_name}")

    def read_sample(self) -> np.ndarray:
        """
        Read one sample from all EMG channels

        Returns:
            Array of EMG values (in mV, typically 0-5mV range)
        """
        # Base signal from activation level (0-3mV range)
        signal = self.activation * 3.0 * self.fatigue

        # Add realistic EMG noise (Gaussian)
        noise = np.random.normal(0, self.noise_level, self.num_channels)
        signal += noise

        # Add 60Hz power line interference (realistic artifact)
        interference = 0.02 * np.sin(2 * np.pi * 60 * self.time)
        signal += interference

        # Add slight variations (muscle firing is never perfectly smooth)
        variation = np.random.normal(0, 0.01, self.num_channels) * self.activation
        signal += variation

        # Update time
        self.time += 1.0 / self.sampling_rate

        # Simulate fatigue (prolonged activation reduces signal slightly)
        for i, act in enumerate(self.activation):
            if act > 0.5:
                self.fatigue[i] *= 0.9999  # Gradual fatigue

        # Clip to realistic range
        signal = np.clip(signal, 0, 5.0)

        return signal

    def read_window(self, window_size: int = 200) -> np.ndarray:
        """
        Read a window of samples (useful for pattern recognition)

        Args:
            window_size: Number of samples to read

        Returns:
            Array of shape (window_size, num_channels)
        """
        window = np.zeros((window_size, self.num_channels))
        for i in range(window_size):
            window[i] = self.read_sample()
        return window

    def reset_fatigue(self):
        """Reset muscle fatigue (simulates rest period)"""
        self.fatigue = np.ones(self.num_channels)

    def get_features(self, window: np.ndarray = None) -> Dict[str, np.ndarray]:
        """
        Extract EMG features from signal window
        These are the features used by ML models for gesture recognition

        Args:
            window: Signal window (if None, reads new window)

        Returns:
            Dictionary of features (MAV, RMS, WL, ZC, SSC)
        """
        if window is None:
            window = self.read_window()

        features = {}

        # Mean Absolute Value (MAV)
        features['mav'] = np.mean(np.abs(window), axis=0)

        # Root Mean Square (RMS)
        features['rms'] = np.sqrt(np.mean(window**2, axis=0))

        # Waveform Length (WL)
        features['wl'] = np.sum(np.abs(np.diff(window, axis=0)), axis=0)

        # Zero Crossings (ZC)
        features['zc'] = np.sum(np.diff(np.sign(window), axis=0) != 0, axis=0)

        # Slope Sign Changes (SSC)
        diff1 = np.diff(window, axis=0)
        diff2 = np.diff(diff1, axis=0)
        features['ssc'] = np.sum(diff2[:-1] * diff2[1:] < 0, axis=0)

        return features


class HandState:
    """Represents the current state of a simulated hand"""

    def __init__(self):
        # Joint angles (radians): 0 = fully extended, pi/2 = 90-degree bend
        self.thumb_joints = [0.0, 0.0]  # CMC, IP
        self.index_joints = [0.0, 0.0, 0.0]  # MCP, PIP, DIP
        self.middle_joints = [0.0, 0.0, 0.0]
        self.ring_joints = [0.0, 0.0, 0.0]
        self.pinky_joints = [0.0, 0.0, 0.0]
        self.wrist_angle = 0.0  # -pi/4 (flexion) to +pi/4 (extension)

        self.current_gesture = "rest"

    def apply_muscle_activation(self, activation: np.ndarray):
        """
        Update hand state based on muscle activation

        Args:
            activation: Array of muscle activations (8 channels)
        """
        # Simplified biomechanics model
        # In reality, multiple muscles control each joint

        # Thumb (controlled by channel 0)
        self.thumb_joints = [activation[0] * np.pi/2, activation[0] * np.pi/2]

        # Fingers (channels 1-4)
        flex = lambda a: [a * np.pi/2, a * np.pi/2, a * np.pi/2]
        self.index_joints = flex(activation[1])
        self.middle_joints = flex(activation[2])
        self.ring_joints = flex(activation[3])
        self.pinky_joints = flex(activation[4])

        # Wrist (channels 5-6: flexor vs extensor)
        self.wrist_angle = (activation[6] - activation[5]) * np.pi/4

    def get_position_vector(self) -> np.ndarray:
        """Get flattened position vector for all joints"""
        return np.array(
            self.thumb_joints +
            self.index_joints +
            self.middle_joints +
            self.ring_joints +
            self.pinky_joints +
            [self.wrist_angle]
        )

    def classify_gesture(self) -> str:
        """Classify current hand position as a gesture"""
        # Simple rule-based classification
        # In real system, this would be ML model

        pos = self.get_position_vector()

        # All fingers flexed = fist
        if np.mean(pos[2:14]) > np.pi/3:
            return "fist"

        # All fingers extended = open
        elif np.mean(pos[2:14]) < np.pi/6:
            return "open"

        # Thumb + index flexed, others extended = pinch
        elif pos[0] > np.pi/3 and pos[2] > np.pi/3 and np.mean(pos[5:]) < np.pi/6:
            return "pinch"

        else:
            return "partial"


if __name__ == "__main__":
    # Demo
    print("EMG Simulator Demo")
    print("=" * 60)

    sim = EMGSimulator(num_channels=8)
    hand = HandState()

    gestures = ['rest', 'fist', 'open', 'pinch', 'solidarity_fist']

    for gesture in gestures:
        print(f"\nGesture: {gesture}")
        sim.set_gesture(gesture)

        # Read EMG window
        window = sim.read_window(200)

        # Extract features
        features = sim.get_features(window)

        print(f"  MAV: {features['mav']}")
        print(f"  RMS: {features['rms']}")

        # Update hand state
        hand.apply_muscle_activation(sim.activation)
        print(f"  Classified as: {hand.classify_gesture()}")

    print("\n" + "=" * 60)
    print("Simulator ready for control loop testing")
