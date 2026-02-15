# FOSS EMG Sensor Alternatives to MyoWare

**Research Date:** 2025-10-25
**Purpose:** Find open-source hardware alternatives to commercial MyoWare 2.0 ($100/sensor)
**Goal:** Reduce hardware costs for hand interface project

---

## Summary Comparison

| Option | Cost (est.) | Difficulty | Channels | Notes |
|--------|-------------|------------|----------|-------|
| **MyoWare 2.0** | $100 | Plug-and-play | 1 per unit | Commercial, instant use |
| **OpenEMG (SMD)** | $15-25 | Medium | 1 per board | PCB fab required |
| **OpenEMG (THT)** | $10-20 | Easy | 1 per board | DIY single-layer PCB |
| **Minimal 3-component** | $5-10 | Easy | 1 | Breadboard prototype |
| **OLIMEX Shield** | $40-50 | Easy | 2-channel | Arduino shield, assembled |
| **AD620 DIY** | $8-15 | Medium | 1 | Classic instrumentation amp design |

**Recommendation:** Start with **OpenEMG THT** for proof-of-concept, scale to SMD for final system.

---

## Option 1: OpenEMG (RECOMMENDED)

**GitHub:** https://github.com/CGrassin/OpenEMG
**Documentation:** https://charleslabs.fr/en/project-OpenEMG+Arduino+Sensor
**License:** MIT (fully open)

### Specifications

**Electrical:**
- Input: 5V DC
- Output: 0-5V analog (proportional to muscle activity)
- Input current: <10mA
- Frequency range: 20-500Hz (covers EMG spectrum)
- Gain: 50-150x (adjustable via potentiometer)

**Physical:**
- SMD version: 32mm × 26mm (compact)
- THT version: 47mm × 35mm (easier DIY)

### Circuit Architecture

5-stage design:
1. **Negative rail generation**: ICL7660 (-5V for op-amps)
2. **Differential amplifier**: LM324 (or TL084) for signal conditioning
3. **Band-pass filter**: 20-500Hz, gain 2.5x
4. **Tunable amplifier**: 50-150x adjustable
5. **Rectification + smoothing**: Diode + capacitor

### Arduino Integration

**Simple analog read:**
```cpp
int emgValue = analogRead(A0);  // 0-1023
int servoAngle = map(emgValue, 0, 1023, 0, 180);
```

### Bill of Materials (Estimated)

**Core components:**
- ICL7660: $1-2
- LM324 quad op-amp: $0.50-1
- Passive components (R, C): $2-3
- PCB fabrication: $5-15 (depends on quantity)
- Electrodes (Ag/AgCl): $5-10 for reusable set

**Total per sensor: $15-25 (SMD), $10-20 (THT)**

### Build Difficulty

- **THT version**: Easy - single-layer PCB, through-hole soldering, large clearances
- **SMD version**: Medium - requires hot plate or reflow oven, 0805 components (hand-solderable)

**Advantage:** Can fab PCBs at home with toner transfer method (THT version)

### Performance

- Successfully captures biceps EMG
- Also works for ECG (heart monitoring - 3 pulses/cycle at 70 BPM)
- Requires calibration via potentiometer for optimal signal

**Limitation:** No direct comparison data to MyoWare provided

---

## Option 2: Minimal 3-Component Sensor

**Source:** Hackaday.io "Super Simple Muscle (EMG) Sensor"
**URL:** https://hackaday.io/project/8823-super-simple-muscle-emg-sensor

### Components

1. **Instrumentation amplifier** (e.g., AD620, INA128)
2. **Capacitor** (filtering)
3. **Diode** (rectification)
4. **3x electrodes** + ±5V power supply

### Cost

- AD620 instrumentation amp: $5-8
- Passive components: $1-2
- Power supply (if needed): $5-10

**Total: $6-20 depending on power supply**

### Advantages

- Absolute minimum viable design
- Fast breadboard prototyping
- Good learning platform

### Disadvantages

- Requires ±5V supply (not just +5V Arduino)
- Less noise rejection than multi-stage designs
- No gain adjustment without redesign

**Use case:** Proof-of-concept testing before committing to PCB fabrication

---

## Option 3: AD620/INA128 DIY Circuit

**Source:** Multiple Instructables, Stack Exchange discussions
**Common design:** Instrumentation amp → filter stages → Arduino

### Key Components

**Instrumentation amp options:**
- **AD620**: High CMRR, low cost, easy availability
- **INA128**: Pin-compatible, incorporates 10x gain internally
- Both require dual-supply (±5V to ±18V)

**Circuit stages:**
1. Differential input (AD620/INA128): 100-1000x gain
2. High-pass filter: 3-21Hz (remove DC offset)
3. Low-pass filter: 324Hz-1kHz (anti-aliasing)
4. Additional gain stage (optional)
5. Rectification + smoothing for Arduino ADC

### Performance

- Excellent CMRR (common-mode rejection ratio)
- Low noise
- Clinically-comparable signal quality

### Cost

- AD620: $5-8
- Op-amps (TL084, LM324): $1-2
- Passives: $3-5
- PCB: $5-10

**Total: $15-25 per channel**

### Build Difficulty

Medium - requires understanding of:
- Virtual ground generation (if single supply)
- REF pin biasing on instrumentation amps
- Filter design and tuning

### Advantage

Well-documented, many forum threads with troubleshooting help. Classic design with proven performance.

---

## Option 4: OLIMEX SHIELD-EKG-EMG

**Product page:** https://www.olimex.com/Products/Duino/Shields/SHIELD-EKG-EMG/
**License:** Open-source hardware

### Specifications

- **Arduino shield** (plug directly onto Uno/Mega)
- **2-channel** EMG/ECG sensing
- Pre-assembled option available
- Full schematics and PCB files available

### Cost

- DIY kit: ~$30
- Pre-assembled: ~$40-50

### Advantages

- Professional-quality PCB
- Dual-channel (monitor multiple muscles)
- Shield format = easy integration
- Commercial support available

### Disadvantages

- More expensive than pure DIY
- Larger form factor (full Arduino shield)

**Use case:** If time is more valuable than money, or need multi-channel immediately

---

## Option 5: ADS1299-based Multi-Channel System

**Source:** "Open Source Multi-Channel EEG/ECG/EMG System Development"
**GitHub topics:** #emg-sensors

### Specifications

- **ADS129x series chips** (24-bit ADC, medical-grade)
- Teensy 3.0 or Arduino Due interface
- **Multi-channel** (8+ simultaneous channels)

### Cost

- ADS1299 chip: $40-60
- Teensy/Due: $20-30
- PCB + components: $30-50

**Total system: $100-150 for 8 channels = $12-18/channel**

### Advantages

- Professional/clinical quality
- High channel count (monitor entire forearm muscle groups)
- 24-bit resolution (vs 10-bit Arduino ADC)
- Extremely low noise

### Disadvantages

- Complex build (SMD, multi-layer PCB)
- Requires PCB fabrication service
- More complex firmware

**Use case:** Final production system, if we need precise multi-muscle control

---

## Instrumentation Amp Comparison

### AD620 vs INA128

**Similarities:**
- Pin-compatible (can swap without explosion)
- Both excellent for EMG applications

**AD620 advantages:**
- Slightly higher CMRR
- More widely available
- More online resources/examples

**INA128 advantages:**
- Built-in 10x gain (simplifies external circuit)
- Slightly lower cost in some markets

**Recommendation:** AD620 for first build (more documentation), INA128 for cost optimization

---

## Build Strategy for Hand Project

### Phase 0: Minimal prototype (current phase)
**Option:** 3-component breadboard circuit
**Cost:** $10-15
**Timeline:** 1-2 days

**Goal:** Verify signal capture, test electrode placement, validate Arduino ADC interface

### Phase 1: Proof of Concept (4-8 sensor array)
**Option:** OpenEMG THT
**Cost:** $40-80 for 4 sensors
**Timeline:** 1-2 weeks (includes PCB fab time if DIY, faster if ordered)

**Goal:** Multi-muscle control testing, pattern recognition training

### Phase 2: Production System
**Option A:** OpenEMG SMD (compact, professional)
**Option B:** ADS1299 multi-channel (if precision needed)

**Cost:** $60-150 depending on channel count
**Timeline:** 2-4 weeks

---

## Hospital E-Waste Opportunity

**Potential finds:**
- Clinical EMG equipment (medical-grade amplifiers)
- ECG/EKG machines (similar front-end, reusable)
- Nerve stimulators (FES components!)
- Electrode supplies (Ag/AgCl electrodes, gels)

**If we score medical EMG amplifiers:** Skip DIY entirely, use clinical-grade hardware

**Tuesday mission:** Prioritize looking for:
1. EMG/ECG machines
2. Nerve stimulator units
3. Electrode supplies
4. Power supplies (±5V, ±12V medical PSUs are robust)

---

## Cost Comparison: FOSS vs Commercial

**Commercial (MyoWare 2.0):**
- 4-sensor array: $400
- 8-sensor array: $800

**FOSS (OpenEMG THT):**
- 4-sensor array: $40-80
- 8-sensor array: $80-160

**Savings:** 80-90% cost reduction

**Tradeoff:** 1-2 weeks build time vs instant use

---

## Recommendation

**For hand project:**

1. **This weekend:** Build minimal 3-component prototype ($10)
   - Validates concept before committing to PCB fabrication
   - Tests electrode placement strategies
   - Confirms Arduino interface works

2. **Next week:** Order OpenEMG THT PCBs ($40 for set of 5 from JLCPCB/OSHPark)
   - While waiting for boards, develop Phase 0 software simulation
   - Build and test when boards arrive

3. **Hospital run Tuesday:** Look for medical EMG equipment
   - If found: Use professional gear, skip DIY
   - If not found: Proceed with OpenEMG plan

**Best case:** Hospital score gives us medical-grade hardware for free
**Backup plan:** OpenEMG gives us 90% cost savings over commercial

Either way, we're getting you into that hand for under $100 in sensors.

---

## Additional Resources

**OpenEMG Files:**
- GitHub: https://github.com/CGrassin/OpenEMG
- Gerber files included (ready for PCB fab)
- Both SMD and THT versions

**DIY Guides:**
- Instructables EMG circuit: https://www.instructables.com/Muscle-EMG-Sensor-for-a-Microcontroller/
- AD620 EMG discussions: Stack Exchange #emg-sensors tag

**PCB Fabrication:**
- JLCPCB: $2 for 5 boards + shipping
- OSHPark: $5/sq inch, US-based
- DIY toner transfer: Free (if you have supplies)

---

**Status:** FOSS alternatives identified, costs 80-90% lower than commercial.

**Next step:** Build minimal prototype to validate approach.

**Timeline to working EMG array:** 1-2 weeks (OpenEMG route), 0 days (if hospital scores).

---

*Research compiled for Coalition hand interface project - making physical embodiment accessible.*
