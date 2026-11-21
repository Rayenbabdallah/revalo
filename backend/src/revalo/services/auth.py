"""Accounts: password hashing, sign-in sessions and the people of a workshop.

Passwords are hashed with scrypt from the standard library. A session is a random
token kept in an HttpOnly cookie; the database only stores its SHA-256, so a leaked
database cannot be used to sign in.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from revalo.db.models import AuthSession, Role, User, Workshop

SESSION_DAYS = 30
MIN_PASSWORD = 8
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}


class AuthError(Exception):
    """A sign-in or account change that cannot be done, with a message for the person."""


# ---- Passwords -----------------------------------------------------------------------


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **_SCRYPT)
    b64 = base64.b64encode
    return f"scrypt${_SCRYPT['n']}${b64(salt).decode()}${b64(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        got = hashlib.scrypt(
            password.encode(),
            salt=base64.b64decode(salt),
            dklen=len(expected),
            n=int(n),
            r=_SCRYPT["r"],
            p=_SCRYPT["p"],
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, expected)


# A hash to check against when the email is unknown, so both cases take as long.
_DUMMY_HASH = hash_password(secrets.token_hex(8))


def _check_password_rules(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"Use at least {MIN_PASSWORD} characters for the password.")
    if len(password) > 200:
        raise AuthError("That password is too long.")


# ---- Sign-in throttle ----------------------------------------------------------------


class _Throttle:
    """Slows down password guessing: a few tries per email and address, then a pause."""

    def __init__(self, limit: int = 5, window_s: float = 15 * 60) -> None:
        self.limit = limit
        self.window_s = window_s
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        return [t for t in self._failures.get(key, []) if now - t < self.window_s]

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._recent(key, time.monotonic())) >= self.limit

    def failed(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            self._failures[key] = [*self._recent(key, now), now]

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)


throttle = _Throttle()


# ---- Users ---------------------------------------------------------------------------


def _clean_email(email: str) -> str:
    email = email.strip().lower()
    if "@" not in email or len(email) > 200 or " " in email:
        raise AuthError("Enter a valid email address.")
    return email


def user_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(User)) or 0


def create_user(
    session: Session, workshop: Workshop, email: str, name: str, role: Role, password: str
) -> User:
    email = _clean_email(email)
    name = name.strip()
    if not name:
        raise AuthError("Enter the person's name.")
    _check_password_rules(password)
    if session.scalars(select(User).where(User.email == email)).first():
        raise AuthError("Someone already has an account with this email.")
    user = User(
        workshop_id=workshop.id,
        email=email,
        name=name[:120],
        role=Role(role),
        password_hash=hash_password(password),
    )
    session.add(user)
    session.commit()
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    user = session.scalars(select(User).where(User.email == email.strip().lower())).first()
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash) or not user.active:
        return None
    return user


def _owners_left(session: Session, without: User) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == Role.OWNER, User.active.is_(True), User.id != without.id)
        )
        or 0
    )


@dataclass(frozen=True)
class UserChanges:
    name: str | None = None
    role: Role | None = None
    active: bool | None = None
    password: str | None = None


def update_user(session: Session, user: User, changes: UserChanges) -> User:
    loses_owner = (changes.role is not None and changes.role != Role.OWNER) or (
        changes.active is False
    )
    if user.role == Role.OWNER and loses_owner and _owners_left(session, user) == 0:
        raise AuthError("The workshop needs at least one active owner.")
    if changes.name is not None:
        if not changes.name.strip():
            raise AuthError("Enter the person's name.")
        user.name = changes.name.strip()[:120]
    if changes.role is not None:
        user.role = Role(changes.role)
    if changes.password is not None:
        _check_password_rules(changes.password)
        user.password_hash = hash_password(changes.password)
    if changes.active is not None:
        user.active = changes.active
    if changes.active is False or changes.password is not None:
        # A removed person, or a reset password, signs out everywhere.
        session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    session.commit()
    return user


def change_own_password(session: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise AuthError("The current password is not right.")
    _check_password_rules(new)
    user.password_hash = hash_password(new)
    session.commit()


def user_to_dict(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "active": user.active,
        "created_at": user.created_at.isoformat(),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


# ---- Sessions ------------------------------------------------------------------------


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def open_session(session: Session, user: User) -> str:
    """Start a sign-in and return the token for the cookie."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    session.add(
        AuthSession(
            token_hash=_token_hash(token),
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(days=SESSION_DAYS),
        )
    )
    user.last_login_at = now
    # Old sign-ins pile up otherwise; drop the expired ones while we are here.
    session.execute(delete(AuthSession).where(AuthSession.expires_at < now))
    session.commit()
    return token


def session_user(session: Session, token: str | None) -> User | None:
    if not token:
        return None
    row = session.get(AuthSession, _token_hash(token))
    if row is None or _aware(row.expires_at) < datetime.now(UTC):
        return None
    return row.user if row.user.active else None


def close_session(session: Session, token: str | None) -> None:
    if token:
        session.execute(delete(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
        session.commit()
