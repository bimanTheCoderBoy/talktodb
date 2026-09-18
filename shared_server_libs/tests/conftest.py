from __future__ import annotations

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: tests requiring live Postgres/Redis")


@pytest.fixture
def integration_db_available() -> bool:
    return bool(os.getenv("DB_HOST"))


@pytest.fixture
def integration_redis_available() -> bool:
    return bool(os.getenv("REDIS_URL"))
