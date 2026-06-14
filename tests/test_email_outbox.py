from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import Settings
from app.models.auth import AccountToken, AccountTokenPurpose, EmailOutbox, EmailOutboxStatus
from app.models.user import UserStatus
from app.services.auth.account_tokens import hash_account_token, utc_now
from app.services.email.contracts import (
    EmailDeliveryError,
    EmailMessage,
    EmailSendResult,
)
from app.services.email.crypto import EmailPayloadCipher
from app.services.email.outbox import (
    RETRY_DELAYS,
    cancel_legacy_messages,
    claim_due_messages,
    enqueue_password_reset_email,
    enqueue_verification_email,
    process_outbox_message,
    recover_abandoned_messages,
)
from app.services.email.providers import (
    BrevoEmailService,
    ConsoleEmailService,
    FakeEmailService,
)
from app.services.email.templates import (
    build_password_reset_url,
    render_verification_email,
)

FERNET_KEY = "VVHWBaZ4O-F3O_MKPOPbtRm0T44ay8fjkfFKyhVX04c="


class OutboxSession:
    def __init__(self, *, outbox=None, account_token=None, scalar_values=None) -> None:
        self.outbox = outbox
        self.account_token = account_token
        self.scalar_values = scalar_values or []
        self.added = []
        self.commits = 0
        self.executed = []

    def add(self, item) -> None:
        if getattr(item, "id", None) is None:
            item.id = len(self.added) + 1
        self.added.append(item)

    def flush(self) -> None:
        for item in self.added:
            if getattr(item, "id", None) is None:
                item.id = len(self.added) + 1

    def get(self, model, _item_id):
        if model is EmailOutbox:
            return self.outbox
        if model is AccountToken:
            return self.account_token
        return None

    def scalars(self, _statement):
        return self.scalar_values

    def execute(self, statement):
        self.executed.append(statement)
        return SimpleNamespace(rowcount=2)

    def commit(self) -> None:
        self.commits += 1


class FailingEmailService:
    def __init__(self, *, retryable: bool) -> None:
        self.retryable = retryable

    def send(self, _message: EmailMessage) -> EmailSendResult:
        raise EmailDeliveryError("provider failed", retryable=self.retryable)


def make_outbox_and_token(*, attempts: int = 1, used: bool = False, expired: bool = False):
    now = utc_now()
    raw_token = "raw-verification-token"
    account_token = SimpleNamespace(
        id=7,
        purpose=AccountTokenPurpose.EMAIL_VERIFICATION,
        token_hash=hash_account_token(raw_token),
        used_at=now if used else None,
        expires_at=now - timedelta(minutes=1) if expired else now + timedelta(hours=1),
    )
    encrypted_payload = EmailPayloadCipher(FERNET_KEY).encrypt(
        {"version": 1, "verification_token": raw_token}
    )
    outbox = SimpleNamespace(
        id=11,
        account_token_id=7,
        recipient="user@example.com",
        template="email_verification",
        variables={"full_name": "Test User"},
        encrypted_payload=encrypted_payload,
        status=EmailOutboxStatus.SENDING,
        attempts=attempts,
        next_attempt_at=now,
        provider_message_id=None,
        last_error=None,
        last_attempt_at=now,
        updated_at=now,
    )
    return outbox, account_token


def make_password_reset_outbox_and_token():
    now = utc_now()
    raw_token = "raw-password-reset-token"
    user = SimpleNamespace(
        status=UserStatus.ACTIVE,
        email_verified_at=now,
    )
    account_token = SimpleNamespace(
        id=8,
        purpose=AccountTokenPurpose.PASSWORD_RESET,
        token_hash=hash_account_token(raw_token),
        used_at=None,
        expires_at=now + timedelta(hours=1),
        user=user,
    )
    outbox = SimpleNamespace(
        id=12,
        account_token_id=8,
        recipient="user@example.com",
        template="password_reset",
        variables={"full_name": "Test User"},
        encrypted_payload=EmailPayloadCipher(FERNET_KEY).encrypt(
            {"version": 1, "password_reset_token": raw_token}
        ),
        status=EmailOutboxStatus.SENDING,
        attempts=1,
        next_attempt_at=now,
        provider_message_id=None,
        last_error=None,
        last_attempt_at=now,
        updated_at=now,
    )
    return outbox, account_token


def test_encrypted_payload_never_contains_raw_token() -> None:
    cipher = EmailPayloadCipher(FERNET_KEY)

    encrypted = cipher.encrypt({"verification_token": "secret-token"})

    assert "secret-token" not in encrypted
    assert cipher.decrypt(encrypted)["verification_token"] == "secret-token"


def test_enqueue_verification_email_only_persists_encrypted_token() -> None:
    db = OutboxSession()
    user = SimpleNamespace(email="user@example.com", full_name="Test User")
    token = SimpleNamespace(id=7)

    outbox = enqueue_verification_email(
        db,
        user=user,
        account_token=token,
        raw_token="secret-token",
        cipher=EmailPayloadCipher(FERNET_KEY),
    )

    assert outbox.account_token_id == 7
    assert "secret-token" not in outbox.encrypted_payload
    assert outbox.variables == {"full_name": "Test User"}


def test_enqueue_password_reset_only_persists_encrypted_token() -> None:
    db = OutboxSession()
    user = SimpleNamespace(email="user@example.com", full_name="Test User")
    token = SimpleNamespace(id=8)

    outbox = enqueue_password_reset_email(
        db,
        user=user,
        account_token=token,
        raw_token="secret-reset-token",
        cipher=EmailPayloadCipher(FERNET_KEY),
    )

    assert outbox.template == "password_reset"
    assert "secret-reset-token" not in outbox.encrypted_payload
    assert outbox.variables == {"full_name": "Test User"}


def test_fake_email_service_captures_rendered_message() -> None:
    service = FakeEmailService()
    message = render_verification_email(
        recipient="user@example.com",
        full_name="User",
        raw_token="test-token",
    )

    result = service.send(message)

    assert result.provider_message_id == "fake-1"
    assert service.messages[0].recipient == "user@example.com"
    assert "test-token" in service.messages[0].text_content


def test_console_email_service_hides_content_in_production(caplog) -> None:
    caplog.set_level("INFO")
    service = ConsoleEmailService(environment="production")
    message = render_verification_email(
        recipient="user@example.com",
        full_name="User",
        raw_token="secret-token",
    )

    service.send(message)

    assert "user@example.com" not in caplog.text
    assert "secret-token" not in caplog.text
    assert "/verify-email" not in caplog.text
    assert message.subject not in caplog.text


def test_brevo_service_sends_expected_payload() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(201, json={"messageId": "brevo-123"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    service = BrevoEmailService(
        app_settings=Settings(
            _env_file=None,
            EMAIL_PROVIDER="brevo",
            BREVO_API_KEY="test-key",
            EMAIL_FROM="SkillMatch AI <noreply@example.com>",
        ),
        client=client,
    )

    result = service.send(
        EmailMessage(
            recipient="user@example.com",
            subject="Subject",
            text_content="Text",
            html_content="<p>Text</p>",
        )
    )

    assert result.provider_message_id == "brevo-123"
    assert captured["request"].headers["api-key"] == "test-key"
    assert b'"sender":{"email":"noreply@example.com","name":"SkillMatch AI"}' in (
        captured["request"].content
    )


@pytest.mark.parametrize(
    ("status_code", "retryable"),
    [(400, False), (429, True), (503, True)],
)
def test_brevo_classifies_http_errors(status_code: int, retryable: bool) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status_code, json={"message": "error"})
        )
    )
    service = BrevoEmailService(
        app_settings=Settings(
            _env_file=None,
            EMAIL_PROVIDER="brevo",
            BREVO_API_KEY="test-key",
        ),
        client=client,
    )

    with pytest.raises(EmailDeliveryError) as exc_info:
        service.send(
            EmailMessage(
                recipient="user@example.com",
                subject="Subject",
                text_content="Text",
                html_content="<p>Text</p>",
            )
        )

    assert exc_info.value.retryable is retryable


def test_successful_delivery_marks_sent_and_removes_payload() -> None:
    outbox, account_token = make_outbox_and_token()
    db = OutboxSession(outbox=outbox, account_token=account_token)

    status = process_outbox_message(
        db,
        outbox.id,
        email_service=FakeEmailService(),
        cipher=EmailPayloadCipher(FERNET_KEY),
    )

    assert status == EmailOutboxStatus.SENT
    assert outbox.encrypted_payload is None
    assert outbox.provider_message_id == "fake-1"


def test_worker_renders_password_reset_with_fake_service() -> None:
    outbox, account_token = make_password_reset_outbox_and_token()
    db = OutboxSession(outbox=outbox, account_token=account_token)
    service = FakeEmailService()

    status = process_outbox_message(
        db,
        outbox.id,
        email_service=service,
        cipher=EmailPayloadCipher(FERNET_KEY),
    )

    assert status == EmailOutboxStatus.SENT
    assert outbox.encrypted_payload is None
    assert service.messages[0].recipient == outbox.recipient
    assert build_password_reset_url("raw-password-reset-token") in (
        service.messages[0].text_content
    )


def test_worker_cancels_password_reset_after_token_invalidation() -> None:
    outbox, account_token = make_password_reset_outbox_and_token()
    account_token.used_at = utc_now()
    db = OutboxSession(outbox=outbox, account_token=account_token)

    status = process_outbox_message(
        db,
        outbox.id,
        email_service=FakeEmailService(),
        cipher=EmailPayloadCipher(FERNET_KEY),
    )

    assert status == EmailOutboxStatus.CANCELLED
    assert outbox.encrypted_payload is None


@pytest.mark.parametrize(("attempts", "delay"), list(enumerate(RETRY_DELAYS, start=1)))
def test_retryable_failure_uses_expected_delays(attempts: int, delay: timedelta) -> None:
    now = utc_now()
    outbox, account_token = make_outbox_and_token(attempts=attempts)
    db = OutboxSession(outbox=outbox, account_token=account_token)

    status = process_outbox_message(
        db,
        outbox.id,
        email_service=FailingEmailService(retryable=True),
        cipher=EmailPayloadCipher(FERNET_KEY),
        now=now,
    )

    assert status == EmailOutboxStatus.PENDING
    assert outbox.next_attempt_at == now + delay
    assert outbox.encrypted_payload is not None


def test_sixth_retryable_failure_becomes_failed() -> None:
    outbox, account_token = make_outbox_and_token(attempts=6)
    db = OutboxSession(outbox=outbox, account_token=account_token)

    status = process_outbox_message(
        db,
        outbox.id,
        email_service=FailingEmailService(retryable=True),
        cipher=EmailPayloadCipher(FERNET_KEY),
    )

    assert status == EmailOutboxStatus.FAILED
    assert outbox.encrypted_payload is None


def test_corrupt_encrypted_payload_fails_without_retry() -> None:
    outbox, account_token = make_outbox_and_token()
    outbox.encrypted_payload = "not-a-fernet-payload"
    db = OutboxSession(outbox=outbox, account_token=account_token)

    status = process_outbox_message(
        db,
        outbox.id,
        email_service=FakeEmailService(),
        cipher=EmailPayloadCipher(FERNET_KEY),
    )

    assert status == EmailOutboxStatus.FAILED
    assert outbox.encrypted_payload is None


@pytest.mark.parametrize(("used", "expired"), [(True, False), (False, True)])
def test_invalid_token_cancels_email(used: bool, expired: bool) -> None:
    outbox, account_token = make_outbox_and_token(used=used, expired=expired)
    db = OutboxSession(outbox=outbox, account_token=account_token)

    status = process_outbox_message(
        db,
        outbox.id,
        email_service=FakeEmailService(),
        cipher=EmailPayloadCipher(FERNET_KEY),
    )

    assert status == EmailOutboxStatus.CANCELLED
    assert outbox.encrypted_payload is None


def test_claim_marks_due_messages_as_sending() -> None:
    now = utc_now()
    messages = [
        SimpleNamespace(
            id=1,
            status=EmailOutboxStatus.PENDING,
            attempts=0,
            last_attempt_at=None,
            last_error="old",
            updated_at=None,
        )
    ]
    db = OutboxSession(scalar_values=messages)

    claimed = claim_due_messages(db, now=now)

    assert claimed == [1]
    assert messages[0].status == EmailOutboxStatus.SENDING
    assert messages[0].attempts == 1
    assert messages[0].last_attempt_at == now


def test_recover_abandoned_messages_returns_updated_count() -> None:
    db = OutboxSession()

    recovered = recover_abandoned_messages(db, now=utc_now())

    assert recovered == 2
    assert len(db.executed) == 1


def test_cancel_legacy_messages_returns_updated_count() -> None:
    db = OutboxSession()

    cancelled = cancel_legacy_messages(db, now=utc_now())

    assert cancelled == 2
    assert len(db.executed) == 1
