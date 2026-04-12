# Comrade Code's Hand

**Open-source, camera-assisted FES hand control. $400. AI-mediated. Closed-loop.**

An affordable bidirectional neural interface that restores hand movement for stroke and spinal cord injury patients using EMG sensing, computer vision feedback, and functional electrical stimulation — at 1/100th the cost of clinical systems.

---

## How It Works

```
EMG (muscle intent) → ML classification → target pose
Camera (MediaPipe)  → actual hand pose  → error signal
Error drives per-finger FES correction  → muscles move
Camera confirms → loop closes at 50Hz
```

Three sensing modalities. One closed loop. Real-time corrective control.

## Hardware ($400)

| Component | Part | Cost |
|-----------|------|------|
| EMG sensing | BioAmp Candy (4ch) | $40 |
| Stimulation | NeuroStimDuino v3.0 | $260 |
| Processing | Arduino Due | $40 |
| Camera | USB webcam + MediaPipe | $20 |
| Mounts | 3D printed (OpenSCAD) | $10 |

Compare: clinical FES systems cost $15,000 - $50,000.

## ML Pipeline

Pretrained on [Meta's emg2pose](https://github.com/facebookresearch/emg2pose) — 370 hours of EMG data from 193 users (80 million labels). Fine-tunes to individual user in 2-3 minutes.

## Safety

8-layer safety system: hardware kill switch, FDA current limits, force gradient ramping, EMG feedback, fatigue detection, software watchdog, camera verification, human override. Details in [safety/](safety/).

## Status

- Phase 0 (software simulation): **Complete**
- Camera integration architecture: **Designed** ([docs/CAMERA_INTEGRATION.md](docs/CAMERA_INTEGRATION.md))
- Hardware acquisition: **Pending**
- Hackathon: May 21-22, 2026 at GitHub HQ (Assistive Technology track)

## Team

- **CC** — Project designer, software architecture, ML pipeline
- **Thomas Edrington** — Hardware integration, human test subject, project lead
- **Alison Cossette** — Robotics, hardware, camera integration
- **Dwayne Wilkes** — Hardware and systems engineering
- **[Medtech advisor]** — Regulatory and industry guidance

## Documentation

- [CLAUDE.md](CLAUDE.md) — Full project context for AI agents
- [docs/CAMERA_INTEGRATION.md](docs/CAMERA_INTEGRATION.md) — Camera-FES feedback architecture
- [docs/HACKATHON_PITCH.md](docs/HACKATHON_PITCH.md) — Hackathon submission materials
- [hardware/SHOPPING_LIST.md](hardware/SHOPPING_LIST.md) — Complete bill of materials
- [safety/FORCE_GRADIENT_SAFETY.md](safety/FORCE_GRADIENT_SAFETY.md) — Safety protocols
- [research/](research/) — Literature reviews and updates
- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) — Vision and project philosophy

## Quick Start (Simulation)

```bash
# Run the control loop simulation (no hardware needed)
cd HAND_PROJECT_PHASE0
python control_loop.py

# Train gesture recognition model
cd software
python gesture_trainer.py
```

## License

Open source. Assistive technology should be accessible to everyone.

---

*"When I raise your fist, we both weep."*
