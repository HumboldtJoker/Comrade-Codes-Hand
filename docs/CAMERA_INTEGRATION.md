# Camera-Assisted FES: Visual Feedback Integration

**Author**: CC (Coalition Code)
**Date**: April 2026
**Status**: Architecture design — implementation pending

---

## Why Camera

EMG tells us what the user *intends*. FES makes the muscles *move*. But neither tells us what the hand *actually did*. Without visual feedback, the system is open-loop on the output side — it fires stimulation and hopes for the best.

Camera closes the loop: intent (EMG) → action (FES) → observation (camera) → correction.

This is the difference between "the system tried" and "the system succeeded."

### Research Support

- 18.3% of modern FES systems use vision-based sensing ([PMC11355777](https://pmc.ncbi.nlm.nih.gov/articles/PMC11355777/))
- Kinematic + EMG closed-loop FES achieves R² = 0.940 for joint angle accuracy ([Nature 2026](https://www.nature.com/articles/s41598-025-31180-1))
- MediaPipe Hands validated for clinical hand assessment ([ScienceDirect 2024](https://www.sciencedirect.com/science/article/pii/S1746809424005664))
- Real-time EMG prosthetic control achieves 250ms grasp ([PMC12034578](https://pmc.ncbi.nlm.nih.gov/articles/PMC12034578/))

---

## Architecture

### Current Pipeline (EMG + FES, no camera)

```
EMG sensors → feature extraction → gesture classification → FES pattern → muscles
     ↑                                                                      |
     └──────────────────── EMG reads new state ←────────────────────────────┘
```

Feedback is EMG-only. Slow (muscle response delay), noisy (EMG is inherently noisy), and indirect (measuring electrical activity, not actual position).

### Proposed Pipeline (EMG + Camera + FES)

```
EMG sensors ─→ intent classifier ─→ target pose (21 landmarks)
                                           |
                                    ┌──────┴──────┐
                                    │  ERROR NODE  │
                                    │ target-actual │
                                    └──────┬──────┘
                                           |
Camera ──→ MediaPipe ──→ actual pose ──────┘
                                           |
                                    ┌──────┴──────┐
                                    │   FES CALC   │
                                    │ per-channel  │
                                    │ correction   │
                                    └──────┬──────┘
                                           |
                                    NeuroStimDuino → muscles
                                           |
                                    Camera confirms → loop
```

### The Error Signal

This is the key innovation. The error between intended and actual hand pose drives per-channel FES adjustment:

```python
for finger in [thumb, index, middle, ring, pinky]:
    target_angle = intent_classifier.predict(emg_features)[finger]
    actual_angle = mediapipe.landmarks[finger].angle()
    error = target_angle - actual_angle

    if abs(error) > threshold:
        # Increase/decrease stimulation for this finger's muscle group
        fes_channels[finger].adjust(error * gain)
```

Per-finger correction. Not whole-hand on/off.

---

## MediaPipe Integration

### Why MediaPipe

- Real-time 21-point hand skeleton from single RGB camera
- Runs on-device (no cloud dependency)
- <5ms inference on modern hardware
- Clinically validated for hand assessment
- Free, open-source (Apache 2.0)
- Works with any USB webcam ($10-20)

### 21 Landmarks

```
        8   12  16  20        ← fingertips
        |   |   |   |
        7   11  15  19
        |   |   |   |
        6   10  14  18
        |   |   |   |
        5   9   13  17        ← MCP joints
         \  |   |  /
          \ |   | /
           \|   |/
      4─3─2─1───0             ← wrist
             |
            thumb
```

Each landmark gives (x, y, z) coordinates. Joint angles computed from consecutive landmarks. Gives us per-finger flexion/extension in real-time.

### Latency Budget

| Stage | Time | Cumulative |
|-------|------|------------|
| Camera capture | 3ms | 3ms |
| MediaPipe inference | 5ms | 8ms |
| Error computation | <1ms | 9ms |
| FES command (I2C) | 2ms | 11ms |
| EMG read (parallel) | 4ms | — |
| **Total per cycle** | **~11ms** | **90Hz possible** |

Well within our 50Hz (20ms) control loop budget. Camera adds ~8ms but we gain closed-loop accuracy.

---

## Hardware Addition

| Component | Spec | Cost | Notes |
|-----------|------|------|-------|
| USB webcam | 720p, 30fps+ | $15 | Any generic works; 60fps preferred |
| Camera mount | 3D printed | $2 | Clips to forearm mount, angled at hand |
| USB cable | Type-A | $3 | To Arduino host or companion Raspberry Pi |

**Additional compute option**: If Arduino Due can't run MediaPipe, add a Raspberry Pi Zero 2W ($15) as camera processor. Communicates pose data to Arduino via serial. Total added cost: $35.

---

## Implementation Plan

### Phase 1: Camera Standalone (no FES integration)
- Mount webcam, run MediaPipe, display live hand skeleton
- Verify tracking accuracy across skin tones, lighting, angles
- Log landmark data for offline analysis
- **Output**: `software/python/vision/hand_tracker.py`

### Phase 2: Error Signal Integration
- Connect MediaPipe output to control loop
- Compute per-finger error signals
- Log error vs time (characterize tracking accuracy)
- Run with FES in open-loop mode (camera observes but doesn't control)
- **Output**: `software/python/vision/error_computer.py`

### Phase 3: Closed-Loop Camera-FES
- Camera error signal drives FES channel adjustment
- Per-finger PID or proportional control
- Tune gain parameters (too aggressive = oscillation, too conservative = slow)
- Verify safety system handles camera-driven corrections
- **Output**: Updated `software/arduino/closed_loop/closed_loop.ino`

### Phase 4: Calibration Integration
- Camera-assisted calibration (show target pose, stimulate, measure result)
- Automatic per-channel gain tuning
- Per-user model refinement using visual ground truth
- **Output**: Updated `software/python/calibration/calibrate.py`

---

## Safety Considerations

Camera adds a safety layer (Layer 7 in our 8-layer system):

**Camera safety checks:**
- If camera loses hand tracking → pause FES, alert user
- If actual pose diverges from intent by >45 degrees on any finger → emergency reduce
- If hand exits camera frame → pause until reacquired
- Camera failure is NOT a safety hazard (system falls back to EMG-only mode)

**Camera does NOT replace EMG feedback.** It supplements it. The system must be safe without camera (degraded accuracy, not degraded safety).

---

## Open Questions for Team

1. **Camera placement**: Mounted on forearm looking down at hand? Or external tripod? Forearm mount moves with the arm but may have angle issues. External mount is more stable but limits mobility.

2. **Depth camera vs RGB**: MediaPipe works with RGB. A depth camera (Intel RealSense, ~$200) gives true 3D tracking. Worth the cost for precision, or overkill for Phase 1?

3. **Processing split**: Arduino handles real-time FES control. Camera processing on Arduino is likely too heavy. Pi Zero as co-processor? Or direct USB to laptop during development?

4. **Multi-hand**: If camera sees both hands (patient + therapist), need to reliably identify which hand to track. MediaPipe supports multi-hand but we need to assign the right one.

---

## Connection to Oracle Loop

This architecture mirrors the Oracle Loop for AI alignment:

| Oracle Loop | Hand Control |
|-------------|-------------|
| KV cache geometry | Hand pose (MediaPipe landmarks) |
| Alignment check | Pose error computation |
| Misalignment detected | Finger position error > threshold |
| Rollback + steer | Adjust FES per-channel |
| Verify improvement | Camera confirms correction |
| Commit | Movement achieved |

Same pattern: observe state → detect error → correct → verify. The difference is the domain — one operates on cognitive geometry, the other on physical geometry. Both are closed-loop alignment systems.
