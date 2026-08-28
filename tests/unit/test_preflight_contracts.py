"""Tests for stable preflight report domain contracts."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from chaos_agent.domain.preflight import (
    PreflightCheck,
    PreflightCheckStatus,
    PreflightOutcome,
    PreflightReport,
)

TARGET_ID = UUID("8d047f58-0dc7-4d61-a165-82b02edbc2c8")


def passing_check() -> PreflightCheck:
    return PreflightCheck(
        name="target_identity",
        status=PreflightCheckStatus.PASS,
        message="target identity matches",
        duration_ms=12,
    )


def test_passing_report_requires_all_checks_to_pass() -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    report = PreflightReport(
        outcome=PreflightOutcome.PASS,
        expected_target_id=TARGET_ID,
        target_label="dev-web.internal:22",
        started_at=now,
        completed_at=now + timedelta(milliseconds=12),
        checks=(passing_check(),),
    )

    assert report.schema_version == 1
    assert report.outcome is PreflightOutcome.PASS


def test_passing_report_rejects_failed_or_skipped_check() -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    failed = PreflightCheck(
        name="target_identity",
        status=PreflightCheckStatus.FAIL,
        message="target identity mismatch",
        duration_ms=10,
    )

    with pytest.raises(ValidationError, match="every check to pass"):
        PreflightReport(
            outcome=PreflightOutcome.PASS,
            expected_target_id=TARGET_ID,
            target_label="dev-web.internal:22",
            started_at=now,
            completed_at=now,
            checks=(failed,),
        )


def test_refused_report_requires_safe_category() -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)

    with pytest.raises(ValidationError, match="requires a category"):
        PreflightReport(
            outcome=PreflightOutcome.REFUSED,
            expected_target_id=TARGET_ID,
            target_label="dev-web.internal:22",
            started_at=now,
            completed_at=now,
            checks=(passing_check(),),
        )


def test_report_rejects_unknown_fields_and_invalid_time_order() -> None:
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    values = {
        "outcome": "error",
        "expected_target_id": TARGET_ID,
        "target_label": "dev-web.internal:22",
        "started_at": now,
        "completed_at": now - timedelta(seconds=1),
        "checks": (passing_check(),),
        "category": "connection_failed",
        "unexpected": "forbidden",
    }

    with pytest.raises(ValidationError):
        PreflightReport.model_validate(values)
