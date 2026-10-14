"""Safety layers 4, 5, 7 and 8 (python/fes/safety_layers.py). Each test names what must not get through.

These layers are not yet called by the pipeline: wiring them waits on how EMG is read during stimulation
(docs/HARDWARE_OPTIONS_20261014.md, sections 4 and 5, gates G2 and G6). Until then they are tested as units.
"""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from python.fes.safety_layers import (  # noqa: E402
    CameraDivergenceMonitor, EMGFeedbackMonitor, FatigueMonitor, HumanOverrideMonitor, SafetyAction,
    SafetyLayerStack,
)

OK, REDUCE, STOP = SafetyAction.OK, SafetyAction.REDUCE, SafetyAction.STOP
BAD_READINGS = [float("nan"), float("inf"), -float("inf"), None, "12", True]


# ---- a sensor that is missing or not a number is the worst case, never OK -----------------------------------------
@pytest.mark.parametrize("bad", BAD_READINGS)
def test_every_layer_stops_on_a_reading_that_is_missing_or_not_finite(bad):
    assert EMGFeedbackMonitor().check(True, bad).action is STOP
    assert FatigueMonitor().check(2000, bad).action is STOP
    assert FatigueMonitor().check(bad, 500.0).action is STOP
    assert CameraDivergenceMonitor().check(bad, True).action is STOP
    assert HumanOverrideMonitor().check(bad).action is STOP


def test_the_stack_stops_when_every_sensor_reads_nan():
    action, scale, _ = SafetyLayerStack().check(True, 2000, math.nan, math.nan, math.nan)
    assert action is STOP and scale == 0.0


def test_a_missing_reading_while_stimulation_is_off_blocks_nothing_that_is_not_running():
    assert EMGFeedbackMonitor().check(False, math.nan).action is OK
    assert CameraDivergenceMonitor().check(math.nan, False).action is OK
    assert FatigueMonitor().check(0, math.nan).action is OK


# ---- layer 4: EMG feedback -------------------------------------------------------------------------------------------
def test_no_emg_response_during_stimulation_stops_at_the_patience_limit():
    m = EMGFeedbackMonitor(no_response_patience=3)
    assert [m.check(True, 10.0).action for _ in range(3)] == [OK, OK, STOP]


def test_an_excessive_response_reduces_by_half_then_stops():
    m = EMGFeedbackMonitor(excessive_patience=3)
    r1, r2, r3 = (m.check(True, 5000.0) for _ in range(3))
    assert (r1.action, r1.scale) == (REDUCE, 0.5) and r2.action is REDUCE and r3.action is STOP


def test_a_normal_response_resets_both_counts():
    m = EMGFeedbackMonitor(no_response_patience=2, excessive_patience=2)
    m.check(True, 10.0)
    assert m.check(True, 500.0).action is OK
    assert m.check(True, 10.0).action is OK          # the count started again
    m.check(True, 5000.0)
    m.check(True, 500.0)
    assert m.check(True, 5000.0).action is REDUCE    # not STOP: reset by the normal reading


def test_stimulation_off_resets_the_counts():
    m = EMGFeedbackMonitor(no_response_patience=2)
    m.check(True, 10.0)
    m.check(False, 10.0)
    assert m.check(True, 10.0).action is OK


def test_the_thresholds_are_strict():
    m = EMGFeedbackMonitor(no_response_patience=1, excessive_patience=1)
    assert m.check(True, m.min_response_uv).action is OK
    assert m.check(True, m.max_response_uv).action is OK


# ---- layer 5: fatigue ------------------------------------------------------------------------------------------------
def _fatigue_after(baseline_uv, later_uv, n_later=10):
    m = FatigueMonitor()
    for _ in range(m.min_samples):
        m.check(1000, baseline_uv)
    r = None
    for _ in range(n_later):
        r = m.check(1000, later_uv)
    return r


def test_fatigue_collects_a_baseline_before_judging():
    m = FatigueMonitor()
    assert all(m.check(1000, 1.0).action is OK for _ in range(m.min_samples - 1))


def test_a_response_below_half_the_baseline_reduces():
    r = _fatigue_after(1000.0, 400.0)
    assert r.action is REDUCE and r.scale == pytest.approx(0.4)


def test_a_response_below_three_tenths_of_the_baseline_stops():
    assert _fatigue_after(1000.0, 200.0).action is STOP


def test_the_reduction_never_goes_below_three_tenths():
    r = _fatigue_after(1000.0, 310.0)
    assert r.action is REDUCE and r.scale == pytest.approx(0.31)


def test_a_steady_response_is_ok():
    assert _fatigue_after(1000.0, 1000.0).action is OK


def test_no_stimulation_is_not_counted():
    m = FatigueMonitor()
    for _ in range(50):
        assert m.check(0, 1000.0).action is OK
    assert len(m._response_ratios) == 0


# ---- layer 7: camera divergence --------------------------------------------------------------------------------------
def test_the_error_computers_safety_flag_stops_at_once():
    assert CameraDivergenceMonitor().check(1.0, True, safety_limited=True).action is STOP


def test_a_growing_error_above_the_threshold_reduces_then_stops():
    m = CameraDivergenceMonitor(max_divergence_cycles=3)
    out = [m.check(20.0 + i, True).action for i in range(8)]
    assert out[:4] == [OK] * 4                        # collecting a baseline
    assert REDUCE in out and out[-1] is STOP


def test_a_shrinking_error_is_ok():
    m = CameraDivergenceMonitor()
    assert all(m.check(60.0 - i, True).action is OK for i in range(20))


def test_a_growing_error_below_the_threshold_is_ok():
    m = CameraDivergenceMonitor()
    assert all(m.check(1.0 + i * 0.5, True).action is OK for i in range(20))


def test_stimulation_off_clears_the_history():
    m = CameraDivergenceMonitor(max_divergence_cycles=2)
    for i in range(6):
        m.check(20.0 + i, True)
    assert m.check(25.0, False).action is OK
    assert m._diverging_count == 0 and len(m._errors) == 0


# ---- layer 8: human override -----------------------------------------------------------------------------------------
def test_voluntary_effort_suppresses_stimulation_completely():
    m = HumanOverrideMonitor(voluntary_patience=3)
    out = [m.check(500.0) for _ in range(3)]
    assert [r.action for r in out] == [OK, OK, REDUCE] and out[-1].scale == 0.0


def test_quiet_readings_wind_the_count_down_one_at_a_time():
    m = HumanOverrideMonitor(voluntary_patience=3)
    m.check(500.0)
    m.check(500.0)
    m.check(10.0)
    assert m._voluntary_count == 1


# ---- the stack -------------------------------------------------------------------------------------------------------
def test_one_stop_stops_everything_with_zero_scale():
    stack = SafetyLayerStack()
    action, scale, results = stack.check(True, 2000, 500.0, 50.0, 5.0, safety_limited=True)
    assert action is STOP and scale == 0.0 and len(results) == 4


def test_reductions_multiply():
    stack = SafetyLayerStack()
    stack.emg_feedback.excessive_patience = 99
    action, scale, _ = stack.check(True, 2000, 5000.0, 50.0, 5.0)   # layer 4 halves; nothing else reduces
    assert action is REDUCE and scale == pytest.approx(0.5)
    stack.human_override.voluntary_patience = 1
    action, scale, _ = stack.check(True, 2000, 5000.0, 500.0, 5.0)  # layer 8 adds a 0.0
    assert action is REDUCE and scale == 0.0


def test_all_quiet_is_ok_at_full_scale():
    action, scale, _ = SafetyLayerStack().check(True, 2000, 500.0, 50.0, 5.0)
    assert action is OK and scale == 1.0


def test_every_check_is_logged_and_reset_clears_the_layers():
    stack = SafetyLayerStack()
    stack.check(True, 2000, 10.0, 50.0, 5.0)
    assert len(stack.log) == 1
    stack.reset()
    assert stack.emg_feedback._no_response_count == 0


def test_the_fatigue_reduction_never_goes_below_three_tenths_when_the_stop_is_set_lower():
    m = FatigueMonitor(severe_fatigue_threshold=0.1)
    for _ in range(m.min_samples):
        m.check(1000, 1000.0)
    r = None
    for _ in range(10):
        r = m.check(1000, 200.0)
    assert r.action is REDUCE and r.scale == pytest.approx(0.3)
