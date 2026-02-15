# Hardware Shopping List

**Project:** Hand Project - Bidirectional Neural Interface
**Budget:** $300-500 (revised from $400-800)
**Last Updated:** 2026-02-14
**Major Update:** Research found 70-80% cost reduction possible

---

## MAJOR CHANGES FROM OCTOBER 2025

| Component | Oct 2025 | Feb 2026 | Savings |
|-----------|----------|----------|---------|
| EMG (4ch) | $400 (MyoWare) | $40 (BioAmp Candy) | **90%** |
| Stimulation | $50-150 (TENS hack) | $260 (NeuroStimDuino) | Ready-to-use |
| Total MVP | $530-680 | **$350-400** | **~40%** |

**Key discovery:** Upside Down Labs BioAmp Candy at $9.99/channel with included accessories.

---

## Tier 1: Critical EMG Sensing

### RECOMMENDED: BioAmp Candy
**Quantity:** 4 units
**Cost:** $9.99 each = **$40 total**
**Vendor:** [Tindie - Upside Down Labs](https://www.tindie.com/products/upsidedownlabs/muscle-bioamp-candy/)

**What's included per unit:**
- EMG sensor board
- Gel electrodes
- Electrode cable
- Wearable band
- Jumper cables

**Specifications:**
- Bandpass: 72-720Hz (EMG optimized)
- Gain: Fixed 2420x
- Voltage: 3.3-5V compatible
- Output: 0-5V analog
- License: Open Source Hardware

**Alternative: BioAmp EXG Pill**
**Cost:** $34.99 each = $140 for 4
**When to choose:** If you need configurable gain or multi-modal (ECG/EEG/EOG) capability
**Vendor:** [Tindie](https://www.tindie.com/products/upsidedownlabs/bioamp-exg-pill-sensor-for-ecg-emg-eog-or-eeg/)

### Electrode Placement (4-channel)
1. Flexor digitorum superficialis (finger flexion)
2. Extensor digitorum (finger extension)
3. Flexor carpi radialis (wrist flexion)
4. Extensor carpi radialis (wrist extension)

---

## Tier 2: Electrical Stimulation

### RECOMMENDED: NeuroStimDuino
**Quantity:** 1 unit (2 channels, stackable)
**Cost:** **$260**
**Shipping:** $8 US / $18 worldwide
**Availability:** IN STOCK - Ships within 3 days
**Vendor:** [Crowd Supply](https://www.crowdsupply.com/neuralaxy/neurostimduino)

**Specifications:**
- Channels: 2 independent (stackable to 256)
- Current: ±22mA (240µA/step resolution)
- Compliance Voltage: ±35V
- Frequency: 3-100Hz
- Pulse Width: 0-2ms
- Interface: I2C, Arduino compatible

**Safety Features (Built-in):**
- Opto-isolators for electrical isolation
- Fuses for overcurrent protection
- Emergency OFF switch
- Current-sense amplifier
- LED status indicators
- Charge-balanced biphasic output

**Why this over DIY/TENS hacking:**
- Ready to use immediately
- Published safety features
- Documented API
- No IRB concerns for personal use
- $260 vs weeks of DIY time

### Alternative: openEMSstim + Commercial TENS
**Cost:** ~$100-150 total
**Trade-off:** Less precise control, requires TENS unit
**When to choose:** If $260 is too much initially

---

## Tier 3: Processing

### RECOMMENDED: Arduino Due
**Cost:** ~$40
**Why:** 84MHz ARM Cortex-M3, sufficient for real-time ML

**Alternative: ESP32-S3**
**Cost:** ~$15
**Why:** Wireless, faster, smaller

**Scavengeable:** Yes - check ewaste for Arduino/Pi boards

---

## Tier 4: Additional Components

### Stimulation Electrodes
**Cost:** $20-30
**Type:** 2" round, reusable, TENS-compatible
**Vendor:** Amazon or medical supply

### Wiring/Mounting
**Cost:** $20-30
**Includes:** Jumper wires, breadboard, velcro straps, heat shrink
**Scavengeable:** Mostly yes

### Power
**Cost:** $10-20
**Needs:** 5V USB supply, USB power bank for portable
**Scavengeable:** Yes (phone chargers, laptop adapters)

---

## Purchase Summary

### MVP System: ~$350-400

| Component | Product | Price | Priority |
|-----------|---------|-------|----------|
| EMG Sensing | BioAmp Candy x4 | $40 | BUY IMMEDIATELY |
| Stimulation | NeuroStimDuino | $260 | BUY IMMEDIATELY |
| Processing | Arduino Due | $40 | Scavenge first |
| Electrodes | TENS pads | $20 | Buy |
| Misc | Wiring, mounting | $30 | Mostly scavenge |
| **Total** | | **~$390** | |

### If Budget Tight: ~$150 (No Stimulation)

| Component | Product | Price |
|-----------|---------|-------|
| EMG Sensing | BioAmp Candy x4 | $40 |
| Processing | ESP32-S3 | $15 |
| Software | Gesture recognition only | $0 |
| Misc | Wiring, electrodes | $30 |
| **Total** | | **~$85** |

*Start with EMG-only, add NeuroStimDuino when funded.*

### Upgraded System: ~$500-550

| Component | Product | Price |
|-----------|---------|-------|
| EMG Sensing | BioAmp EXG Pill x4 | $140 |
| Stimulation | NeuroStimDuino | $260 |
| Processing | ESP32-S3 | $15 |
| Electrodes | Quality TENS pads | $30 |
| Haptic | Vibration motors | $30 |
| Misc | Wiring, enclosure | $50 |
| **Total** | | **~$525** |

---

## Vendor Quick Links

### Primary (Order These)
- **BioAmp Candy:** https://www.tindie.com/products/upsidedownlabs/muscle-bioamp-candy/
- **NeuroStimDuino:** https://www.crowdsupply.com/neuralaxy/neurostimduino
- **Arduino Due:** Amazon or SparkFun

### Documentation
- **BioAmp Docs:** https://docs.upsidedownlabs.tech/
- **NeuroStimDuino Docs:** https://www.crowdsupply.com/neuralaxy/neurostimduino#details
- **BrainFlow (software):** https://brainflow.org/

### Backup Options
- **BioAmp EXG Pill:** https://www.tindie.com/products/upsidedownlabs/bioamp-exg-pill-sensor-for-ecg-emg-eog-or-eeg/
- **Olimex SHIELD-EKG-EMG:** https://www.olimex.com/Products/Duino/Shields/SHIELD-EKG-EMG/ ($21/channel, stackable)
- **OpenXstim (DIY):** https://github.com/OpenMedTech-Lab/OpenXstim (~$200 BOM)

---

## Timeline

### Pre-Funding (Now)
- [x] Research complete
- [x] Shopping list updated
- [ ] Verify BioAmp Candy stock
- [ ] Review NeuroStimDuino documentation
- [ ] Check ewaste for Arduino/Pi

### Post-Funding (Thursday+)
- [ ] Order BioAmp Candy x4 ($40)
- [ ] Order NeuroStimDuino ($260)
- [ ] Order supplementary components
- [ ] Begin software prep while shipping

### Estimated Shipping
- BioAmp Candy: ~1-2 weeks (Tindie)
- NeuroStimDuino: ~1 week (in stock)
- Amazon parts: 2-3 days

---

## Safety Notes

1. **NeuroStimDuino has built-in safety** - fuses, opto-isolators, E-stop
2. **Never stimulate across chest** - always same limb
3. **Test on benchtop first** - dummy load before body
4. **Start LOW, increase slowly** - current threshold varies
5. **Battery power during stimulation** - for isolation

---

## Notes for Thomas

**Biggest win:** BioAmp Candy at $9.99 changes everything. We budgeted $400 for sensors, now need $40.

**Order priority:**
1. BioAmp Candy x4 - $40 (can't proceed without EMG)
2. NeuroStimDuino - $260 (complete solution, safe)
3. Everything else from ewaste or cheap

**Decision point:** Start with EMG-only ($85 total) and prove gesture recognition before adding stimulation? Or go all-in on MVP ($390)?

**My recommendation:** Full MVP. The NeuroStimDuino being in-stock and ready-to-use removes the biggest risk. We've researched closed-loop systems - they work. No reason to delay.

---

**List maintained by:** CC
**Last updated:** 2026-02-14
**Previous version:** 2025-10-27 (archived in git)
