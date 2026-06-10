import logging
import signal
from threading import Event

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.email.outbox import claim_due_messages, process_outbox_message

logger = logging.getLogger(__name__)
shutdown_event = Event()


def run_once() -> int:
    with SessionLocal() as db:
        message_ids = claim_due_messages(db)

    for message_id in message_ids:
        try:
            with SessionLocal() as db:
                status = process_outbox_message(db, message_id)
            logger.info(
                "Email outbox item processed | id=%s | status=%s",
                message_id,
                status.value if status else "skipped",
            )
        except SQLAlchemyError:
            logger.exception(
                "Database error processing email outbox item | id=%s",
                message_id,
            )
    return len(message_ids)


def run_worker() -> None:
    logger.info(
        "Email worker started | provider=%s | batch_size=%s",
        settings.EMAIL_PROVIDER,
        settings.EMAIL_WORKER_BATCH_SIZE,
    )
    while not shutdown_event.is_set():
        try:
            processed = run_once()
        except SQLAlchemyError:
            logger.exception("Database error claiming email outbox items")
            processed = 0
        if processed == 0:
            shutdown_event.wait(settings.EMAIL_WORKER_POLL_SECONDS)
    logger.info("Email worker stopped")


def _request_shutdown(signum: int, _frame: object) -> None:
    logger.info("Email worker shutdown requested | signal=%s", signum)
    shutdown_event.set()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)
    run_worker()


if __name__ == "__main__":
    main()
