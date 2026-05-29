"""Pytest fixtures shared across tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    from voicesaju.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
