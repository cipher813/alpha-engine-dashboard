"""Regression tests pinning the staging/daily_closes/ prefix in
``health_checker.py`` + ``pages/4_System_Health.py``.

Coordinated with alpha-engine-data PR #112 (writer + in-repo readers
migrated) + alpha-engine-research PR #49 (research reader migrated).
Hard-cutover, no fallback (per ``feedback_no_silent_fails``).

The dashboard's two daily_closes touch points are pure observability —
neither blocks production trading — but a regression here would silently
report ``status=missing`` on the daily_closes health check + show 0
daily_closes objects in the System Health UI after the 7-day staging
lifecycle eats the legacy parquets, masking actual outages.
"""

from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return (Path(__file__).parent.parent / path).read_text()


def test_health_checker_uses_staging_prefix():
    src = _read("health_checker.py")
    # Both today + yesterday probes must point at staging/
    assert 'f"staging/daily_closes/{today_str_dc}.parquet"' in src, (
        "health_checker.py daily_closes today probe is not on staging/. "
        "Hard-cutover requires this exact f-string per the no-fallback "
        "contract."
    )
    assert 'f"staging/daily_closes/{yesterday_dc}.parquet"' in src, (
        "health_checker.py daily_closes yesterday probe is not on staging/. "
        "Hard-cutover requires this exact f-string per the no-fallback "
        "contract."
    )


def test_health_checker_no_legacy_prefix():
    """Belt-and-suspenders: forbid the legacy string anywhere in
    health_checker.py source."""
    src = _read("health_checker.py")
    assert "predictor/daily_closes" not in src, (
        "health_checker.py contains 'predictor/daily_closes' — the prefix "
        "was migrated to staging/ on 2026-04-29. No fallback per "
        "feedback_no_silent_fails."
    )


def test_system_health_page_uses_staging_prefix():
    src = _read("pages/4_System_Health.py")
    assert '"staging/daily_closes/"' in src, (
        "pages/4_System_Health.py is not counting staging/daily_closes/ "
        "objects. The 2026-04-29 prefix migration requires this exact "
        "string."
    )


def test_system_health_page_no_legacy_prefix():
    src = _read("pages/4_System_Health.py")
    assert "predictor/daily_closes" not in src, (
        "pages/4_System_Health.py contains 'predictor/daily_closes' — "
        "the prefix was migrated to staging/. No fallback."
    )
