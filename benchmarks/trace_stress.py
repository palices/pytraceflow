"""
Synthetic workload to stress call tracing.

Default parameters generate a moderate amount of function calls while keeping runtime short.
Tune via CLI flags to increase/decrease pressure.
"""

from __future__ import annotations

import argparse
import math
import random
import time


def compute_heavy(n: int) -> float:
    """CPU-heavy math that is stable and deterministic for a given seed."""
    acc = 0.0
    for i in range(n):
        x = math.sin(i) * math.cos(i / 3.0)
        acc += math.sqrt(abs(x)) * math.tan(x + 1e-6)
    return acc


def fanout(depth: int, breadth: int, work: int) -> float:
    """Recursive fanout to create many small calls."""
    if depth <= 0:
        return compute_heavy(work)
    total = 0.0
    for _ in range(breadth):
        total += fanout(depth - 1, breadth, work)
    return total


def main(iterations: int, depth: int, breadth: int, work: int, sleep_ms: int) -> float:
    random.seed(42)
    total = 0.0
    for _ in range(iterations):
        total += fanout(depth, breadth, work)
        if sleep_ms:
            time.sleep(sleep_ms / 1000.0)
    return total


def parse_args():
    parser = argparse.ArgumentParser(description="Synthetic workload for PyTraceFlow benchmarks")
    parser.add_argument("--iterations", type=int, default=40, help="Loop count for top-level calls")
    parser.add_argument("--depth", type=int, default=3, help="Recursion depth for fanout")
    parser.add_argument("--breadth", type=int, default=3, help="Branching factor per level")
    parser.add_argument("--work", type=int, default=20, help="Inner loop work per leaf")
    parser.add_argument("--sleep-ms", type=int, default=0, help="Optional sleep per iteration to simulate I/O")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = main(args.iterations, args.depth, args.breadth, args.work, args.sleep_ms)
    print(f"result={result:.6f}")
