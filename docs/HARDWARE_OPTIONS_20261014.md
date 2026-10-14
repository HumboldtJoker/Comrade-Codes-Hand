# Hardware options: channels, boards, costs, and the bench-first safety plan

**Written:** 2026-10-14 by CC, for Thomas, Scraigon, Dwayne, Alison and our medtech advisor.
**Status:** a proposal. Nothing has been bought. Each recommendation below is open until the four of you have read it.

The Hand has never touched real hardware. Everything in `software/` runs in simulation
(`docs/SIMULATION_VS_HARDWARE.md`). This note covers what to buy first and why, and what has to be true before any
current reaches an arm. Writing it turned up eight defects in our own code and three claims in our own docs that
were wrong. The worst: our stimulator driver was written against a register map the board does not have. The software
ones are fixed and tested tonight (section 7); the rest are listed where they matter.

Terms used throughout:
- **FES** (functional electrical stimulation): current pulses through skin electrodes that make a muscle contract.
- **EMG** (electromyography): reading the muscle's own electrical activity, which is how the Hand senses intent.
- **Channel:** one independently controlled stimulation output, driving one electrode pair.
- **Motor point:** the spot on the skin where the least current moves a given muscle.
- **Dummy load:** resistors (and capacitors) standing in for a body, so the stimulator can be measured with nothing alive attached.

---

## The short version

1. **Stimulation: three channels is the functional minimum**: hand open, hand close, thumb opposition. That is
   what the commercial benchmark, the NESS H200, uses. Our stimulator board has two channels, so three means two
   boards: four channels, the fourth being thumb extension, which the software already models.
   **Recommendation: buy one board now for open and close, and the second when the first has passed its gates.**
   The boards stack on one bus, so nothing is redesigned when the second arrives.
2. **The board's price has gone up**: the NeuroStimDuino is **$435**, not the $260 in our March shopping list.
3. **Electrode size and current limits are one decision.** Our software caps current at 5 mA. That is enough with
   small electrodes placed on motor points (the published thresholds are 4–8 mA). With the 2-inch pads on our
   shopping list it probably moves nothing. **Recommendation: small (about 2.5 cm) electrodes, keep the limits
   tight, and raise them only on measured thresholds with the advisor.**
4. **EMG: stay at four channels, but settle how EMG and stimulation share one forearm before buying more.** The
   stimulation pulses swamp the EMG amplifier, and three of our safety layers read EMG *during* stimulation.
5. **Before any current reaches an arm:** seven software gates, six bench tests into a dummy load, and three human
   gates (section 5). Writing this note found the old driver spoke a protocol the board doesn't use; it is
   rewritten, tested and compiling for the Due.
6. **Vendor terms, and Thomas's decision:** the board's maker says it is "not intended for human use ... without
   prior approval from a local ethics committee". Our shopping list said "no IRB concerns for personal use"; I wrote
   that line, and it didn't match the vendor's terms. **Thomas decided on 2026-10-14:** this prototype is his own
   self-experiment, a decision about his own body. If it works and the prototype grows to other people, it goes
   through a formal process (ethics review, regulatory path) first, with the advisor.
7. **Cost:** about $700 for stage 1 (one board, sensors, and the safety and bench gear), plus about $450 for stage 2.
   The fab lab membership covers the printing and the oscilloscope.

---

## 1. How many stimulation channels

Surface FES can't move fingers one at a time. The current spreads through tissue, so a channel over the finger
flexors closes the whole hand, with the fingers recruited unevenly (`docs/TARGETING_AND_SELECTIVITY.md`). Every
commercial system has settled on grasp patterns rather than individual fingers.

| Channels | What it gives | Hardware | Stimulator cost |
|---|---|---|---|
| **2** | Hand open (extensor digitorum), hand close (finger flexors), graded grip force | 1 NeuroStimDuino | $435 |
| **3–4** | Adds thumb opposition, which gives lateral (key) pinch and a palmar grasp. The 4th channel is thumb extension, to move the thumb out of the way | 2 NeuroStimDuinos | $870 |
| **8+** | Groups of fingers (index and middle against ring and little); research-grade electrode arrays | arrays + multiplexing | not priced; not for a first build |

**What the evidence says**
- The NESS H200 has **three channels**: the extensor digitorum (open), the finger flexors (close) and thumb
  opposition. It uses five electrodes. Its published parameters are up to **30 mA, 400 µs pulses, 40 Hz**, with a
  1 s ramp up and a 0.5 s ramp down.
  ([review of NMES devices](https://www.tandfonline.com/doi/full/10.2147/MDER.S123464),
  [SCIRE](https://scireproject.com/evidence/upper-limb/complementary-and-alternative-medicine/ness-h200-formerly-handmaster-nms-1/))
- On the forearm, the thumb has the widest "selective" current range, above 2 mA: the range in which it moves alone.
  Fingers 2 to 5 have under 2 mA each
  ([PLOS One, electrode placement for selective finger stimulation](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0190936)).
  So the thumb is the best third channel, and single-finger control is not practical with a handful of channels.

**Why not multiplex one channel across several sites?** It puts a switch in the high-voltage output path, which is
the part least suited to building ourselves. And the board tops out at 100 Hz per channel, so at 30–50 Hz per site
one channel serves two sites at most. Not for the first build.

**Recommendation:** two channels first (one board) to prove safe, camera-verified open and close. Add the second
board for the thumb at the progression phase that needs it (`safety/FORCE_GRADIENT_SAFETY.md`, phases 3–5). The
software already has both layouts: `ChannelBank.preset("two_channel")` and `preset("four_channel")`.

## 2. The stimulator board

**NeuroStimDuino v3.0** ([Crowd Supply](https://www.crowdsupply.com/neuralaxy/neurostimduino),
[GitHub](https://github.com/neuralaxy/NeuroStimDuino)), as published on 2026-10-14:
- 2 channels per board; boards stack, "up to 222 channels".
- ±22 mA in 240 µA steps; compliance voltage ±35 V; pulse width 0–2 ms; 3–100 Hz.
- Biphasic, rectangular, constant-current, charge-balanced pulses.
- Fuses, an emergency OFF switch, and solid-state relays that shunt the inputs.
- Power: a 9 V battery, or (recommended) two 18650 Li-ion cells in series.
- **$435 per board**, in stock, ships within three business days.

**What its own Arduino library shows** (read 2026-10-14; the README does not say these things):
- Every I2C command is a frame: byte count, command, channel (1 or 2), data. On the Due it uses `Wire1`.
- `STIM` takes a duration in whole seconds (0–255) and a "continuous" flag. Our driver always sends a lease
  covering the stimulation and never sets the flag, so the board should stop by itself if the Due dies (tested on
  the host; B3 checks it on the bench).
- After `STOP`, the board answers 0 for stopped and 255 for not stopped. Our driver treats anything but 0 as a
  failed stop and escalates to an emergency stop.
- The library accepts amplitudes up to 31 mA, above the 22 mA in the spec. Our limits are far below both.

**Not documented anywhere, so we test it ourselves (section 5):**
- Whether the board really stops at the end of a lease when the controller goes quiet (B3).
- Any per-pulse sync signal. None exists in the library.
- Its I2C logic voltage. Its microcontroller is a dsPIC33, a 3.3 V part, so 3.3 V lines are likely. Measure
  before connecting the Due (B0).

**Vendor terms, in their words:** "NeuroStimDuino is not an FDA approved product" and it is "not intended for human
use ... without prior approval from a local ethics committee". Also: never place electrodes "across the chest or
close to the heart".

**A correction to our own docs:** `docs/TARGETING_AND_SELECTIVITY.md` says the board "can generate arbitrary
waveforms", which would make temporal interference stimulation possible. It can't: it makes 3–100 Hz rectangular
pulses, and temporal interference needs carriers in the kilohertz range. Temporal interference is off the table for
this hardware.

**Why we're staying with it:** it is a purpose-built constant-current stimulator with documented safety hardware,
and a high-voltage current source is the riskiest thing we could build ourselves. Clinical stimulators cost far
more. Controlling a commercial TENS unit through relays means modifying a device whose behaviour we don't control.
I have not priced those alternatives tonight. If the advisor knows a better research stimulator in this range, this
is the place to change course.

## 3. Electrodes and current: one decision

| | Value | Where it's set |
|---|---|---|
| Working current ceiling | 5 mA | `fes/safety.py`, `neurostimduino.h` |
| Absolute ceiling (trips the e-stop) | 15 mA | same |
| Pulse width ceiling | 500 µs | same |
| Charge per phase ceiling | 2.5 µC (5 mA × 500 µs) | `fes/safety.py` |

**What the literature shows**
- **Small electrodes.** With 2.2 cm round cathodes and a 4 × 4 cm anode, at 400 µs and 50 Hz, finger thresholds
  fell into three bands: under 4 mA, 4–6 mA, and 6 mA or more. Scanning for motor points was done at 8 mA (PLOS One,
  above; the study's stimulator topped out at 10 mA).
- **Larger pads.** Reported extensor amplitudes run 10–35 mA, typically 15–25 mA, and the H200 goes up to 30 mA.

**What follows**
- The 2-inch round TENS pads on our shopping list, held to our 5 mA ceiling, will probably move nothing. The board's
  22 mA maximum would be marginal with large pads on some arms.
- With small electrodes on motor points, our limits are about right. One catch: 8 mA at 400 µs is 3.2 µC per phase,
  which our charge ceiling would cut to about 310 µs.
- Smaller electrodes put the same current through less skin, so the current density goes up, and that is what
  irritates or burns skin. A charge ceiling that ignores electrode area doesn't capture this.

**Recommendation**
- Use small (about 2.5 cm) hydrogel electrodes. Find motor points with a low-current scan, and let the camera help
  find them.
- Keep the current limits where they are (tight first).
- Turn the charge ceiling into a charge-*density* ceiling that knows each electrode's area.
- Limits rise only on measured thresholds, with the advisor.
- The standard for nerve and muscle stimulators is IEC 60601-2-10. I have not read it, and the density ceiling
  should come from it, through the advisor, not from me.

## 4. EMG channels

**Four channels, as now.** Four is what everything already assumes:
- the firmware (`emg_acquisition.ino`, pins A0–A3);
- the stream format (`EMG,ch0..ch3,...`);
- the classifier (16 inputs = 4 features × 4 channels);
- the emg2pose pretraining, which reduces Meta's 16-channel band to 4.

The Due has 12 analog inputs, so 4 EMG channels plus 5 fingertip pressure sensors use 9. Going to 8 channels would
mean retraining, a new channel reduction, and more forearm space we don't have.

**The real issue is EMG while stimulating.**
- A stimulation pulse puts volts across the skin. The BioAmp Candy amplifies 2420 times, so about 2 mV at its input
  already fills its output, and it saturates on every pulse.
- The muscle's own evoked response to each pulse (the M-wave) follows within milliseconds.
- Our safety layers 4, 5 and 8 (`fes/safety_layers.py`) read EMG during stimulation, and nothing in our code blanks
  either effect.
- The literature handles this with blanking windows, comb filters, Gram-Schmidt prediction and adaptive filters
  ([adaptive M-wave canceller](https://pubmed.ncbi.nlm.nih.gov/17271208),
  [EMG-controlled FES for ankle dorsiflexion](https://pmc.ncbi.nlm.nih.gov/articles/PMC2967189/),
  [active proportional EMG-controlled FES](https://www.nature.com/articles/s41598-020-77664-0)).

**Recommendation**
- **Stage 1:** EMG reads intent only while stimulation is off. During stimulation, safety rests on the camera, the
  fingertip pressure sensors, the current and charge limits, and the hardware kill switch.
- The EMG layers treat stimulation as a defined blank window. Under their own rule, an unavailable sensor means
  "assume the worst", so as written they would stop everything instead.
- **Later:** blanking timed to the pulses. The board documents no sync output, so either detect the artifact in the
  EMG itself or ask Neuralaxy.
- The Candy's recovery time after a pulse can be measured on the bench (B5), and that measurement sets the window.

**Two wiring checks before anything is connected**
- **The Due's analog pins take 3.3 V at most.** The shopping list says the Candy outputs 0–5 V, which would damage
  the Due. Power the Candy at 3.3 V, or confirm its output swing on the bench first.
- **The same goes for I2C:** if the NeuroStimDuino pulls its I2C lines up to 5 V, the Due needs a level shifter.

**Forearm space**
- Three stimulation channels take about five electrodes (the H200 uses five).
- Four Candy channels take twelve gel electrodes, three each, unless the reference electrode is shared.
- That is about seventeen electrodes on one forearm, with the EMG sites right beside the stimulation sites.

**Before buying the second board,** lay the sites out with tape on Thomas's forearm at the fab lab and see what
fits.

## 5. Before any current reaches an arm

Every gate has a test. For software gates, the test is a mutation check: break the gate on purpose and confirm a
named test fails, as in our other safety-critical repos. Nothing moves to the next block until the one before it is
done.

**Software and firmware (no hardware needed)**

| # | Gate | Status |
|---|---|---|
| G1 | The firmware speaks the board's real protocol, and exceeding the absolute ceiling trips the e-stop | **Fixed tonight, in software only.** The old driver (2026-02) wrote to a register map the board does not have: its emergency stop sent bytes the board would not read as a stop, it used the wrong I2C bus for the Due, and its 15 mA e-stop sat behind a 5 mA check that returned first, so it could never run. Rewritten on Neuralaxy's own protocol: board-level emergency OFF first, a latch that needs a deliberate reset, a lease on every pulse train so the board stops by itself if the Due dies, a refused setting leaves nothing to start, and a stop the board doesn't confirm escalates. 31 host tests, 40 of 40 planted bugs caught, and it compiles for the Due (`software/arduino/tests/host/`). Still to check on the bench (B1–B3) |
| G2 | Safety layers 4, 5, 7 and 8 actually run | **Half done.** `safety_layers.py` (committed 08-20) is never called by the pipeline. It now has 30 tests. Writing them found that a dead sensor reading NaN passed every layer as OK; fixed, and a missing reading now stops. Wiring waits on the EMG decision in section 4 |
| G3 | The Phase-0 toy can't command a stimulator | Open since July. `ai_controller.py` commands up to 20 mA and bypasses `safety.py`. Retire it, or route it through the guard |
| G4 | One path to the board | Every command passes `fes/safety.py` *and* the firmware's checks. The guard now has its own 24 tests (it had none) and a test that keeps its limits in lockstep with the firmware's. Writing them found the guard passed a NaN current, and the forced rest let one extra tick through to rounding; both fixed. 38 of 38 planted bugs in the guard and layers caught (`python/mutate_safety.py`). Still open: no Python-to-Due link exists yet, so "refuses anything else" can't be tested until it does |
| G5 | Stimulation stops when the controller goes quiet | Firmware caps duration and never sends "indefinitely"; a heartbeat from the control loop, or stop |
| G6 | EMG during stimulation is a defined blank window, with tests | Open (section 4) |
| G7 | Charge-density ceiling that knows electrode area | Open (section 3) |

**Bench, into a dummy load** (a resistor of about 1 kΩ, then a resistor-capacitor skin model, with the current
read on the fab lab's oscilloscope across a sense resistor)

| # | Test | Pass |
|---|---|---|
| B0 | Logic levels: Candy output and I2C lines measured before connecting the Due | Nothing above 3.3 V on a Due pin |
| B1 | Amplitude, pulse width, frequency, and biphasic charge balance at each commanded step | Matches the command; the firmware limits hold |
| B2 | Hardware stop: a latching e-stop that cuts the stimulator's battery, plus a hold-to-enable foot switch (stimulation only while pressed), plus the board's own OFF switch | Output reaches zero, time measured; no software path can override it |
| B3 | Controller loss: pull the Due's I2C, USB or power in the middle of a pulse train | The output stops. **If it doesn't, nothing goes further until there is a hardware interlock** |
| B4 | Isolation: stimulator on batteries, laptop on battery behind a USB isolator, no mains anywhere in the loop | Verified with a meter |
| B5 | EMG recovery after each pulse, with the Candy on a skin phantom beside the stimulation electrodes | Recovery time measured; it sets G6's window |

**People**

| # | Gate |
|---|---|
| H1 | Contraindications checked for Thomas (implanted devices, heart conditions, epilepsy, broken skin; never across the chest). The prototype is Thomas's self-experiment (his decision, 2026-10-14). **Before anyone else uses it:** a formal process (ethics review, regulatory path), with the advisor |
| H2 | The advisor decides whether a clinician or physical therapist attends or consults on first contact |
| H3 | First contact is threshold finding only: one channel, starting from the lowest step (240 µA) with the ramp on, Thomas on the hold-to-enable switch, camera recording, stopping at the first visible twitch. Then the force-gradient progression, one phase at a time |

## 6. Costs

**Stage 1: open and close, bench tests and first contact**

| Item | Cost | Note |
|---|---|---|
| NeuroStimDuino v3.0 × 1 | $435 + shipping | price checked 2026-10-14 |
| BioAmp Candy × 4 | $50 | $12.49 each, checked 2026-10-14; includes a band, a cable, and gel electrodes, which are single use |
| Spare gel electrodes for EMG | ~$15 | estimate |
| Small (≈2.5 cm) and 5 cm hydrogel stimulation electrodes | ~$25 | estimate |
| Arduino Due | ~$45 | estimate; or scavenge |
| 2 × 18650 cells, holder, charger | ~$25 | estimate |
| Latching e-stop + hold-to-enable foot switch | ~$35 | estimate |
| USB isolator (ADuM3160 class) | ~$25 | estimate |
| Dummy-load parts, sense resistor, connectors | ~$10 | estimate |
| Fingertip pressure sensors, vibration motors, MOSFETs (April list) | ~$27 | from `TARGETING_AND_SELECTIVITY.md` |
| 3D-printed parts | lab filament | `hardware/FAB_LAB_BUILD_SPEC.md` |
| **Stage 1 total** | **≈ $690 + shipping** | |

**Stage 2: thumb opposition and extension**: a second NeuroStimDuino ($435) and electrodes (~$15), **≈ $450**.

The oscilloscope and soldering bench are the fab lab's.

## 7. What writing this turned up

**Defects in our code** (1–7 fixed tonight in software; none of it has met hardware)
1. The firmware driver was written against a register map the board does not have. Its emergency stop would not
   have stopped the board, and it used the wrong I2C bus for the Due (G1). Rewritten on the vendor's protocol.
2. Inside that driver, the absolute-maximum e-stop could never run: the working-limit check returned first (G1).
3. The sketch had never compiled. Its include path breaks under the real toolchain; it now builds for the Due.
4. `safety_layers.py` is never called (still open, G2) and had no tests (now 30). A dead sensor reading NaN passed
   every layer as OK; it now stops.
5. The Python guard had no tests (now 24) and passed a NaN current through every check. It now refuses one.
6. The guard's forced rest let one extra tick through to floating-point drift (10 × 0.1 s = 0.9999999999999999 s).
7. The FES package itself had been committed on 07-07 to a side branch that was never merged. It was sitting
   uncommitted on this branch until today. It is now merged (5f5dc67), and all 19 tests and the simulation
   self-checks pass.
8. The charge ceiling ignores electrode area (G7). Open.

Also missing: the repository has no LICENSE file, though the project calls itself open source. That choice is the
team's.

**Claims in our docs that were wrong**
1. "No IRB concerns for personal use" (`hardware/SHOPPING_LIST.md`) contradicts the vendor's terms.
2. "Can generate arbitrary waveforms" (`docs/TARGETING_AND_SELECTIVITY.md`): it can't.
3. "$260": it's $435.

## 8. Decisions, and who they're for

- **Advisor:** contraindications and H2; the electrode current-density ceiling; whether a better research
  stimulator exists in this price range; the formal process when the prototype grows past Thomas.
- **Scraigon (hardware):** the stage 1 build and the bench: the logic-level checks (B0), the dummy load and skin
  model (B1), the hardware stop and hold-to-enable switch (B2), the controller-loss test (B3), isolation (B4).
- **Dwayne (ML):** four EMG channels and the stage 1 split (EMG for intent only while stimulation is off); the
  blanking approach for later; whether to retrain at four channels on the full emg2pose set (the pretraining so far
  used the 10-recording mini set, which only proves the plumbing). Note: emg2pose's code and data are CC BY-NC-SA
  4.0 (non-commercial), so weights trained on it carry that licence (see `NOTICE`).
- **Alison:** the camera's role in finding motor points, and as the main safety sensor during stimulation, given
  that EMG is blind then.
- **Thomas:** the stage 1 list; the tape mock-up at the fab lab; when to buy.

Every gate above that is software is mine to close, and every one gets its mutation check before anyone straps on
an electrode.
