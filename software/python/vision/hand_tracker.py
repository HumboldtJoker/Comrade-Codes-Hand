"""
hand_tracker.py — MediaPipe hand landmark tracking for FES feedback.

Wraps MediaPipe Hands to extract 21-point hand skeleton from a webcam
frame and compute per-finger joint angles. Designed for real-time use
in the FES control loop (~5ms inference on modern hardware).

Phase 1 deliverable per docs/CAMERA_INTEGRATION.md.

Usage:
    tracker = HandTracker()
    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        pose = tracker.process(frame)
        if pose:
            print(pose.finger_angles)
"""
import time
import math
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from enum import IntEnum

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import mediapipe as mp
except ImportError:
    mp = None


class Finger(IntEnum):
    THUMB = 0
    INDEX = 1
    MIDDLE = 2
    RING = 3
    PINKY = 4


# MediaPipe landmark indices per finger (MCP, PIP, DIP, TIP)
FINGER_LANDMARKS = {
    Finger.THUMB:  [1, 2, 3, 4],
    Finger.INDEX:  [5, 6, 7, 8],
    Finger.MIDDLE: [9, 10, 11, 12],
    Finger.RING:   [13, 14, 15, 16],
    Finger.PINKY:  [17, 18, 19, 20],
}

WRIST = 0


@dataclass
class FingerAngles:
    """Per-finger flexion angles in degrees (0 = extended, ~90 = fully flexed)."""
    thumb: float = 0.0
    index: float = 0.0
    middle: float = 0.0
    ring: float = 0.0
    pinky: float = 0.0

    def as_array(self) -> np.ndarray:
        return np.array([self.thumb, self.index, self.middle,
                         self.ring, self.pinky])

    def __getitem__(self, finger: Finger) -> float:
        return self.as_array()[finger]


@dataclass
class HandPose:
    """Complete hand pose from a single frame."""
    landmarks: np.ndarray  # (21, 3) — x, y, z per landmark
    finger_angles: FingerAngles
    handedness: str  # "Left" or "Right"
    confidence: float
    timestamp: float
    frame_index: int = 0

    @property
    def wrist(self) -> np.ndarray:
        return self.landmarks[WRIST]


def _angle_between(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle at point b formed by segments a-b and b-c, in degrees."""
    ba = a - b
    bc = c - b
    dot = np.dot(ba, bc)
    mag = np.linalg.norm(ba) * np.linalg.norm(bc)
    if mag < 1e-8:
        return 0.0
    cos_angle = np.clip(dot / mag, -1.0, 1.0)
    return math.degrees(math.acos(cos_angle))


def _finger_flexion(landmarks: np.ndarray, finger: Finger) -> float:
    """Compute flexion angle for a finger using its PIP joint angle.

    Uses the angle at the PIP joint (middle joint of the finger).
    Extended finger ≈ 170-180 degrees, fully flexed ≈ 60-90 degrees.
    Returns a normalized 0-90 scale where 0 = extended, 90 = fully flexed.
    """
    indices = FINGER_LANDMARKS[finger]
    mcp = landmarks[indices[0]]
    pip = landmarks[indices[1]]
    dip = landmarks[indices[2]]

    raw_angle = _angle_between(mcp, pip, dip)
    flexion = max(0.0, 180.0 - raw_angle)
    return min(flexion, 90.0)


class HandTracker:
    """Real-time hand landmark tracker using MediaPipe.

    Args:
        max_hands: Number of hands to detect (1 for patient hand).
        min_detection_confidence: MediaPipe detection threshold.
        min_tracking_confidence: MediaPipe tracking threshold.
        target_hand: "Left" or "Right" — which hand to track.
            None means track whichever hand is detected.
    """

    def __init__(
        self,
        max_hands: int = 1,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.6,
        target_hand: Optional[str] = None,
    ):
        if mp is None:
            raise ImportError("mediapipe is required: pip install mediapipe")
        if cv2 is None:
            raise ImportError("opencv-python is required: pip install opencv-python")

        self._mp_hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=max_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._target_hand = target_hand
        self._frame_count = 0
        self._last_pose: Optional[HandPose] = None

    def process(self, frame: np.ndarray) -> Optional[HandPose]:
        """Process a BGR frame and return hand pose if detected.

        Args:
            frame: BGR image from cv2.VideoCapture.

        Returns:
            HandPose if a hand is detected, None otherwise.
        """
        t0 = time.perf_counter()
        self._frame_count += 1

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._mp_hands.process(rgb)

        if not results.multi_hand_landmarks:
            return None

        hand_idx = 0
        handedness = "Unknown"
        confidence = 0.0

        if results.multi_handedness:
            for i, hand_info in enumerate(results.multi_handedness):
                label = hand_info.classification[0].label
                score = hand_info.classification[0].score
                if self._target_hand and label != self._target_hand:
                    continue
                hand_idx = i
                handedness = label
                confidence = score
                break

        if hand_idx >= len(results.multi_hand_landmarks):
            return None

        hand_lm = results.multi_hand_landmarks[hand_idx]
        h, w = frame.shape[:2]

        landmarks = np.array([
            [lm.x * w, lm.y * h, lm.z * w]
            for lm in hand_lm.landmark
        ])

        angles = FingerAngles(
            thumb=_finger_flexion(landmarks, Finger.THUMB),
            index=_finger_flexion(landmarks, Finger.INDEX),
            middle=_finger_flexion(landmarks, Finger.MIDDLE),
            ring=_finger_flexion(landmarks, Finger.RING),
            pinky=_finger_flexion(landmarks, Finger.PINKY),
        )

        pose = HandPose(
            landmarks=landmarks,
            finger_angles=angles,
            handedness=handedness,
            confidence=confidence,
            timestamp=time.perf_counter(),
            frame_index=self._frame_count,
        )
        self._last_pose = pose
        return pose

    @property
    def last_pose(self) -> Optional[HandPose]:
        return self._last_pose

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def close(self):
        self._mp_hands.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def draw_hand(frame: np.ndarray, pose: HandPose,
              color: Tuple[int, int, int] = (0, 255, 128),
              thickness: int = 2) -> np.ndarray:
    """Draw hand skeleton on a frame for visualization."""
    if cv2 is None:
        return frame

    annotated = frame.copy()
    lm = pose.landmarks

    connections = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (0, 5), (5, 6), (6, 7), (7, 8),
        (0, 9), (9, 10), (10, 11), (11, 12),
        (0, 13), (13, 14), (14, 15), (15, 16),
        (0, 17), (17, 18), (18, 19), (19, 20),
        (5, 9), (9, 13), (13, 17),
    ]

    for i, j in connections:
        p1 = (int(lm[i][0]), int(lm[i][1]))
        p2 = (int(lm[j][0]), int(lm[j][1]))
        cv2.line(annotated, p1, p2, color, thickness)

    for i in range(21):
        pt = (int(lm[i][0]), int(lm[i][1]))
        r = 5 if i in [4, 8, 12, 16, 20] else 3
        cv2.circle(annotated, pt, r, (0, 200, 255), -1)

    return annotated


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hand tracker standalone test")
    parser.add_argument("--camera", type=int, default=0, help="Camera index")
    parser.add_argument("--hand", choices=["Left", "Right"], default=None,
                        help="Which hand to track")
    parser.add_argument("--log", action="store_true", help="Log angles to CSV")
    args = parser.parse_args()

    if cv2 is None:
        print("ERROR: opencv-python required. pip install opencv-python")
        exit(1)
    if mp is None:
        print("ERROR: mediapipe required. pip install mediapipe")
        exit(1)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"ERROR: Could not open camera {args.camera}")
        exit(1)

    log_file = None
    if args.log:
        log_file = open("hand_tracking_log.csv", "w")
        log_file.write("frame,time,thumb,index,middle,ring,pinky,confidence\n")

    print(f"Hand Tracker — Camera {args.camera}")
    print(f"Target hand: {args.hand or 'any'}")
    print("Press 'q' to quit")

    with HandTracker(target_hand=args.hand) as tracker:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            pose = tracker.process(frame)

            if pose:
                a = pose.finger_angles
                frame = draw_hand(frame, pose)

                text = (f"T:{a.thumb:.0f} I:{a.index:.0f} M:{a.middle:.0f} "
                        f"R:{a.ring:.0f} P:{a.pinky:.0f}")
                cv2.putText(frame, text, (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 128), 2)
                cv2.putText(frame, f"{pose.handedness} ({pose.confidence:.2f})",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (200, 200, 200), 1)

                if log_file:
                    log_file.write(
                        f"{pose.frame_index},{pose.timestamp:.4f},"
                        f"{a.thumb:.1f},{a.index:.1f},{a.middle:.1f},"
                        f"{a.ring:.1f},{a.pinky:.1f},{pose.confidence:.3f}\n"
                    )
            else:
                cv2.putText(frame, "No hand detected", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow("Hand Tracker", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()
    if log_file:
        log_file.close()
        print(f"Logged {tracker.frame_count} frames to hand_tracking_log.csv")
