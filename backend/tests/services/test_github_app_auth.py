from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import (
    serialization,
)
from cryptography.hazmat.primitives.asymmetric import (
    rsa,
)

from app.services.github_app_auth import (
    GitHubAppAuthConfig,
    GitHubAppNotConfiguredError,
    GitHubAppPrivateKeyError,
    build_github_app_jwt,
    load_github_app_auth_config,
)


def create_test_private_key(
    key_path: Path,
) -> rsa.RSAPrivateKey:
    private_key = (
        rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
    )

    private_key_pem = (
        private_key.private_bytes(
            encoding=(
                serialization
                .Encoding.PEM
            ),
            format=(
                serialization
                .PrivateFormat
                .TraditionalOpenSSL
            ),
            encryption_algorithm=(
                serialization
                .NoEncryption()
            ),
        )
    )

    key_path.write_bytes(
        private_key_pem,
    )

    return private_key


def test_load_config_requires_app_id(
    tmp_path: Path,
) -> None:
    key_path = (
        tmp_path
        / "private-key.pem"
    )

    key_path.write_text(
        "test",
        encoding="utf-8",
    )

    with pytest.raises(
        GitHubAppNotConfiguredError,
        match="App ID",
    ):
        load_github_app_auth_config(
            app_id=None,
            private_key_path=key_path,
        )


def test_load_config_requires_key_path() -> None:
    with pytest.raises(
        GitHubAppNotConfiguredError,
        match="private key path",
    ):
        load_github_app_auth_config(
            app_id="123456",
            private_key_path=None,
        )


def test_build_jwt_requires_readable_key(
    tmp_path: Path,
) -> None:
    config = GitHubAppAuthConfig(
        app_id="123456",
        private_key_path=(
            tmp_path
            / "missing.pem"
        ),
    )

    with pytest.raises(
        GitHubAppPrivateKeyError,
        match="cannot be read",
    ):
        build_github_app_jwt(
            config=config,
        )


def test_build_jwt_rejects_invalid_key(
    tmp_path: Path,
) -> None:
    key_path = (
        tmp_path
        / "invalid.pem"
    )

    key_path.write_text(
        "not-a-private-key",
        encoding="utf-8",
    )

    config = GitHubAppAuthConfig(
        app_id="123456",
        private_key_path=key_path,
    )

    with pytest.raises(
        GitHubAppPrivateKeyError,
        match="invalid",
    ):
        build_github_app_jwt(
            config=config,
        )


def test_build_jwt_uses_rs256_and_required_claims(
    tmp_path: Path,
) -> None:
    key_path = (
        tmp_path
        / "private-key.pem"
    )

    private_key = (
        create_test_private_key(
            key_path,
        )
    )

    config = GitHubAppAuthConfig(
        app_id="123456",
        private_key_path=key_path,
    )

    now = datetime(
        2026,
        7,
        16,
        12,
        0,
        0,
        tzinfo=UTC,
    )

    token = build_github_app_jwt(
        config=config,
        now=now,
    )

    header = (
        jwt.get_unverified_header(
            token,
        )
    )

    public_key = (
        private_key.public_key()
    )

    claims = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        options={
            "verify_exp": False,
            "verify_iat": False,
        },
    )

    expected_now = int(
        now.timestamp(),
    )

    assert header["alg"] == "RS256"

    assert claims["iss"] == "123456"

    assert claims["iat"] == (
        expected_now - 60
    )

    assert claims["exp"] == (
        expected_now + 540
    )

    assert (
        claims["exp"]
        - expected_now
        <= 600
    )