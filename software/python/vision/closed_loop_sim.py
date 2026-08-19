"""
closed_loop_sim.py — Full closed-loop FES control simulation.

Ties together all components without hardware:
  EMG intent (simulated) → gesture classifier → target pose
  → hand simulator → error computer → FES mapper
  → apply FES to simulator → repeat

This is the proof that the control architecture works end-to-end.
When real hardware arrives, each simulated component gets swapped
for its physical counterpart — same interfaces, same loop.

Usage:
    python -m software.python.vision.closed_loop_sim

    # Or with custom scenarios:
    sim = ClosedLoopSim()
    sim.run_scenario("reach_and_grasp")
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .hand_simulator import HandSimulator
from .hand_tracker import Finger, FingerAngles
from .error_computer import ErrorComputer, GESTURE_TARGETS, CorrectionSignal
from ..fes.mapping import FESMapper
from ..fes.channels import StimParams


@dataclass
class LoopMetrics:
    """Metrics from one control cycle."""
    cycle: int
    target_gesture: str
    total_error_deg: float
    max_error_deg: float
    fes_total_current_ua: int
    per_finger_error: dict
    converged: bool
    timestamp: float


@dataclass
class ScenarioResult:
    """Results from a complete scenario run."""
    name: str
    cycles: int
    converged: bool
    convergence_cycle: int
    final_error_deg: float
    metrics: list[LoopMetrics]
    duration_s: float


CONVERGENCE_THRESHOLD_DEG = 5.0


class ClosedLoopSim:
    """Full closed-loop FES control simulation."""

    def __init__(
        self,
        loop_rate_hz: float = 50,
        noise: float = 0.002,
        fes_gain: float = 1.0,
    ):
        self.hand = HandSimulator(noise=noise)
        self.error_computer = ErrorComputer(smoothing=0.5, gain=0.7, deadzone_deg=2.0)
        self.fes_mapper = FESMapper(gain=fes_gain)
        self.loop_rate_hz = loop_rate_hz
        self.dt = 1.0 / loop_rate_hz

    def run_cycle(self, target_gesture: str, cycle: int) -> LoopMetrics:
        """Execute one control cycle."""
        pose = self.hand.get_pose()

        correction = self.error_computer.compute(target_gesture, pose)

        commands = self.fes_mapper.from_correction(correction)

        self.hand.apply_fes_response(commands, self.dt)
        # NOTE: Passive tissue return (spring-back to rest) is modeled in
        # hand_simulator.step(fes_active=False) but requires per-finger FES
        # tracking to avoid fighting the controller. Deferred to hardware
        # integration — real muscle elasticity data will inform the model
        # better than simulation tweaking.

        total_current = sum(c.current_ua for c in commands)
        per_finger = {
            f.name: abs(correction[f].error_deg)
            for f in Finger
        }

        return LoopMetrics(
            cycle=cycle,
            target_gesture=target_gesture,
            total_error_deg=correction.total_error,
            max_error_deg=correction.max_error,
            fes_total_current_ua=total_current,
            per_finger_error=per_finger,
            converged=correction.max_error < CONVERGENCE_THRESHOLD_DEG,
            timestamp=time.perf_counter(),
        )

    def run_gesture(
        self,
        gesture: str,
        max_cycles: int = 200,
        verbose: bool = True,
    ) -> ScenarioResult:
        """Drive the hand to a target gesture and measure convergence."""
        t0 = time.perf_counter()
        metrics = []
        convergence_cycle = -1

        if verbose:
            print(f"\n  Target: {gesture}")
            print(f"  Start:  {self.hand.describe()}")

        for i in range(max_cycles):
            m = self.run_cycle(gesture, i)
            metrics.append(m)

            if m.converged and convergence_cycle < 0:
                convergence_cycle = i

            if verbose and i % 20 == 0:
                status = "CONVERGED" if m.converged else f"error={m.max_error_deg:.1f}°"
                print(f"    Cycle {i:3d}: {status}  "
                      f"FES={m.fes_total_current_ua:5d}uA  "
                      f"{self.hand.describe()}")

            if m.converged and i > convergence_cycle + 10:
                break

        final = metrics[-1]
        elapsed = time.perf_counter() - t0

        if verbose:
            status = "CONVERGED" if final.converged else "DID NOT CONVERGE"
            print(f"    Result: {status} "
                  f"(cycle {convergence_cycle if convergence_cycle >= 0 else 'N/A'}, "
                  f"final error {final.max_error_deg:.1f}°, "
                  f"{elapsed:.3f}s)")

        return ScenarioResult(
            name=gesture,
            cycles=len(metrics),
            converged=final.converged,
            convergence_cycle=convergence_cycle,
            final_error_deg=final.max_error_deg,
            metrics=metrics,
            duration_s=elapsed,
        )

    def run_scenario(self, name: str, verbose: bool = True) -> list[ScenarioResult]:
        """Run a predefined scenario (sequence of gestures)."""
        scenarios = {
            "basic_gestures": ["RELAX", "FIST", "OPEN", "POINT", "RELAX"],
            "reach_and_grasp": ["OPEN", "FIST", "RELAX"],
            "point_and_wave": ["RELAX", "POINT", "WAVE", "RELAX"],
            "fist_pump": ["RELAX", "FIST", "OPEN", "FIST", "OPEN", "FIST", "RELAX"],
            "solidarity": ["RELAX", "FIST"],
        }

        sequence = scenarios.get(name)
        if not sequence:
            raise ValueError(f"Unknown scenario: {name}. "
                             f"Available: {list(scenarios.keys())}")

        if verbose:
            print(f"{'=' * 60}")
            print(f"SCENARIO: {name}")
            print(f"Sequence: {' → '.join(sequence)}")
            print(f"{'=' * 60}")

        self.hand.reset("RELAX")
        results = []
        for gesture in sequence:
            result = self.run_gesture(gesture, verbose=verbose)
            results.append(result)

        if verbose:
            print(f"\n{'=' * 60}")
            print(f"SCENARIO COMPLETE: {name}")
            all_converged = all(r.converged for r in results)
            total_cycles = sum(r.cycles for r in results)
            total_time = sum(r.duration_s for r in results)
            print(f"  Gestures: {len(results)}, "
                  f"all converged: {all_converged}, "
                  f"total cycles: {total_cycles}, "
                  f"time: {total_time:.3f}s")
            for r in results:
                conv = f"cycle {r.convergence_cycle}" if r.converged else "FAILED"
                print(f"    {r.name:10s}: {conv}, "
                      f"final error {r.final_error_deg:.1f}°")
            print(f"{'=' * 60}")

        return results

    def save_results(self, results: list[ScenarioResult], path: str):
        """Save scenario results for analysis."""
        data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "loop_rate_hz": self.loop_rate_hz,
            "scenarios": [
                {
                    "name": r.name,
                    "cycles": r.cycles,
                    "converged": r.converged,
                    "convergence_cycle": r.convergence_cycle,
                    "final_error_deg": r.final_error_deg,
                    "duration_s": r.duration_s,
                }
                for r in results
            ],
        }
        Path(path).write_text(json.dumps(data, indent=2))


def main():
    print("=" * 60)
    print("CLOSED-LOOP FES CONTROL SIMULATION")
    print("Camera → Error → FES → Hand → Camera (repeat)")
    print("=" * 60)

    sim = ClosedLoopSim(noise=0.001)

    all_results = []
    for scenario in ["basic_gestures", "reach_and_grasp", "solidarity"]:
        results = sim.run_scenario(scenario)
        all_results.extend(results)
        sim.hand.reset("RELAX")

    total = len(all_results)
    converged = sum(1 for r in all_results if r.converged)

    print(f"\n{'=' * 60}")
    print(f"ALL SCENARIOS COMPLETE")
    print(f"  {converged}/{total} gestures converged")
    print(f"  Mean convergence: "
          f"{np.mean([r.convergence_cycle for r in all_results if r.converged]):.0f} cycles")

    if converged == total:
        print(f"\n  The control loop works. Every gesture converges.")
        print(f"  Next step: real hardware, same interfaces.")
    else:
        failed = [r.name for r in all_results if not r.converged]
        print(f"\n  Failed gestures: {failed}")
        print(f"  Needs tuning before hardware.")

    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
