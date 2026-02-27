"""
ATHENA - Shared pytest fixtures (conftest.py)

Automatically loaded by pytest for all tests in this directory.
Provides reusable fixtures without explicit imports in test modules.

Fixtures:
  stub_mode   — patches Settings.is_stub_mode → True (no Deploy.AI API calls)
  clean_store — resets the in-memory job store between tests
  api_client  — FastAPI TestClient pre-configured with stub_mode + clean_store

Note: These fixtures are NOT autouse, meaning they must be explicitly
requested. Tests that need their own autouse variant (e.g. test_stub_pipeline)
define their own module-level fixtures, which take precedence here.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def stub_mode(monkeypatch):
    """
    Patches Settings.is_stub_mode to always return True regardless of
    .env file credentials, ensuring no real Deploy.AI API calls in tests.

    Uses monkeypatch for automatic cleanup after each test function.

    Usage:
        def test_something(stub_mode):
            result = asyncio.run(run_scout("TestCo"))
    """
    from app.core.config import Settings
    monkeypatch.setattr(Settings, "is_stub_mode", property(lambda self: True))


@pytest.fixture()
def clean_store():
    """
    Resets the in-memory job store (_jobs dict + _locks dict) before and
    after each test to prevent state leakage between tests.

    Usage:
        def test_something(clean_store):
            j = create_job("TestCo")
    """
    from app.services.job_store import _jobs, _locks
    _jobs.clear()
    _locks.clear()
    yield
    _jobs.clear()
    _locks.clear()


@pytest.fixture()
def api_client(stub_mode, clean_store):
    """
    FastAPI TestClient pre-configured with:
      - stub_mode: patches is_stub_mode → True (no Deploy.AI API calls)
      - clean_store: isolated job store per test (prevents cross-test pollution)
      - raise_server_exceptions=False: HTTP error responses returned as-is

    Usage:
        def test_health(api_client):
            r = api_client.get("/api/v1/health")
            assert r.status_code == 200
    """
    from app.main import app
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
