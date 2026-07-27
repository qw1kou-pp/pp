from __future__ import annotations

import argparse
import os
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from tests.repository_acceptance.acceptance_live import (
    LiveAcceptanceSettings,
    execute_live_acceptance,
)
from tests.repository_acceptance.acceptance_models import AcceptanceStatus
from tests.repository_acceptance.repository_matrix import get_repository_case


SCENARIOS = ("scan_once", "heartbeat", "max_attempts", "all")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run repository recovery acceptance scenarios against the API"
        )
    )
    parser.add_argument(
        "--scenario",
        choices=SCENARIOS,
        default="all",
        help="Recovery scenario to run",
    )
    parser.add_argument(
        "--repository",
        default="requests",
        help="Repository matrix key used for the scenario run",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Override REPOSITORY_RECOVERY_ACCEPTANCE_OUTPUT_DIR",
    )
    return parser


def scenario_names(selected: str) -> tuple[str, ...]:
    if selected == "all":
        return ("scan_once", "heartbeat", "max_attempts")
    return (selected,)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        case = get_repository_case(args.repository)
        settings = LiveAcceptanceSettings.from_environment(
            require_enabled=False
        )
    except (KeyError, ValueError) as exc:
        parser.error(str(exc))

    output_dir = (
        args.output_dir
        or Path(
            os.environ.get(
                "REPOSITORY_RECOVERY_ACCEPTANCE_OUTPUT_DIR",
                "artifacts/repository-recovery-acceptance",
            )
        )
    )
    settings = replace(settings, output_dir=output_dir)

    failed = False
    for scenario in scenario_names(args.scenario):
        result, paths = execute_live_acceptance(
            cases=(case,),
            settings=settings,
            run_name=f"repository-recovery-{scenario}",
        )
        print(
            f"Repository recovery acceptance {scenario}: "
            f"{result.status.value}; passed={result.passed_count}; "
            f"failed={result.failed_count}"
        )
        print(f"JSON report: {paths.json_path}")
        print(f"Markdown report: {paths.markdown_path}")
        failed = failed or result.status is not AcceptanceStatus.PASSED

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
