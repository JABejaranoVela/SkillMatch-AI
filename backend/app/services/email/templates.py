from html import escape
from urllib.parse import urlencode

from app.core.config import settings
from app.services.email.contracts import EmailMessage


EMAIL_VERIFICATION_TEMPLATE = "email_verification"
PASSWORD_RESET_TEMPLATE = "password_reset"


def build_verification_url(raw_token: str) -> str:
    query = urlencode({"token": raw_token})
    return f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?{query}"


def build_password_reset_url(raw_token: str) -> str:
    query = urlencode({"token": raw_token})
    return f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?{query}"


def render_verification_email(
    *,
    recipient: str,
    full_name: str | None,
    raw_token: str,
) -> EmailMessage:
    verification_url = build_verification_url(raw_token)
    greeting = f"Hola {full_name.strip()}," if full_name and full_name.strip() else "Hola,"
    text_content = (
        f"{greeting}\n\n"
        "Verifica tu correo para activar tu cuenta de SkillMatch AI:\n"
        f"{verification_url}\n\n"
        "El enlace caduca en 24 horas y solo puede utilizarse una vez."
    )
    html_content = (
        "<!doctype html><html><body>"
        f"<p>{escape(greeting)}</p>"
        "<p>Verifica tu correo para activar tu cuenta de SkillMatch AI.</p>"
        f'<p><a href="{escape(verification_url, quote=True)}">'
        "Verificar correo</a></p>"
        "<p>El enlace caduca en 24 horas y solo puede utilizarse una vez.</p>"
        "</body></html>"
    )
    return EmailMessage(
        recipient=recipient,
        subject="Verifica tu correo en SkillMatch AI",
        text_content=text_content,
        html_content=html_content,
    )


def render_password_reset_email(
    *,
    recipient: str,
    full_name: str | None,
    raw_token: str,
) -> EmailMessage:
    reset_url = build_password_reset_url(raw_token)
    ttl_minutes = settings.PASSWORD_RESET_TTL_MINUTES
    greeting = f"Hola {full_name.strip()}," if full_name and full_name.strip() else "Hola,"
    text_content = (
        f"{greeting}\n\n"
        "Hemos recibido una solicitud para restablecer tu contrasena:\n"
        f"{reset_url}\n\n"
        f"El enlace caduca en {ttl_minutes} minutos y solo puede utilizarse una vez. "
        "Si no solicitaste este cambio, puedes ignorar este correo."
    )
    html_content = (
        "<!doctype html><html><body>"
        f"<p>{escape(greeting)}</p>"
        "<p>Hemos recibido una solicitud para restablecer tu contrasena.</p>"
        f'<p><a href="{escape(reset_url, quote=True)}">'
        "Restablecer contrasena</a></p>"
        f"<p>El enlace caduca en {ttl_minutes} minutos y solo puede utilizarse una vez.</p>"
        "<p>Si no solicitaste este cambio, puedes ignorar este correo.</p>"
        "</body></html>"
    )
    return EmailMessage(
        recipient=recipient,
        subject="Restablece tu contrasena de SkillMatch AI",
        text_content=text_content,
        html_content=html_content,
    )
