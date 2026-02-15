#!/usr/bin/env python3
"""
Live EMG Visualization

Real-time display of EMG signals from Arduino.
Useful for debugging sensor placement and signal quality.

Author: CC (Coalition Code)
Date: 2026-02-14

Usage:
    python live_emg.py --port COM3
    python live_emg.py --simulate
"""

import argparse
import sys
import time
from pathlib import Path
from collections import deque
import numpy as np

# Check for matplotlib (optional dependency)
try:
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    from matplotlib.patches import Rectangle
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Note: matplotlib not installed. Using text-based display.")

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from signal_processing.emg_processor import EMGStreamReader, EMGSample


class TextDisplay:
    """Simple text-based EMG display for terminals"""

    def __init__(self, num_channels: int = 4, width: int = 50):
        self.num_channels = num_channels
        self.width = width
        self.channel_names = [
            "Flex Dig (A0)",
            "Ext Dig  (A1)",
            "Flex Car (A2)",
            "Ext Car  (A3)"
        ]

    def update(self, values: np.ndarray, mav: np.ndarray):
        """Update display with new values"""
        # Clear previous lines
        print("\033[F" * (self.num_channels + 2), end="")

        print("-" * (self.width + 25))
        for i in range(self.num_channels):
            # Normalize value to 0-1 range (12-bit ADC)
            normalized = (values[i] - 1500) / 1500
            normalized = max(0, min(1, (normalized + 1) / 2))

            # Create bar
            bar_len = int(normalized * self.width)
            bar = "#" * bar_len + "-" * (self.width - bar_len)

            # MAV indicator
            mav_pct = min(mav[i] / 500, 1.0) * 100

            print(f"{self.channel_names[i]:12} [{bar}] MAV:{mav_pct:5.1f}%")
        print("-" * (self.width + 25))

    def setup(self):
        """Initialize display"""
        # Print initial empty lines
        for _ in range(self.num_channels + 2):
            print()


class GraphDisplay:
    """Matplotlib-based real-time EMG graph"""

    def __init__(self, num_channels: int = 4, history_len: int = 500):
        self.num_channels = num_channels
        self.history_len = history_len

        # Data buffers
        self.data = [deque(maxlen=history_len) for _ in range(num_channels)]
        self.mav = [deque(maxlen=history_len) for _ in range(num_channels)]

        # Initialize with zeros
        for ch in range(num_channels):
            for _ in range(history_len):
                self.data[ch].append(2048)
                self.mav[ch].append(0)

        # Channel info
        self.channel_names = [
            "Flexor Digitorum (A0)",
            "Extensor Digitorum (A1)",
            "Flexor Carpi (A2)",
            "Extensor Carpi (A3)"
        ]
        self.channel_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']

        # Current gesture
        self.current_gesture = "RELAX"
        self.confidence = 0.0

    def setup(self):
        """Create matplotlib figure"""
        plt.style.use('dark_background')

        self.fig, self.axes = plt.subplots(
            self.num_channels, 1,
            figsize=(12, 8),
            sharex=True
        )

        self.fig.suptitle('Hand Project - Live EMG Signals', fontsize=14)

        self.lines = []
        self.mav_lines = []

        x = np.arange(self.history_len)

        for i, ax in enumerate(self.axes):
            # Raw signal
            line, = ax.plot(x, list(self.data[i]),
                           color=self.channel_colors[i],
                           linewidth=1,
                           label='Raw')

            # MAV overlay (scaled)
            mav_line, = ax.plot(x, list(self.mav[i]),
                               color='white',
                               linewidth=2,
                               alpha=0.7,
                               label='MAV')

            self.lines.append(line)
            self.mav_lines.append(mav_line)

            ax.set_ylabel(self.channel_names[i], fontsize=9)
            ax.set_ylim(0, 4096)
            ax.axhline(y=2048, color='gray', linestyle='--', alpha=0.3)
            ax.legend(loc='upper right', fontsize=8)
            ax.grid(True, alpha=0.2)

        self.axes[-1].set_xlabel('Samples')

        # Add gesture display
        self.gesture_text = self.fig.text(
            0.02, 0.98,
            f"Gesture: {self.current_gesture}",
            fontsize=12,
            color='white',
            verticalalignment='top'
        )

        self.confidence_text = self.fig.text(
            0.02, 0.94,
            f"Confidence: {self.confidence:.1%}",
            fontsize=10,
            color='gray',
            verticalalignment='top'
        )

        plt.tight_layout()
        plt.subplots_adjust(top=0.92)

    def update(self, values: np.ndarray, mav: np.ndarray):
        """Add new data point"""
        for ch in range(self.num_channels):
            self.data[ch].append(values[ch])
            # Scale MAV for display (add to midpoint)
            self.mav[ch].append(2048 + mav[ch] * 2)

    def update_gesture(self, gesture: str, confidence: float):
        """Update gesture display"""
        self.current_gesture = gesture
        self.confidence = confidence

    def animate(self, frame):
        """Animation update function"""
        for i in range(self.num_channels):
            self.lines[i].set_ydata(list(self.data[i]))
            self.mav_lines[i].set_ydata(list(self.mav[i]))

        self.gesture_text.set_text(f"Gesture: {self.current_gesture}")
        self.confidence_text.set_text(f"Confidence: {self.confidence:.1%}")

        return self.lines + self.mav_lines + [self.gesture_text, self.confidence_text]

    def show(self):
        """Start animation"""
        self.ani = animation.FuncAnimation(
            self.fig,
            self.animate,
            interval=20,  # 50 FPS
            blit=True
        )
        plt.show()


def simulate_emg():
    """Generate synthetic EMG-like data for testing"""
    t = time.time()

    # Simulate muscle activity patterns
    values = np.array([
        2048 + int(500 * np.sin(2 * np.pi * 50 * t) + np.random.randn() * 100),
        2048 + int(300 * np.sin(2 * np.pi * 80 * t + 1) + np.random.randn() * 80),
        2048 + int(400 * np.sin(2 * np.pi * 60 * t + 2) + np.random.randn() * 90),
        2048 + int(200 * np.sin(2 * np.pi * 100 * t + 3) + np.random.randn() * 70),
    ])

    # Simulate occasional muscle contractions
    if int(t) % 5 < 2:  # Contract every 5 seconds
        values[0] += 800
        values[2] += 600

    mav = np.abs(values - 2048) / 2

    return values, mav


def main():
    parser = argparse.ArgumentParser(description="Live EMG Visualization")
    parser.add_argument("--port", "-p", default="COM3", help="Serial port")
    parser.add_argument("--simulate", "-s", action="store_true", help="Simulation mode")
    parser.add_argument("--text", "-t", action="store_true", help="Text display only")

    args = parser.parse_args()

    # Choose display type
    use_graph = HAS_MATPLOTLIB and not args.text

    if use_graph:
        display = GraphDisplay()
    else:
        display = TextDisplay()

    display.setup()

    # Connect or simulate
    reader = None
    if not args.simulate:
        try:
            reader = EMGStreamReader(args.port)
            if not reader.connect():
                print("Could not connect to Arduino. Use --simulate for demo.")
                return
            reader.start_streaming()
        except Exception as e:
            print(f"Connection error: {e}")
            print("Use --simulate for demo mode.")
            return

    print("\nStarting live display. Press Ctrl+C to stop.\n")

    try:
        if use_graph:
            # Graph mode - use matplotlib animation
            def update_data(frame):
                if args.simulate:
                    values, mav = simulate_emg()
                else:
                    sample = reader.read_sample()
                    if sample:
                        values = sample.raw
                        mav = sample.mav
                    else:
                        return display.lines

                display.update(values, mav)
                return display.animate(frame)

            ani = animation.FuncAnimation(
                display.fig,
                update_data,
                interval=10,
                blit=True
            )
            plt.show()
        else:
            # Text mode - simple loop
            while True:
                if args.simulate:
                    values, mav = simulate_emg()
                else:
                    sample = reader.read_sample()
                    if sample:
                        values = sample.raw
                        mav = sample.mav
                    else:
                        continue

                display.update(values, mav)
                time.sleep(0.05)  # 20 FPS

    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        if reader:
            reader.close()


if __name__ == "__main__":
    main()
