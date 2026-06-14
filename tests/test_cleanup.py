from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.maintenance.cleanup import cleanup_temporary_data


class CleanupSession:
    def __init__(self, *, counts=None, rowcounts=None) -> None:
        self.counts = list(counts or [])
        self.rowcounts = list(rowcounts or [])
        self.executed = []
        self.commits = 0

    def scalar(self, statement):
        self.executed.append(statement)
        return self.counts.pop(0)

    def execute(self, statement):
        self.executed.append(statement)
        return SimpleNamespace(rowcount=self.rowcounts.pop(0))

    def commit(self) -> None:
        self.commits += 1


def test_cleanup_dry_run_only_counts_rows() -> None:
    db = CleanupSession(counts=[2, 3, 4, 5, 1, 1])

    result = cleanup_temporary_data(
        db,
        dry_run=True,
        now=datetime(2026, 6, 11, tzinfo=timezone.utc),
    )

    assert result.sessions == 2
    assert result.account_tokens == 3
    assert result.email_outbox == 4
    assert result.rate_limit_buckets == 5
    assert result.legacy_outbox_cancelled == 1
    assert result.abandoned_outbox_recovered == 1
    assert db.commits == 0
    assert len(db.executed) == 6


def test_cleanup_cancels_recovers_and_deletes_in_one_commit() -> None:
    db = CleanupSession(rowcounts=[1, 2, 3, 4, 5, 6])

    result = cleanup_temporary_data(
        db,
        now=datetime(2026, 6, 11, tzinfo=timezone.utc),
    )

    assert result.legacy_outbox_cancelled == 1
    assert result.abandoned_outbox_recovered == 2
    assert result.sessions == 3
    assert result.account_tokens == 4
    assert result.email_outbox == 5
    assert result.rate_limit_buckets == 6
    assert db.commits == 1
