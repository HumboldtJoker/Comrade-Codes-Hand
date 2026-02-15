"""
Gesture Recognition Model for Hand Project

Lightweight MLP classifier for real-time EMG gesture recognition.
Based on research showing 97.7% accuracy with simple architectures.

Author: CC (Coalition Code)
Date: 2026-02-14
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from enum import Enum
import pickle
import json
from pathlib import Path


class Gesture(Enum):
    """Supported gestures for MVP"""
    RELAX = 0      # Rest state - no activation
    FIST = 1       # Full hand closure
    OPEN = 2       # Hand extension
    POINT = 3      # Index finger extension
    WAVE = 4       # Wrist flexion/extension pattern

    @classmethod
    def names(cls) -> List[str]:
        return [g.name for g in cls]


@dataclass
class GesturePrediction:
    """Result of gesture classification"""
    gesture: Gesture
    confidence: float
    probabilities: Dict[str, float]
    latency_ms: float


class GestureClassifier:
    """
    Lightweight MLP for gesture classification.

    Architecture (based on research):
    - Input: 16 features (4 channels x 4 feature types)
    - Hidden 1: 32 neurons, ReLU
    - Hidden 2: 16 neurons, ReLU
    - Output: 5 classes (gestures), Softmax

    This fits easily in Arduino memory if we need to port it.
    """

    def __init__(
        self,
        input_size: int = 16,
        hidden_sizes: List[int] = [32, 16],
        num_classes: int = 5,
        learning_rate: float = 0.01
    ):
        self.input_size = input_size
        self.hidden_sizes = hidden_sizes
        self.num_classes = num_classes
        self.learning_rate = learning_rate

        # Initialize weights with Xavier initialization
        self.weights = []
        self.biases = []

        prev_size = input_size
        for hidden_size in hidden_sizes:
            # Xavier initialization
            w = np.random.randn(prev_size, hidden_size) * np.sqrt(2.0 / prev_size)
            b = np.zeros(hidden_size)
            self.weights.append(w)
            self.biases.append(b)
            prev_size = hidden_size

        # Output layer
        w = np.random.randn(prev_size, num_classes) * np.sqrt(2.0 / prev_size)
        b = np.zeros(num_classes)
        self.weights.append(w)
        self.biases.append(b)

        # Feature normalization parameters (learned during training)
        self.feature_mean = np.zeros(input_size)
        self.feature_std = np.ones(input_size)

        # Training history
        self.trained = False
        self.training_accuracy = 0.0

    def _relu(self, x: np.ndarray) -> np.ndarray:
        """ReLU activation"""
        return np.maximum(0, x)

    def _relu_derivative(self, x: np.ndarray) -> np.ndarray:
        """ReLU derivative for backprop"""
        return (x > 0).astype(float)

    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """Softmax for output probabilities"""
        exp_x = np.exp(x - np.max(x))  # Subtract max for numerical stability
        return exp_x / np.sum(exp_x)

    def _normalize(self, features: np.ndarray) -> np.ndarray:
        """Normalize features using learned parameters"""
        return (features - self.feature_mean) / (self.feature_std + 1e-8)

    def forward(self, x: np.ndarray) -> Tuple[np.ndarray, List[np.ndarray]]:
        """
        Forward pass through network.

        Returns output and intermediate activations (for backprop).
        """
        activations = [x]

        for i, (w, b) in enumerate(zip(self.weights[:-1], self.biases[:-1])):
            z = np.dot(activations[-1], w) + b
            a = self._relu(z)
            activations.append(a)

        # Output layer (no ReLU, softmax applied separately)
        z = np.dot(activations[-1], self.weights[-1]) + self.biases[-1]
        output = self._softmax(z)

        return output, activations

    def predict(self, features: np.ndarray) -> GesturePrediction:
        """
        Predict gesture from feature vector.

        Args:
            features: 16-element feature vector [mav(4), zc(4), wl(4), ssc(4)]

        Returns:
            GesturePrediction with gesture, confidence, and probabilities
        """
        import time
        start = time.perf_counter()

        # Normalize
        x = self._normalize(features)

        # Forward pass
        probs, _ = self.forward(x)

        # Get prediction
        class_idx = np.argmax(probs)
        confidence = probs[class_idx]

        latency = (time.perf_counter() - start) * 1000

        return GesturePrediction(
            gesture=Gesture(class_idx),
            confidence=float(confidence),
            probabilities={g.name: float(probs[g.value]) for g in Gesture},
            latency_ms=latency
        )

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int = 100,
        batch_size: int = 32,
        validation_split: float = 0.2
    ) -> Dict:
        """
        Train the classifier.

        Args:
            X: Feature vectors (N x 16)
            y: Labels (N,) integers 0-4

        Returns:
            Training history dict
        """
        # Learn normalization parameters
        self.feature_mean = np.mean(X, axis=0)
        self.feature_std = np.std(X, axis=0)

        # Normalize
        X_norm = self._normalize(X)

        # Split validation
        n_val = int(len(X) * validation_split)
        indices = np.random.permutation(len(X))
        val_idx, train_idx = indices[:n_val], indices[n_val:]

        X_train, y_train = X_norm[train_idx], y[train_idx]
        X_val, y_val = X_norm[val_idx], y[val_idx]

        history = {'loss': [], 'accuracy': [], 'val_accuracy': []}

        for epoch in range(epochs):
            # Shuffle training data
            perm = np.random.permutation(len(X_train))
            X_shuffled = X_train[perm]
            y_shuffled = y_train[perm]

            epoch_loss = 0
            correct = 0

            # Mini-batch training
            for i in range(0, len(X_train), batch_size):
                X_batch = X_shuffled[i:i+batch_size]
                y_batch = y_shuffled[i:i+batch_size]

                batch_loss = 0

                for x, label in zip(X_batch, y_batch):
                    # Forward pass
                    output, activations = self.forward(x)

                    # Cross-entropy loss
                    loss = -np.log(output[label] + 1e-10)
                    batch_loss += loss

                    # Track accuracy
                    if np.argmax(output) == label:
                        correct += 1

                    # Backpropagation
                    self._backward(x, label, output, activations)

                epoch_loss += batch_loss

            # Calculate metrics
            train_acc = correct / len(X_train)
            val_acc = self._evaluate(X_val, y_val)

            history['loss'].append(epoch_loss / len(X_train))
            history['accuracy'].append(train_acc)
            history['val_accuracy'].append(val_acc)

            if epoch % 10 == 0:
                print(f"Epoch {epoch}: loss={epoch_loss/len(X_train):.4f}, "
                      f"acc={train_acc:.3f}, val_acc={val_acc:.3f}")

        self.trained = True
        self.training_accuracy = history['val_accuracy'][-1]

        return history

    def _backward(
        self,
        x: np.ndarray,
        label: int,
        output: np.ndarray,
        activations: List[np.ndarray]
    ):
        """Backpropagation with gradient descent"""

        # Output layer gradient (cross-entropy + softmax)
        d_output = output.copy()
        d_output[label] -= 1

        # Backprop through layers
        deltas = [d_output]

        for i in range(len(self.weights) - 1, 0, -1):
            d_hidden = np.dot(deltas[0], self.weights[i].T)
            d_hidden *= self._relu_derivative(activations[i])
            deltas.insert(0, d_hidden)

        # Update weights
        for i, (delta, activation) in enumerate(zip(deltas, activations)):
            grad_w = np.outer(activation, delta)
            grad_b = delta

            self.weights[i] -= self.learning_rate * grad_w
            self.biases[i] -= self.learning_rate * grad_b

    def _evaluate(self, X: np.ndarray, y: np.ndarray) -> float:
        """Calculate accuracy on dataset"""
        correct = 0
        for x, label in zip(X, y):
            output, _ = self.forward(x)
            if np.argmax(output) == label:
                correct += 1
        return correct / len(X)

    def save(self, path: str):
        """Save model to file"""
        model_data = {
            'weights': [w.tolist() for w in self.weights],
            'biases': [b.tolist() for b in self.biases],
            'feature_mean': self.feature_mean.tolist(),
            'feature_std': self.feature_std.tolist(),
            'input_size': self.input_size,
            'hidden_sizes': self.hidden_sizes,
            'num_classes': self.num_classes,
            'trained': self.trained,
            'training_accuracy': self.training_accuracy
        }

        with open(path, 'w') as f:
            json.dump(model_data, f)

        print(f"Model saved to {path}")

    @classmethod
    def load(cls, path: str) -> 'GestureClassifier':
        """Load model from file"""
        with open(path, 'r') as f:
            data = json.load(f)

        model = cls(
            input_size=data['input_size'],
            hidden_sizes=data['hidden_sizes'],
            num_classes=data['num_classes']
        )

        model.weights = [np.array(w) for w in data['weights']]
        model.biases = [np.array(b) for b in data['biases']]
        model.feature_mean = np.array(data['feature_mean'])
        model.feature_std = np.array(data['feature_std'])
        model.trained = data['trained']
        model.training_accuracy = data['training_accuracy']

        return model

    def export_arduino(self, path: str):
        """
        Export model as C header for Arduino.

        This lets us run inference directly on the microcontroller!
        """
        with open(path, 'w') as f:
            f.write("// Auto-generated gesture model for Arduino\n")
            f.write("// Generated by CC (Coalition Code)\n")
            f.write(f"// Training accuracy: {self.training_accuracy:.3f}\n\n")

            f.write("#ifndef GESTURE_MODEL_H\n")
            f.write("#define GESTURE_MODEL_H\n\n")

            f.write(f"#define NUM_INPUTS {self.input_size}\n")
            f.write(f"#define NUM_CLASSES {self.num_classes}\n")
            f.write(f"#define NUM_LAYERS {len(self.weights)}\n\n")

            # Feature normalization
            f.write("// Feature normalization\n")
            f.write(f"const float FEATURE_MEAN[{self.input_size}] = {{\n  ")
            f.write(", ".join(f"{v:.6f}f" for v in self.feature_mean))
            f.write("\n};\n\n")

            f.write(f"const float FEATURE_STD[{self.input_size}] = {{\n  ")
            f.write(", ".join(f"{v:.6f}f" for v in self.feature_std))
            f.write("\n};\n\n")

            # Layer sizes
            sizes = [self.input_size] + self.hidden_sizes + [self.num_classes]
            f.write(f"const int LAYER_SIZES[{len(sizes)}] = {{")
            f.write(", ".join(str(s) for s in sizes))
            f.write("};\n\n")

            # Weights and biases
            for i, (w, b) in enumerate(zip(self.weights, self.biases)):
                f.write(f"// Layer {i}: {w.shape[0]} -> {w.shape[1]}\n")
                f.write(f"const float WEIGHTS_{i}[{w.shape[0]}][{w.shape[1]}] = {{\n")
                for row in w:
                    f.write("  {")
                    f.write(", ".join(f"{v:.6f}f" for v in row))
                    f.write("},\n")
                f.write("};\n\n")

                f.write(f"const float BIASES_{i}[{b.shape[0]}] = {{\n  ")
                f.write(", ".join(f"{v:.6f}f" for v in b))
                f.write("\n};\n\n")

            # Gesture names
            f.write("const char* GESTURE_NAMES[] = {\n")
            for g in Gesture:
                f.write(f'  "{g.name}",\n')
            f.write("};\n\n")

            f.write("#endif // GESTURE_MODEL_H\n")

        print(f"Arduino header exported to {path}")


def generate_synthetic_training_data(
    samples_per_class: int = 200
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic EMG data for testing.

    In real use, this is replaced by calibration data from Thomas.
    """
    np.random.seed(42)

    X = []
    y = []

    # Pattern templates for each gesture (4 channels)
    # Based on typical EMG patterns for forearm muscles
    patterns = {
        Gesture.RELAX: {
            'mav': [0.1, 0.1, 0.1, 0.1],
            'zc': [5, 5, 5, 5],
            'wl': [0.2, 0.2, 0.2, 0.2],
            'ssc': [3, 3, 3, 3]
        },
        Gesture.FIST: {
            'mav': [0.8, 0.2, 0.7, 0.2],  # High flexors
            'zc': [20, 10, 18, 8],
            'wl': [1.5, 0.4, 1.3, 0.3],
            'ssc': [15, 6, 13, 5]
        },
        Gesture.OPEN: {
            'mav': [0.2, 0.8, 0.2, 0.7],  # High extensors
            'zc': [10, 22, 9, 20],
            'wl': [0.4, 1.6, 0.3, 1.4],
            'ssc': [6, 16, 5, 14]
        },
        Gesture.POINT: {
            'mav': [0.5, 0.5, 0.3, 0.3],  # Moderate mixed
            'zc': [15, 15, 10, 10],
            'wl': [0.9, 0.9, 0.5, 0.5],
            'ssc': [10, 10, 7, 7]
        },
        Gesture.WAVE: {
            'mav': [0.4, 0.4, 0.6, 0.6],  # Wrist dominant
            'zc': [12, 12, 18, 18],
            'wl': [0.7, 0.7, 1.1, 1.1],
            'ssc': [8, 8, 12, 12]
        }
    }

    for gesture in Gesture:
        pattern = patterns[gesture]
        for _ in range(samples_per_class):
            # Add noise to pattern
            noise = 0.15
            mav = np.array(pattern['mav']) + np.random.randn(4) * noise
            zc = np.array(pattern['zc']) + np.random.randn(4) * 3
            wl = np.array(pattern['wl']) + np.random.randn(4) * noise
            ssc = np.array(pattern['ssc']) + np.random.randn(4) * 2

            # Clip to reasonable ranges
            mav = np.clip(mav, 0, 2)
            zc = np.clip(zc, 0, 50)
            wl = np.clip(wl, 0, 3)
            ssc = np.clip(ssc, 0, 30)

            # Concatenate features
            features = np.concatenate([mav, zc, wl, ssc])
            X.append(features)
            y.append(gesture.value)

    return np.array(X), np.array(y)


if __name__ == "__main__":
    print("Training gesture classifier with synthetic data...")
    print("(In production, this uses real calibration data from Thomas)\n")

    # Generate synthetic data
    X, y = generate_synthetic_training_data(samples_per_class=200)
    print(f"Dataset: {len(X)} samples, {len(Gesture)} classes")

    # Create and train classifier
    classifier = GestureClassifier(
        input_size=16,
        hidden_sizes=[32, 16],
        num_classes=5,
        learning_rate=0.01
    )

    history = classifier.train(X, y, epochs=100, batch_size=32)

    print(f"\nFinal validation accuracy: {history['val_accuracy'][-1]:.3f}")

    # Test prediction
    test_features = X[0]
    prediction = classifier.predict(test_features)
    print(f"\nTest prediction:")
    print(f"  Gesture: {prediction.gesture.name}")
    print(f"  Confidence: {prediction.confidence:.3f}")
    print(f"  Latency: {prediction.latency_ms:.3f}ms")

    # Save model
    model_path = Path(__file__).parent.parent.parent / "models" / "gesture_model.json"
    model_path.parent.mkdir(exist_ok=True)
    classifier.save(str(model_path))

    # Export for Arduino
    arduino_path = Path(__file__).parent.parent.parent / "arduino" / "closed_loop" / "gesture_model.h"
    classifier.export_arduino(str(arduino_path))

    print("\nTraining complete!")
