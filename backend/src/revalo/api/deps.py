"""Who is making the request, and whether their role allows it."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from revalo.db.models import Role, User
from revalo.db.session import get_session
from revalo.services.auth import session_user

COOKIE = "revalo_session"

DbSession = Annotated[Session, Depends(get_session)]


def current_user(request: Request, session: DbSession) -> User | None:
    return session_user(session, request.cookies.get(COOKIE))


def require(role: Role) -> Callable[..., User]:
    def dependency(user: Annotated[User | None, Depends(current_user)]) -> User:
        if user is None:
            raise HTTPException(401, "Sign in to continue.")
        if Role(user.role).rank < role.rank:
            raise HTTPException(403, f"Only a {role.value} or above can do this.")
        return user

    return dependency


SignedIn = Annotated[User, Depends(require(Role.OPERATOR))]
ManagerUser = Annotated[User, Depends(require(Role.MANAGER))]
OwnerUser = Annotated[User, Depends(require(Role.OWNER))]

signed_in = Depends(require(Role.OPERATOR))
manager_only = Depends(require(Role.MANAGER))
