"""Read-only, privacy-safe checks for the email monitor."""

import argparse
import json
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.auth import EmailOutbox, EmailOutboxStatus

BREVO_ACCOUNT_URL = "https://api.brevo.com/v3/account"
OVERDUE_MINUTES = 10


def check_brevo(*, client: httpx.Client | None = None) -> dict[str, object]:
    key = settings.BREVO_API_KEY.get_secret_value().strip() if settings.BREVO_API_KEY else ""
    if settings.EMAIL_PROVIDER != "brevo" or not key:
        return {"ok": False, "reason": "brevo_not_configured"}
    try:
        if client is None:
            with httpx.Client(timeout=settings.EMAIL_HTTP_TIMEOUT_SECONDS) as http:
                response = http.get(BREVO_ACCOUNT_URL, headers={"api-key": key})
        else:
            response = client.get(BREVO_ACCOUNT_URL, headers={"api-key": key})
    except httpx.RequestError:
        return {"ok": False, "reason": "network_error"}
    return {"ok": response.status_code == 200, "http_status": response.status_code}


def check_outbox(db: Session, *, now: datetime | None = None) -> dict[str, object]:
    current = now or datetime.now(timezone.utc)
    counts = {status.value: 0 for status in EmailOutboxStatus}
    for status, count in db.execute(
        select(EmailOutbox.status, func.count()).group_by(EmailOutbox.status)
    ):
        counts[status.value] = count

    failed_ids = list(db.scalars(select(EmailOutbox.id).where(
        EmailOutbox.status == EmailOutboxStatus.FAILED
    ).order_by(EmailOutbox.id)))
    overdue = db.scalar(select(func.count()).select_from(EmailOutbox).where(
        EmailOutbox.status == EmailOutboxStatus.PENDING,
        EmailOutbox.next_attempt_at <= current - timedelta(minutes=OVERDUE_MINUTES),
    )) or 0
    stale_before = current - timedelta(minutes=settings.EMAIL_WORKER_STALE_MINUTES)
    abandoned = db.scalar(select(func.count()).select_from(EmailOutbox).where(
        EmailOutbox.status == EmailOutboxStatus.SENDING,
        (EmailOutbox.last_attempt_at <= stale_before)
        | (EmailOutbox.last_attempt_at.is_(None) & (EmailOutbox.updated_at <= stale_before)),
    )) or 0
    return {
        "ok": True,
        "counts": counts,
        "failed_ids": failed_ids,
        "overdue_count": overdue,
        "abandoned_count": abandoned,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=("api", "outbox"))
    args = parser.parse_args()
    if args.check == "api":
        result = check_brevo()
    else:
        try:
            with SessionLocal() as db:
                result = check_outbox(db)
        except Exception:
            # Database exception text may contain connection credentials.
            result = {"ok": False, "reason": "database_error"}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
