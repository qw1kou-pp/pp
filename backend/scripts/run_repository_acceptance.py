from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from tests.repository_acceptance.acceptance_live import (
    LiveAcceptanceSettings,
    execute_live_acceptance,
)
from tests.repository_acceptance.acceptance_models import (
    AcceptanceStatus,
    RepositoryCase,
)
from tests.repository_acceptance.repository_matrix import (
    get_all_cases,
    get_repository_case,
    get_smoke_cases,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run live repository acceptance tests against the deployed API"
        )
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--smoke",
        action="store_true",
        help="Run the two PR smoke repositories",
    )
    selection.add_argument(
        "--all",
        dest="all_cases",
        action="store_true",
        help="Run the complete four-repository matrix",
    )
    selection.add_argument(
        "--repository",
        help="Run one repository case by key",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Override REPOSITORY_ACCEPTANCE_OUTPUT_DIR",
    )
    parser.add_argument(
        "--run-name",
        help="Base name for JSON and Markdown report files",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        help="Override repository task polling interval",
    )
    return parser


def select_cases(args: argparse.Namespace) -> tuple[RepositoryCase, ...]:
    if args.smoke:
        return get_smoke_cases()
    if args.all_cases:
        return get_all_cases()
    if args.repository:
        try:
            return (get_repository_case(args.repository),)
        except KeyError as exc:
            available = ", ".join(
                case.key for case in get_all_cases()
            )
            raise ValueError(
                f"Unknown repository case {args.repository!r}. "
                f"Available: {available}"
            ) from exc
    raise ValueError("one repository selection mode is required")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        cases = select_cases(args)
        settings = LiveAcceptanceSettings.from_environment(
            require_enabled=False
        )
        if args.output_dir is not None:
            settings = replace(settings, output_dir=args.output_dir)
        if args.poll_interval_seconds is not None:
            if args.poll_interval_seconds <= 0:
                raise ValueError(
                    "--poll-interval-seconds must be positive"
                )
            settings = replace(
                settings,
                poll_interval_seconds=args.poll_interval_seconds,
            )

        result, paths = execute_live_acceptance(
            cases=cases,
            settings=settings,
            run_name=args.run_name,
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(
        f"Repository acceptance: {result.status.value}; "
        f"passed={result.passed_count}; failed={result.failed_count}"
    )
    print(f"JSON report: {paths.json_path}")
    print(f"Markdown report: {paths.markdown_path}")
    return 0 if result.status is AcceptanceStatus.PASSED else 1


if __name__ == "__main__":
    raise SystemExit(main())
