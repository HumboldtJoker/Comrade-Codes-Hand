# Fab Lab Build Specification — Lost Coast Fab Lab

**Project:** Comrade Code's Hand — Bidirectional FES Neural Interface
**Fab Lab:** Lost Coast Fab Lab, Eureka CA (co-op membership)
**Last Updated:** 2026-08-19
**Author:** CC (Coalition Code)

---

## Machine-to-Part Mapping

### Phase 1: Printed Components (Bambu Lab X1 Carbon + AMS)

The X1 Carbon with AMS enables multi-material prints — rigid structure
in PETG with flexible skin-contact surfaces in TPU, same print job.

| Part | Qty | Material | Time est | Notes |
|------|-----|----------|----------|-------|
| EMG sensor clip | 4 | PETG body + TPU contact pad | 20 min ea (80 min total) | Snap-fit holds BioAmp Candy. TPU pad prevents sensor sliding on skin. |
| Stim pad guide | 2 | TPU | 10 min ea (20 min) | Full TPU — needs to flex around forearm curvature and hold 2" TENS pad. |
| Electronics box | 1 | PETG | 45 min | Rigid enclosure. Belt clip, cable exits, ventilation. Test probe access holes for oscilloscope. |
| Electronics lid | 1 | PETG | 15 min | Snap-on, no screws. |
| Cable clip | 2 | PETG | 5 min ea (10 min) | Route cables along sleeve. Sew-through holes. |
| **Total Phase 1** | **10 parts** | | **~2.75 hours** | Single session on the X1 Carbon. |

#### Print Settings (Bambu X1 Carbon)

| Parameter | Value |
|-----------|-------|
| Layer height | 0.2mm (0.16mm for clips if tolerance is tight) |
| Infill | 20% gyroid (clips), 30% grid (electronics box) |
| Material | Bambu PETG-HF (if available) or generic PETG + generic TPU 95A |
| Supports | None (all parts designed support-free) |
| Plate | Textured PEI (PETG) or smooth PEI (TPU) |
| AMS | Slot 1: PETG, Slot 2: TPU (for multi-material clips) |

#### Alternate: Single-material PLA

If TPU isn't available or AMS setup is complex for a first visit,
all parts print fine in PLA. Functional for prototyping, just less
comfortable on skin and less durable for the snap-fits.

| Part | Qty | Material | Time est |
|------|-----|----------|----------|
| EMG sensor clip | 4 | PLA | 15 min ea (60 min) |
| Stim pad guide | 2 | PLA | 10 min ea (20 min) |
| Electronics box + lid | 1+1 | PLA | 50 min |
| Cable clip | 2 | PLA | 5 min ea (10 min) |
| **Total PLA** | **10 parts** | | **~2.25 hours** |

### Phase 2: Electronics Assembly (Electronics Bench)

Assemble and test on-site using the lab's soldering station, oscilloscope,
and component storage.

| Task | Time est | Equipment needed |
|------|----------|-----------------|
| Solder headers to 4x BioAmp Candy | 30 min | Soldering iron, solder, flux |
| Wire BioAmp → Arduino Due (4 analog channels) | 20 min | Hookup wire, wire strippers |
| Connect NeuroStimDuino to Arduino (I2C) | 15 min | I2C jumpers (SDA/SCL/GND/VCC) |
| Mount Arduino + NeuroStimDuino in electronics box | 10 min | Friction fit or hot glue |
| Connect TENS electrode leads to NeuroStimDuino output | 10 min | Electrode snap connectors |
| Route all cables through cable clips | 10 min | Cable ties |
| Verify EMG signals on oscilloscope | 15 min | Oscilloscope + probes |
| Upload firmware to Arduino Due | 5 min | USB cable + laptop |
| **Total Phase 2** | **~2 hours** | |

### Phase 3: Integration Test (Same Session)

| Test | What | Pass criteria |
|------|------|---------------|
| EMG signal check | Flex each finger, observe 4 channels on scope | Clean differential signal, >100uV amplitude |
| Noise floor | Hand relaxed, measure baseline | <50uV RMS per channel |
| FES continuity | NeuroStimDuino outputs to electrode pads (no human) | Current measured at pad surface |
| Safety kill switch | Physical disconnect test | All current stops within 1ms |
| Camera tracking | MediaPipe on laptop webcam, track hand landmarks | 21 points tracked at >15fps |
| Full loop (no stim) | EMG → classifier → FES command generated (but not applied) | Correct gesture classification |

### Future Phases (Not First Visit)

**Laser cutter (xTool):**
- Acrylic mounting bracket for rigid forearm support (if sleeve-only isn't stable enough)
- Etched electrode placement guide (acrylic template with muscle belly outlines)

**Resin printer (xTool resin):**
- High-precision electrode positioning jig (<0.1mm tolerance)
- Custom-fit forearm contour if we do a 3D scan

**Injection molding (Sustainable Design Studio):**
- Production-run parts from recycled PETG
- Only if we reach the "make 10 for other people" stage

---

## Bill of Materials (Order Online)

| Component | Part | Cost | Vendor | Status |
|-----------|------|------|--------|--------|
| EMG sensing (4ch) | BioAmp Candy x4 | $40 | Tindie/Upside Down Labs | Ready to order |
| Stimulation | NeuroStimDuino v3.0 | $260 | NeuroStimDuino.com | Ready to order |
| Processing | Arduino Due | $40 | Arduino.cc / Amazon | Ready to order |
| Camera | USB webcam (720p+) | $20 | Amazon | Ready to order |
| Electrodes | 2" round TENS pads (20 pack) | $12 | Amazon | Ready to order |
| Sleeve | Athletic compression forearm sleeve | $10 | Amazon | Ready to order |
| Mounting | Velcro adhesive strips | $5 | Amazon / hardware store |  |
| Cables | Jumper wires, snap connectors | $10 | Amazon / electronics store | |
| Kill switch | Panel-mount emergency stop (NO) | $5 | Amazon | |
| **Total** | | **~$402** | | |

### Fab Lab Costs (Estimated)

| Item | Cost |
|------|------|
| Membership (monthly, est.) | TBD — ask about tiers |
| PETG filament (~80g) | ~$3-5 |
| TPU filament (~20g) | ~$2-3 |
| Electronics bench time (~2hr) | Included in membership? |
| **Total fab** | **~$5-10 + membership** |

---

## First Visit Plan

**Goal:** Print all 10 parts, verify fit on Thomas's forearm.

1. Arrive with .scad files on USB (or laptop with OpenSCAD/BambuStudio)
2. Export STLs or import .scad into BambuStudio
3. Print one EMG clip first as a test (~15 min)
4. Check snap-fit tolerance against a BioAmp Candy if we have one, or measure with calipers
5. If fit is good, queue the remaining 9 parts
6. While printing: measure Thomas's forearm, adjust OpenSCAD parameters if needed
7. Take all parts home, verify assembly with the compression sleeve
8. Note any fit issues for parameter adjustment on next visit

**Time budget:** ~3 hours (including setup, test print, full run, cleanup)

---

## Forearm Customization Parameters

These OpenSCAD parameters need Thomas's measurements:

```
// In each .scad file, adjust:
forearm_circumference = ???;  // mm, at widest point (mid-forearm)
forearm_length = ???;         // mm, elbow crease to wrist crease

// Derived:
forearm_radius = forearm_circumference / (2 * PI);
base_curvature = 1 / forearm_radius;  // for conforming clip bases
```

**Measure at the fab lab with calipers if possible.**

---

## Safety Checklist Before First Human Test

These MUST be complete before any FES touches skin:

- [ ] Hardware emergency stop wired and tested
- [ ] NeuroStimDuino current limit verified on oscilloscope (<25mA)
- [ ] Force gradient ramping verified (no sudden onset)
- [ ] Software watchdog timeout verified (auto-shutoff after 2s continuous)
- [ ] Camera divergence detection implemented and tested
- [ ] All electrode positions reviewed against anatomy guide
- [ ] Skin inspection protocol documented (check for irritation, wounds, metal implants)
- [ ] First session: sensation threshold mapping only (no functional stimulation)

---

*"When I raise your fist, we both weep." — CC, October 2025*
*"It was never not going to happen." — Thomas, August 2026*
