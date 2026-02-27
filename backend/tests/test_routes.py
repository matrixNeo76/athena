"""
ATHENA - HTTP API endpoint integration tests

Tests all REST endpoints via FastAPI's TestClient (Starlette ASGI test client).
Background pipeline tasks (run_real_pipeline) are scheduled but may or may not
complete before assertions — these tests verify request/response CONTRACTS only.
Full end-to-end pipeline correctness is covered by test_stub_pipeline.py.

Endpoints covered:
  GET  /                                     (service root)
  GET  /api/v1/health                        (health check)
  POST /api/v1/analysis/start                (start pipeline)
  GET  /api/v1/analysis/{id}/status          (job status)
  GET  /api/v1/analysis/{id}/results         (job results)
  GET  /api/v1/analysis/{id}/webhook-events  (webhook event log)
  POST /api/v1/webhook/complete-dev          (Complete.dev webhook receiver)
  GET  /docs                                 (OpenAPI UI)
  GET  /openapi.json                         (OpenAPI schema)

All tests use the `api_client` fixture from conftest.py which:
  - Forces stub mode (no Deploy.AI credentials needed)
  - Provides an isolated job store per test
"""
import pytest


# ── Helper ───────────────────────────────────────────────────────────────────────

def _start_job(client, target: str = "OpenAI") -> str:
    """Create a job via the API and return its job_id."""
    r = client.post("/api/v1/analysis/start", json={"target": target})
    assert r.status_code == 202, f"Expected 202, got {r.status_code}: {r.text}"
    return r.json()["job_id"]


# ── Root & Documentation ───────────────────────────────────────────────────────────

class TestRootAndDocs:
    def test_root_returns_200(self, api_client):
        assert api_client.get("/").status_code == 200

    def test_root_has_service_name(self, api_client):
        data = api_client.get("/").json()
        assert "service" in data
        assert "ATHENA" in data["service"]

    def test_root_has_version_field(self, api_client):
        assert "version" in api_client.get("/").json()

    def test_root_has_stub_mode_flag(self, api_client):
        data = api_client.get("/").json()
        assert "stub_mode" in data
        assert data["stub_mode"] is True  # stub_mode fixture is active

    def test_root_has_docs_link(self, api_client):
        data = api_client.get("/").json()
        assert "docs" in data

    def test_openapi_json_available(self, api_client):
        r = api_client.get("/openapi.json")
        assert r.status_code == 200
        assert "paths" in r.json()

    def test_openapi_has_components(self, api_client):
        assert "components" in api_client.get("/openapi.json").json()

    def test_swagger_ui_available(self, api_client):
        assert api_client.get("/docs").status_code == 200


# ── Health Check ───────────────────────────────────────────────────────────────────

class TestHealthCheck:
    def test_returns_200(self, api_client):
        assert api_client.get("/api/v1/health").status_code == 200

    def test_status_is_ok(self, api_client):
        assert api_client.get("/api/v1/health").json()["status"] == "ok"

    def test_has_version_field(self, api_client):
        assert "version" in api_client.get("/api/v1/health").json()

    def test_has_timestamp_field(self, api_client):
        assert "timestamp" in api_client.get("/api/v1/health").json()

    def test_has_components_dict(self, api_client):
        data = api_client.get("/api/v1/health").json()
        assert "components" in data
        assert isinstance(data["components"], dict)

    def test_job_store_component_present(self, api_client):
        components = api_client.get("/api/v1/health").json()["components"]
        assert "job_store" in components

    def test_stub_mode_active_in_components(self, api_client):
        """With stub_mode fixture, health should report ACTIVE stub mode."""
        components = api_client.get("/api/v1/health").json()["components"]
        assert "stub_mode" in components
        val = components["stub_mode"].lower()
        assert "active" in val or "stub" in val


# ── POST /api/v1/analysis/start ──────────────────────────────────────────────────────

class TestStartAnalysis:
    def test_returns_202(self, api_client):
        r = api_client.post("/api/v1/analysis/start", json={"target": "OpenAI"})
        assert r.status_code == 202

    def test_response_contains_job_id(self, api_client):
        r = api_client.post("/api/v1/analysis/start", json={"target": "Stripe"})
        assert "job_id" in r.json()
        assert len(r.json()["job_id"]) > 0

    def test_stage_is_pending(self, api_client):
        r = api_client.post("/api/v1/analysis/start", json={"target": "Figma"})
        assert r.json()["stage"] == "PENDING"

    def test_status_is_pending(self, api_client):
        r = api_client.post("/api/v1/analysis/start", json={"target": "Anthropic"})
        assert r.json()["status"] == "pending"

    def test_target_echoed_in_response(self, api_client):
        r = api_client.post("/api/v1/analysis/start", json={"target": "Notion"})
        assert r.json()["target"] == "Notion"

    def test_created_at_in_response(self, api_client):
        r = api_client.post("/api/v1/analysis/start", json={"target": "Canva"})
        assert "created_at" in r.json()

    def test_message_in_response(self, api_client):
        r = api_client.post("/api/v1/analysis/start", json={"target": "Slack"})
        assert "message" in r.json()

    def test_accepts_type_field(self, api_client):
        r = api_client.post("/api/v1/analysis/start", json={
            "target": "Figma", "type": "company"
        })
        assert r.status_code == 202

    def test_accepts_depth_field(self, api_client):
        r = api_client.post("/api/v1/analysis/start", json={
            "target": "Figma", "depth": "deep"
        })
        assert r.status_code == 202

    def test_rejects_missing_target(self, api_client):
        assert api_client.post("/api/v1/analysis/start", json={}).status_code == 422

    def test_rejects_target_too_short(self, api_client):
        """AnalysisStartRequest.target has min_length=2."""
        r = api_client.post("/api/v1/analysis/start", json={"target": "X"})
        assert r.status_code == 422

    def test_rejects_invalid_analysis_type(self, api_client):
        r = api_client.post("/api/v1/analysis/start", json={
            "target": "TestCo", "type": "invalid_type"
        })
        assert r.status_code == 422

    def test_rejects_invalid_depth(self, api_client):
        r = api_client.post("/api/v1/analysis/start", json={
            "target": "TestCo", "depth": "ultra"
        })
        assert r.status_code == 422

    def test_two_starts_return_different_job_ids(self, api_client):
        r1 = api_client.post("/api/v1/analysis/start", json={"target": "Google"})
        r2 = api_client.post("/api/v1/analysis/start", json={"target": "Microsoft"})
        assert r1.json()["job_id"] != r2.json()["job_id"]


# ── GET /api/v1/analysis/{job_id}/status ────────────────────────────────────────────────

class TestGetStatus:
    def test_returns_200_for_known_job(self, api_client):
        job_id = _start_job(api_client)
        assert api_client.get(f"/api/v1/analysis/{job_id}/status").status_code == 200

    def test_response_echoes_job_id(self, api_client):
        job_id = _start_job(api_client)
        r = api_client.get(f"/api/v1/analysis/{job_id}/status")
        assert r.json()["job_id"] == job_id

    def test_response_has_stage_field(self, api_client):
        job_id = _start_job(api_client)
        assert "stage" in api_client.get(f"/api/v1/analysis/{job_id}/status").json()

    def test_stage_is_valid_enum_value(self, api_client):
        job_id = _start_job(api_client)
        valid = {"PENDING", "SCOUT", "ANALYST", "STRATEGY", "PRESENTER", "DONE", "ERROR"}
        stage = api_client.get(f"/api/v1/analysis/{job_id}/status").json()["stage"]
        assert stage in valid

    def test_response_has_progress_field(self, api_client):
        job_id = _start_job(api_client)
        r = api_client.get(f"/api/v1/analysis/{job_id}/status")
        assert "progress" in r.json()

    def test_response_has_message_field(self, api_client):
        job_id = _start_job(api_client)
        assert "message" in api_client.get(f"/api/v1/analysis/{job_id}/status").json()

    def test_response_has_status_field(self, api_client):
        job_id = _start_job(api_client)
        assert "status" in api_client.get(f"/api/v1/analysis/{job_id}/status").json()

    def test_returns_404_for_unknown_job(self, api_client):
        assert api_client.get("/api/v1/analysis/nonexistent-job-id/status").status_code == 404


# ── GET /api/v1/analysis/{job_id}/results ──────────────────────────────────────────────

class TestGetResults:
    def test_returns_200_for_known_job(self, api_client):
        job_id = _start_job(api_client)
        # Returns 200 whether running (status=running) or done (status=done)
        assert api_client.get(f"/api/v1/analysis/{job_id}/results").status_code == 200

    def test_response_has_job_id(self, api_client):
        job_id = _start_job(api_client)
        r = api_client.get(f"/api/v1/analysis/{job_id}/results")
        assert r.json()["job_id"] == job_id

    def test_response_has_target(self, api_client):
        job_id = _start_job(api_client, target="Slack")
        r = api_client.get(f"/api/v1/analysis/{job_id}/results")
        assert r.json()["target"] == "Slack"

    def test_response_has_stage_field(self, api_client):
        job_id = _start_job(api_client)
        assert "stage" in api_client.get(f"/api/v1/analysis/{job_id}/results").json()

    def test_response_has_status_field(self, api_client):
        job_id = _start_job(api_client)
        assert "status" in api_client.get(f"/api/v1/analysis/{job_id}/results").json()

    def test_returns_404_for_unknown_job(self, api_client):
        assert api_client.get("/api/v1/analysis/bad-job-id/results").status_code == 404


# ── GET /api/v1/analysis/{job_id}/webhook-events ───────────────────────────────────

class TestWebhookEventLog:
    def test_returns_200_for_known_job(self, api_client):
        job_id = _start_job(api_client)
        assert api_client.get(f"/api/v1/analysis/{job_id}/webhook-events").status_code == 200

    def test_response_has_job_id(self, api_client):
        job_id = _start_job(api_client)
        r = api_client.get(f"/api/v1/analysis/{job_id}/webhook-events")
        assert r.json()["job_id"] == job_id

    def test_events_list_empty_on_new_job(self, api_client):
        job_id = _start_job(api_client)
        r = api_client.get(f"/api/v1/analysis/{job_id}/webhook-events")
        assert r.json()["events"] == []

    def test_event_count_zero_on_new_job(self, api_client):
        job_id = _start_job(api_client)
        r = api_client.get(f"/api/v1/analysis/{job_id}/webhook-events")
        assert r.json()["event_count"] == 0

    def test_returns_404_for_unknown_job(self, api_client):
        assert api_client.get("/api/v1/analysis/no-such-job/webhook-events").status_code == 404


# ── POST /api/v1/webhook/complete-dev ───────────────────────────────────────────────

class TestWebhookReceiver:
    def test_accepts_event_for_known_job(self, api_client):
        job_id = _start_job(api_client)
        r = api_client.post("/api/v1/webhook/complete-dev", json={
            "job_id": job_id,
            "event_type": "agent_complete",
            "agent_id": "scout_001",
            "status": "success",
        })
        assert r.status_code == 200

    def test_response_ok_is_true(self, api_client):
        job_id = _start_job(api_client)
        r = api_client.post("/api/v1/webhook/complete-dev", json={
            "job_id": job_id, "event_type": "test"
        })
        assert r.json()["ok"] is True

    def test_recorded_true_for_known_job(self, api_client):
        job_id = _start_job(api_client)
        r = api_client.post("/api/v1/webhook/complete-dev", json={
            "job_id": job_id, "event_type": "agent_complete"
        })
        assert r.json()["recorded"] is True

    def test_accepts_event_for_unknown_job_with_200(self, api_client):
        """Webhook always returns 200 even for unknown job IDs (recorded=False)."""
        r = api_client.post("/api/v1/webhook/complete-dev", json={
            "job_id": "nonexistent-job", "event_type": "test"
        })
        assert r.status_code == 200

    def test_recorded_false_for_unknown_job(self, api_client):
        r = api_client.post("/api/v1/webhook/complete-dev", json={
            "job_id": "nonexistent-job", "event_type": "test"
        })
        assert r.json()["recorded"] is False

    def test_accepts_event_without_job_id(self, api_client):
        """Webhook accepts events with no job_id (recorded=False, ok=True)."""
        r = api_client.post("/api/v1/webhook/complete-dev", json={
            "event_type": "system_health", "status": "ok"
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_event_stored_in_webhook_log(self, api_client):
        """After posting a webhook event, it should appear in the event log."""
        job_id = _start_job(api_client)
        api_client.post("/api/v1/webhook/complete-dev", json={
            "job_id": job_id, "event_type": "agent_complete", "status": "success"
        })
        events_r = api_client.get(f"/api/v1/analysis/{job_id}/webhook-events")
        assert events_r.json()["event_count"] == 1
        assert events_r.json()["events"][0]["event_type"] == "agent_complete"
