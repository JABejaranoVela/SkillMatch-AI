import logging
from email.utils import parseaddr

import httpx

from app.core.config import Settings, settings
from app.services.email.contracts import (
    EmailDeliveryError,
    EmailMessage,
    EmailSendResult,
    EmailService,
)

logger = logging.getLogger(__name__)


class ConsoleEmailService:
    def __init__(self, *, environment: str | None = None) -> None:
        self.environment = environment or settings.ENVIRONMENT

    def send(self, message: EmailMessage) -> EmailSendResult:
        if self.environment == "production":
            logger.info("EMAIL SENT TO CONSOLE | recipient=%s", message.recipient)
        else:
            logger.warning(
                "EMAIL SENT TO CONSOLE | recipient=%s | subject=%s | content=%s",
                message.recipient,
                message.subject,
                message.text_content,
            )
        return EmailSendResult()


class FakeEmailService:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> EmailSendResult:
        self.messages.append(message)
        return EmailSendResult(provider_message_id=f"fake-{len(self.messages)}")


class BrevoEmailService:
    def __init__(
        self,
        *,
        app_settings: Settings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = app_settings or settings
        self.client = client

    def send(self, message: EmailMessage) -> EmailSendResult:
        api_key = (
            self.settings.BREVO_API_KEY.get_secret_value().strip()
            if self.settings.BREVO_API_KEY
            else ""
        )
        if not api_key:
            raise EmailDeliveryError(
                "Brevo no esta configurado",
                retryable=False,
            )

        sender_name, sender_email = parseaddr(self.settings.EMAIL_FROM)
        if not sender_email:
            raise EmailDeliveryError(
                "EMAIL_FROM no contiene un email valido",
                retryable=False,
            )

        payload = {
            "sender": {
                "email": sender_email,
                **({"name": sender_name} if sender_name else {}),
            },
            "to": [{"email": message.recipient}],
            "subject": message.subject,
            "htmlContent": message.html_content,
            "textContent": message.text_content,
        }
        headers = {
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        }

        try:
            if self.client is not None:
                response = self.client.post(
                    self.settings.BREVO_API_URL,
                    headers=headers,
                    json=payload,
                )
            else:
                with httpx.Client(
                    timeout=self.settings.EMAIL_HTTP_TIMEOUT_SECONDS
                ) as client:
                    response = client.post(
                        self.settings.BREVO_API_URL,
                        headers=headers,
                        json=payload,
                    )
        except httpx.RequestError as exc:
            raise EmailDeliveryError(
                "Brevo no esta disponible",
                retryable=True,
            ) from exc

        if response.status_code >= 400:
            raise EmailDeliveryError(
                f"Brevo rechazo el correo con HTTP {response.status_code}",
                retryable=response.status_code == 429 or response.status_code >= 500,
                status_code=response.status_code,
            )

        try:
            response_payload = response.json()
        except ValueError:
            response_payload = {}
        message_id = (
            response_payload.get("messageId")
            if isinstance(response_payload, dict)
            else None
        )
        return EmailSendResult(provider_message_id=message_id)


def get_email_service(
    app_settings: Settings | None = None,
) -> EmailService:
    selected_settings = app_settings or settings
    if selected_settings.EMAIL_PROVIDER == "brevo":
        return BrevoEmailService(app_settings=selected_settings)
    if selected_settings.EMAIL_PROVIDER == "fake":
        return FakeEmailService()
    return ConsoleEmailService(environment=selected_settings.ENVIRONMENT)
