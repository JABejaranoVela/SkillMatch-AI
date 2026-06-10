import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EmailPayloadError(ValueError):
    pass


class EmailPayloadCipher:
    def __init__(self, key: str | bytes | None = None) -> None:
        raw_key = key or settings.EMAIL_PAYLOAD_ENCRYPTION_KEY.get_secret_value()
        encoded_key = raw_key.encode() if isinstance(raw_key, str) else raw_key
        try:
            self._fernet = Fernet(encoded_key)
        except (TypeError, ValueError) as exc:
            raise EmailPayloadError(
                "EMAIL_PAYLOAD_ENCRYPTION_KEY no es una clave Fernet valida"
            ) from exc

    def encrypt(self, payload: dict[str, Any]) -> str:
        serialized = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return self._fernet.encrypt(serialized).decode()

    def decrypt(self, encrypted_payload: str) -> dict[str, Any]:
        try:
            serialized = self._fernet.decrypt(encrypted_payload.encode())
            payload = json.loads(serialized)
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EmailPayloadError("No se pudo descifrar el payload de correo") from exc
        if not isinstance(payload, dict):
            raise EmailPayloadError("El payload de correo no es un objeto")
        return payload
