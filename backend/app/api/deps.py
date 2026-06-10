from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth import AuthSession
from app.models.user import User, UserStatus
from app.services.auth.sessions import (
    find_session,
    is_session_active,
    session_token_from_request,
    touch_session,
)


def get_current_session(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> AuthSession:
    auth_session = find_session(db, session_token_from_request(request))
    if auth_session is None or not is_session_active(auth_session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se pudieron validar las credenciales",
        )
    if auth_session.user.status == UserStatus.DISABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta esta deshabilitada",
        )
    touch_session(db, auth_session)
    return auth_session


def get_current_user(
    auth_session: Annotated[AuthSession, Depends(get_current_session)],
) -> User:
    return auth_session.user


def get_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if (
        current_user.status != UserStatus.ACTIVE
        or current_user.email_verified_at is None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debes verificar tu correo para acceder a esta funcionalidad",
        )
    return current_user


def get_pending_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.status != UserStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La cuenta ya esta verificada",
        )
    return current_user
