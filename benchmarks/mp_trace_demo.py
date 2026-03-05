"""
Multiprocessing demo showing how to trace child processes with PyTraceFlow.

Modes:
- Default: run workers directly via multiprocessing.Pool (no child traces).
- --trace-children: launch each worker under pytraceflow.py, writing one JSON per child.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from multiprocessing import Pool

ROOT = Path(__file__).resolve().parent.parent
PYTRACEFLOW = ROOT / "pytraceflow.py"
WORKER = ROOT / "benchmarks" / "mp_worker.py"

# Ensure child processes can import mp_worker when using spawn (Windows/macOS)
sys.path.insert(0, str(ROOT / "benchmarks"))


def run_worker(iterations: int) -> float:
    import mp_worker  # type: ignore

    return mp_worker.compute(iterations)


def run_pool(jobs: int, iterations: int) -> None:
    with Pool(processes=jobs) as pool:
        results = pool.map(run_worker, [iterations] * jobs)
    print(f"[demo] pool finished, results={results}")


def run_traced_children(jobs: int, iterations: int, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for idx in range(jobs):
        out = output_dir / f"worker_{idx}.json"
        cmd = [
            sys.executable,
            str(PYTRACEFLOW),
            "-s",
            str(WORKER),
            "-o",
            str(out),
            "--flush-interval",
            "5",
            "--flush-call-threshold",
            "500",
            "--skip-inputs",
            "--skip-outputs",
            "--verbose",
            "--",
            "--iterations",
            str(iterations),
        ]
        print(f"[demo] launching traced worker {idx}: {' '.join(cmd)}")
        completed = subprocess.run(cmd, capture_output=True, text=True)
        print(f"[demo] worker {idx} rc={completed.returncode}")
        if completed.stdout:
            print(f"[demo] worker {idx} stdout:\n{completed.stdout}")
        if completed.stderr:
            print(f"[demo] worker {idx} stderr:\n{completed.stderr}")
    print(f"[demo] traced workers done. JSONs in {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Multiprocessing + PyTraceFlow demo")
    parser.add_argument("--jobs", type=int, default=4, help="Number of workers")
    parser.add_argument("--iterations", type=int, default=200_000, help="Iterations per worker")
    parser.add_argument(
        "--trace-children",
        action="store_true",
        help="Run each worker under pytraceflow, one JSON per child",
    )
    parser.add_argument(
        "--output-dir",
        default="bench-output/mp",
        help="Where to write worker JSONs when tracing children",
    )
    args = parser.parse_args()

    if args.trace_children:
        run_traced_children(args.jobs, args.iterations, Path(args.output_dir))
    else:
        run_pool(args.jobs, args.iterations)


if __name__ == "__main__":
    main()
