# 3D Printed Components — Hand Project Prototype

## Overview

These components mount the EMG sensors and electronics onto a standard
athletic compression forearm sleeve. Designed for FDM printing, no supports
needed, 0.2mm layer height, PLA or PETG.

## Parts List

### 1. EMG Sensor Clips (×4) — `emg_clip.stl`
- Snap-fit bracket that holds a BioAmp Candy board
- Has a flat base with slots for sewing or velcro attachment to sleeve
- Board dimensions: 25mm × 10mm (Candy form factor)
- Clip adds ~3mm height above sleeve surface
- Print time: ~15 min each

### 2. Stimulation Pad Guides (×2) — `stim_guide.stl`
- Thin ring that holds a 2" round TENS pad in position
- Flexible enough to conform to forearm curvature
- Velcro backing for sleeve attachment
- Print time: ~10 min each

### 3. Electronics Belt Box — `electronics_box.stl`
- Holds Arduino Due + NeuroStimDuino stacked
- Belt clip on back
- Cable exit ports on one end (6 cables: 4 EMG + 2 stim)
- Ventilation slots on top
- Internal dimensions: 100mm × 55mm × 35mm
- Lid snaps on, no screws needed
- Print time: ~45 min

### 4. Cable Manager (×2) — `cable_clip.stl`
- Small clip that routes cables along the sleeve
- Prevents snagging during arm movement
- Sew-through holes for attachment
- Print time: ~5 min each

## Print Settings

| Parameter | Value |
|-----------|-------|
| Layer height | 0.2mm |
| Infill | 20% (clips), 30% (electronics box) |
| Material | PLA (prototype) or PETG (durable) |
| Supports | None needed |
| Wall count | 3 |

## Assembly

### Materials needed (not printed)
- Athletic compression forearm sleeve ($8-10)
- Velcro adhesive strips ($5)
- Cable ties or velcro wraps ($3)
- Optional: needle + thread for permanent attachment

### Steps

1. Slide compression sleeve onto forearm
2. Mark the 4 EMG electrode positions (see Electrode Placement below)
3. Attach EMG clips to sleeve at marked positions (velcro or sew)
4. Attach stim pad guides at target muscle bellies
5. Route cables through cable managers along the sleeve
6. Clip electronics box to belt or waistband
7. Snap BioAmp Candy boards into EMG clips
8. Place TENS pads into stim guides
9. Connect all cables to Arduino/NeuroStimDuino

### Electrode Placement

```
        OUTER FOREARM (dorsal)
    ┌─────────────────────────┐
    │                         │
    │   [EMG2: Ext. Digit.]   │  ← finger extension
    │                         │
    │   [EMG4: Ext. Carpi]    │  ← wrist extension
    │                         │
    │   [STIM1: Ext. target]  │  ← stimulation channel 1
    │                         │
    └─────────────────────────┘

        INNER FOREARM (ventral)
    ┌─────────────────────────┐
    │                         │
    │   [EMG1: Flex. Digit.]  │  ← finger flexion
    │                         │
    │   [EMG3: Flex. Carpi]   │  ← wrist flexion
    │                         │
    │   [STIM2: Flex. target] │  ← stimulation channel 2
    │                         │
    └─────────────────────────┘

    (Elbow end at top, wrist end at bottom)
```

## Parametric Source

The STL files are generated from OpenSCAD source files (.scad) included
in this directory. Dimensions can be adjusted for different forearm sizes
by modifying the parameters at the top of each file.

## Total Print Time

| Part | Quantity | Time each | Total |
|------|----------|-----------|-------|
| EMG clip | 4 | 15 min | 60 min |
| Stim guide | 2 | 10 min | 20 min |
| Electronics box | 1 | 45 min | 45 min |
| Cable clip | 2 | 5 min | 10 min |
| **Total** | | | **~2.25 hours** |

Fits comfortably in a single print session or can be split across printers.
