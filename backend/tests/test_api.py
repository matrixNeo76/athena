"""
Integration tests for the ATHENA FastAPI endpoints.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c


@pytest.mark.anyio
class TestHealthEndpoint:
    async def test_health_returns_200(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    async def test_health_contains_status(self, client):
        data = (await client.get("/api/v1/health")).json()
        assert "status" in data


@pytest.mark.anyio
class TestAnalysisStart:
    async def test_start_returns_202(self, client):
        with patch(
            "app.services.job_store.create_job",
            return_value="mock-job-id-001",
        ):
            response = await client.post(
                "/api/v1/analysis/start",
                json={"target": "OpenAI", "target_type": "company", "depth": "quick"},
            )
        assert response.status_code in (200, 201, 202)

    async def test_start_missing_target_returns_422(self, client):
        response = await client.post(
            "/api/v1/analysis/start",
            json={"target_type": "company"},
        )
        assert response.status_code == 422


@pytest.mark.anyio
class TestAnalysisStatus:
    async def test_status_unknown_job_returns_404(self, client):
        with patch(
            "app.services.job_store.get_job",
            return_value=None,
        ):
            response = await client.get("/api/v1/analysis/nonexistent-id/status")
        assert response.status_code == 404

    async def test_status_known_job_returns_200(self, client):
        mock_job = {
            "job_id": "test-123",
            "status": "PENDING",
            "stage": "PENDING",
            "progress": 0,
            "target": "Anthropic",
            "target_type": "company",
            "created_at": "2026-02-27T00:00:00Z",
            "updated_at": "2026-02-27T00:00:00Z",
            "error": None,
        }
        with patch("app.services.job_store.get_job", return_value=mock_job):
            response = await client.get("/api/v1/analysis/test-123/status")
        assert response.status_code == 200


@pytest.mark.anyio
class TestWebhookEndpoint:
    async def test_webhook_accepts_payload(self, client):
        payload = {
            "event": "agent.completed",
            "job_id": "some-job",
            "agent_id": "scout-agent",
            "data": {},
        }
        response = await client.post("/api/v1/analysis/complete-dev", json=payload)
        # Webhook should return 200 or 202 (not 4xx/5xx)
        assert response.status_code < 400
