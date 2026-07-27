from __future__ import annotations

import pytest

from scripts.run_repository_acceptance import build_parser, select_cases


def test_cli_selects_smoke_cases() -> None:
    args = build_parser().parse_args(["--smoke"])

    cases = select_cases(args)

    assert [case.key for case in cases] == [
        "requests",
        "full-stack-fastapi-template",
    ]


def test_cli_selects_single_repository() -> None:
    args = build_parser().parse_args(["--repository", "zustand"])

    cases = select_cases(args)

    assert [case.key for case in cases] == ["zustand"]


def test_cli_rejects_unknown_repository() -> None:
    args = build_parser().parse_args(["--repository", "missing"])

    with pytest.raises(ValueError, match="Unknown repository case"):
        select_cases(args)
