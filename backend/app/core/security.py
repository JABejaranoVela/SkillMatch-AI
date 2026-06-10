import bcrypt
from pwdlib import PasswordHash

argon2_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return argon2_password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    if hashed_password.startswith("$argon2"):
        return argon2_password_hash.verify(password, hashed_password)
    if not hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        return False
    try:
        return bcrypt.checkpw(password.encode(), hashed_password.encode())
    except ValueError:
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    if not hashed_password.startswith("$argon2"):
        return True
    return argon2_password_hash.current_hasher.check_needs_rehash(hashed_password)


def verify_password_and_update(
    password: str,
    hashed_password: str,
) -> tuple[bool, str | None]:
    if hashed_password.startswith("$argon2"):
        return argon2_password_hash.verify_and_update(password, hashed_password)
    if verify_password(password, hashed_password):
        return True, hash_password(password)
    return False, None
