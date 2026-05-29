"""Smoke tests for the repo-root `docker-compose.yml` (ISSUE-004).

These tests parse the compose file as plain text (no PyYAML dependency) and
assert that the required services, image tags, ports, healthchecks, and named
volumes are present. They do NOT run docker — that is verified manually per
`docs/RUNBOOK.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
ENV_EXAMPLE = REPO_ROOT / "api" / ".env.example"
RUNBOOK = REPO_ROOT / "docs" / "RUNBOOK.md"


@pytest.fixture(scope="module")
def compose_text() -> str:
    assert COMPOSE_FILE.exists(), f"missing {COMPOSE_FILE}"
    return COMPOSE_FILE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def env_text() -> str:
    assert ENV_EXAMPLE.exists(), f"missing {ENV_EXAMPLE}"
    return ENV_EXAMPLE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def runbook_text() -> str:
    assert RUNBOOK.exists(), f"missing {RUNBOOK}"
    return RUNBOOK.read_text(encoding="utf-8")


# --- docker-compose.yml ---------------------------------------------------


def test_compose_defines_postgres_service(compose_text: str) -> None:
    assert "\n  postgres:" in compose_text
    assert "image: postgres:16-alpine" in compose_text


def test_compose_defines_redis_service(compose_text: str) -> None:
    assert "\n  redis:" in compose_text
    assert "image: redis:7-alpine" in compose_text


def test_compose_postgres_exposes_5432(compose_text: str) -> None:
    assert '"5432:5432"' in compose_text


def test_compose_redis_exposes_6379(compose_text: str) -> None:
    assert '"6379:6379"' in compose_text


def test_compose_postgres_has_healthcheck(compose_text: str) -> None:
    # pg_isready is the canonical healthcheck for the official image
    assert "pg_isready" in compose_text


def test_compose_redis_has_healthcheck(compose_text: str) -> None:
    assert "redis-cli" in compose_text and "ping" in compose_text


def test_compose_uses_named_volumes(compose_text: str) -> None:
    # named volumes survive `docker compose down` (without -v)
    assert "postgres_data:" in compose_text
    assert "redis_data:" in compose_text
    # explicit `name:` aliases for cross-project clarity
    assert "voicesaju_postgres_data" in compose_text
    assert "voicesaju_redis_data" in compose_text


def test_compose_pins_credentials_in_dev_only(compose_text: str) -> None:
    """Dev credentials are intentionally trivial; ensure they match .env.example."""
    assert "POSTGRES_USER: voicesaju" in compose_text
    assert "POSTGRES_PASSWORD: voicesaju" in compose_text
    assert "POSTGRES_DB: voicesaju" in compose_text


# --- api/.env.example -----------------------------------------------------


def test_env_example_has_database_url(env_text: str) -> None:
    assert (
        "DATABASE_URL=postgresql+asyncpg://voicesaju:voicesaju@localhost:5432/voicesaju"
        in env_text
    )


def test_env_example_has_redis_url(env_text: str) -> None:
    assert "REDIS_URL=redis://localhost:6379/0" in env_text


def test_env_example_has_local_kek_placeholder(env_text: str) -> None:
    # value must be a placeholder, never a real base64-encoded 32-byte key
    assert "LOCAL_KEK_BASE64=" in env_text
    assert "REPLACE_WITH_BASE64_32_BYTES" in env_text


def test_env_example_has_kms_provider(env_text: str) -> None:
    assert "KMS_PROVIDER=local" in env_text


def test_env_example_no_real_secrets(env_text: str) -> None:
    """Defensive check: ensure no obviously-real credentials slipped in."""
    forbidden = ("AKIA", "ghp_", "sk-", "gho_")
    for token in forbidden:
        assert (
            token not in env_text
        ), f"forbidden token {token!r} present in .env.example"


# --- docs/RUNBOOK.md ------------------------------------------------------


def test_runbook_documents_compose_up(runbook_text: str) -> None:
    assert "docker compose up -d" in runbook_text


def test_runbook_documents_verification(runbook_text: str) -> None:
    assert "SELECT version()" in runbook_text
    assert "PING" in runbook_text


def test_runbook_documents_reset(runbook_text: str) -> None:
    assert "docker compose down" in runbook_text
    assert "docker compose down -v" in runbook_text
