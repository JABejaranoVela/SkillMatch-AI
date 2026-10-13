from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.commands import email_diagnostics


def test_brevo_account_success_and_auth_failure(monkeypatch):
    monkeypatch.setattr(email_diagnostics, "settings", SimpleNamespace(
        EMAIL_PROVIDER="brevo", BREVO_API_KEY=SecretStr("example-test-value"),
        EMAIL_HTTP_TIMEOUT_SECONDS=2,
    ))
    for code in (200, 401):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(code, json={"email": "private@example.test"})
        client = httpx.Client(transport=httpx.MockTransport(
            respond
        ))
        result = email_diagnostics.check_brevo(client=client)
        assert result == {"ok": code == 200, "http_status": code}
        assert "private" not in str(result)
        assert requests[0].method == "GET"
        assert str(requests[0].url) == email_diagnostics.BREVO_ACCOUNT_URL


def test_brevo_network_error(monkeypatch):
    monkeypatch.setattr(email_diagnostics, "settings", SimpleNamespace(
        EMAIL_PROVIDER="brevo", BREVO_API_KEY=SecretStr("example-test-value"),
        EMAIL_HTTP_TIMEOUT_SECONDS=2,
    ))
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("offline", request=request))
    ))
    assert email_diagnostics.check_brevo(client=client) == {
        "ok": False, "reason": "network_error"
    }


def test_outbox_states_are_read_only(monkeypatch):
    monkeypatch.setattr(email_diagnostics, "settings", SimpleNamespace(
        EMAIL_WORKER_STALE_MINUTES=15,
    ))
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("""CREATE TABLE email_outbox (
            id INTEGER PRIMARY KEY, status VARCHAR(20), next_attempt_at DATETIME,
            last_attempt_at DATETIME, updated_at DATETIME
        )"""))
        now = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
        values = [
            (1, "failed", now, now, now),
            (2, "pending", now - timedelta(minutes=11), None, now),
            (3, "sending", now, now - timedelta(minutes=16), now),
            (4, "sent", now, now, now),
        ]
        for row in values:
            connection.execute(text("""INSERT INTO email_outbox
                (id, status, next_attempt_at, last_attempt_at, updated_at)
                VALUES (:id, :status, :next_at, :last_at, :updated_at)"""), dict(
                    zip(("id", "status", "next_at", "last_at", "updated_at"), row)
                ))
    with Session(engine) as db:
        result = email_diagnostics.check_outbox(db, now=now)
        assert result["failed_ids"] == [1]
        assert result["overdue_count"] == 1
        assert result["abandoned_count"] == 1
        assert result["counts"]["sent"] == 1
        assert not db.dirty
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM email_outbox")) == 4
