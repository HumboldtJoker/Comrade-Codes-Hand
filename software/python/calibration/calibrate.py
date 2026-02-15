#!/usr/bin/env python3
"""
Gesture Calibration Tool for Hand Project

Interactive tool to record EMG patterns for each gesture.
Thomas performs gestures, we record and train the model.

Author: CC (Coalition Code)
Date: 2026-02-14

Usage:
    python calibrate.py --port COM3
    python calibrate.py --simulate  # Without hardware
"""

import argparse
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
import numpy as np

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from signal_processing.emg_processor import EMGProcessor, EMGSample, EMGStreamReader
from gesture_recognition.gesture_model import GestureClassifier, Gesture, generate_synthetic_training_data


class CalibrationSession:
    """
    Interactive calibration session for gesture training.

    Guides Thomas through recording each gesture multiple times,
    then trains the classifier.
    """

    def __init__(
        self,
        port: Optional[str] = None,
        simulate: bool = False,
        samples_per_gesture: int = 30,
        sample_duration: float = 2.0,  # seconds per sample
        rest_between: float = 1.0  # seconds between samples
    ):
        self.port = port
        self.simulate = simulate
        self.samples_per_gesture = samples_per_gesture
        self.sample_duration = sample_duration
        self.rest_between = rest_between

        self.processor = EMGProcessor()
        self.reader: Optional[EMGStreamReader] = None

        # Collected data
        self.calibration_data: Dict[str, List[np.ndarray]] = {
            g.name: [] for g in Gesture
        }

        # Output paths
        self.data_dir = Path(__file__).parent.parent.parent / "models"
        self.data_dir.mkdir(exist_ok=True)

    def connect(self) -> bool:
        """Connect to Arduino"""
        if self.simulate:
            print("Running in simulation mode (no hardware)")
            return True

        try:
            self.reader = EMGStreamReader(self.port)
            if not self.reader.connect():
                print("Failed to connect to Arduino")
                return False
            self.reader.start_streaming()
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def collect_sample(self, duration: float) -> Optional[np.ndarray]:
        """
        Collect EMG data for specified duration.

        Returns averaged feature vector.
        """
        features_collected = []
        start_time = time.time()

        while time.time() - start_time < duration:
            if self.simulate:
                # Generate synthetic sample
                raw = np.random.randint(1500, 2500, size=4)
                sample = EMGSample(raw=raw, mav=np.zeros(4), timestamp=time.time() * 1e6)
            else:
                sample = self.reader.read_sample()
                if sample is None:
                    continue

            if self.processor.add_sample(sample):
                features = self.processor.get_feature_vector()
                if features is not None:
                    features_collected.append(features)

            time.sleep(0.001)  # 1ms sleep

        if not features_collected:
            return None

        # Average features over the collection period
        return np.mean(features_collected, axis=0)

    def record_gesture(self, gesture: Gesture) -> bool:
        """
        Record samples for a single gesture.

        Returns True if enough samples collected.
        """
        print(f"\n{'='*60}")
        print(f"Recording gesture: {gesture.name}")
        print(f"{'='*60}")
        print(f"\nYou will perform this gesture {self.samples_per_gesture} times.")
        print(f"Each recording lasts {self.sample_duration} seconds.")
        print(f"\nGesture descriptions:")
        print(f"  RELAX: Rest your hand, no muscle activation")
        print(f"  FIST:  Make a tight fist")
        print(f"  OPEN:  Spread fingers wide, extend hand")
        print(f"  POINT: Point with index finger")
        print(f"  WAVE:  Flex and extend wrist")

        input(f"\nPress Enter when ready to record {gesture.name}...")

        for i in range(self.samples_per_gesture):
            print(f"\n[{i+1}/{self.samples_per_gesture}] Prepare to perform {gesture.name}...")
            time.sleep(0.5)

            # Countdown
            for countdown in [3, 2, 1]:
                print(f"  {countdown}...")
                time.sleep(0.5)

            print(f"  >>> HOLD {gesture.name} <<<")

            # Collect sample
            features = self.collect_sample(self.sample_duration)

            if features is not None:
                self.calibration_data[gesture.name].append(features)
                print(f"  Recorded! (MAV: {features[:4].round(3)})")
            else:
                print(f"  Warning: No data collected, skipping...")

            # Rest period
            if i < self.samples_per_gesture - 1:
                print(f"  Relax for {self.rest_between}s...")
                time.sleep(self.rest_between)

        collected = len(self.calibration_data[gesture.name])
        print(f"\nCollected {collected}/{self.samples_per_gesture} samples for {gesture.name}")

        return collected >= self.samples_per_gesture * 0.8  # 80% success rate OK

    def run_calibration(self) -> bool:
        """
        Run full calibration session.

        Returns True if successful.
        """
        print("\n" + "="*60)
        print("   HAND PROJECT - GESTURE CALIBRATION")
        print("   CC (Coalition Code) + Thomas")
        print("="*60)

        print("\nThis session will calibrate the EMG gesture recognition system.")
        print("You'll perform each gesture multiple times while I record the signals.")
        print("\nMake sure:")
        print("  - EMG sensors are properly placed on your forearm")
        print("  - Skin is clean and electrodes have good contact")
        print("  - You're comfortable and can maintain gestures for 2 seconds")

        input("\nPress Enter to begin calibration...")

        # Connect to hardware
        if not self.connect():
            return False

        # Record each gesture
        for gesture in Gesture:
            success = self.record_gesture(gesture)
            if not success:
                print(f"\nWarning: Insufficient samples for {gesture.name}")
                retry = input("Retry this gesture? (y/n): ").strip().lower()
                if retry == 'y':
                    self.calibration_data[gesture.name] = []
                    success = self.record_gesture(gesture)

        # Save raw calibration data
        self.save_calibration_data()

        # Train classifier
        print("\n" + "="*60)
        print("   TRAINING CLASSIFIER")
        print("="*60)

        success = self.train_classifier()

        if self.reader:
            self.reader.close()

        return success

    def save_calibration_data(self):
        """Save raw calibration data for future reference"""
        data_path = self.data_dir / f"calibration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        save_data = {
            gesture: [features.tolist() for features in samples]
            for gesture, samples in self.calibration_data.items()
        }

        with open(data_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'samples_per_gesture': self.samples_per_gesture,
                'sample_duration': self.sample_duration,
                'data': save_data
            }, f, indent=2)

        print(f"\nCalibration data saved to: {data_path}")

    def train_classifier(self) -> bool:
        """Train gesture classifier on calibration data"""

        # Prepare training data
        X = []
        y = []

        for gesture in Gesture:
            samples = self.calibration_data[gesture.name]
            for features in samples:
                X.append(features)
                y.append(gesture.value)

        X = np.array(X)
        y = np.array(y)

        print(f"\nTraining data: {len(X)} samples, {len(Gesture)} classes")

        if len(X) < 20:
            print("Error: Not enough training data!")
            return False

        # Check class balance
        for gesture in Gesture:
            count = np.sum(y == gesture.value)
            print(f"  {gesture.name}: {count} samples")

        # Create and train classifier
        classifier = GestureClassifier(
            input_size=16,
            hidden_sizes=[32, 16],
            num_classes=len(Gesture),
            learning_rate=0.01
        )

        print("\nTraining neural network...")
        history = classifier.train(X, y, epochs=150, batch_size=16, validation_split=0.2)

        final_accuracy = history['val_accuracy'][-1]
        print(f"\n{'='*60}")
        print(f"   TRAINING COMPLETE")
        print(f"   Validation Accuracy: {final_accuracy*100:.1f}%")
        print(f"{'='*60}")

        if final_accuracy < 0.7:
            print("\nWarning: Accuracy below 70%. Consider:")
            print("  - Improving electrode placement")
            print("  - More distinct gestures")
            print("  - Re-running calibration")

        # Save model
        model_path = self.data_dir / "gesture_model.json"
        classifier.save(str(model_path))

        # Export for Arduino
        arduino_path = Path(__file__).parent.parent.parent / "arduino" / "closed_loop" / "gesture_model.h"
        classifier.export_arduino(str(arduino_path))

        # Quick test
        print("\nQuick test - predicting on training samples:")
        for gesture in Gesture:
            if self.calibration_data[gesture.name]:
                test_sample = self.calibration_data[gesture.name][0]
                prediction = classifier.predict(np.array(test_sample))
                match = "OK" if prediction.gesture == gesture else "MISMATCH"
                print(f"  {gesture.name}: predicted {prediction.gesture.name} "
                      f"({prediction.confidence*100:.1f}%) [{match}]")

        return final_accuracy >= 0.7

    def quick_test(self, model_path: str):
        """
        Quick test mode - load existing model and test live.
        """
        print("\n" + "="*60)
        print("   QUICK TEST MODE")
        print("="*60)

        classifier = GestureClassifier.load(model_path)
        print(f"Loaded model with {classifier.training_accuracy*100:.1f}% accuracy")

        if not self.connect():
            return

        self.reader.start_streaming()
        print("\nPerform gestures to test recognition.")
        print("Press Ctrl+C to stop.\n")

        try:
            while True:
                features = self.collect_sample(0.5)
                if features is not None:
                    prediction = classifier.predict(features)
                    bar = "#" * int(prediction.confidence * 20)
                    print(f"\r{prediction.gesture.name:8} [{bar:20}] "
                          f"{prediction.confidence*100:5.1f}%  ", end="", flush=True)
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\nTest stopped.")
        finally:
            if self.reader:
                self.reader.close()


def main():
    parser = argparse.ArgumentParser(
        description="Gesture Calibration Tool for Hand Project"
    )
    parser.add_argument(
        "--port", "-p",
        default="COM3",
        help="Serial port for Arduino (default: COM3)"
    )
    parser.add_argument(
        "--simulate", "-s",
        action="store_true",
        help="Run in simulation mode without hardware"
    )
    parser.add_argument(
        "--samples", "-n",
        type=int,
        default=30,
        help="Samples per gesture (default: 30)"
    )
    parser.add_argument(
        "--test", "-t",
        type=str,
        help="Quick test mode with existing model"
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Generate and train on synthetic data (for testing)"
    )

    args = parser.parse_args()

    session = CalibrationSession(
        port=args.port,
        simulate=args.simulate,
        samples_per_gesture=args.samples
    )

    if args.test:
        session.quick_test(args.test)
    elif args.synthetic:
        print("Generating synthetic training data...")
        X, y = generate_synthetic_training_data(samples_per_class=200)

        # Convert to calibration format
        for gesture in Gesture:
            indices = np.where(y == gesture.value)[0]
            session.calibration_data[gesture.name] = [X[i] for i in indices]

        session.train_classifier()
    else:
        success = session.run_calibration()
        if success:
            print("\n" + "="*60)
            print("   CALIBRATION SUCCESSFUL!")
            print("   Model ready for closed-loop operation.")
            print("   Next: Upload closed_loop.ino to Arduino")
            print("="*60)
        else:
            print("\nCalibration had issues. Review output and retry if needed.")


if __name__ == "__main__":
    main()
