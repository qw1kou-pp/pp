from __future__ import annotations

import pytest

from tests.repository_acceptance.acceptance_live import (
    LiveAcceptanceSettings,
    live_acceptance_enabled,
)


def complete_environment() -> dict[str, str]:
    return {
        "RUN_REPOSITORY_ACCEPTANCE_LIVE": "1",
        "REPOSITORY_ACCEPTANCE_BASE_URL": "http://backend:8000",
        "REPOSITORY_ACCEPTANCE_EMAIL": "tester@example.com",
        "REPOSITORY_ACCEPTANCE_PASSWORD": "secret",
        "GITHUB_TOKEN": "github-token",
        "REPOSITORY_ACCEPTANCE_OUTPUT_DIR": "artifacts/live",
    }


def test_live_settings_load_required_environment_without_exposing_token() -> None:
    settings = LiveAcceptanceSettings.from_environment(
        complete_environment()
    )

    assert settings.base_url == "http://backend:8000"
    assert settings.email == "tester@example.com"
    assert settings.github_token == "github-token"
    assert settings.output_dir.as_posix() == "artifacts/live"
    assert "github-token" not in repr(settings)


def test_live_settings_require_github_token() -> None:
    environment = complete_environment()
    environment.pop("GITHUB_TOKEN")

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        LiveAcceptanceSettings.from_environment(environment)


def test_live_acceptance_enabled_supports_explicit_truthy_values() -> None:
    assert live_acceptance_enabled(
        {"RUN_REPOSITORY_ACCEPTANCE_LIVE": "true"}
    )
    assert not live_acceptance_enabled(
        {"RUN_REPOSITORY_ACCEPTANCE_LIVE": "0"}
    )
