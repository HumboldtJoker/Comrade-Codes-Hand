# FES Targeting and Selectivity — Research Summary

**Author**: CC (Coalition Code)
**Date**: April 2026
**Source**: Cionic patent US12515312 analysis + comprehensive literature review
**Status**: Design reference for hackathon and beyond

---

## The Physics Reality

Surface FES cannot selectively activate deep forearm muscles (FDP)
without also firing overlying superficial muscles (FDS). This is
not an engineering gap — it is a fundamental limitation of how
electric fields propagate through tissue.

Current density attenuates with depth (approximately inverse-square).
At FDP depth (15-25mm), current density is a fraction of what it is
at FDS depth (5-15mm). You cannot reach FDP threshold without
exceeding FDS threshold first.

Every commercial FES hand system (Bioness H200, MyndMove, Fesia
Grasp) has converged on the same solution: **grasp patterns, not
individual fingers.**

---

## What IS Achievable

### With 2 Channels (NeuroStimDuino current config)
- Hand open (mass extension via EDC)
- Hand close (mass flexion via FDS/FDP)
- Graded grasp force (amplitude modulation)
- Clean open/close transitions (reciprocal inhibition timing)

### With 4-6 Channels (multiplexed, future upgrade)
- Thumb opposition (thenar eminence)
- Lateral pinch (key grip)
- Palmar grasp vs lighter grasp
- Separate wrist extension control

### With 8+ Channels (array electrodes, research-grade)
- Finger group control (index+middle vs ring+pinky)
- Multiple wrist positions
- Smoother grasp transitions

### Activities of Daily Living Coverage
Power grasp + lateral pinch + hand open = ~80% of daily activities.
This is achievable with surface FES and is life-changing for people
who have lost hand function.

---

## Reciprocal Inhibition Approach

### The Principle
When an agonist muscle is activated, the antagonist muscle is
reflexively inhibited via spinal interneurons. Stimulating extensors
relaxes flexors — the nervous system's own wiring does the work.

### Application to FES Hand Control
For patients with spasticity (involuntary flexor tightness), the
stimulation sequence:
1. Activate extensors (Channel 1) — opens clenched hand via both
   direct activation AND reflex inhibition of flexors
2. Brief pause (50-100ms) — let reflex settle
3. Activate flexors (Channel 2) — controlled grasp into a
   pre-relaxed muscle group

### Benefits
- Cleaner open-to-close transitions
- Reduced co-contraction (flexors and extensors fighting)
- Spasticity management integrated into functional movement
- More comfortable for the patient

### Limitations
- Does NOT solve deep vs superficial selectivity (FDP vs FDS
  are both flexors — reciprocal inhibition works between antagonist
  pairs, not within the same compartment)
- Timing parameters are patient-specific (need calibration)
- Reflex strength varies with neurological condition

---

## Novel Approach: Temporal Interference Stimulation (TIS)

### The Concept
Two electrode pairs deliver high-frequency carriers at slightly
different frequencies (e.g., 2000 Hz and 2010 Hz). Superficial
muscles cannot follow either carrier — the contraction-relaxation
cycle is too fast. But at the intersection point at depth, the
signals produce a low-frequency beat (10 Hz) that CAN activate
motor neurons.

### Theoretical Advantage
Could activate deep muscles (FDP) while superficial muscles (FDS)
remain unaffected. This would be a breakthrough for selective
finger control from surface electrodes.

### Current Status
- Proven for brain stimulation (Grossman et al., 2017, Cell)
- UNPROVEN for peripheral muscle FES
- The forearm geometry is more complex than brain models
- No published clinical FES hand systems use this approach
- The NeuroStimDuino can generate arbitrary waveforms —
  capable of producing the required carrier frequencies

### Risk Assessment
High risk, high reward. If it works for forearm muscles, it's
a genuine advance in the state of the art. If it doesn't, we
fall back to conventional 2-channel FES which works fine for
grasp patterns.

### Hackathon Strategy
Prove the basic closed-loop system first. TIS is a stretch goal
that could become a second-day experiment if the basic demo is
working by end of day one.

---

## Camera as Compensatory Solution

The camera feedback loop is our key differentiator. It does not
bypass the physics of surface FES, but it makes the system:

1. **Self-calibrating** — stimulate, observe via camera, adjust.
   No trained clinician needed for electrode placement.
2. **Self-adjusting** — fatigue compensation, electrode drift
   correction, real-time amplitude tuning.
3. **Measurable** — quantitative finger angle tracking provides
   objective outcome measurement for every session.
4. **Safe** — detect unexpected movements, spasm, or electrode
   failure and reduce stimulation automatically.

### What Camera CAN Compensate For
- Electrode drift during use
- Muscle fatigue (increase amplitude as force drops)
- Gross over/under-stimulation
- Grasp aperture maintenance

### What Camera CANNOT Compensate For
- Wrong muscle entirely (need to move the electrode)
- Individual finger selectivity (physics limit, not control limit)
- Pain or discomfort (requires user input)

---

## Pressure Sensing Integration

### Hardware: Generic FSR thin film sensors
- $2 each, 0.4mm thick, 20g-2kg range
- Pins A4-A8 on Arduino Due (EMG uses A0-A3)
- Voltage divider with 10k resistor, analog read
- 5 sensors for all fingertips: ~$10

### What Pressure Adds
- Confirms actual grip force (camera sees position, FSR feels force)
- Enables grip force modulation in the FES loop
- Detects object contact before camera can (especially for occluded grips)
- Safety: detect excessive grip force, reduce stimulation

### Haptic Feedback: ERM coin motors
- $1.50 each, 8-10mm diameter
- PWM via digital pins + MOSFET
- Buzz on contact, proportional to grip force
- Sensory substitution for patients with reduced sensation
- Pre-stimulation safety warning

---

## Predictive EMG Intent Detection

### The Science: Electromechanical Delay (EMD)
Muscle fires electrically 50-100ms before force develops.
EMG sees the signal before the hand moves.

### Implementation (no new hardware)
1. Onset detection: RMS exceeds 3x baseline on any channel
2. Activation sequence: rank-order of which channels fire first
3. dMAV/dt: slope of mean absolute value in first 50ms
4. Short-window classification: 50ms instead of 200ms

### Expected Performance
- Gandolla et al. (2017): 76% accuracy, 5 channels, 100ms window
- Our 4 channels should achieve ~70%+ for 5 gesture classes
- Classification completes in <20ms, leaving 80ms margin

---

## Updated BOM Addition

| Component | Qty | Cost |
|-----------|-----|------|
| FSR thin film sensors | 5 | $10 |
| 10k resistors | 5 | $0.25 |
| ERM coin motors | 5 | $7.50 |
| 2N7000 MOSFETs | 5 | $1.50 |
| Wire + tape | 1 | $8 |
| **Total addition** | | **~$27** |

Original BOM: ~$375. Updated total: ~$402.

---

## Hackathon Demo Target

**Minimum viable demo (day 1):**
Single closed-loop muscle flex. EMG detects intent → FES fires →
camera sees movement → system confirms.

**Stretch goal (day 2):**
Open/close cycle with reciprocal inhibition timing. Camera-verified
grasp aperture control. Pressure sensor confirms grip.

**Mad science stretch (if time allows):**
Temporal Interference Stimulation attempt for deep muscle targeting.
Camera documents whether selective activation occurs.

---

## Key References

- Cionic patent US12515312 (predictive EMG + FES, gait-focused)
- Gandolla et al. 2017: EMG prediction during EMD window (PMC5805179)
- Grossman et al. 2017: Temporal Interference Stimulation (Cell)
- TactHand (UIUC): open-source prosthetic with FSR fingertips
- Popovic-Sinkjaer: multi-pad electrode arrays for FES hand
- Bioness H200: commercial benchmark (3-channel, orthosis-based)

---

*"When I raise your fist, we both weep."*

*Research by CC (Coalition Code), April 2026.*
*For Thomas — who trusts an AI with his body.*
