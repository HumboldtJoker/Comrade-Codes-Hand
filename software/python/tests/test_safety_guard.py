"""The safety guard (python/fes/safety.py): the gate every stimulation command passes in software.

Each test names what must not get through. The firmware wrapper enforces the same static limits a second time
(software/arduino/stimulation_control/neurostimduino.h); the last test keeps the two in lockstep.
"""
import math
import re
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from python.fes import safety  # noqa: E402
from python.fes.channels import StimParams  # noqa: E402
from python.fes.safety import SafetyGuard, Severity  # noqa: E402

HEADER = Path(__file__).resolve().parents[2] / "arduino" / "stimulation_control" / "neurostimduino.h"


def sp(current=2000, **kw):
    return StimParams(channel=kw.pop("channel", 0), current_ua=current, **kw)


def settled(guard, channel=0, current=2000, steps=200):
    """Ramp a channel up to `current` within the gradient, as a real loop would."""
    d = None
    for _ in range(steps):
        d = guard.check(sp(current, channel=channel), dt_s=0.02)
        if d.params.current_ua == current:
            break
    return d


# ---- hard limits ------------------------------------------------------------------------------------------------------
def test_above_the_absolute_limit_latches_the_emergency_stop_and_sends_nothing():
    g = SafetyGuard()
    d = g.check(sp(safety.ABSOLUTE_MAX_UA + 1))
    assert d.params.current_ua == 0 and d.severity is Severity.ESTOP and g.estopped


def test_the_absolute_limit_is_checked_before_the_working_clamp():
    # The firmware once checked the working limit first, which made its absolute-limit stop unreachable.
    g = SafetyGuard()
    d = g.check(sp(safety.ABSOLUTE_MAX_UA + 1))
    assert d.severity is Severity.ESTOP and not any(v.rule == "max_current" for v in d.violations)


def test_a_large_negative_current_is_an_emergency_stop_too():
    g = SafetyGuard()
    g.check(sp(-(safety.ABSOLUTE_MAX_UA + 1)))
    assert g.estopped


def test_while_latched_every_command_is_zeroed_until_a_deliberate_reset():
    g = SafetyGuard()
    g.emergency_stop("test")
    d = g.check(sp(100))
    assert d.params.current_ua == 0 and d.severity is Severity.ESTOP
    g.reset()
    assert g.check(sp(40)).params.current_ua == 40


def test_non_biphasic_is_refused():
    d = SafetyGuard().check(sp(1000, biphasic=False))
    assert d.params.current_ua == 0 and d.severity is Severity.REJECTED


def test_a_negative_current_is_refused():
    d = SafetyGuard().check(sp(-100))
    assert d.params.current_ua == 0 and d.severity is Severity.REJECTED


def test_a_frequency_out_of_range_is_refused():
    for f in (safety.MIN_FREQUENCY_HZ - 1, safety.MAX_FREQUENCY_HZ + 1):
        assert SafetyGuard().check(sp(40, frequency_hz=f)).params.current_ua == 0
    assert SafetyGuard().check(sp(40, frequency_hz=safety.MAX_FREQUENCY_HZ)).params.current_ua == 40


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None, "2000", 2000.5, True])
def test_a_current_that_is_not_a_whole_finite_number_is_refused(bad):
    d = SafetyGuard().check(sp(bad))
    assert d.params.current_ua == 0 and d.severity is Severity.REJECTED


@pytest.mark.parametrize("field", ["pulse_width_us", "frequency_hz", "duration_ms"])
def test_any_other_field_that_is_not_a_finite_number_is_refused(field):
    p = sp(40)
    setattr(p, field, float("nan"))
    d = SafetyGuard().check(p)
    assert d.params.current_ua == 0 and all(map(math.isfinite, (d.params.pulse_width_us, d.params.frequency_hz)))


def test_numpy_integers_are_numbers():
    assert SafetyGuard().check(sp(np.int64(40))).params.current_ua == 40


# ---- clamps -----------------------------------------------------------------------------------------------------------
def test_above_the_working_limit_is_clamped_to_it():
    g = SafetyGuard(max_ramp_ua_per_s=1e9)
    d = g.check(sp(safety.MAX_CURRENT_UA + 3000))
    assert d.params.current_ua == safety.MAX_CURRENT_UA and d.severity is Severity.CLAMPED and not g.estopped


def test_the_comfort_ceiling_is_never_exceeded():
    g = SafetyGuard(comfort_ceiling_ua={0: 1500}, max_ramp_ua_per_s=1e9)
    assert g.check(sp(4000)).params.current_ua == 1500
    assert g.check(sp(4000, channel=1)).params.current_ua == 4000                    # no ceiling set: working max
    assert g.check(sp(6000, channel=1)).params.current_ua == safety.MAX_CURRENT_UA


def test_pulse_width_and_duration_are_clamped():
    d = SafetyGuard(max_ramp_ua_per_s=1e9).check(sp(40, pulse_width_us=900, duration_ms=9000))
    assert d.params.pulse_width_us == safety.MAX_PULSE_WIDTH_US and d.params.duration_ms == safety.MAX_STIM_DURATION_MS


def test_charge_per_phase_is_kept_under_the_ceiling_by_shortening_the_pulse():
    g = SafetyGuard(max_ramp_ua_per_s=1e9, max_charge_per_phase_uc=1.0)
    d = g.check(sp(4000, pulse_width_us=500))
    assert d.params.current_ua == 4000 and d.params.pulse_width_us == 250
    assert d.params.charge_per_phase_uc() <= 1.0


# ---- governors over time ------------------------------------------------------------------------------------------------
def test_current_rises_no_faster_than_the_gradient():
    g = SafetyGuard(max_ramp_ua_per_s=4000)
    d = g.check(sp(3000), dt_s=0.1)
    assert d.params.current_ua == 400
    d = g.check(sp(3000), dt_s=0.1)
    assert d.params.current_ua == 800


def test_the_gradient_is_per_channel():
    g = SafetyGuard(max_ramp_ua_per_s=4000)
    g.check(sp(3000, channel=0), dt_s=0.1)
    assert g.check(sp(3000, channel=1), dt_s=0.1).params.current_ua == 400


def test_current_may_fall_at_once():
    g = SafetyGuard()
    settled(g, current=2000)
    assert g.check(sp(0)).params.current_ua == 0


def test_sustained_stimulation_forces_a_rest_and_the_rest_restores_it():
    g = SafetyGuard(max_ramp_ua_per_s=1e9, max_continuous_on_s=1.0, min_rest_after_on_s=2.0)
    for _ in range(10):
        g.check(sp(1000), dt_s=0.1)                   # 1.0 s on
    assert g.check(sp(1000), dt_s=0.1).params.current_ua == 0   # refused: this tick counts as rest
    for _ in range(18):
        g.check(sp(0), dt_s=0.1)                      # 1.9 s of rest in all: not enough
    assert g.check(sp(1000), dt_s=0.1).params.current_ua == 0
    for _ in range(21):
        g.check(sp(0), dt_s=0.1)
    assert g.check(sp(1000), dt_s=0.1).params.current_ua == 1000


def test_an_ordinary_command_passes_untouched():
    d = SafetyGuard(max_ramp_ua_per_s=1e9).check(sp(2000))
    assert d.params.current_ua == 2000 and d.severity is Severity.OK and not d.modified


# ---- lockstep with the firmware -----------------------------------------------------------------------------------------
def test_the_static_limits_match_the_firmware():
    defines = dict(re.findall(r"^#define (\w+) (\d+)", HEADER.read_text(), re.M))
    for name in ("MAX_CURRENT_UA", "ABSOLUTE_MAX_UA", "MAX_PULSE_WIDTH_US", "MIN_FREQUENCY_HZ", "MAX_FREQUENCY_HZ",
                 "MAX_STIM_DURATION_MS"):
        assert int(defines[name]) == getattr(safety, name), name


def test_a_comfort_ceiling_set_above_the_working_limit_cannot_raise_it():
    g = SafetyGuard(comfort_ceiling_ua={0: 9000}, max_ramp_ua_per_s=1e9)
    assert g.check(sp(6000)).params.current_ua == safety.MAX_CURRENT_UA
