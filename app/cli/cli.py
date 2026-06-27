"""CLIApplication encapsulates command parsing, configuration, and runner execution."""

import sys
import time
import uuid
from collections.abc import Sequence

from app.cli.exceptions import CLIException
from app.cli.models import CLIRequest, CLIResult, CommandContext, ExitStatus
from app.cli.parser import args_to_request, create_parser
from app.cli.runner import PipelineRunner
from app.cli.telemetry import CLITelemetry
from app.config.manager import ConfigurationManager


class CLIApplication:
    """Core CLI Application managing global bootstrap, arguments validation, and runner execution."""

    def __init__(self, runner: PipelineRunner | None = None) -> None:
        """Initialize CLIApplication."""
        self.runner = runner or PipelineRunner()
        self.parser = create_parser()

    def _init_config(self, request: CLIRequest) -> None:
        """Initialize global configuration manager with profile overrides."""
        if request.config_file:
            from pathlib import Path

            config_path = Path(request.config_file)
            if not config_path.exists():
                raise FileNotFoundError(
                    f"Configuration file '{request.config_file}' not found."
                )
        try:
            overrides = {}
            if request.profile:
                overrides["app"] = {"app_env": request.profile}

            ConfigurationManager().load_configuration(
                config_file_path=request.config_file,
                programmatic_overrides=overrides if overrides else None,
            )
        except Exception as e:
            raise CLIException(f"Configuration initialization failed: {e}") from e

    async def run(self, argv: Sequence[str] | None = None) -> int:
        """Run SeedOps CLI process topologically and return exit code."""
        start_time = time.perf_counter()
        correlation_id = str(uuid.uuid4())
        exit_code: ExitStatus | None = None

        # 1. Parse CLI arguments
        try:
            args = self.parser.parse_args(argv)
            request = args_to_request(args)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 0
            exit_code = ExitStatus.SUCCESS if code == 0 else ExitStatus.VALIDATION_ERROR
        except FileNotFoundError as e:
            sys.stderr.write(f"Error: {e}\n")
            exit_code = ExitStatus.VALIDATION_ERROR
        except Exception:
            exit_code = ExitStatus.VALIDATION_ERROR

        # 2. Initialize configuration
        if exit_code is None:
            try:
                self._init_config(request)
            except FileNotFoundError as e:
                sys.stderr.write(f"Error: {e}\n")
                exit_code = ExitStatus.CONFIGURATION_ERROR
            except Exception:
                exit_code = ExitStatus.CONFIGURATION_ERROR

        if exit_code is not None:
            return exit_code

        # 3. Setup telemetry correlation tracing
        CommandContext(request=request, correlation_id=correlation_id)

        CLITelemetry.log_cli_started(request.command, correlation_id)

        # 4. Command mapping and execution
        result: CLIResult
        try:
            cmd_method = getattr(self.runner, request.command, None)
            if not cmd_method:
                result = CLIResult(
                    exit_code=ExitStatus.UNKNOWN_ERROR,
                    message=f"Command '{request.command}' is not implemented on the PipelineRunner.",
                )
            elif request.command in ("version", "config", "health"):
                result = await cmd_method()
            else:
                result = await cmd_method(request)
        except Exception as e:
            CLITelemetry.log_cli_error(request.command, str(e), correlation_id)
            result = CLIResult(
                exit_code=ExitStatus.RUNTIME_ERROR,
                message=f"Execution error: {e}",
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        CLITelemetry.log_cli_completed(
            request.command, result.exit_code, duration_ms, correlation_id
        )

        # 5. Output format display
        if result.exit_code == ExitStatus.SUCCESS:
            sys.stdout.write(f"{result.message}\n")
            if result.summary:
                sys.stdout.write("\n--- Execution Summary ---\n")
                sys.stdout.write(
                    f"Total Tables Processed: {result.summary.total_tables}\n"
                )
                sys.stdout.write(
                    f"Total Records Generated: {result.summary.total_records}\n"
                )
                sys.stdout.write(f"Duration: {result.summary.duration_ms:.2f} ms\n")
                if result.summary.statistics:
                    sys.stdout.write("Details:\n")
                    for k, v in result.summary.statistics.items():
                        sys.stdout.write(f"  - {k}: {v}\n")
        else:
            sys.stderr.write(f"Error: {result.message}\n")
            if result.summary:
                sys.stderr.write("\n--- Execution Summary ---\n")
                sys.stderr.write(
                    f"Total Tables Processed: {result.summary.total_tables}\n"
                )
                sys.stderr.write(
                    f"Total Records Generated: {result.summary.total_records}\n"
                )
                sys.stderr.write(f"Duration: {result.summary.duration_ms:.2f} ms\n")

        return result.exit_code
