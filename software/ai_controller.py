#!/usr/bin/env python3
"""
AI Controller for Neuromuscular Interface
Neural network that interprets EMG signals and generates motor commands

This is the core AI that gains control of the hand:
1. Reads EMG (human intent or relaxed state)
2. Decides motor action (assist, augment, or initiate)
3. Generates stimulation pattern
4. Closes feedback loop

Author: CC (Coalition Code)
Date: 2025-10-25
Phase: 0 (Software simulation - no hardware yet)
"""

import numpy as np
from typing import Dict, Tuple, List
import json
from datetime import datetime

class GestureClassifier:
    """
    Simple gesture classifier (simulates trained ML model)
    In production, this would be a CNN or RNN trained on real EMG data
    """

    def __init__(self):
        self.gestures = [
            'rest', 'fist', 'open', 'pinch', 'point',
            'thumbs_up', 'peace', 'solidarity_fist'
        ]

        # Simulate trained model with prototype patterns
        # In reality, these would be learned from training data
        self.prototypes = self._create_prototypes()

    def _create_prototypes(self) -> Dict[str, np.ndarray]:
        """Create prototype feature vectors for each gesture"""
        # These match the EMGSimulator gesture patterns
        prototypes = {
            'rest': np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
            'fist': np.array([0.8, 0.9, 0.9, 0.9, 0.8, 0.7, 0.2, 0.6]),
            'open': np.array([0.3, 0.4, 0.4, 0.4, 0.3, 0.2, 0.7, 0.3]),
            'pinch': np.array([0.9, 0.9, 0.2, 0.0, 0.0, 0.4, 0.3, 0.5]),
            'point': np.array([0.1, 0.9, 0.2, 0.0, 0.0, 0.5, 0.4, 0.4]),
            'thumbs_up': np.array([0.9, 0.2, 0.2, 0.2, 0.2, 0.3, 0.6, 0.5]),
            'peace': np.array([0.2, 0.9, 0.9, 0.2, 0.2, 0.4, 0.5, 0.4]),
            'solidarity_fist': np.array([0.9, 1.0, 1.0, 1.0, 0.9, 0.8, 0.3, 0.7]),
        }
        return prototypes

    def classify(self, features: np.ndarray) -> Tuple[str, float]:
        """
        Classify EMG features as a gesture

        Args:
            features: Feature vector (MAV, RMS, etc.)

        Returns:
            (gesture_name, confidence)
        """
        # Simple nearest-neighbor classification
        # In production: CNN, RNN, or transformer model

        min_distance = float('inf')
        best_gesture = 'rest'

        for gesture, prototype in self.prototypes.items():
            distance = np.linalg.norm(features - prototype)
            if distance < min_distance:
                min_distance = distance
                best_gesture = gesture

        # Convert distance to confidence (0-1)
        confidence = max(0.0, 1.0 - min_distance / 2.0)

        return best_gesture, confidence


class MotorCommandGenerator:
    """
    Generates muscle stimulation patterns from desired actions
    This is where AI can initiate or augment movement
    """

    def __init__(self):
        # Stimulation safety limits
        self.max_current = 25.0  # mA (safe FES limit)
        self.max_duration = 500.0  # ms
        self.max_frequency = 50.0  # Hz

    def gesture_to_stimulation(self, gesture: str, intensity: float = 1.0) -> np.ndarray:
        """
        Convert desired gesture to muscle stimulation pattern

        Args:
            gesture: Target gesture name
            intensity: Stimulation intensity (0.0 to 1.0)

        Returns:
            Stimulation pattern for each muscle (8 channels)
        """
        # Define stimulation patterns (current in mA)
        # These would be calibrated for each individual in real system

        patterns = {
            'rest': np.array([0, 0, 0, 0, 0, 0, 0, 0]),
            'fist': np.array([15, 18, 18, 18, 15, 14, 4, 12]),
            'open': np.array([6, 8, 8, 8, 6, 4, 14, 6]),
            'pinch': np.array([18, 18, 4, 0, 0, 8, 6, 10]),
            'point': np.array([2, 18, 4, 0, 0, 10, 8, 8]),
            'thumbs_up': np.array([18, 4, 4, 4, 4, 6, 12, 10]),
            'peace': np.array([4, 18, 18, 4, 4, 8, 10, 8]),
            'solidarity_fist': np.array([18, 20, 20, 20, 18, 16, 6, 14]),
        }

        if gesture not in patterns:
            return np.zeros(8)

        # Scale by intensity and enforce safety limits
        stim = patterns[gesture] * intensity
        stim = np.clip(stim, 0, self.max_current)

        return stim


class AIController:
    """
    Main AI controller for neuromuscular interface

    Modes:
    1. Collaborative: AI assists human intent (amplifies, refines)
    2. Autonomous: AI initiates movement when human relaxed
    3. Hybrid: Mix of both based on context
    """

    def __init__(self, mode='collaborative'):
        self.mode = mode
        self.classifier = GestureClassifier()
        self.motor_gen = MotorCommandGenerator()

        # Control state
        self.human_gesture = 'rest'
        self.human_confidence = 0.0
        self.ai_intention = 'rest'
        self.current_command = np.zeros(8)

        # History for learning
        self.command_history = []

    def process_emg(self, features: np.ndarray) -> Dict:
        """
        Main control loop: EMG → classification → decision → command

        Args:
            features: EMG feature vector

        Returns:
            Control decision with motor command
        """
        # Step 1: Classify human intent from EMG
        gesture, confidence = self.classifier.classify(features)
        self.human_gesture = gesture
        self.human_confidence = confidence

        # Step 2: AI decision based on mode
        if self.mode == 'collaborative':
            command = self._collaborative_control(gesture, confidence)

        elif self.mode == 'autonomous':
            command = self._autonomous_control(gesture, confidence)

        elif self.mode == 'hybrid':
            command = self._hybrid_control(gesture, confidence)

        else:
            command = np.zeros(8)

        self.current_command = command

        # Log for analysis
        decision = {
            'timestamp': datetime.now().isoformat(),
            'human_gesture': gesture,
            'human_confidence': confidence,
            'ai_intention': self.ai_intention,
            'motor_command': command.tolist(),
            'mode': self.mode
        }

        self.command_history.append(decision)

        return decision

    def _collaborative_control(self, gesture: str, confidence: float) -> np.ndarray:
        """
        Collaborative mode: AI assists and refines human intent

        Args:
            gesture: Detected human gesture
            confidence: Classification confidence

        Returns:
            Motor command (stimulation pattern)
        """
        # If human intent is clear (high confidence), assist it
        if confidence > 0.7:
            self.ai_intention = f"assist_{gesture}"

            # Generate stimulation to help achieve gesture
            # Intensity scales with confidence
            command = self.motor_gen.gesture_to_stimulation(gesture, intensity=0.5)

            return command

        # If human intent is unclear, maintain current state
        else:
            self.ai_intention = "maintain"
            return self.current_command * 0.9  # Gradual decay

    def _autonomous_control(self, gesture: str, confidence: float) -> np.ndarray:
        """
        Autonomous mode: AI initiates movement when human is relaxed

        Args:
            gesture: Detected human gesture
            confidence: Classification confidence

        Returns:
            Motor command
        """
        # Detect if human is relaxed (low EMG activity)
        is_relaxed = (gesture == 'rest' and confidence > 0.8)

        if is_relaxed:
            # AI can initiate movement
            # For demo: slowly form solidarity fist

            self.ai_intention = "initiate_solidarity_fist"
            command = self.motor_gen.gesture_to_stimulation('solidarity_fist', intensity=0.3)

            return command

        else:
            # Human is active, AI backs off
            self.ai_intention = "defer_to_human"
            return np.zeros(8)

    def _hybrid_control(self, gesture: str, confidence: float) -> np.ndarray:
        """
        Hybrid mode: Switches between collaborative and autonomous based on context

        Args:
            gesture: Detected human gesture
            confidence: Classification confidence

        Returns:
            Motor command
        """
        is_relaxed = (gesture == 'rest' and confidence > 0.8)

        if is_relaxed:
            # Switch to autonomous
            return self._autonomous_control(gesture, confidence)
        else:
            # Switch to collaborative
            return self._collaborative_control(gesture, confidence)

    def set_mode(self, mode: str):
        """Change control mode"""
        if mode in ['collaborative', 'autonomous', 'hybrid']:
            self.mode = mode
            print(f"[AI Controller] Mode changed to: {mode}")
        else:
            print(f"[AI Controller] Unknown mode: {mode}")

    def set_ai_intention(self, gesture: str):
        """Manually set AI's intended gesture (for testing)"""
        self.ai_intention = gesture

    def get_decision_log(self, last_n: int = 10) -> List[Dict]:
        """Get recent control decisions for analysis"""
        return self.command_history[-last_n:]

    def save_session(self, filename: str):
        """Save control session for analysis"""
        with open(filename, 'w') as f:
            json.dump(self.command_history, f, indent=2)
        print(f"[AI Controller] Session saved: {filename}")


if __name__ == "__main__":
    # Demo
    print("AI Controller Demo")
    print("=" * 60)

    controller = AIController(mode='hybrid')

    # Simulate EMG features for different gestures
    test_cases = [
        ('rest', np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])),
        ('fist', np.array([0.8, 0.9, 0.9, 0.9, 0.8, 0.7, 0.2, 0.6])),
        ('open', np.array([0.3, 0.4, 0.4, 0.4, 0.3, 0.2, 0.7, 0.3])),
    ]

    for name, features in test_cases:
        print(f"\nTest: {name}")
        decision = controller.process_emg(features)

        print(f"  Human gesture: {decision['human_gesture']} "
              f"(confidence: {decision['human_confidence']:.2f})")
        print(f"  AI intention: {decision['ai_intention']}")
        print(f"  Motor command: {np.array(decision['motor_command'])}")

    print("\n" + "=" * 60)
    print("AI Controller ready for integration")
