import contextlib
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


class StartupMonitor:
    def __init__(self, component_name: str) -> None:
        self.component_name: str = component_name
        self.current_phase: str | None = None
        self.current_func: str | None = None
        self.phase_start_time: float | None = None
        self.lock: threading.Lock = threading.Lock()
        self.stop_event: threading.Event = threading.Event()
        self.thread: threading.Thread = threading.Thread(
            target=self._monitor_loop, daemon=True
        )
        self.thread.start()

    def start_phase(self, phase_name: str, func_name: str) -> None:
        with self.lock:
            self.current_phase = phase_name
            self.current_func = func_name
            self.phase_start_time = time.time()
            print(f"\n{phase_name} Starting...", flush=True)  # noqa: T201
            self._write_log(f"BEFORE Phase: {phase_name} | Function: {func_name}")

    def end_phase(self, phase_name: str) -> None:
        with self.lock:
            if self.current_phase == phase_name and self.phase_start_time is not None:
                elapsed = time.time() - self.phase_start_time
                print("Complete", flush=True)  # noqa: T201
                self._write_log(f"AFTER Phase: {phase_name} | Elapsed: {elapsed:.4f}s")
                self.current_phase = None
                self.current_func = None
                self.phase_start_time = None

    def update_func(self, func_name: str) -> None:
        with self.lock:
            self.current_func = func_name

    def _write_log(self, message: str) -> None:
        with contextlib.suppress(Exception):
            logs_dir = Path.cwd() / "logs"
            logs_dir.mkdir(exist_ok=True)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_file = logs_dir / "startup_instrumentation.log"
            with log_file.open("a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{self.component_name}] {message}\n")

    def _monitor_loop(self) -> None:
        while not self.stop_event.is_set():
            time.sleep(1.0)
            with self.lock:
                if self.current_phase and self.phase_start_time is not None:
                    elapsed = time.time() - self.phase_start_time
                    if elapsed > 5.0:
                        self._write_log(
                            f"Still waiting... in {self.current_func} for {elapsed:.1f}s"
                        )


# Global instances for backend and CLI
monitor: StartupMonitor = StartupMonitor("STARTUP")


def log_external_command(args: list[Any], cwd: Any | None = None) -> None:
    cmd_str = " ".join(str(x) for x in args)
    msg = f"External command before execution: {cmd_str}"
    if cwd:
        msg += f" (Cwd: {cwd})"
    with contextlib.suppress(Exception):
        logs_dir = Path.cwd() / "logs"
        logs_dir.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_file = logs_dir / "startup_instrumentation.log"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [SUBPROCESS] {msg}\n")


def log_subprocess_invocation(args: list[Any]) -> None:
    cmd_str = " ".join(str(x) for x in args)
    msg = f"Subprocess invoked: {cmd_str}"
    with contextlib.suppress(Exception):
        logs_dir = Path.cwd() / "logs"
        logs_dir.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_file = logs_dir / "startup_instrumentation.log"
        with log_file.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [SUBPROCESS] {msg}\n")


def instrumented_run(
    args: list[Any], **kwargs: Any
) -> subprocess.CompletedProcess[Any]:
    with contextlib.suppress(Exception):
        log_external_command(args, cwd=kwargs.get("cwd"))
    with contextlib.suppress(Exception):
        log_subprocess_invocation(args)
    return subprocess.run(args, **kwargs)  # noqa: S603, PLW1510


def instrumented_Popen(  # noqa: N802
    args: list[Any], **kwargs: Any
) -> subprocess.Popen[Any]:
    with contextlib.suppress(Exception):
        log_external_command(args, cwd=kwargs.get("cwd"))
    with contextlib.suppress(Exception):
        log_subprocess_invocation(args)
    return subprocess.Popen(args, **kwargs)  # noqa: S603
