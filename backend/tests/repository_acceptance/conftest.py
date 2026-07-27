from __future__ import annotations

import pytest

from tests.repository_acceptance.acceptance_live import (
    LiveAcceptanceSettings,
    live_acceptance_enabled,
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "repository_live: calls the deployed API and real GitHub repositories",
    )
    config.addinivalue_line(
        "markers",
        "repository_smoke: two-repository PR acceptance matrix",
    )
    config.addinivalue_line(
        "markers",
        "repository_matrix: complete four-repository acceptance matrix",
    )


@pytest.fixture(scope="session")
def live_acceptance_settings() -> LiveAcceptanceSettings:
    if not live_acceptance_enabled():
        pytest.skip(
            "set RUN_REPOSITORY_ACCEPTANCE_LIVE=1 to run live acceptance"
        )
    return LiveAcceptanceSettings.from_environment()
