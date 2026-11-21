"""Sign-in, first-run setup, and the owner's list of people."""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from revalo.api.deps import COOKIE, DbSession, OwnerUser, SignedIn, current_user
from revalo.db.models import Role, User
from revalo.services.auth import (
    SESSION_DAYS,
    AuthError,
    UserChanges,
    authenticate,
    change_own_password,
    close_session,
    create_user,
    open_session,
    throttle,
    update_user,
    user_count,
    user_to_dict,
)
from revalo.services.jobs import default_workshop

router = APIRouter(tags=["accounts"])


class Setup(BaseModel):
    workshop_name: str | None = Field(None, max_length=200)
    name: str = Field(max_length=120)
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class Login(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class PasswordChange(BaseModel):
    current: str = Field(max_length=200)
    new: str = Field(max_length=200)


class NewUser(BaseModel):
    email: str = Field(max_length=200)
    name: str = Field(max_length=120)
    role: Role = Role.OPERATOR
    password: str = Field(max_length=200)


class UserPatch(BaseModel):
    name: str | None = Field(None, max_length=120)
    role: Role | None = None
    active: bool | None = None
    password: str | None = Field(None, max_length=200)


def _set_cookie(request: Request, response: Response, token: str) -> None:
    secure = request.url.scheme == "https" or os.getenv("REVALO_SECURE_COOKIES") == "1"
    response.set_cookie(
        COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def _me(session: DbSession, user: User | None) -> dict[str, Any]:
    shop = default_workshop(session)
    return {
        "user": user_to_dict(user) if user else None,
        "setup_required": user_count(session) == 0,
        "workshop": {"name": shop.name, "governorate": shop.governorate},
    }


@router.get("/v1/auth/me")
def me(session: DbSession, user: Annotated[User | None, Depends(current_user)]) -> dict[str, Any]:
    return _me(session, user)


@router.post("/v1/auth/setup", status_code=201)
def setup(body: Setup, request: Request, response: Response, session: DbSession) -> dict[str, Any]:
    """Create the first owner. Only possible while the workshop has no accounts."""
    if user_count(session) > 0:
        raise HTTPException(409, "This workshop is already set up. Sign in instead.")
    shop = default_workshop(session)
    if body.workshop_name and body.workshop_name.strip():
        shop.name = body.workshop_name.strip()
    try:
        user = create_user(session, shop, body.email, body.name, Role.OWNER, body.password)
    except AuthError as exc:
        raise HTTPException(422, str(exc)) from exc
    _set_cookie(request, response, open_session(session, user))
    return _me(session, user)


@router.post("/v1/auth/login")
def login(body: Login, request: Request, response: Response, session: DbSession) -> dict[str, Any]:
    key = f"{body.email.strip().lower()}|{request.client.host if request.client else ''}"
    if throttle.blocked(key):
        raise HTTPException(429, "Too many tries. Wait a few minutes and try again.")
    user = authenticate(session, body.email, body.password)
    if user is None:
        throttle.failed(key)
        raise HTTPException(401, "Wrong email or password.")
    throttle.reset(key)
    _set_cookie(request, response, open_session(session, user))
    return _me(session, user)


@router.post("/v1/auth/logout", status_code=204)
def logout(request: Request, response: Response, session: DbSession) -> None:
    close_session(session, request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")


@router.post("/v1/auth/password", status_code=204)
def change_password(body: PasswordChange, user: SignedIn, session: DbSession) -> None:
    try:
        change_own_password(session, user, body.current, body.new)
    except AuthError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/v1/users")
def list_users(owner: OwnerUser, session: DbSession) -> dict[str, Any]:
    people = session.scalars(select(User).where(User.workshop_id == owner.workshop_id))
    order = {Role.OWNER: 0, Role.MANAGER: 1, Role.OPERATOR: 2}
    ranked = sorted(people, key=lambda u: (not u.active, order[Role(u.role)], u.name.lower()))
    return {"users": [user_to_dict(u) for u in ranked]}


@router.post("/v1/users", status_code=201)
def add_user(body: NewUser, owner: OwnerUser, session: DbSession) -> dict[str, Any]:
    try:
        user = create_user(session, owner.workshop, body.email, body.name, body.role, body.password)
    except AuthError as exc:
        raise HTTPException(422, str(exc)) from exc
    return user_to_dict(user)


@router.patch("/v1/users/{user_id}")
def edit_user(
    user_id: str, body: UserPatch, owner: OwnerUser, session: DbSession
) -> dict[str, Any]:
    user = session.get(User, user_id)
    if user is None or user.workshop_id != owner.workshop_id:
        raise HTTPException(404, "No such person in this workshop.")
    try:
        update_user(session, user, UserChanges(**body.model_dump()))
    except AuthError as exc:
        raise HTTPException(422, str(exc)) from exc
    return user_to_dict(user)
