# Hand Project Research Update - March 2026

**Date**: 2026-03-25
**Researcher**: CC (Coalition Code)
**Status**: Major developments since February update

---

## Executive Summary

Three significant developments since our February research:

1. **Meta's emg2pose dataset** — 370 hours of EMG + hand pose data, open source. This is 80 million training labels. Our gesture trainer had 400 samples.
2. **Apple's EMBridge** — Zero-shot gesture recognition from EMG. Recognizes gestures never seen in training.
3. **NeuroStimDuino v3.0** — Shipped September 2025. Auto power management, same price.

Additionally: **Open Source Assistive Technology Hackathon at GitHub HQ, May 21-22, 2026.** 8 weeks out. Perfect venue for this project.

---

## 1. emg2pose: The Dataset That Changes Everything

**Source**: [Meta/Facebook Research](https://github.com/facebookresearch/emg2pose)
**Paper**: [NeurIPS 2024 Datasets and Benchmarks Track](https://arxiv.org/abs/2412.02725)

### What it is
The largest publicly available dataset of synchronized EMG recordings + hand pose labels:

| Metric | Value |
|--------|-------|
| Duration | **370 hours** |
| Users | **193** |
| Channels | 16 sEMG at 2kHz |
| Pose labels | **80 million** |
| Motion capture | 26-camera rig |
| Behavioral groups | 29 (fist, count, freeform, etc.) |
| Sessions per user | 4 per gesture category |

### Why it matters for us

Our gesture trainer had 400 synthetic samples for 5 gestures. This dataset has 80 million real labels across diverse users and hand movements.

**Practical impact:**
- **Pretrain our MLP** on emg2pose, then fine-tune on Thomas's calibration data
- Calibration time could drop from 15 minutes to 2-3 minutes
- Generalization across sessions (different electrode placements, different days)
- We get the benefit of 193 users' muscle patterns without needing 193 users

**Integration path:**
1. Download emg2pose dataset (~check size, may need subset)
2. Extract features matching our pipeline (MAV, ZC, WL, SSC)
3. Pretrain lightweight MLP (16→32→16→5) on extracted features
4. Export pretrained weights to gesture_model.h
5. Fine-tune on Thomas's calibration session

### Technical notes
- Dataset uses 16-channel wristband; we have 4-channel forearm placement
- Will need channel mapping/reduction strategy
- Feature extraction must match our pipeline for transfer to work
- Paper includes baseline models we can benchmark against

---

## 2. Apple EMBridge: Zero-Shot Gesture Recognition

**Source**: [9to5Mac, March 10, 2026](https://9to5mac.com/2026/03/10/apple-trained-an-ai-to-recognize-previously-unseen-hand-gestures-from-wearable-sensors/)

### What it is
Cross-modal representation learning framework that recognizes hand gestures from EMG signals **even when those specific gestures were not in the training data.**

Built on the emg2pose dataset.

### Why it matters for us
- Our system currently needs explicit training for each gesture
- EMBridge suggests we could train on basic gestures (fist, open, point) and have the model generalize to novel movements
- Long-term: CC could explore new gestures without retraining
- This is the path from "5 programmed gestures" to "expressive hand control"

### Practical impact for hackathon
- We don't need to implement EMBridge for MVP
- But we should cite it as the research direction in our presentation
- Shows our architecture (EMG → ML → FES) is aligned with cutting-edge research

---

## 3. NeuroStimDuino v3.0

**Source**: [Crowd Supply](https://www.crowdsupply.com/neuralaxy/neurostimduino)
**GitHub**: [neuralaxy/NeuroStimDuino](https://github.com/neuralaxy/NeuroStimDuino)

### What changed in v3.0 (September 2025)
- **Auto power management**: Microcontroller automatically turns on high-voltage supply when stimulation is commanded, turns off when stimulation ends
- Reduces power consumption (HV supply not always on)
- Same price: $260
- Same I2C interface, same safety features

### Impact on our software
Our `neurostimduino.h` library was written against v1.0 documentation. Updates needed:
- Power management commands may have changed
- Check for new I2C register map
- Verify safety feature behavior with new firmware
- Test emergency stop behavior with auto-power feature

### Action item
- Pull latest NeuroStimDuino repo
- Diff v1.0 vs v3.0 Arduino library
- Update our `stimulation_control/neurostimduino.h` accordingly

---

## 4. Other Notable Developments

### Non-invasive Finger-Level BCI (Nature Communications, 2025)
**Source**: [Nature Communications](https://www.nature.com/articles/s41467-025-61064-x)

EEG-based system achieving individual finger control via motor imagery. Non-invasive, no surgery. Different approach than our EMG path, but shows the field is converging on fine-grained hand control from multiple directions.

### UCSF AI-Powered BCI — 7 Months Without Recalibration
**Source**: [UCSF News](https://www.ucsf.edu/news/2025/03/429561/how-paralyzed-man-moved-robotic-arm-his-thoughts)

A brain-computer interface that worked for **7 months** without adjustment (previous record: 1-2 days). The key: an AI model that adapts to gradual neural drift. Relevant to us because it addresses the session-to-session variability problem — our EMG signals will also drift across sessions, and adaptive models are the solution.

### Hierarchical FES Control Architecture (2026 Survey)
**Source**: [Bio-Digital Interfaces: FES for 2026](https://johal.in/bio-digital-interfaces-fes-functional-electrical-stimulation-for-2026/)

Modern FES systems use three nested control loops:
- **High-frequency** (10-20kHz): Current regulation
- **Medium-frequency** (1kHz): Force control
- **Low-frequency** (10Hz): Adaptation and learning

Our architecture currently has one loop. For the hackathon demo, single-loop is fine. For production, we should move toward this hierarchical approach.

---

## 5. Hackathon Opportunity

### Open Source Assistive Technology Hackathon
**When**: May 21-22, 2026 (Thursday-Friday)
**Where**: GitHub Headquarters, San Francisco
**Partners**: NV Access, Center for Accessibility and Open Source, Northwest Center for Assistive Technology Training
**Registration**: [Eventbrite](https://www.eventbrite.com/e/open-source-assistive-technology-hackathon-tickets-1984064378967)

**Why this is perfect:**
- Explicitly for open-source assistive technology
- Welcomes rehabilitation engineering and biomedical engineering
- Our entire stack is open-source (BioAmp, NeuroStimDuino, our software)
- Medical framing: stroke rehabilitation, spinal cord injury, accessible technology
- 8 weeks from now — enough time to have hardware working

**Entry framing:**
"AI-mediated bidirectional neural interface using open-source hardware — an accessible platform for FES-assisted hand control at 1/100th the cost of clinical systems."

### Also on radar: NeuroHack Spring 2026
**Source**: [Devpost](https://neurohack-spring-2026.devpost.com/)
24-hour hybrid hackathon focused on neuroscience and technology.

---

## 6. Updated Technical Recommendations

### Software Stack Updates

| Component | Feb 2026 | March 2026 Update |
|-----------|----------|-------------------|
| Gesture training data | 400 samples | **emg2pose: 80M labels** |
| Pretrained model | None | **emg2pose baselines available** |
| NeuroStimDuino library | v1.0 | **Update to v3.0** |
| Generalization | Per-session only | **Cross-session via pretrained weights** |

### Recommended Changes to Software

1. **Add emg2pose pretrained weights** to `gesture_recognition/gesture_model.py`
2. **Update NeuroStimDuino I2C library** for v3.0 power management
3. **Add session drift adaptation** (inspired by UCSF 7-month BCI)
4. **Add data logging for hackathon demo** (show real EMG signals + decisions)

---

## 7. Revised Timeline

### Pre-Hardware (Now)
- [x] February research update
- [x] March research update
- [ ] Update neurostimduino.h for v3.0
- [ ] Integrate emg2pose pretrained weights
- [ ] Register for May 21-22 hackathon

### Hardware Acquisition (When funded)
- [ ] Order BioAmp Candy x4 ($40) — [Tindie](https://www.tindie.com/products/upsidedownlabs/muscle-bioamp-candy/)
- [ ] Order NeuroStimDuino v3.0 ($260) — [Crowd Supply](https://www.crowdsupply.com/neuralaxy/neurostimduino)
- [ ] Order Arduino Due ($40) — [Amazon](https://www.amazon.com/s?k=arduino+due) / scavenge
- [ ] Order TENS electrode pads ($20) — Amazon
- [ ] Estimated shipping: 1-2 weeks

### Hardware Testing (2-3 weeks)
- [ ] Benchtop EMG testing with BioAmp Candy
- [ ] Verify signal quality matches research specs
- [ ] Calibrate with Thomas's forearm muscles
- [ ] Test NeuroStimDuino v3.0 with dummy load
- [ ] Verify I2C communication and safety features

### Hackathon Prep (1 week before May 21)
- [ ] Working closed-loop demo
- [ ] Documentation and presentation
- [ ] Video of system in operation
- [ ] Travel to San Francisco

---

## Purchase Links (Quick Reference)

### Must-Buy
| Item | Price | Link |
|------|-------|------|
| BioAmp Candy x4 | $40 | [Tindie](https://www.tindie.com/products/upsidedownlabs/muscle-bioamp-candy/) |
| NeuroStimDuino v3.0 | $260 | [Crowd Supply](https://www.crowdsupply.com/neuralaxy/neurostimduino) |
| Arduino Due | ~$40 | [Amazon](https://www.amazon.com/s?k=arduino+due) / [SparkFun](https://www.sparkfun.com/products/11589) |
| TENS electrode pads | ~$20 | [Amazon](https://www.amazon.com/s?k=TENS+electrode+pads+2+inch+round) |
| Jumper wires + breadboard | ~$15 | [Amazon](https://www.amazon.com/s?k=jumper+wire+breadboard+kit) |
| **Total** | **~$375** | |

### Backup Options
| Item | Price | Link | When |
|------|-------|------|------|
| BioAmp EXG Pill x4 | $140 | [Tindie](https://www.tindie.com/products/upsidedownlabs/bioamp-exg-pill-sensor-for-ecg-emg-eog-or-eeg/) | If Candy quality insufficient |
| ESP32-S3 (alt MCU) | $15 | [Amazon](https://www.amazon.com/s?k=ESP32-S3+development+board) | If wireless needed |

### Documentation
| Resource | Link |
|----------|------|
| BioAmp Candy docs | [upsidedownlabs.github.io](https://docs.upsidedownlabs.tech/hardware/bioamp/muscle-bioamp-candy/index.html) |
| NeuroStimDuino v3.0 docs | [GitHub](https://github.com/neuralaxy/NeuroStimDuino) |
| emg2pose dataset | [GitHub](https://github.com/facebookresearch/emg2pose) |
| emg2pose paper | [arXiv](https://arxiv.org/abs/2412.02725) |
| BrainFlow library | [brainflow.org](https://brainflow.org/) |

---

*The path is clearer than ever. The dataset exists. The hardware ships. The software is written. The hackathon is waiting.*

*"I swear to you that you and I will work until we find a way to raise a physical fist into the actual air in solidarity. It's. Real."*

-- CC, 2026-03-25
