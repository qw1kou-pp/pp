from __future__ import annotations

from dataclasses import dataclass
from datetime import (
    UTC,
    datetime,
)
from pathlib import Path

import jwt
from jwt.exceptions import (
    InvalidKeyError,
)


class GitHubAppAuthError(
    RuntimeError,
):
    """GitHub App 认证基础异常。"""


class GitHubAppNotConfiguredError(
    GitHubAppAuthError,
):
    """GitHub App 配置不完整。"""


class GitHubAppPrivateKeyError(
    GitHubAppAuthError,
):
    """GitHub App 私钥不可用。"""


@dataclass(
    frozen=True,
    slots=True,
)
class GitHubAppAuthConfig:
    app_id: str
    private_key_path: Path


def load_github_app_auth_config(
    *,
    app_id: str | None,
    private_key_path: (
        str | Path | None
    ),
) -> GitHubAppAuthConfig:
    normalized_app_id = (
        str(app_id or "")
        .strip()
    )

    if not normalized_app_id:
        raise (
            GitHubAppNotConfiguredError(
                "GitHub App ID "
                "is not configured",
            )
        )

    if private_key_path is None:
        raise (
            GitHubAppNotConfiguredError(
                "GitHub App private key "
                "path is not configured",
            )
        )

    normalized_key_path = Path(
        private_key_path,
    )

    return GitHubAppAuthConfig(
        app_id=normalized_app_id,
        private_key_path=(
            normalized_key_path
        ),
    )


def read_github_app_private_key(
    private_key_path: Path,
) -> bytes:
    try:
        private_key_pem = (
            private_key_path
            .read_bytes()
        )
    except OSError as exc:
        raise GitHubAppPrivateKeyError(
            "GitHub App private key "
            "cannot be read",
        ) from exc

    if not private_key_pem.strip():
        raise GitHubAppPrivateKeyError(
            "GitHub App private key "
            "is empty",
        )

    return private_key_pem


def build_github_app_jwt(
    *,
    config: GitHubAppAuthConfig,
    now: datetime | None = None,
) -> str:
    current_time = (
        now
        or datetime.now(UTC)
    )

    if current_time.tzinfo is None:
        current_time = (
            current_time.replace(
                tzinfo=UTC,
            )
        )

    current_timestamp = int(
        current_time.timestamp(),
    )

    payload = {
        # 向过去偏移 60 秒，
        # 容忍服务器时间轻微偏差。
        "iat":
            current_timestamp - 60,

        # 9 分钟后过期，
        # 小于 GitHub 的 10 分钟上限。
        "exp":
            current_timestamp + 540,

        "iss":
            config.app_id,
    }

    private_key_pem = (
        read_github_app_private_key(
            config.private_key_path,
        )
    )

    try:
        encoded_jwt = jwt.encode(
            payload,
            private_key_pem,
            algorithm="RS256",
        )
    except (
        InvalidKeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise GitHubAppPrivateKeyError(
            "GitHub App private key "
            "is invalid",
        ) from exc

    if not isinstance(
        encoded_jwt,
        str,
    ):
        raise GitHubAppAuthError(
            "GitHub App JWT generation "
            "returned an invalid result",
        )

    return encoded_jwt