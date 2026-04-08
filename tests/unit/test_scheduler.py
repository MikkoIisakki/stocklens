"""Unit tests for the scheduler job wiring.

Does NOT start the scheduler or touch the database.  Verifies that:
  - build_scheduler() registers exactly the two expected jobs
  - run_us_job / run_fi_job delegate to the correct ingest functions
"""

from unittest.mock import AsyncMock, MagicMock, patch

from app.jobs.scheduler import build_scheduler, run_fi_job, run_us_job


def test_build_scheduler_registers_two_jobs() -> None:
    scheduler = build_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert job_ids == {"fi_eod_ingest", "us_eod_ingest"}


def test_fi_job_cron_is_17_00_utc() -> None:
    scheduler = build_scheduler()
    fi_job = next(j for j in scheduler.get_jobs() if j.id == "fi_eod_ingest")
    # CronTrigger fields are accessible via .fields
    fields = {f.name: f for f in fi_job.trigger.fields}
    assert str(fields["hour"]) == "17"
    assert str(fields["minute"]) == "0"


def test_us_job_cron_is_21_30_utc() -> None:
    scheduler = build_scheduler()
    us_job = next(j for j in scheduler.get_jobs() if j.id == "us_eod_ingest")
    fields = {f.name: f for f in us_job.trigger.fields}
    assert str(fields["hour"]) == "21"
    assert str(fields["minute"]) == "30"


def _make_pool() -> MagicMock:
    pool = MagicMock()
    pool.close = AsyncMock()
    return pool


def test_run_us_job_calls_us_ingest() -> None:
    mock_pool = _make_pool()
    mock_ingest = AsyncMock()

    async def fake_create_pool(*_: object, **__: object) -> MagicMock:
        return mock_pool

    with (
        patch("app.jobs.scheduler.asyncpg.create_pool", side_effect=fake_create_pool),
        patch("app.jobs.scheduler.run_us_ingest", new=mock_ingest),
    ):
        run_us_job()

    mock_ingest.assert_awaited_once_with(mock_pool)
    mock_pool.close.assert_awaited_once()


def test_run_fi_job_calls_fi_ingest() -> None:
    mock_pool = _make_pool()
    mock_ingest = AsyncMock()

    async def fake_create_pool(*_: object, **__: object) -> MagicMock:
        return mock_pool

    with (
        patch("app.jobs.scheduler.asyncpg.create_pool", side_effect=fake_create_pool),
        patch("app.jobs.scheduler.run_fi_ingest", new=mock_ingest),
    ):
        run_fi_job()

    mock_ingest.assert_awaited_once_with(mock_pool)
    mock_pool.close.assert_awaited_once()


def test_misfire_grace_time_is_set() -> None:
    scheduler = build_scheduler()
    for job in scheduler.get_jobs():
        assert job.misfire_grace_time == 3600, f"{job.id} missing misfire_grace_time"
