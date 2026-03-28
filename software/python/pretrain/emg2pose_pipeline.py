#!/usr/bin/env python3
"""
emg2pose Pretrain Pipeline
===========================
Downloads Meta's emg2pose mini dataset, extracts features matching our
4-channel pipeline (MAV, ZC, WL, SSC), and pretrains the GestureClassifier.

The pretrained weights give the model a massive head start — 193 users'
muscle patterns instead of training from scratch on one person's data.

Usage:
    python emg2pose_pipeline.py --download    # Download mini dataset
    python emg2pose_pipeline.py --extract     # Extract features
    python emg2pose_pipeline.py --train       # Pretrain MLP
    python emg2pose_pipeline.py --all         # Do everything
    python emg2pose_pipeline.py --export      # Export weights for Arduino

Author: CC (Coalition Code)
Date: 2026-03-28
"""

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [pretrain] %(message)s")
logger = logging.getLogger("pretrain")

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "emg2pose"
FEATURES_DIR = DATA_DIR / "features"
WEIGHTS_DIR = PROJECT_ROOT / "software" / "python" / "pretrain" / "weights"

# ── EMG Feature Extraction ───────────────────────────────────────────────────
# These must match exactly what our signal_processing/emg_processor.py computes
# and what the Arduino firmware expects

SAMPLE_RATE = 2000  # emg2pose is 2kHz
WINDOW_SIZE_MS = 200  # 200ms windows (same as our real-time pipeline)
WINDOW_SAMPLES = int(SAMPLE_RATE * WINDOW_SIZE_MS / 1000)  # 400 samples
WINDOW_STRIDE_MS = 50  # 50ms stride for overlap
STRIDE_SAMPLES = int(SAMPLE_RATE * WINDOW_STRIDE_MS / 1000)  # 100 samples

# Channel mapping: emg2pose has 16 channels on a wristband
# Our system has 4 channels on specific forearm muscles
# Strategy: select 4 channels spaced evenly around the wristband
# that best approximate our electrode positions
CHANNEL_GROUPS = [
    [0, 1, 2, 3],      # Group 1: channels 0-3
    [4, 5, 6, 7],      # Group 2: channels 4-7
    [8, 9, 10, 11],    # Group 3: channels 8-11
    [12, 13, 14, 15],  # Group 4: channels 12-15
]
# For each group, we'll take the max-energy channel
# This simulates having 4 well-placed electrodes

# Gesture mapping: emg2pose has 29 stages, we need to map to our 5 gestures
# We'll map based on the stage descriptions in the dataset
GESTURE_MAP = {
    # emg2pose stages -> our gesture classes
    "fist": 1,          # FIST
    "open": 2,          # OPEN
    "point": 3,         # POINT (index extension)
    "wave": 4,          # WAVE
    "rest": 0,          # RELAX
    "relax": 0,         # RELAX
    "neutral": 0,       # RELAX
}
NUM_GESTURES = 5
GESTURE_NAMES = ["RELAX", "FIST", "OPEN", "POINT", "WAVE"]

# Zero-crossing threshold
ZC_THRESHOLD = 0.02


def compute_features_window(window: np.ndarray) -> np.ndarray:
    """
    Compute 4 time-domain features for each channel in a window.

    Args:
        window: shape (window_samples, n_channels)

    Returns:
        features: shape (n_channels * 4,) — [MAV, ZC, WL, SSC] per channel
    """
    n_channels = window.shape[1]
    features = np.zeros(n_channels * 4)

    for ch in range(n_channels):
        signal = window[:, ch]
        offset = ch * 4

        # MAV: Mean Absolute Value
        features[offset + 0] = np.mean(np.abs(signal))

        # ZC: Zero Crossings (with threshold to reduce noise)
        diff_sign = np.diff(np.sign(signal))
        zc_mask = np.abs(diff_sign) > 0
        amp_mask = np.abs(signal[:-1]) > ZC_THRESHOLD
        features[offset + 1] = np.sum(zc_mask & amp_mask)

        # WL: Waveform Length
        features[offset + 2] = np.sum(np.abs(np.diff(signal)))

        # SSC: Slope Sign Changes
        d = np.diff(signal)
        if len(d) > 1:
            ssc = np.sum((d[:-1] * d[1:]) < 0)
            features[offset + 3] = ssc

    return features


def reduce_channels(emg_16ch: np.ndarray) -> np.ndarray:
    """
    Reduce 16-channel wristband EMG to 4 channels.

    Strategy: for each of 4 channel groups (4 channels each),
    select the channel with highest energy (RMS). This approximates
    having 4 well-placed electrodes on the forearm.

    Args:
        emg_16ch: shape (samples, 16)

    Returns:
        emg_4ch: shape (samples, 4)
    """
    n_samples = emg_16ch.shape[0]
    emg_4ch = np.zeros((n_samples, 4))

    for i, group in enumerate(CHANNEL_GROUPS):
        # Compute RMS energy for each channel in the group
        energies = [np.sqrt(np.mean(emg_16ch[:, ch] ** 2)) for ch in group]
        best_ch = group[np.argmax(energies)]
        emg_4ch[:, i] = emg_16ch[:, best_ch]

    return emg_4ch


def extract_features_from_session(emg_data: np.ndarray) -> np.ndarray:
    """
    Extract windowed features from a full session of EMG data.

    Args:
        emg_data: shape (samples, 4) — already channel-reduced

    Returns:
        features: shape (n_windows, 16) — 4 features × 4 channels
    """
    n_samples = emg_data.shape[0]
    windows = []

    for start in range(0, n_samples - WINDOW_SAMPLES, STRIDE_SAMPLES):
        window = emg_data[start:start + WINDOW_SAMPLES]
        feat = compute_features_window(window)
        windows.append(feat)

    return np.array(windows) if windows else np.empty((0, 16))


# ── Download ─────────────────────────────────────────────────────────────────

def download_mini_dataset():
    """Download the emg2pose mini dataset (~600MB)."""
    import urllib.request

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    url = "https://fb-ctrl-oss.s3.amazonaws.com/emg2pose/emg2pose_dataset_mini.tar"
    tar_path = DATA_DIR / "emg2pose_dataset_mini.tar"

    if tar_path.exists():
        logger.info("Mini dataset already downloaded: %s", tar_path)
        return tar_path

    logger.info("Downloading emg2pose mini dataset (~600MB)...")
    logger.info("URL: %s", url)

    def progress(count, block_size, total_size):
        pct = min(100, int(count * block_size * 100 / total_size))
        if count % 100 == 0:
            mb = count * block_size / 1e6
            print(f"\r  {pct}% ({mb:.0f}MB)", end="", flush=True)

    urllib.request.urlretrieve(url, str(tar_path), reporthook=progress)
    print()
    logger.info("Downloaded to %s", tar_path)

    # Extract
    import tarfile
    logger.info("Extracting...")
    with tarfile.open(tar_path, "r") as tar:
        tar.extractall(str(DATA_DIR))
    logger.info("Extraction complete")

    return tar_path


# ── Feature Extraction ───────────────────────────────────────────────────────

def extract_all_features():
    """Extract features from all HDF5 session files."""
    try:
        import h5py
    except ImportError:
        logger.error("h5py required: pip install h5py")
        sys.exit(1)

    FEATURES_DIR.mkdir(parents=True, exist_ok=True)

    # Find all HDF5 files
    h5_files = sorted(DATA_DIR.rglob("*.hdf5"))
    if not h5_files:
        h5_files = sorted(DATA_DIR.rglob("*.h5"))
    if not h5_files:
        logger.error("No HDF5 files found in %s — run with --download first", DATA_DIR)
        return

    logger.info("Found %d session files", len(h5_files))

    all_features = []
    all_labels = []
    processed = 0
    skipped = 0

    for h5_path in h5_files:
        try:
            with h5py.File(h5_path, "r") as f:
                # emg2pose stores EMG in 'emg' dataset, poses in 'joint_angles'
                if "emg" not in f:
                    skipped += 1
                    continue

                emg_raw = f["emg"][:]  # shape: (samples, 16)

                if emg_raw.shape[1] < 16:
                    skipped += 1
                    continue

                # Reduce to 4 channels
                emg_4ch = reduce_channels(emg_raw)

                # Extract windowed features
                features = extract_features_from_session(emg_4ch)

                if len(features) == 0:
                    skipped += 1
                    continue

                # Try to get gesture labels from filename or metadata
                # emg2pose stages are encoded in the file metadata or path
                stage_name = h5_path.stem.lower()
                gesture_label = None

                for keyword, label in GESTURE_MAP.items():
                    if keyword in stage_name:
                        gesture_label = label
                        break

                if gesture_label is None:
                    # For unmapped stages, try to classify by EMG energy
                    # High energy → active gesture, low energy → rest
                    mean_energy = np.mean(features[:, 0::4])  # MAV channels
                    gesture_label = 0 if mean_energy < 0.05 else -1  # -1 = unknown

                if gesture_label >= 0:
                    labels = np.full(len(features), gesture_label)
                    all_features.append(features)
                    all_labels.append(labels)

                processed += 1
                if processed % 50 == 0:
                    logger.info("  Processed %d/%d files (%d skipped)",
                                processed, len(h5_files), skipped)

        except Exception as e:
            logger.warning("  Error processing %s: %s", h5_path.name, e)
            skipped += 1

    if not all_features:
        logger.error("No features extracted!")
        return

    X = np.concatenate(all_features, axis=0)
    y = np.concatenate(all_labels, axis=0)

    logger.info("Feature extraction complete:")
    logger.info("  Sessions processed: %d (skipped: %d)", processed, skipped)
    logger.info("  Total windows: %d", len(X))
    logger.info("  Feature shape: %s", X.shape)
    logger.info("  Label distribution:")
    for i, name in enumerate(GESTURE_NAMES):
        count = np.sum(y == i)
        logger.info("    %s: %d (%.1f%%)", name, count, count / len(y) * 100)

    # Save
    np.save(FEATURES_DIR / "X_pretrain.npy", X)
    np.save(FEATURES_DIR / "y_pretrain.npy", y)
    logger.info("Saved to %s", FEATURES_DIR)

    return X, y


# ── Training ─────────────────────────────────────────────────────────────────

def pretrain_model():
    """Pretrain the GestureClassifier on extracted features."""
    X_path = FEATURES_DIR / "X_pretrain.npy"
    y_path = FEATURES_DIR / "y_pretrain.npy"

    if not X_path.exists():
        logger.error("Features not found — run with --extract first")
        return

    X = np.load(X_path)
    y = np.load(y_path)

    logger.info("Loaded %d samples, %d features", len(X), X.shape[1])

    # Normalize features
    feature_mean = X.mean(axis=0)
    feature_std = X.std(axis=0)
    feature_std[feature_std < 1e-8] = 1.0  # Prevent division by zero
    X_norm = (X - feature_mean) / feature_std

    # Train/val split (80/20)
    n = len(X_norm)
    indices = np.random.permutation(n)
    split = int(0.8 * n)
    X_train, X_val = X_norm[indices[:split]], X_norm[indices[split:]]
    y_train, y_val = y[indices[:split]], y[indices[split:]]

    logger.info("Train: %d, Val: %d", len(X_train), len(X_val))

    # Import our model
    sys.path.insert(0, str(PROJECT_ROOT / "software" / "python"))
    from gesture_recognition.gesture_model import GestureClassifier

    model = GestureClassifier(
        input_size=16,
        hidden_sizes=[32, 16],
        num_classes=NUM_GESTURES,
        learning_rate=0.005,
    )

    # Set normalization parameters
    model.feature_mean = feature_mean
    model.feature_std = feature_std

    # Train
    epochs = 50
    batch_size = 256
    best_val_acc = 0
    best_weights = None

    logger.info("Training for %d epochs, batch size %d...", epochs, batch_size)

    for epoch in range(epochs):
        # Shuffle training data
        perm = np.random.permutation(len(X_train))
        X_shuffled = X_train[perm]
        y_shuffled = y_train[perm]

        epoch_loss = 0
        n_batches = 0

        for i in range(0, len(X_shuffled), batch_size):
            X_batch = X_shuffled[i:i + batch_size]
            y_batch = y_shuffled[i:i + batch_size]

            # Forward + backward pass using model's built-in training
            for j in range(len(X_batch)):
                model._forward(X_batch[j])
                target = np.zeros(NUM_GESTURES)
                target[int(y_batch[j])] = 1.0
                model._backward(target)

            n_batches += 1

        # Validation accuracy
        correct = 0
        for j in range(len(X_val)):
            pred = model.predict_raw(X_val[j])
            if np.argmax(pred) == y_val[j]:
                correct += 1

        val_acc = correct / len(X_val)

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_weights = {
                "weights": [w.copy() for w in model.weights],
                "biases": [b.copy() for b in model.biases],
                "feature_mean": feature_mean.copy(),
                "feature_std": feature_std.copy(),
            }

        if (epoch + 1) % 10 == 0 or epoch == 0:
            logger.info("  Epoch %d/%d — Val accuracy: %.1f%% (best: %.1f%%)",
                        epoch + 1, epochs, val_acc * 100, best_val_acc * 100)

    # Restore best weights
    if best_weights:
        model.weights = best_weights["weights"]
        model.biases = best_weights["biases"]
        model.feature_mean = best_weights["feature_mean"]
        model.feature_std = best_weights["feature_std"]

    model.trained = True
    model.training_accuracy = best_val_acc

    # Save weights
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    weights_path = WEIGHTS_DIR / "pretrained_emg2pose.npz"
    np.savez(
        weights_path,
        **{f"w{i}": w for i, w in enumerate(model.weights)},
        **{f"b{i}": b for i, b in enumerate(model.biases)},
        feature_mean=model.feature_mean,
        feature_std=model.feature_std,
    )

    logger.info("Pretrained weights saved to %s", weights_path)
    logger.info("Best validation accuracy: %.1f%%", best_val_acc * 100)
    logger.info("")
    logger.info("To use in calibration: load these weights, then fine-tune")
    logger.info("on Thomas's calibration data. Expected calibration time: 2-3 min")

    return model


# ── Arduino Export ────────────────────────────────────────────────────────────

def export_arduino_header():
    """Export pretrained weights as a C header for Arduino."""
    weights_path = WEIGHTS_DIR / "pretrained_emg2pose.npz"
    if not weights_path.exists():
        logger.error("Pretrained weights not found — run with --train first")
        return

    data = np.load(weights_path)
    header_path = PROJECT_ROOT / "software" / "arduino" / "closed_loop" / "gesture_model_pretrained.h"

    with open(header_path, "w") as f:
        f.write("// Auto-generated pretrained gesture model weights\n")
        f.write("// Source: emg2pose dataset (193 users, 370 hours)\n")
        f.write("// Architecture: MLP 16->32->16->5\n")
        f.write(f"// Generated by CC's pretrain pipeline\n\n")
        f.write("#ifndef GESTURE_MODEL_PRETRAINED_H\n")
        f.write("#define GESTURE_MODEL_PRETRAINED_H\n\n")

        # Export each weight matrix and bias vector
        for key in sorted(data.files):
            arr = data[key]
            flat = arr.flatten()
            name = key.upper()

            if arr.ndim == 2:
                f.write(f"// Shape: ({arr.shape[0]}, {arr.shape[1]})\n")
            else:
                f.write(f"// Shape: ({arr.shape[0]},)\n")

            f.write(f"const float {name}[] = {{\n  ")
            for i, val in enumerate(flat):
                f.write(f"{val:.6f}f")
                if i < len(flat) - 1:
                    f.write(", ")
                if (i + 1) % 8 == 0:
                    f.write("\n  ")
            f.write("\n};\n\n")

        f.write("#endif // GESTURE_MODEL_PRETRAINED_H\n")

    logger.info("Arduino header exported to %s", header_path)
    logger.info("Include this in closed_loop.ino to use pretrained weights")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="emg2pose Pretrain Pipeline")
    parser.add_argument("--download", action="store_true", help="Download mini dataset")
    parser.add_argument("--extract", action="store_true", help="Extract features")
    parser.add_argument("--train", action="store_true", help="Pretrain MLP")
    parser.add_argument("--export", action="store_true", help="Export Arduino header")
    parser.add_argument("--all", action="store_true", help="Run full pipeline")
    args = parser.parse_args()

    if args.all:
        args.download = args.extract = args.train = args.export = True

    if not any([args.download, args.extract, args.train, args.export]):
        parser.print_help()
        return

    print("=" * 50)
    print("emg2pose Pretrain Pipeline")
    print("=" * 50)

    if args.download:
        download_mini_dataset()

    if args.extract:
        extract_all_features()

    if args.train:
        pretrain_model()

    if args.export:
        export_arduino_header()


if __name__ == "__main__":
    main()
