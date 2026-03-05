import argparse
import inspect
import json
import threading
import runpy
import sys
import time
import sysconfig
import tracemalloc
from pathlib import Path


class PyFlowTraceProfiler:
    def __init__(
        self,
        script_path,
        output_path,
        script_args=None,
        flush_interval=5.0,
        flush_every_call=False,
        log_flushes=False,
        flush_call_threshold=0,
        capture_memory=False,
        capture_inputs=True,
        capture_outputs=True,
        enable_tracemalloc=False,
        verbose=False,
    ):
        self.script_path = Path(script_path).resolve()
        self.output_path = Path(output_path)
        # argumentos que se pasaran al script perfilado (por ejemplo: -- foo 1 bar)
        self.script_args = list(script_args or [])
        if self.script_args and self.script_args[0] == "--":
            self.script_args = self.script_args[1:]
        self.records = []
        self._inflight = {}
        self._stack = []
        self._instance_roots = {}
        self._next_id = 1
        self._root_entry = None
        self._root_dir = self.script_path.parent
        # rutas a ignorar: stdlib y site-packages
        self._ignore_prefixes = []
        for key in ("stdlib", "platstdlib", "purelib", "platlib"):
            p = sysconfig.get_paths().get(key)
            if p:
                self._ignore_prefixes.append(Path(p).resolve())
        for p in (sys.prefix, sys.base_prefix, sys.exec_prefix):
            try:
                self._ignore_prefixes.append(Path(p).resolve())
            except Exception:
                pass
        self._tracemalloc_enabled = False
        self._write_lock = threading.Lock()
        self._flush_interval = 0.2
        self._last_flush = -1e9  # fuerza un primer flush inmediato
        self._stop_flush = threading.Event()
        self._flush_thread = None
        self._last_seen_callable = None
        self._flush_interval = float(flush_interval)
        self._flush_call_threshold = int(flush_call_threshold)
        self._pending_new_records = 0
        self._flush_every_call = flush_every_call
        self._log_flushes = log_flushes
        self._dirty = False
        self._run_started = None
        self._capture_memory = capture_memory
        self._capture_inputs_enabled = capture_inputs
        self._capture_outputs_enabled = capture_outputs
        self._enable_tracemalloc = enable_tracemalloc
        self._verbose = verbose
        self._heartbeat_thread = None
        self._flush_count = 0
        self._last_snapshot_bytes = 0
        self._live_mode_started = False
        self._live_mode_stopped = False

    def _memory_snapshot(self):
        if not self._capture_memory:
            return {}
        snapshot = {}
        try:
            import psutil  # type: ignore

            proc = psutil.Process()
            with proc.oneshot():
                mem = proc.memory_info()
                snapshot["rss_bytes"] = mem.rss
                snapshot["vms_bytes"] = mem.vms
        except Exception:
            # psutil no disponible o falló; continuamos con tracemalloc si está activo
            pass
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            snapshot["py_tracemalloc_current"] = current
            snapshot["py_tracemalloc_peak"] = peak
        return snapshot

    def _serialize(self, value, depth=0, max_depth=3):
        if depth >= max_depth:
            return repr(value)
        if isinstance(value, dict):
            return {
                str(key): self._serialize(val, depth + 1, max_depth)
                for key, val in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [self._serialize(val, depth + 1, max_depth) for val in value]
        if hasattr(value, "__dict__"):
            return self._serialize(value.__dict__, depth + 1, max_depth)
        try:
            json.dumps(value)
            return value
        except TypeError:
            return repr(value)

    def _capture_inputs(self, frame):
        # Fast path: when inputs capture is disabled, avoid inspect/serialization entirely
        if not self._capture_inputs_enabled:
            return {}
        try:
            args = inspect.getargvalues(frame)
        except Exception:
            return {}

        values = {name: frame.f_locals.get(name) for name in args.args}
        if args.varargs:
            values[args.varargs] = frame.f_locals.get(args.varargs)
        if args.keywords:
            values[args.keywords] = frame.f_locals.get(args.keywords)
        values.pop("self", None)
        values.pop("cls", None)
        return {key: self._serialize(val) for key, val in values.items()}

    def _get_class_name(self, frame):
        if "self" in frame.f_locals:
            return type(frame.f_locals["self"]).__name__
        if "cls" in frame.f_locals and inspect.isclass(frame.f_locals["cls"]):
            return frame.f_locals["cls"].__name__
        return None

    def _should_trace(self, frame):
        filename_str = frame.f_code.co_filename
        module_name = frame.f_globals.get("__name__", "")
        # descartar frames internos/builtins/frozen
        if filename_str.startswith("<"):
            return False
        if module_name.startswith(("importlib", "encodings", "zipimport")):
            return False
        try:
            filename = Path(filename_str).resolve()
        except Exception:
            return False
        if filename == Path(__file__).resolve():
            return False
        # ignorar stdlib / site-packages
        for prefix in self._ignore_prefixes:
            try:
                filename.relative_to(prefix)
                return False
            except ValueError:
                continue
        # trazar cualquier archivo dentro del directorio raíz del script
        try:
            filename.relative_to(self._root_dir)
            return True
        except ValueError:
            return False

    def _is_class_constructor_call(self, frame):
        if frame.f_globals.get("__name__") != "__main__":
            return False
        name = frame.f_code.co_name
        obj = frame.f_globals.get(name)
        return inspect.isclass(obj)

    def _is_class_definition(self, frame):
        if frame.f_globals.get("__name__") != "__main__":
            return False
        if "__module__" not in frame.f_locals or "__qualname__" not in frame.f_locals:
            return False
        return frame.f_code.co_name == frame.f_locals.get("__qualname__")

    def _profile(self, frame, event, arg):
        if not self._should_trace(frame):
            return

        if frame.f_code.co_name == "<module>":
            return
        if frame.f_code.co_name.startswith("<"):
            # omite frames sintéticos (listcomp/lambda/genexpr) pero deja que sus hijos se enganchen al padre real
            return
        if self._is_class_definition(frame):
            return
        if self._is_class_constructor_call(frame):
            return

        frame_id = id(frame)
        if event == "call":
            class_name = self._get_class_name(frame)
            instance_id = None
            if "self" in frame.f_locals:
                instance_id = id(frame.f_locals["self"])
            if frame.f_code.co_name == "__init__" and instance_id is not None:
                if instance_id not in self._instance_roots:
                    instance_entry = {
                        "id": self._next_id,
                        "callable": "__instance__",
                        "module": frame.f_globals.get("__name__", ""),
                        "called": class_name if class_name else frame.f_code.co_name,
                        "instance_id": instance_id,
                        "inputs": self._capture_inputs(frame),
                        "output": None,
                        "error": None,
                        "duration_ms": None,
                        "calls": [],
                    }
                    self._next_id += 1
                    root_calls = (
                        self._root_entry["calls"]
                        if self._root_entry is not None
                        else self.records
                    )
                    root_calls.append(instance_entry)
                    self._instance_roots[instance_id] = instance_entry
                    self._pending_new_records += 1

            entry = {
                "id": self._next_id,
                "callable": frame.f_code.co_name,
                "module": frame.f_globals.get("__name__", ""),
                "called": class_name if class_name else frame.f_code.co_name,
                "caller": None,
                "instance_id": instance_id,
                "inputs": self._capture_inputs(frame),
                "calls": [],
            }
            self._next_id += 1
            self._inflight[frame_id] = (entry, time.time())
            self._last_seen_callable = entry["callable"]
            if self._stack:
                parent = self._stack[-1]
                entry["caller"] = f"{parent.get('called')}::{parent.get('callable')}"
            if instance_id is not None and instance_id in self._instance_roots:
                parent = self._stack[-1] if self._stack and self._stack[-1].get(
                    "instance_id"
                ) == instance_id else self._instance_roots[instance_id]
                parent["calls"].append(entry)
            elif self._stack:
                self._stack[-1]["calls"].append(entry)
            else:
                self.records.append(entry)
            self._stack.append(entry)
            entry["memory_before"] = self._memory_snapshot()
            self._dirty = True
            self._pending_new_records += 1
            self._maybe_flush(
                force=self._flush_every_call, current=entry["callable"], log=False
            )
            return

        if frame_id not in self._inflight:
            return

        entry, started = self._inflight[frame_id]
        if event == "return":
            entry["inputs_after"] = self._capture_inputs(frame)
            if entry.get("error") is None:
                if self._capture_outputs_enabled:
                    entry["output"] = self._serialize(arg)
                else:
                    entry["output"] = None
                entry["error"] = None
            entry["duration_ms"] = round((time.time() - started) * 1000, 3)
            entry["memory_after"] = self._memory_snapshot()
            self._inflight.pop(frame_id, None)
            if self._stack and self._stack[-1] is entry:
                self._stack.pop()
            self._dirty = True
            self._maybe_flush(
                force=self._flush_every_call, current=entry["callable"], log=False
            )
        elif event == "exception":
            exc_type, exc_value, _ = arg
            entry["inputs_after"] = self._capture_inputs(frame)
            entry["output"] = None
            entry["error"] = repr(exc_value if exc_value else exc_type)
            entry["duration_ms"] = round((time.time() - started) * 1000, 3)
            entry["memory_after"] = self._memory_snapshot()
            self._inflight.pop(frame_id, None)
            if self._stack and self._stack[-1] is entry:
                self._stack.pop()
            self._dirty = True
            self._maybe_flush(
                force=self._flush_every_call, current=entry["callable"], log=False
            )

    def run(self):
        script_name = self.script_path.name
        self._begin_profile(script_name)
        old_argv = sys.argv
        # emula la ejecucion normal del script, permitiendo argumentos personalizados
        sys.argv = [str(self.script_path)] + self.script_args
        exc_raised: BaseException | None = None
        try:
            runpy.run_path(str(self.script_path), run_name="__main__")
        except BaseException as exc:  # capturamos para reflejar error en la raiz
            exc_raised = exc
            self._root_entry["error"] = repr(exc)
            self._root_entry["output"] = None
            # marca como error cualquier frame inflight (p.ej. validate_config)
            now = time.time()
            for entry, started in list(self._inflight.values()):
                entry["output"] = None
                entry["error"] = repr(exc)
                entry["duration_ms"] = round((now - started) * 1000, 3)
                entry["memory_after"] = self._memory_snapshot()
            self._propagate_error(self._root_entry, repr(exc))
        finally:
            sys.argv = old_argv
            self._end_profile(self.script_path.name, exc_raised)
            print()

    def _prune_calls(self, node):
        pruned = []
        for child in node.get("calls", []):
            self._prune_calls(child)
            # descarta nodos sintéticos de python y reancla sus hijos al padre
            if str(child.get("callable", "")).startswith("<"):
                pruned.extend(child.get("calls", []))
                continue
            if self._is_class_definition_node(child):
                pruned.extend(child.get("calls", []))
                continue
            if child.get("callable") == "__instance__" and not child.get("calls"):
                continue
            if (
                child.get("callable") == "__init__"
                and not child.get("calls")
                and child.get("output") is None
                and child.get("error") is None
            ):
                continue
            pruned.append(child)
        node["calls"] = pruned

    def _propagate_error(self, node, exc_repr):
        if node.get("output") is None and node.get("error") is None:
            node["error"] = exc_repr
        for child in node.get("calls", []):
            self._propagate_error(child, exc_repr)

    def start_live(self):
        """Start profiling the current process (for multiprocessing autotrace)."""
        if self._live_mode_started:
            return
        script_name = Path(sys.argv[0]).name or "__process__"
        self._live_mode_started = True
        self._begin_profile(script_name)

    def stop_live(self):
        """Stop profiling the current process (safe to call multiple times)."""
        if not self._live_mode_started or self._live_mode_stopped:
            return
        self._live_mode_stopped = True
        try:
            self._end_profile(Path(sys.argv[0]).name or "__process__", None)
        except Exception:
            # Avoid raising during atexit
            pass

    def _write_output(self, payload):
        with open(self.output_path, "w", encoding="utf-8", newline="") as f:
            f.write(payload)
            f.flush()

    def _maybe_flush(self, force=False, current=None, log=None):
        if log is None:
            log = self._log_flushes
        now = time.time()
        time_ready = self._flush_interval > 0 and now - self._last_flush >= self._flush_interval
        threshold_ready = (
            self._flush_call_threshold > 0
            and self._pending_new_records >= self._flush_call_threshold
        )
        if not force:
            if not self._dirty:
                return
            if not (time_ready or threshold_ready):
                return
        with self._write_lock:
            if not force:
                time_ready = (
                    self._flush_interval > 0 and now - self._last_flush >= self._flush_interval
                )
                threshold_ready = (
                    self._flush_call_threshold > 0
                    and self._pending_new_records >= self._flush_call_threshold
                )
                if not self._dirty or not (time_ready or threshold_ready):
                    return
            snapshot = json.dumps(
                self.records, ensure_ascii=True, separators=(",", ":")
            )
            snapshot_bytes = len(snapshot.encode("utf-8"))
            current_call = (
                current
                or (f"{self._stack[-1].get('module','')}::{self._stack[-1].get('callable','')}" if self._stack else None)
                or self._last_seen_callable
                or self._root_entry.get("callable", "")
            )
            self._last_flush = now
            self._dirty = False
            self._pending_new_records = 0
            self._flush_count += 1
            self._last_snapshot_bytes = snapshot_bytes
        if log:
            sys.stderr.write(
                f"[FlowTrace] Writing snapshot (callable={current_call}) to {self.output_path} "
                f"(flush#{self._flush_count} size={self._last_snapshot_bytes}B records={len(self.records)})\n"
            )
            sys.stderr.flush()
        self._write_output(snapshot)

    def _flush_loop(self):
        while not self._stop_flush.is_set():
            try:
                self._maybe_flush(log=False)
            except Exception:
                pass
            self._stop_flush.wait(self._flush_interval)

    def _heartbeat_loop(self):
        interval = self._flush_interval if self._flush_interval > 0 else 5.0
        interval = max(interval, 5.0)
        while not self._stop_flush.is_set():
            try:
                msg = (
                    f"[FlowTrace] heartbeat calls={len(self.records)} "
                    f"inflight={len(self._inflight)} "
                    f"pending_flush={self._pending_new_records} "
                    f"flushes={self._flush_count} "
                    f"last_snapshot_bytes={self._last_snapshot_bytes} "
                    f"since_last_flush={time.time() - self._last_flush:.1f}s"
                )
                sys.stderr.write(msg + "\n")
                sys.stderr.flush()
            except Exception:
                pass
            self._stop_flush.wait(interval)

    def _begin_profile(self, script_name: str):
        self._root_entry = {
            "id": 0,
            "callable": script_name,
            "module": "__main__",
            "called": script_name,
            "inputs": {},
            "output": None,
            "error": None,
            "duration_ms": None,
            "calls": [],
        }
        self.records = [self._root_entry]
        self._stack = [self._root_entry]
        self._dirty = True
        if self._enable_tracemalloc and self._capture_memory:
            tracemalloc.start(10)
            self._tracemalloc_enabled = True
        else:
            self._tracemalloc_enabled = False
        if self._verbose:
            sys.stderr.write("[FlowTrace] verbose mode enabled\n")
            sys.stderr.flush()
        self._run_started = time.perf_counter()
        self._root_entry["memory_before"] = self._memory_snapshot()
        self._maybe_flush(
            force=True,
            current=self._root_entry.get("callable"),
            log=self._log_flushes,
        )  # snapshot inicial
        sys.setprofile(self._profile)
        self._stop_flush.clear()
        if self._flush_interval > 0:
            self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
            self._flush_thread.start()
        if self._verbose:
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop, daemon=True
            )
            self._heartbeat_thread.start()

    def _end_profile(self, script_name: str, exc_raised: BaseException | None):
        sys.setprofile(None)
        total_ms = (
            round((time.perf_counter() - self._run_started) * 1000, 3)
            if self._run_started is not None
            else None
        )
        if self._root_entry is not None:
            self._root_entry["duration_ms"] = total_ms
            self._root_entry["memory_after"] = self._memory_snapshot()
        if self._tracemalloc_enabled:
            tracemalloc.stop()
        if self._root_entry is not None:
            self._prune_calls(self._root_entry)
        self._dirty = True
        self._maybe_flush(force=True, log=self._log_flushes)
        self._stop_flush.set()
        if self._flush_thread:
            self._flush_thread.join(timeout=1)
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=1)
        if total_ms is not None:
            sys.stderr.write(
                f"[FlowTrace] Profiling finished in {total_ms/1000:.3f}s (script={script_name})\n"
            )
            sys.stderr.flush()
        if exc_raised:
            raise exc_raised

    def _is_class_definition_node(self, node):
        return (
            node.get("module") == "__main__"
            and node.get("callable") == node.get("called")
            and not node.get("inputs")
            and node.get("output") is None
            and node.get("error") is None
            and node.get("callable") not in ("__main__", "__instance__")
        )


def _build_parser():
    parser = argparse.ArgumentParser(description="Post-mortem JSON trace profiler")
    parser.add_argument(
        "-s",
        "--script",
        required=True,
        help="Path to the Python script to profile",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="pft.json",
        help="JSON output path (default: pft.json)",
    )
    parser.add_argument(
        "--flush-interval",
        type=float,
        default=5.0,
        help="Seconds between background flushes; <=0 disables periodic flush",
    )
    parser.add_argument(
        "--flush-call-threshold",
        type=int,
        default=500,
        help="Flush after N new calls regardless of time; 0 disables this threshold",
    )
    parser.add_argument(
        "--flush-every-call",
        action="store_true",
        help="Force flush on every event (slower; legacy)",
    )
    parser.add_argument(
        "--log-flushes",
        action="store_true",
        help="Log each flush to stderr",
    )
    parser.add_argument(
        "--with-memory",
        action="store_true",
        help="Capture memory snapshots (psutil + tracemalloc); disabled by default",
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Disable memory snapshots entirely (psutil + tracemalloc)",
    )
    parser.add_argument(
        "--no-tracemalloc",
        action="store_true",
        help="Disable tracemalloc even when memory snapshots are enabled",
    )
    parser.add_argument(
        "--skip-inputs",
        action="store_true",
        help="Do not record call inputs/outputs (reduces serialization)",
    )
    parser.add_argument(
        "--skip-outputs",
        action="store_true",
        help="Do not record call outputs/return values (reduces serialization)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging: flush logs to stderr and periodic heartbeats",
    )
    return parser


def _parse_args(argv=None):
    parser = _build_parser()
    args, unknown = parser.parse_known_args(argv)
    # Any unknown args are forwarded to the profiled script
    args.script_args = list(unknown)
    if args.script_args and args.script_args[0] == "--":
        args.script_args = args.script_args[1:]
    return parser, args


def main():
    # If no arguments are provided, show help and exit cleanly
    if len(sys.argv) == 1:
        _build_parser().print_help()
        sys.exit(0)
    _, args = _parse_args()
    capture_memory = args.with_memory and not args.no_memory
    enable_tracemalloc = capture_memory and not args.no_tracemalloc
    if args.verbose:
        args.log_flushes = True
    profiler = PyFlowTraceProfiler(
        args.script,
        args.output,
        args.script_args,
        flush_interval=args.flush_interval,
        flush_call_threshold=args.flush_call_threshold,
        flush_every_call=args.flush_every_call,
        log_flushes=args.log_flushes,
        capture_memory=capture_memory,
        capture_inputs=not args.skip_inputs,
        capture_outputs=not args.skip_outputs,
        enable_tracemalloc=enable_tracemalloc,
        verbose=args.verbose,
    )
    profiler.run()


if __name__ == "__main__":
    main()
