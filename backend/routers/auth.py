from __future__ import annotations

import logging

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from backend.routers.deps import _COOKIE_NAME, _MAX_AGE, SessionUser, get_store, get_signer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

_ph = PasswordHasher()


class LoginBody(BaseModel):
    username: str
    password: str


class SetupBody(BaseModel):
    username: str
    password: str


MIN_PASSWORD_LENGTH = 8


def _set_session(request: Request, response: Response, username: str) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=get_signer(request).dumps(username),
        httponly=True,
        samesite="lax",
        max_age=_MAX_AGE,
    )


@router.get("/status")
async def auth_status(request: Request) -> dict:
    """Public: tells the login page whether the household login still has to be created."""
    auth = get_store(request).read().get("auth", {})
    return {"data": {"needs_setup": auth.get("password_hash") is None}, "error": None}


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response) -> dict:
    store = get_store(request)
    doc = store.read()
    auth = doc.get("auth", {})
    stored_hash = auth.get("password_hash")
    if stored_hash is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No login exists yet. Create one first.")
    if auth.get("username") != body.username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        _ph.verify(stored_hash, body.password)
    except (VerifyMismatchError, InvalidHashError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    _set_session(request, response, body.username)
    return {"data": {"username": body.username}, "error": None}


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(_COOKIE_NAME)
    return {"data": None, "error": None}


@router.post("/setup")
async def setup(body: SetupBody, request: Request, response: Response) -> dict:
    """First run only: create the household login, then sign in."""
    store = get_store(request)
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose a username.")
    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )
    hashed = _ph.hash(body.password)
    created = False

    def _apply(d: dict) -> None:
        nonlocal created
        # Checked inside the lock so two simultaneous setups cannot both win.
        if d.setdefault("auth", {}).get("password_hash") is not None:
            return
        d["auth"]["username"] = username
        d["auth"]["password_hash"] = hashed
        created = True

    store.mutate(_apply)
    if not created:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A login already exists. Sign in instead.")
    _set_session(request, response, username)
    return {"data": {"username": username}, "error": None}


class PasswordBody(BaseModel):
    current_password: str
    new_password: str


class UsernameBody(BaseModel):
    username: str


@router.post("/password")
async def change_password(body: PasswordBody, request: Request, _user: SessionUser) -> dict:
    store = get_store(request)
    stored_hash = store.read().get("auth", {}).get("password_hash")
    try:
        if stored_hash is None:
            raise VerifyMismatchError()
        _ph.verify(stored_hash, body.current_password)
    except (VerifyMismatchError, InvalidHashError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")
    if len(body.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters.",
        )
    new_hash = _ph.hash(body.new_password)

    def _apply(d: dict) -> None:
        d["auth"]["password_hash"] = new_hash

    store.mutate(_apply)
    return {"data": {"changed": True}, "error": None}


@router.post("/username")
async def change_username(
    body: UsernameBody, request: Request, response: Response, _user: SessionUser
) -> dict:
    new_name = body.username.strip()
    if not new_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username cannot be empty.")
    store = get_store(request)

    def _apply(d: dict) -> None:
        d["auth"]["username"] = new_name

    store.mutate(_apply)
    token = get_signer(request).dumps(new_name)
    response.set_cookie(
        key=_COOKIE_NAME, value=token, httponly=True, samesite="lax", max_age=_MAX_AGE
    )
    return {"data": {"username": new_name}, "error": None}
