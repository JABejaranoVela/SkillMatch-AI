from datetime import datetime, timezone

from fastapi import Request

from app.services.auth.rate_limits import client_ip_identifier, consume_rate_limit


class RateLimitSession:
    def __init__(self, count: int) -> None:
        self.count = count
        self.statement = None
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def scalar(self, statement):
        self.statement = statement
        return self.count

    def commit(self) -> None:
        self.commits += 1


def test_rate_limit_allows_until_limit_and_returns_retry_after() -> None:
    db = RateLimitSession(count=3)

    result = consume_rate_limit(
        action="login",
        identifiers=["127.0.0.1", "user@example.com"],
        limit=3,
        window_seconds=900,
        now=datetime(2026, 6, 11, 10, 7, 30, tzinfo=timezone.utc),
        session_factory=lambda: db,
    )

    assert result.allowed is True
    assert result.count == 3
    assert result.retry_after == 450
    assert db.commits == 1


def test_rate_limit_blocks_after_limit_without_exposing_identifiers() -> None:
    db = RateLimitSession(count=11)

    result = consume_rate_limit(
        action="login",
        identifiers=["203.0.113.10", "private@example.com"],
        limit=10,
        window_seconds=900,
        now=datetime(2026, 6, 11, 10, 7, 30, tzinfo=timezone.utc),
        session_factory=lambda: db,
    )

    parameters = str(db.statement.compile().params)
    assert result.allowed is False
    assert "private@example.com" not in parameters
    assert "203.0.113.10" not in parameters


def test_client_ip_ignores_forwarded_header_by_default() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"198.51.100.20")],
            "client": ("127.0.0.1", 50000),
        }
    )

    assert client_ip_identifier(request) == "127.0.0.1"
