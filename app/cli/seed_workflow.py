"""Seed Workflow CLI Entrypoint."""

# ruff: noqa: T201, S603, UP022, RUF013, S110

import importlib.util
import sys
from pathlib import Path


def get_scripts_dir() -> Path:
    """Get the path to internal Repository Guardian scripts."""
    return (
        Path(__file__).resolve().parents[2]
        / ".skills"
        / "repository_guardian"
        / "scripts"
    )


def print_help() -> None:
    """Display CLI commands help details."""
    help_text = """Available Commands:
  status   - Check repository status and run quality gates (Active)
  commit   - Stage, verify quality gates, and commit changes (Active)
  freeze   - Freeze development phase and tag release (Active)
  dev      - One-command developer startup experience (Active)
  check    - Verify project structure (Planned)
  push     - Push committed branch to remote (Planned)
  release  - Generate changelog and release tags (Planned)
  doctor   - Resolve package locks and environments (Planned)
  audit    - Scan dependency vulnerabilities and secrets (Planned)
  upgrade  - Upgrade the Seed workflow components (Planned)"""
    print(help_text)


def main() -> None:
    """Dispatches the CLI execution flow to underlying scripts."""
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    command = sys.argv[1].lower()
    args = sys.argv[2:]

    scripts_map = {
        "status": "repository_status.py",
        "commit": "commit.py",
        "freeze": "freeze_phase.py",
        "dev": "dev_startup.py",
    }

    planned_commands = {
        "check": "Seed Check",
        "push": "Seed Push",
        "release": "Seed Release",
        "doctor": "Seed Doctor",
        "audit": "Seed Audit",
        "upgrade": "Seed Upgrade",
    }

    if command in scripts_map:
        script_name = scripts_map[command]
        script_path = get_scripts_dir() / script_name
        if not script_path.exists():
            print(
                f"Error: Internal script '{script_name}' not found.",
                file=sys.stderr,
            )
            sys.exit(1)

        sys.path.insert(0, str(get_scripts_dir()))
        sys.argv = [str(script_path), *args]

        spec = importlib.util.spec_from_file_location("__main__", str(script_path))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules["__main__"] = module
            try:
                spec.loader.exec_module(module)
            except SystemExit as e:
                sys.exit(e.code)
        else:
            print(
                f"Error: Could not load internal script '{script_name}'.",
                file=sys.stderr,
            )
            sys.exit(1)
    elif command in planned_commands:
        print(
            f"{planned_commands[command]} is planned but has not yet been implemented."
        )
        sys.exit(0)
    else:
        print(f"Unknown command: '{command}'\n", file=sys.stderr)
        print_help()
        sys.exit(1)
