"""
Auto-trace child Python processes with PyTraceFlow when enabled via environment variables.

Usage:
  # Enable autotrace for all Python processes in this env
  set PYTRACEFLOW_AUTOTRACE=1
  set PYTRACEFLOW_OUT_DIR=bench-output/autotrace
  set PYTHONPATH=C:\path\to\repo;%PYTHONPATH%
  # optional knobs:
  set PYTRACEFLOW_FLUSH_INTERVAL=5
  set PYTRACEFLOW_FLUSH_CALL_THRESHOLD=500
  set PYTRACEFLOW_SKIP_INPUTS=1
  set PYTRACEFLOW_SKIP_OUTPUTS=1
  set PYTRACEFLOW_VERBOSE=1
  set PYTRACEFLOW_WITH_MEMORY=0

Notes:
 - Each process writes its own JSON: pft_<pid>.json under OUT_DIR.
 - The main process is also traced unless PYTRACEFLOW_SKIP_MAIN=1.
 - To avoid tracing pytraceflow.py itself, it is skipped automatically.
"""

from __future__ import annotations

import atexit
import os
from pathlib import Path
import sys


def _env_flag(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val not in ("0", "false", "False", "")


def _maybe_start():
    if os.environ.get("PYTRACEFLOW_AUTOTRACE") != "1":
        return
    # Avoid tracing pytraceflow.py itself
    argv0 = Path(sys.argv[0]).name if sys.argv else ""
    if argv0 == "pytraceflow.py":
        return

    repo_root = Path(__file__).resolve().parent
    out_dir = Path(os.environ.get("PYTRACEFLOW_OUT_DIR", repo_root / "bench-output" / "autotrace"))
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"pft_{os.getpid()}.json"

    flush_interval = float(os.environ.get("PYTRACEFLOW_FLUSH_INTERVAL", "5"))
    flush_call_threshold = int(os.environ.get("PYTRACEFLOW_FLUSH_CALL_THRESHOLD", "500"))
    skip_inputs = _env_flag("PYTRACEFLOW_SKIP_INPUTS", False)
    skip_outputs = _env_flag("PYTRACEFLOW_SKIP_OUTPUTS", False)
    verbose = _env_flag("PYTRACEFLOW_VERBOSE", False)
    with_memory = _env_flag("PYTRACEFLOW_WITH_MEMORY", False)
    no_tracemalloc = _env_flag("PYTRACEFLOW_NO_TRACEMALLOC", False)

    try:
        from pytraceflow import PyFlowTraceProfiler  # type: ignore
    except Exception:
        return

    profiler = PyFlowTraceProfiler(
        script_path=sys.argv[0] or "__process__",
        output_path=str(output_path),
        script_args=[],
        flush_interval=flush_interval,
        flush_call_threshold=flush_call_threshold,
        flush_every_call=False,
        log_flushes=verbose,
        capture_memory=with_memory and not _env_flag("PYTRACEFLOW_NO_MEMORY", False),
        capture_inputs=not skip_inputs,
        capture_outputs=not skip_outputs,
        enable_tracemalloc=with_memory and not no_tracemalloc,
        verbose=verbose,
    )
    profiler.start_live()
    atexit.register(profiler.stop_live)


_maybe_start()
