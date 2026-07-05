"""One-command developer startup CLI command automation script."""

# ruff: noqa: T201, S110, PTH123, S607

import argparse
import contextlib
import datetime
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any

from app.platform.configuration.settings import platform_settings
from app.services.developer_startup import DeveloperStartupManager


def log_startup(message: str) -> None:
    """Log messages to startup.log with timestamp."""
    logs_dir = Path.cwd() / "logs"
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with Path(logs_dir / "startup.log").open("a") as f:
        f.write(f"[{timestamp}] {message}\n")


def stream_logs(
    pipe: Any, prefix: str, log_queue: queue.Queue[str], log_file_path: Path
) -> None:
    """Pipes stdout/stderr lines from a process to a unified log queue."""
    try:
        with Path(log_file_path).open("a") as lf:
            for line in iter(pipe.readline, ""):
                if not line:
                    break
                stripped = line.strip()
                # Put to queue for console output
                log_queue.put(f"{prefix} {stripped}")
                # Append to persistent log file
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                lf.write(f"[{timestamp}] {stripped}\n")
                lf.flush()
    except Exception:
        pass
    finally:
        with contextlib.suppress(Exception):
            pipe.close()


def main() -> None:
    """Run one-command developer startup validation, provisioning, and execution."""
    parser = argparse.ArgumentParser(description="SafeSeedOps Developer Startup")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run environment checks without launching services",
    )
    args = parser.parse_args()

    manager = DeveloperStartupManager()

    log_startup("Developer startup initiated.")
    print("==================================================")
    print("SafeSeedOps Lite Developer Startup")
    print("==================================================")

    # Detect env presence
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        msg = "[WARNING] .env file is missing! Application may not run with expected environment variables."
        print(f"\n{msg}")
        log_startup(msg)

    # Start scanner and printer threads
    stop_scanner = threading.Event()
    log_queue: queue.Queue[str] = queue.Queue()
    streamed_services: set[str] = set()
    threads: list[threading.Thread] = []

    def log_scanner() -> None:
        logs_dir = Path.cwd() / "logs"
        logs_dir.mkdir(exist_ok=True)
        while not stop_scanner.is_set():
            for name, info in list(manager.launcher.running_services.items()):
                if name not in streamed_services:
                    streamed_services.add(name)
                    proc = info["proc"]
                    log_file = logs_dir / f"{name}.log"
                    t = threading.Thread(
                        target=stream_logs,
                        args=(proc.stdout, f"[{name.upper()}]", log_queue, log_file),
                        daemon=True,
                    )
                    t.start()
                    threads.append(t)
            time.sleep(0.1)

    def log_printer() -> None:
        while not stop_scanner.is_set() or not log_queue.empty():
            try:
                line = log_queue.get(timeout=0.05)
                # Print colored prefix if stdout is supported
                if "[BACKEND]" in line:
                    # Blue prefix
                    print(f"\033[94m{line[:9]}\033[0m {line[10:]}", flush=True)
                elif "[FRONTEND]" in line:
                    # Green prefix
                    print(f"\033[92m{line[:10]}\033[0m {line[11:]}", flush=True)
                else:
                    print(line, flush=True)
            except queue.Empty:
                pass

    scanner_t = threading.Thread(target=log_scanner, daemon=True)
    scanner_t.start()
    printer_t = threading.Thread(target=log_printer, daemon=True)
    printer_t.start()

    # 1. Start services and run validations
    result = manager.run_dev_startup(dry_run=args.dry_run)

    if not result.success:
        print(
            "\n[FAIL] Environment validation or health checks failed!", file=sys.stderr
        )
        log_startup("Startup failed due to validation or health check errors.")
        for issue in result.diagnostics:
            err_msg = f"- [{issue.issue_type}] {issue.description}"
            print(err_msg, file=sys.stderr)
            print(
                f"  Suggested Resolution: {issue.suggested_resolution}", file=sys.stderr
            )
            log_startup(err_msg)
        stop_scanner.set()
        manager.shutdown()
        sys.exit(1)

    print("\n[PASS] Development environment pre-flight validations passed.")
    log_startup("Pre-flight validations passed.")

    if args.dry_run:
        print("\nDry run completed successfully. (No services launched)")
        stop_scanner.set()
        sys.exit(0)

    # 2. Print Startup Summary
    print("\n==================================================")
    print("Application Ready")
    print("==================================================")
    print(
        f"\nFrontend\nhttp://{platform_settings.dev_host}:{platform_settings.dev_frontend_port}"
    )
    print(
        f"\nBackend\nhttp://{platform_settings.dev_host}:{platform_settings.dev_backend_port}"
    )
    print(
        f"\nAPI Docs\nhttp://{platform_settings.dev_host}:{platform_settings.dev_backend_port}/docs"
    )
    print("\nStreaming logs...")
    print("==================================================\n")

    log_startup("Services started successfully. URLs generated.")

    # 4. Monitor processes & output logs until Ctrl+C
    try:
        while True:
            # Check if any process died prematurely
            for name, info in list(manager.launcher.running_services.items()):
                proc = info["proc"]
                exit_code = proc.poll()
                if exit_code is not None:
                    err_msg = f"[ERROR] {name.upper()} service process exited prematurely with code {exit_code}."
                    print(f"\n{err_msg}", file=sys.stderr)
                    log_startup(err_msg)
                    stop_scanner.set()
                    manager.shutdown()
                    sys.exit(1)

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n[INFO] Shutdown signal received (Ctrl+C). Cleaning up services...")
        log_startup("Shutdown signal received (Ctrl+C). Stopping services...")
        stop_scanner.set()
        manager.shutdown()
        print("\n--------------------------------------------------")
        print("Shutdown Summary")
        print(" Backend:      Stopped")
        print(" Frontend:     Stopped")
        print(" Infrastructure remains running.")
        print("--------------------------------------------------")
        log_startup("Services stopped cleanly. Infrastructure remains running.")
        sys.exit(0)


if __name__ == "__main__":
    main()
