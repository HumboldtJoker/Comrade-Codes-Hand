"""
channels.py — FES channel and muscle-recruitment model.

Defines the electrical stimulation command (`StimParams`, a Python mirror of
the Arduino `StimParams` struct in neurostimduino.h) and the anatomical
channel bank that maps stimulation channels to forearm muscle groups.

Grounded in the physics reality documented in docs/TARGETING_AND_SELECTIVITY.md:
surface FES cannot address individual fingers. Electric fields spread through
tissue, so a single channel over the finger flexors recruits ALL fingers with
tapering weight — it produces a *grasp pattern*, not a per-finger command. Every
commercial system (Bioness H200, MyndMove, Fesia Grasp) converged on this.

We model that spillover honestly with a recruitment matrix: each channel has a
per-finger weight describing how strongly it moves that finger. The simulator
uses it forward (channel activation -> finger movement); the mapping layer uses
it inverse (desired finger movement -> channel activation).

No hardware required. Pure data + numpy.
"""
from dataclasses import dataclass, field
from typing import Dict, List
from enum import IntEnum

import numpy as np

# The vision layer owns the canonical Finger enum; reuse it so a landmark angle
# and a recruitment weight always index the same finger.
try:
    from ..vision.hand_tracker import Finger
except ImportError:  # allow standalone execution (python fes/channels.py)
    class Finger(IntEnum):
        THUMB = 0
        INDEX = 1
        MIDDLE = 2
        RING = 3
        PINKY = 4


# Full flexion angle (degrees) a finger reaches at 100% recruitment. Matches the
# 0..90 flexion scale produced by vision/hand_tracker._finger_flexion.
MAX_FLEXION_DEG = 90.0


class StimDirection(IntEnum):
    """Which way a channel moves the joints it recruits."""
    EXTEND = -1   # opens the hand
    FLEX = 1      # closes the hand


@dataclass
class StimParams:
    """A single electrical stimulation command for one channel.

    Mirror of the `StimParams` struct in
    software/arduino/stimulation_control/neurostimduino.h so the Python control
    layer and the firmware speak the same units. Current in microamps, pulse
    width in microseconds, frequency in Hz, duration in milliseconds.

    `biphasic` MUST stay True: charge-balanced biphasic pulses avoid net DC
    charge accumulation that causes electrode corrosion and tissue damage.
    """
    channel: int
    current_ua: int = 0
    pulse_width_us: int = 200
    frequency_hz: int = 30
    duration_ms: int = 0        # 0 = continuous (governed by the watchdog)
    biphasic: bool = True

    def is_active(self) -> bool:
        return self.current_ua > 0

    def charge_per_phase_uc(self) -> float:
        """Charge delivered per phase, in microcoulombs (I * t).

        Charge per phase (not just current) is what drives tissue safety limits;
        the safety layer bounds it against a charge-density ceiling.
        """
        return (self.current_ua * self.pulse_width_us) / 1e6

    def copy(self) -> "StimParams":
        return StimParams(
            channel=self.channel,
            current_ua=self.current_ua,
            pulse_width_us=self.pulse_width_us,
            frequency_hz=self.frequency_hz,
            duration_ms=self.duration_ms,
            biphasic=self.biphasic,
        )


@dataclass
class Channel:
    """One stimulation channel: an electrode pair over a muscle group.

    recruitment maps each finger to how strongly this channel moves it, in the
    channel's direction. 1.0 = this channel drives that finger fully; 0.0 = no
    effect. Values between model the real spillover of surface stimulation.
    """
    index: int
    name: str
    muscle: str
    direction: StimDirection
    electrode_site: str
    recruitment: Dict[Finger, float] = field(default_factory=dict)

    def weight(self, finger: Finger) -> float:
        return self.recruitment.get(finger, 0.0)


class ChannelBank:
    """A configured set of stimulation channels and their recruitment matrix.

    Presets reflect docs/TARGETING_AND_SELECTIVITY.md:
      - "two_channel":  what the base $260 NeuroStimDuino can do today —
                        mass close (finger flexors) + mass open (extensors).
      - "four_channel": the multiplexed upgrade — adds thumb flex/extend, which
                        unlocks lateral pinch and opposition.
    """

    def __init__(self, channels: List[Channel]):
        self.channels = channels

    def __len__(self) -> int:
        return len(self.channels)

    def __iter__(self):
        return iter(self.channels)

    def __getitem__(self, i: int) -> Channel:
        return self.channels[i]

    def recruitment_matrix(self) -> np.ndarray:
        """(n_channels, 5) signed matrix: row c, col f = direction * weight.

        Positive entries flex the finger, negative extend it. Multiply by a
        column of per-channel activations (0..1) to get each finger's flexion
        delta — the forward biomechanical model the simulator uses.
        """
        m = np.zeros((len(self.channels), len(Finger)))
        for c in self.channels:
            for f in Finger:
                m[c.index, int(f)] = int(c.direction) * c.weight(f)
        return m

    @classmethod
    def preset(cls, name: str = "four_channel") -> "ChannelBank":
        if name == "two_channel":
            return cls([_FINGER_FLEXORS, _FINGER_EXTENSORS])
        if name == "four_channel":
            return cls([_FINGER_FLEXORS, _FINGER_EXTENSORS,
                        _THUMB_FLEXOR, _THUMB_EXTENSOR])
        raise ValueError(f"unknown channel preset: {name!r}")


# ── Anatomical channel definitions ──────────────────────────────────────────
# Weights encode the spillover reality: a flexor channel closes the whole hand
# with the long fingers (middle strongest) recruited more than the thumb. These
# are design estimates, refined per user by the calibration workflow.

_FINGER_FLEXORS = Channel(
    index=0, name="finger_flexors", muscle="FDS/FDP",
    direction=StimDirection.FLEX, electrode_site="volar forearm, proximal third",
    recruitment={Finger.THUMB: 0.2, Finger.INDEX: 0.9, Finger.MIDDLE: 1.0,
                 Finger.RING: 0.9, Finger.PINKY: 0.8},
)

_FINGER_EXTENSORS = Channel(
    index=1, name="finger_extensors", muscle="EDC",
    direction=StimDirection.EXTEND, electrode_site="dorsal forearm, proximal third",
    recruitment={Finger.THUMB: 0.1, Finger.INDEX: 0.9, Finger.MIDDLE: 1.0,
                 Finger.RING: 0.9, Finger.PINKY: 0.8},
)

_THUMB_FLEXOR = Channel(
    index=2, name="thumb_flexor", muscle="FPL/thenar",
    direction=StimDirection.FLEX, electrode_site="thenar eminence",
    recruitment={Finger.THUMB: 1.0, Finger.INDEX: 0.2},
)

_THUMB_EXTENSOR = Channel(
    index=3, name="thumb_extensor", muscle="EPL/EPB",
    direction=StimDirection.EXTEND, electrode_site="dorsal wrist, radial",
    recruitment={Finger.THUMB: 1.0},
)


if __name__ == "__main__":
    bank = ChannelBank.preset("four_channel")
    print(f"ChannelBank: {len(bank)} channels\n")
    for ch in bank:
        arrow = "FLEX " if ch.direction == StimDirection.FLEX else "EXTEND"
        weights = " ".join(f"{f.name[:3]}={ch.weight(f):.1f}" for f in Finger)
        print(f"  CH{ch.index} {ch.name:16s} {arrow} [{ch.muscle:9s}]  {weights}")
    print("\nSigned recruitment matrix (rows=channels, cols=T I M R P):")
    print(np.round(bank.recruitment_matrix(), 2))

    p = StimParams(channel=0, current_ua=3000, pulse_width_us=250)
    print(f"\nExample command: {p.current_ua}uA @ {p.pulse_width_us}us "
          f"-> {p.charge_per_phase_uc():.3f} uC/phase")
