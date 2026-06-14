from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_active_user,
    get_current_session,
    get_current_user,
    get_pending_user,
)
from app.core.config import settings
from app.core.security import hash_password, verify_password, verify_password_and_update
from app.db.session import get_db
from app.models.auth import AccountTokenPurpose, AuthSession
from app.models.user import User, UserStatus
from app.schemas.auth import (
    AuthMessage,
    ForgotPasswordRequest,
    PasswordChange,
    ResetPasswordRequest,
    UserCreate,
    UserRead,
    UserUpdate,
    VerifyEmailRequest,
)
from app.services.auth.account_tokens import (
    create_email_verification_token,
    create_password_reset_token,
    find_email_verification_token,
    find_password_reset_token,
    invalidate_account_tokens,
    is_token_expired,
    password_reset_request_allowed,
    seconds_until_resend_allowed,
)
from app.services.auth.identifiers import normalize_email
from app.services.auth.rate_limits import client_ip_identifier, consume_rate_limit
from app.services.auth.sessions import (
    clear_session_cookie,
    create_session,
    find_session,
    revoke_session,
    revoke_user_sessions,
    session_token_from_request,
    set_session_cookie,
    utc_now,
)
from app.services.email.outbox import (
    enqueue_password_reset_email,
    enqueue_verification_email,
)

router = APIRouter()


REGISTRATION_MESSAGE = (
    "Si el registro es valido, recibiras un correo de verificacion"
)
FORGOT_PASSWORD_MESSAGE = (
    "Si existe una cuenta asociada a este correo, recibirás instrucciones "
    "para restablecer la contraseña."
)
INVALID_RESET_LINK_MESSAGE = "El enlace no es válido o ha caducado."


@router.post(
    "/register",
    response_model=AuthMessage,
    status_code=status.HTTP_202_ACCEPTED,
)
def register(
    payload: UserCreate,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> AuthMessage:
    normalized_email = normalize_email(payload.email)
    rate_limit = consume_rate_limit(
        action="register",
        identifiers=[client_ip_identifier(request)],
        limit=settings.REGISTER_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    if not rate_limit.allowed:
        return AuthMessage(message=REGISTRATION_MESSAGE)

    existing_user = db.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    if existing_user:
        return AuthMessage(message=REGISTRATION_MESSAGE)

    user = User(
        email=normalized_email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        status=UserStatus.PENDING,
        email_verified_at=None,
    )
    db.add(user)
    db.flush()
    account_token, raw_token = create_email_verification_token(db, user.id)
    enqueue_verification_email(
        db,
        user=user,
        account_token=account_token,
        raw_token=raw_token,
    )
    db.commit()
    db.refresh(user)
    return AuthMessage(message=REGISTRATION_MESSAGE)


@router.post("/verify-email", response_model=AuthMessage)
def verify_email(
    payload: VerifyEmailRequest,
    db: Annotated[Session, Depends(get_db)],
) -> AuthMessage:
    account_token = find_email_verification_token(db, payload.token)
    if account_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de verificacion no es valido",
        )
    if account_token.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El enlace de verificacion ya ha sido utilizado",
        )
    if is_token_expired(account_token):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="El enlace de verificacion ha caducado",
        )

    now = utc_now()
    user = account_token.user
    if user.status == UserStatus.DISABLED:
        account_token.used_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de verificacion no es valido para esta cuenta",
        )
    if user.status == UserStatus.PENDING:
        user.status = UserStatus.ACTIVE
        user.email_verified_at = now
    account_token.used_at = now
    db.commit()
    return AuthMessage(message="Correo verificado correctamente")


@router.post("/resend-verification", response_model=AuthMessage)
def resend_verification(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_pending_user)],
) -> AuthMessage:
    rate_limit = consume_rate_limit(
        action="resend_verification",
        identifiers=[str(current_user.id)],
        limit=settings.RESEND_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    if not rate_limit.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Debes esperar antes de solicitar otro correo",
            headers={"Retry-After": str(rate_limit.retry_after)},
        )

    retry_after = seconds_until_resend_allowed(db, current_user.id)
    if retry_after:
        response.headers["Retry-After"] = str(retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Debes esperar antes de solicitar otro correo",
            headers={"Retry-After": str(retry_after)},
        )

    account_token, raw_token = create_email_verification_token(
        db,
        current_user.id,
        invalidate_previous=True,
    )
    enqueue_verification_email(
        db,
        user=current_user,
        account_token=account_token,
        raw_token=raw_token,
    )
    db.commit()
    return AuthMessage(message="Correo de verificacion encolado")


@router.post(
    "/forgot-password",
    response_model=AuthMessage,
    status_code=status.HTTP_202_ACCEPTED,
)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> AuthMessage:
    normalized_email = normalize_email(payload.email)
    ip_rate_limit = consume_rate_limit(
        action="forgot_password_ip",
        identifiers=[client_ip_identifier(request)],
        limit=settings.FORGOT_PASSWORD_IP_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    email_rate_limit = consume_rate_limit(
        action="forgot_password_email",
        identifiers=[normalized_email],
        limit=settings.PASSWORD_RESET_MAX_REQUESTS_PER_HOUR,
        window_seconds=3600,
    )
    if not ip_rate_limit.allowed or not email_rate_limit.allowed:
        return AuthMessage(message=FORGOT_PASSWORD_MESSAGE)

    user = db.scalar(
        select(User)
        .where(func.lower(User.email) == normalized_email)
        .with_for_update()
    )
    if (
        user is None
        or user.status != UserStatus.ACTIVE
        or user.email_verified_at is None
        or not password_reset_request_allowed(db, user.id)
    ):
        return AuthMessage(message=FORGOT_PASSWORD_MESSAGE)

    account_token, raw_token = create_password_reset_token(db, user.id)
    enqueue_password_reset_email(
        db,
        user=user,
        account_token=account_token,
        raw_token=raw_token,
    )
    db.commit()
    return AuthMessage(message=FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=AuthMessage)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> AuthMessage:
    _enforce_rate_limit(
        action="reset_password",
        identifiers=[client_ip_identifier(request)],
        limit=settings.RESET_PASSWORD_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )

    account_token = find_password_reset_token(db, payload.token)
    if account_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_RESET_LINK_MESSAGE,
        )
    if account_token.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=INVALID_RESET_LINK_MESSAGE,
        )
    if is_token_expired(account_token):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=INVALID_RESET_LINK_MESSAGE,
        )

    user = account_token.user
    if user.status != UserStatus.ACTIVE or user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_RESET_LINK_MESSAGE,
        )

    now = utc_now()
    user.hashed_password = hash_password(payload.new_password)
    user.password_changed_at = now
    account_token.used_at = now
    invalidate_account_tokens(
        db,
        user.id,
        AccountTokenPurpose.PASSWORD_RESET,
        now=now,
        exclude_token_id=account_token.id,
    )
    revoke_user_sessions(db, user.id, now=now)
    db.commit()
    return AuthMessage(message="Contrasena restablecida correctamente")


@router.post("/login", response_model=UserRead)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
    request: Request,
    response: Response,
) -> User:
    normalized_email = normalize_email(form_data.username)
    _enforce_rate_limit(
        action="login",
        identifiers=[client_ip_identifier(request), normalized_email],
        limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS,
        window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_MINUTES * 60,
    )
    user = db.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    verified, upgraded_hash = verify_password_and_update(
        form_data.password,
        user.hashed_password,
    )
    if not verified:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if user.status == UserStatus.DISABLED:
        raise HTTPException(status_code=403, detail="La cuenta esta deshabilitada")

    now = utc_now()
    if upgraded_hash:
        user.hashed_password = upgraded_hash
    user.last_login_at = now
    previous_session = find_session(db, session_token_from_request(request))
    if previous_session is not None:
        revoke_session(previous_session, now)
    auth_session, raw_token = create_session(db, user.id, request)
    db.commit()
    db.refresh(user)
    db.refresh(auth_session)
    set_session_cookie(response, raw_token)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    auth_session = find_session(db, session_token_from_request(request))
    if auth_session is not None:
        revoke_session(auth_session)
        db.commit()
    clear_session_cookie(response)


@router.get("/session", response_model=UserRead)
def session(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user


@router.get("/me", response_model=UserRead)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.patch("/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    current_user.full_name = payload.full_name.strip()
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/change-password", response_model=AuthMessage)
def change_password(
    payload: PasswordChange,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_active_user)],
    current_session: Annotated[AuthSession, Depends(get_current_session)],
) -> AuthMessage:
    _enforce_rate_limit(
        action="change_password",
        identifiers=[str(current_user.id)],
        limit=settings.CHANGE_PASSWORD_RATE_LIMIT_PER_HOUR,
        window_seconds=3600,
    )
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo actualizar la contrasena",
        )
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contrasena debe ser diferente de la actual",
        )
    now = utc_now()
    current_user.hashed_password = hash_password(payload.new_password)
    current_user.password_changed_at = now
    invalidate_account_tokens(
        db,
        current_user.id,
        AccountTokenPurpose.PASSWORD_RESET,
        now=now,
    )
    revoke_user_sessions(
        db,
        current_user.id,
        now=now,
        except_session_id=current_session.id,
    )
    db.commit()
    return AuthMessage(message="Contrasena actualizada correctamente")


def _enforce_rate_limit(
    *,
    action: str,
    identifiers: list[str],
    limit: int,
    window_seconds: int,
) -> None:
    result = consume_rate_limit(
        action=action,
        identifiers=identifiers,
        limit=limit,
        window_seconds=window_seconds,
    )
    if result.allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Demasiadas solicitudes. Intentalo de nuevo mas tarde.",
        headers={"Retry-After": str(result.retry_after)},
    )
