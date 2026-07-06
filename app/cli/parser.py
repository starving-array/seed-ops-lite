"""Argument parser definition and request mapping for the CLI."""

import argparse
import json

from app.cli.models import CLIRequest


def parse_row_targets(value: str) -> dict[str, int]:
    """Parse row targets from JSON string or comma-separated key=value pairs."""
    if not value:
        return {}
    try:
        return dict(json.loads(value))
    except json.JSONDecodeError:
        targets = {}
        try:
            for item in value.split(","):
                if "=" in item:
                    k, v = item.split("=")
                    targets[k.strip()] = int(v.strip())
            return targets
        except Exception as e:
            raise argparse.ArgumentTypeError(
                f"Row targets must be valid JSON or format table1=num1,table2=num2. Error: {e}"
            ) from e


def create_parser() -> argparse.ArgumentParser:
    """Create configured argparse parser instance supporting all SeedOps commands."""
    parser = argparse.ArgumentParser(
        description="SeedOps Lite CLI - Synthetic Database Data Generator"
    )

    # Global options
    parser.add_argument(
        "--profile",
        dest="profile",
        help="Active configuration profile (development, testing, production)",
    )
    parser.add_argument(
        "--config-file",
        dest="config_file",
        help="Path to custom runtime config JSON file",
    )

    subparsers = parser.add_subparsers(
        dest="command", required=True, help="CLI Command to run"
    )

    # validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate a SQL DDL schema"
    )
    validate_parser.add_argument("ddl", help="Path to SQL DDL schema file")

    # plan command
    plan_parser = subparsers.add_parser(
        "plan", help="Generate a topological seeding execution plan"
    )
    plan_parser.add_argument("ddl", help="Path to SQL DDL schema file")
    plan_parser.add_argument(
        "--row-targets",
        type=parse_row_targets,
        default={},
        help="Custom table row counts (JSON string or table1=num1,table2=num2)",
    )

    # generate command
    generate_parser = subparsers.add_parser(
        "generate", help="Generate synthetic data (dry run)"
    )
    generate_parser.add_argument("ddl", help="Path to SQL DDL schema file")
    generate_parser.add_argument(
        "--num-records",
        type=int,
        default=10,
        help="Default number of records to generate per table",
    )
    generate_parser.add_argument(
        "--row-targets",
        type=parse_row_targets,
        default={},
        help="Custom table row counts (JSON or table1=num1,table2=num2)",
    )
    generate_parser.add_argument(
        "--seed", type=int, help="Random seed for deterministic generation"
    )

    # export command
    export_parser = subparsers.add_parser(
        "export", help="Generate and export synthetic data"
    )
    export_parser.add_argument("ddl", help="Path to SQL DDL schema file")
    export_parser.add_argument(
        "--export-format",
        default="json",
        choices=["json", "csv"],
        help="Target serialization format",
    )
    export_parser.add_argument(
        "--output-dir", required=True, help="Directory to save the serialized files"
    )
    export_parser.add_argument(
        "--num-records",
        type=int,
        default=10,
        help="Default number of records to generate per table",
    )
    export_parser.add_argument(
        "--row-targets",
        type=parse_row_targets,
        default={},
        help="Custom table row counts (JSON or table1=num1,table2=num2)",
    )
    export_parser.add_argument(
        "--seed", type=int, help="Random seed for deterministic generation"
    )

    # pipeline command
    pipeline_parser = subparsers.add_parser(
        "pipeline", help="Run full pipeline: validate -> plan -> generate -> export"
    )
    pipeline_parser.add_argument("ddl", help="Path to SQL DDL schema file")
    pipeline_parser.add_argument(
        "--export-format",
        default="json",
        choices=["json", "csv"],
        help="Target serialization format",
    )
    pipeline_parser.add_argument(
        "--output-dir", required=True, help="Directory to save the serialized files"
    )
    pipeline_parser.add_argument(
        "--num-records",
        type=int,
        default=10,
        help="Default number of records to generate per table",
    )
    pipeline_parser.add_argument(
        "--row-targets",
        type=parse_row_targets,
        default={},
        help="Custom table row counts (JSON or table1=num1,table2=num2)",
    )
    pipeline_parser.add_argument(
        "--seed", type=int, help="Random seed for deterministic generation"
    )

    # version command
    subparsers.add_parser(
        "version", help="Display SeedOps application version information"
    )

    # config command
    subparsers.add_parser("config", help="Display the active runtime configuration")

    # health command
    subparsers.add_parser("health", help="Check the health of core services (Redis)")

    return parser


def args_to_request(args: argparse.Namespace) -> CLIRequest:
    ddl_content = None
    ddl_path = getattr(args, "ddl", None)
    if ddl_path:
        from pathlib import Path

        path_obj = Path(ddl_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"SQL DDL file '{ddl_path}' not found.")
        with path_obj.open(encoding="utf-8") as f:
            ddl_content = f.read()

    return CLIRequest(
        command=args.command,
        ddl_path=ddl_path,
        ddl_content=ddl_content,
        num_records=getattr(args, "num_records", 10),
        row_targets=getattr(args, "row_targets", {}),
        seed=getattr(args, "seed", None),
        export_format=getattr(args, "export_format", "json"),
        output_dir=getattr(args, "output_dir", None),
        profile=args.profile,
        config_file=args.config_file,
    )
