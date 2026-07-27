from __future__ import annotations

import pytest

from tests.repository_acceptance.acceptance_live import (
    LiveAcceptanceSettings,
    execute_live_acceptance,
)
from tests.repository_acceptance.acceptance_models import AcceptanceStatus
from tests.repository_acceptance.repository_matrix import get_smoke_cases


@pytest.mark.repository_live
@pytest.mark.repository_smoke
def test_live_repository_smoke_matrix(
    live_acceptance_settings: LiveAcceptanceSettings,
) -> None:
    result, paths = execute_live_acceptance(
        cases=get_smoke_cases(),
        settings=live_acceptance_settings,
        run_name="repository-smoke",
    )

    assert result.status is AcceptanceStatus.PASSED, (
        f"live smoke acceptance failed; report={paths.markdown_path}"
    )
