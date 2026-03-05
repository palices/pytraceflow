"""
Simple CPU-bound worker for multiprocessing demos.
"""

from __future__ import annotations

import argparse
import math


def compute(iterations: int) -> float:
    acc = 0.0
    for i in range(iterations):
        x = math.sin(i) * math.cos(i / 3.0)
        acc += math.sqrt(abs(x)) * math.tan(x + 1e-6)
    return acc


def main(iterations: int) -> None:
    result = compute(iterations)
    print(f"worker_result={result:.6f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=200_000)
    args = parser.parse_args()
    main(args.iterations)
