from __future__ import annotations

from tests.repository_acceptance.repository_matrix import (
    REPOSITORY_MATRIX,
    get_repository_case,
    get_smoke_cases,
)


def test_matrix_contains_the_four_approved_real_repositories() -> None:
    assert {case.repository_full_name for case in REPOSITORY_MATRIX} == {
        "psf/requests",
        "fastapi/fastapi",
        "pmndrs/zustand",
        "fastapi/full-stack-fastapi-template",
    }


def test_every_case_uses_https_github_and_has_questions() -> None:
    for case in REPOSITORY_MATRIX:
        assert case.repository_url.startswith("https://github.com/")
        assert case.questions
        assert case.task_timeout_seconds > 0


def test_smoke_matrix_covers_python_and_full_stack() -> None:
    smoke_cases = get_smoke_cases()

    assert {case.key for case in smoke_cases} == {
        "requests",
        "full-stack-fastapi-template",
    }


def test_get_repository_case_rejects_unknown_key() -> None:
    try:
        get_repository_case("missing")
    except KeyError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("unknown repository key must raise KeyError")
