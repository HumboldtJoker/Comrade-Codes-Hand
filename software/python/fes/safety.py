"""
safety.py — Stimulation safety bounds checking and runtime governors.

This is the software half of the 8-layer safety system. It is the last gate
every stimulation command passes through before reaching a stimulator (real or
simulated). Nothing bypasses it.

Two categories of protection:

1. STATIC BOUNDS (mirror of neurostimduino.h SAFETY LIMITS). Current, pulse
   width, frequency, duration, biphasic, channel — validated against the same
   numbers the firmware enforces, so Python and Arduino never disagree about
   what is safe. A command outside hard limits is rejected, not clamped.

2. RUNTIME GOVERNORS (from safety/FORCE_GRADIENT_SAFETY.md). FES bypasses the
   autonomic governors that stop a muscle from tearing itself off the bone, so
   we re-impose them in software:
     - ramp limiting: current can only rise so fast (no sudden jerks),
     - per-channel comfort ceiling from calibration (never exceed the user's
       tolerated maximum),
     - continuous-duration + duty-cycle watchdog (mandatory rest),
     - charge-per-phase ceiling (tissue safety),
     - latched emergency stop requiring manual reset.

The governor CLAMPS where a soft limit protects comfort (ramp, ceiling) and
REJECTS where a hard limit protects safety (absolute current, non-biphasic).
Every intervention is reported so the caller and logs can see it.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

from .channels import StimParams


# ── Static hard limits — keep in lockstep with neurostimduino.h ─────────────
MAX_CURRENT_UA = 5000        # conservative working ceiling
ABSOLUTE_MAX_UA = 15000      # never exceed, ever
MAX_PULSE_WIDTH_US = 500
MIN_FREQUENCY_HZ = 3
MAX_FREQUENCY_HZ = 50        # higher can be painful
MAX_STIM_DURATION_MS = 5000  # 5s max continuous per command

# ── Runtime governor limits — from FORCE_GRADIENT_SAFETY.md ─────────────────
# Force gradient: current may not rise faster than this (per second). Sudden
# forceful contraction is what tears tendons; a ramp keeps movement gradual.
MAX_RAMP_UA_PER_S = 4000
# Charge per phase ceiling (uC). ~ conservative surface-electrode tissue limit.
MAX_CHARGE_PER_PHASE_UC = 2.5
# Duty cycle: after this much continuous ON time, force a rest.
MAX_CONTINUOUS_ON_S = 2.0
MIN_REST_AFTER_ON_S = 5.0


class Severity(Enum):
    OK = "ok"
    CLAMPED = "clamped"      # soft limit applied, command still delivered
    REJECTED = "rejected"    # hard limit hit, command zeroed
    ESTOP = "estop"          # emergency stop latched


@dataclass
class SafetyViolation:
    channel: int
    rule: str
    detail: str
    severity: Severity


@dataclass
class SafetyDecision:
    """Result of checking one channel's command."""
    params: StimParams               # the (possibly clamped/zeroed) command to send
    violations: List[SafetyViolation] = field(default_factory=list)

    @property
    def severity(self) -> Severity:
        if not self.violations:
            return Severity.OK
        order = [Severity.OK, Severity.CLAMPED, Severity.REJECTED, Severity.ESTOP]
        return max((v.severity for v in self.violations), key=order.index)

    @property
    def modified(self) -> bool:
        return self.severity != Severity.OK


@dataclass
class _ChannelState:
    last_current_ua: int = 0
    continuous_on_s: float = 0.0
    resting_s: float = 0.0


class SafetyGuard:
    """Validates and governs stimulation commands over time.

    Stateful: it tracks per-channel current history to enforce ramp and
    duty-cycle limits, so it must see every command in order and be told how
    much wall-clock time elapsed between them (`dt_s`).

    Args:
        comfort_ceiling_ua: per-channel calibrated maximum current the user
            tolerates. Defaults to MAX_CURRENT_UA for any channel not listed.
        max_ramp_ua_per_s / max_charge_per_phase_uc / max_continuous_on_s /
        min_rest_after_on_s: runtime governor tunables (see module constants).
    """

    def __init__(
        self,
        comfort_ceiling_ua: Optional[Dict[int, int]] = None,
        max_ramp_ua_per_s: float = MAX_RAMP_UA_PER_S,
        max_charge_per_phase_uc: float = MAX_CHARGE_PER_PHASE_UC,
        max_continuous_on_s: float = MAX_CONTINUOUS_ON_S,
        min_rest_after_on_s: float = MIN_REST_AFTER_ON_S,
    ):
        self.comfort_ceiling_ua = dict(comfort_ceiling_ua or {})
        self.max_ramp_ua_per_s = max_ramp_ua_per_s
        self.max_charge_per_phase_uc = max_charge_per_phase_uc
        self.max_continuous_on_s = max_continuous_on_s
        self.min_rest_after_on_s = min_rest_after_on_s
        self._state: Dict[int, _ChannelState] = {}
        self._estopped = False
        self._estop_reason = ""

    # ── emergency stop ──────────────────────────────────────────────────
    def emergency_stop(self, reason: str = "manual"):
        """Latch emergency stop. All output is zeroed until reset()."""
        self._estopped = True
        self._estop_reason = reason

    @property
    def estopped(self) -> bool:
        return self._estopped

    def reset(self):
        """Clear the emergency-stop latch. Deliberately manual per protocol."""
        self._estopped = False
        self._estop_reason = ""

    def _st(self, channel: int) -> _ChannelState:
        return self._state.setdefault(channel, _ChannelState())

    # ── the gate ────────────────────────────────────────────────────────
    def check(self, params: StimParams, dt_s: float = 0.02) -> SafetyDecision:
        """Validate and govern a single channel command.

        Args:
            params: requested stimulation for one channel.
            dt_s: seconds elapsed since the previous command on this channel
                (used for ramp and duty-cycle integration). Default 20ms = 50Hz.

        Returns a SafetyDecision whose `params` is the command safe to send —
        the original, a clamped copy, or a zeroed copy.
        """
        p = params.copy()
        violations: List[SafetyViolation] = []
        st = self._st(p.channel)

        def zero(rule: str, detail: str, sev: Severity = Severity.REJECTED):
            violations.append(SafetyViolation(p.channel, rule, detail, sev))
            p.current_ua = 0

        # 0. Emergency stop wins over everything.
        if self._estopped:
            zero("estop", f"E-stop latched: {self._estop_reason}", Severity.ESTOP)
            return self._finish(p, st, violations, dt_s)

        # 1. Biphasic is mandatory — non-negotiable tissue-safety rule.
        if not p.biphasic:
            zero("biphasic", "non-biphasic stimulation is forbidden")

        # 2. Absolute current ceiling. Beyond this we don't just reject the
        #    command, we trip the e-stop: something upstream is badly wrong.
        if abs(p.current_ua) > ABSOLUTE_MAX_UA:
            zero("absolute_max",
                 f"{p.current_ua}uA exceeds absolute max {ABSOLUTE_MAX_UA}uA",
                 Severity.ESTOP)
            self.emergency_stop("current exceeded absolute maximum")
            return self._finish(p, st, violations, dt_s)

        # 3. Negative current is not a valid command here (direction is encoded
        #    by channel, not sign). Reject rather than guess intent.
        if p.current_ua < 0:
            zero("negative_current", f"negative current {p.current_ua}uA")

        # 4. Working current ceiling — clamp toward the conservative max.
        if p.current_ua > MAX_CURRENT_UA:
            violations.append(SafetyViolation(
                p.channel, "max_current",
                f"{p.current_ua}uA clamped to {MAX_CURRENT_UA}uA", Severity.CLAMPED))
            p.current_ua = MAX_CURRENT_UA

        # 5. Per-user comfort ceiling from calibration (may be below the working
        #    max). Never exceed what this user has said is comfortable.
        ceiling = self.comfort_ceiling_ua.get(p.channel, MAX_CURRENT_UA)
        if p.current_ua > ceiling:
            violations.append(SafetyViolation(
                p.channel, "comfort_ceiling",
                f"{p.current_ua}uA clamped to comfort ceiling {ceiling}uA",
                Severity.CLAMPED))
            p.current_ua = ceiling

        # 6. Pulse width, frequency, duration — mirror firmware bounds.
        if p.pulse_width_us > MAX_PULSE_WIDTH_US:
            violations.append(SafetyViolation(
                p.channel, "pulse_width",
                f"{p.pulse_width_us}us clamped to {MAX_PULSE_WIDTH_US}us",
                Severity.CLAMPED))
            p.pulse_width_us = MAX_PULSE_WIDTH_US
        if p.pulse_width_us < 0:
            zero("pulse_width", f"negative pulse width {p.pulse_width_us}us")

        if p.is_active() and not (MIN_FREQUENCY_HZ <= p.frequency_hz <= MAX_FREQUENCY_HZ):
            zero("frequency",
                 f"{p.frequency_hz}Hz outside [{MIN_FREQUENCY_HZ},{MAX_FREQUENCY_HZ}]Hz")

        if p.duration_ms > MAX_STIM_DURATION_MS:
            violations.append(SafetyViolation(
                p.channel, "duration",
                f"{p.duration_ms}ms clamped to {MAX_STIM_DURATION_MS}ms",
                Severity.CLAMPED))
            p.duration_ms = MAX_STIM_DURATION_MS

        # 7. Charge per phase ceiling (tissue safety). Clamp pulse width down to
        #    keep charge = I*t within limit rather than dropping current.
        if p.charge_per_phase_uc() > self.max_charge_per_phase_uc and p.current_ua > 0:
            safe_pw = int(self.max_charge_per_phase_uc * 1e6 / p.current_ua)
            violations.append(SafetyViolation(
                p.channel, "charge_density",
                f"{p.charge_per_phase_uc():.2f}uC/phase clamped "
                f"(pulse width {p.pulse_width_us}->{safe_pw}us)", Severity.CLAMPED))
            p.pulse_width_us = max(0, safe_pw)

        # 8. Ramp limit — force gradient. Current may only rise so fast.
        max_step = int(self.max_ramp_ua_per_s * dt_s)
        rise = p.current_ua - st.last_current_ua
        if rise > max_step:
            capped = st.last_current_ua + max_step
            violations.append(SafetyViolation(
                p.channel, "ramp_limit",
                f"rise {rise}uA/{dt_s*1000:.0f}ms exceeds gradient; "
                f"{p.current_ua}->{capped}uA", Severity.CLAMPED))
            p.current_ua = capped

        # 9. Duty cycle — enforce mandatory rest after sustained stimulation.
        if st.continuous_on_s >= self.max_continuous_on_s and p.is_active():
            zero("duty_cycle",
                 f"continuous ON {st.continuous_on_s:.1f}s reached limit; "
                 f"resting {self.min_rest_after_on_s:.0f}s", Severity.REJECTED)

        return self._finish(p, st, violations, dt_s)

    def _finish(self, p: StimParams, st: _ChannelState,
                violations: List[SafetyViolation], dt_s: float) -> SafetyDecision:
        # Integrate duty-cycle state from what we actually decided to send.
        if p.is_active():
            st.continuous_on_s += dt_s
            st.resting_s = 0.0
        else:
            st.resting_s += dt_s
            if st.resting_s >= self.min_rest_after_on_s:
                st.continuous_on_s = 0.0  # rest satisfied, duty budget restored
        st.last_current_ua = p.current_ua
        return SafetyDecision(params=p, violations=violations)


def check_bank(guard: SafetyGuard, commands: List[StimParams],
               dt_s: float = 0.02) -> List[SafetyDecision]:
    """Convenience: run every channel command in a frame through the guard."""
    return [guard.check(c, dt_s) for c in commands]


if __name__ == "__main__":
    guard = SafetyGuard(comfort_ceiling_ua={0: 3500})
    print("Safety guard self-test\n" + "=" * 50)

    trials = [
        ("normal", StimParams(0, current_ua=2000)),
        ("over working max", StimParams(0, current_ua=9000)),
        ("over comfort ceiling", StimParams(0, current_ua=4000)),
        ("non-biphasic", StimParams(1, current_ua=2000, biphasic=False)),
        ("absolute max -> estop", StimParams(1, current_ua=20000)),
        ("post-estop blocked", StimParams(0, current_ua=1000)),
    ]
    for label, cmd in trials:
        d = guard.check(cmd)
        print(f"\n{label}: sent {d.params.current_ua}uA  [{d.severity.value}]")
        for v in d.violations:
            print(f"    - {v.rule}: {v.detail}")

    print("\nreset() clears the latch:")
    guard.reset()
    d = guard.check(StimParams(0, current_ua=1000))
    print(f"  after reset: sent {d.params.current_ua}uA [{d.severity.value}]")
