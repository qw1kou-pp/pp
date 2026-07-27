from __future__ import annotations

import pytest

from tests.repository_acceptance.acceptance_live import (
    LiveAcceptanceSettings,
    execute_live_acceptance,
)
from tests.repository_acceptance.acceptance_models import AcceptanceStatus
from tests.repository_acceptance.repository_matrix import get_all_cases


@pytest.mark.repository_live
@pytest.mark.repository_matrix
def test_live_complete_repository_matrix(
    live_acceptance_settings: LiveAcceptanceSettings,
) -> None:
    result, paths = execute_live_acceptance(
        cases=get_all_cases(),
        settings=live_acceptance_settings,
        run_name="repository-matrix",
    )

    assert result.status is AcceptanceStatus.PASSED, (
        f"live repository matrix failed; report={paths.markdown_path}"
    )
