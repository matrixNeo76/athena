"""
ATHENA - Job Store unit tests

Tests create_job, get_job, count_active_jobs, record/get_webhook_events,
and the memory-bounding cleanup behaviour.

Uses a module-scoped autouse fixture to reset _jobs/_locks between every
test, ensuring full isolation without inter-test state pollution.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.schemas import PipelineStage
from app.services.job_store import (
    _JOB_TTL_HOURS,
    _MAX_JOBS,
    _cleanup_old_jobs,
    _jobs,
    _locks,
    count_active_jobs,
    create_job,
    get_job,
    get_webhook_events,
    record_webhook_event,
)


# ── Module-level isolation fixture ─────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_store():
    """Reset job store before and after every test in this module."""
    _jobs.clear()
    _locks.clear()
    yield
    _jobs.clear()
    _locks.clear()


# ── create_job ──────────────────────────────────────────────────────────────────────

class TestCreateJob:
    def test_returns_dict_with_job_id(self):
        j = create_job("OpenAI")
        assert "job_id" in j
        assert len(j["job_id"]) > 0

    def test_two_jobs_have_unique_ids(self):
        j1 = create_job("OpenAI")
        j2 = create_job("Stripe")
        assert j1["job_id"] != j2["job_id"]

    def test_stage_starts_as_pending(self):
        j = create_job("OpenAI")
        assert j["stage"] == PipelineStage.PENDING

    def test_target_stored_correctly(self):
        j = create_job("Anthropic")
        assert j["target"] == "Anthropic"

    def test_depth_defaults_to_standard(self):
        j = create_job("X")
        assert j["depth"] == "standard"

    def test_custom_depth_stored(self):
        j = create_job("X", depth="deep")
        assert j["depth"] == "deep"

    def test_created_at_is_datetime(self):
        j = create_job("X")
        assert isinstance(j["created_at"], datetime)

    def test_updated_at_equals_created_at_initially(self):
        j = create_job("X")
        assert j["updated_at"] == j["created_at"]

    def test_all_result_fields_start_as_none(self):
        j = create_job("X")
        for field in [
            "scout_result", "analyst_result", "strategy_result",
            "presenter_result", "results", "error", "failed_at_stage",
        ]:
            assert j[field] is None, f"Expected '{field}' to be None on creation"

    def test_webhook_events_starts_as_empty_list(self):
        j = create_job("X")
        assert j["webhook_events"] == []

    def test_job_retrievable_after_creation(self):
        j = create_job("TestCo")
        fetched = get_job(j["job_id"])
        assert fetched is not None
        assert fetched["target"] == "TestCo"


# ── get_job ────────────────────────────────────────────────────────────────────────

class TestGetJob:
    def test_returns_none_for_unknown_id(self):
        assert get_job("nonexistent-id") is None

    def test_returns_job_for_known_id(self):
        j = create_job("Stripe")
        assert get_job(j["job_id"]) is not None

    def test_returned_job_matches_created_job(self):
        j = create_job("Figma")
        fetched = get_job(j["job_id"])
        assert fetched["job_id"] == j["job_id"]
        assert fetched["target"] == "Figma"

    def test_multiple_jobs_independently_retrievable(self):
        j1 = create_job("Alpha")
        j2 = create_job("Beta")
        assert get_job(j1["job_id"])["target"] == "Alpha"
        assert get_job(j2["job_id"])["target"] == "Beta"


# ── count_active_jobs ──────────────────────────────────────────────────────────────

class TestCountActiveJobs:
    def test_zero_on_empty_store(self):
        assert count_active_jobs() == 0

    def test_increments_per_job(self):
        for i in range(5):
            create_job(f"target-{i}")
        assert count_active_jobs() == 5

    def test_reflects_current_store_size(self):
        create_job("A")
        assert count_active_jobs() == 1
        create_job("B")
        assert count_active_jobs() == 2


# ── record_webhook_event / get_webhook_events ───────────────────────────────────────

class TestWebhookEvents:
    def test_events_empty_on_new_job(self):
        j = create_job("TestCo")
        assert get_webhook_events(j["job_id"]) == []

    def test_get_events_unknown_job_returns_none(self):
        assert get_webhook_events("nonexistent-job") is None

    def test_record_event_appended(self):
        j = create_job("TestCo")
        record_webhook_event(j["job_id"], {"event_type": "agent_start", "agent_id": "scout"})
        events = get_webhook_events(j["job_id"])
        assert len(events) == 1

    def test_recorded_event_contains_original_fields(self):
        j = create_job("TestCo")
        record_webhook_event(j["job_id"], {"event_type": "agent_complete", "status": "success"})
        ev = get_webhook_events(j["job_id"])[0]
        assert ev["event_type"] == "agent_complete"
        assert ev["status"] == "success"

    def test_record_adds_received_at_timestamp(self):
        j = create_job("TestCo")
        record_webhook_event(j["job_id"], {"event_type": "test"})
        ev = get_webhook_events(j["job_id"])[0]
        assert "received_at" in ev

    def test_multiple_events_appended_in_order(self):
        j = create_job("TestCo")
        for i in range(5):
            record_webhook_event(j["job_id"], {"event_type": f"event_{i}"})
        events = get_webhook_events(j["job_id"])
        assert len(events) == 5
        for i, ev in enumerate(events):
            assert ev["event_type"] == f"event_{i}"

    def test_record_unknown_job_returns_none(self):
        result = record_webhook_event("nonexistent-id", {"event_type": "test"})
        assert result is None

    def test_get_events_returns_copy_not_reference(self):
        """Mutating the returned list must NOT affect the store."""
        j = create_job("TestCo")
        record_webhook_event(j["job_id"], {"event_type": "test"})
        events = get_webhook_events(j["job_id"])
        events.clear()  # modify the copy
        assert len(get_webhook_events(j["job_id"])) == 1  # store unchanged

    def test_record_event_returns_updated_job(self):
        j = create_job("TestCo")
        updated = record_webhook_event(j["job_id"], {"event_type": "test"})
        assert updated is not None
        assert updated["job_id"] == j["job_id"]


# ── _cleanup_old_jobs ─────────────────────────────────────────────────────────────────

class TestCleanup:
    def test_no_jobs_removed_when_all_fresh(self):
        create_job("Fresh")
        removed = _cleanup_old_jobs()
        assert removed == 0

    def test_expired_job_removed(self):
        j = create_job("Old")
        # Manually backdate the job beyond TTL
        old_time = datetime.now(timezone.utc) - timedelta(hours=_JOB_TTL_HOURS + 1)
        _jobs[j["job_id"]]["created_at"] = old_time
        removed = _cleanup_old_jobs()
        assert removed >= 1
        assert get_job(j["job_id"]) is None

    def test_expired_job_lock_also_removed(self):
        j = create_job("Old")
        job_id = j["job_id"]
        old_time = datetime.now(timezone.utc) - timedelta(hours=_JOB_TTL_HOURS + 1)
        _jobs[job_id]["created_at"] = old_time
        _cleanup_old_jobs()
        assert job_id not in _locks

    def test_fresh_jobs_not_removed_by_cleanup(self):
        j = create_job("Fresh")
        _cleanup_old_jobs()
        assert get_job(j["job_id"]) is not None

    def test_cap_enforced_on_excess_jobs(self):
        """
        Creating _MAX_JOBS + 5 jobs should trigger FIFO eviction inside
        create_job() (which calls _cleanup_old_jobs on every creation),
        keeping the store at most at _MAX_JOBS.
        """
        for i in range(_MAX_JOBS + 5):
            create_job(f"target-{i}")
        assert count_active_jobs() <= _MAX_JOBS

    def test_cleanup_returns_count_of_removed_jobs(self):
        j = create_job("Old")
        old_time = datetime.now(timezone.utc) - timedelta(hours=_JOB_TTL_HOURS + 1)
        _jobs[j["job_id"]]["created_at"] = old_time
        removed = _cleanup_old_jobs()
        assert isinstance(removed, int)
        assert removed >= 1
