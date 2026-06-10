from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmailMessage:
    recipient: str
    subject: str
    text_content: str
    html_content: str


@dataclass(frozen=True)
class EmailSendResult:
    provider_message_id: str | None = None


class EmailDeliveryError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class EmailService(Protocol):
    def send(self, message: EmailMessage) -> EmailSendResult: ...
