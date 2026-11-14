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


@router.post("/login")
async def login(body: LoginBody, request: Request, response: Response) -> dict:
    store = get_store(request)
    doc = store.read()
    auth = doc.get("auth", {})
    stored_hash = auth.get("password_hash")
    if stored_hash is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No password set; use /api/auth/setup")
    if auth.get("username") != body.username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    try:
        _ph.verify(stored_hash, body.password)
    except VerifyMismatchError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    signer = get_signer(request)
    token = signer.dumps(body.username)
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=_MAX_AGE,
    )
    return {"data": {"username": body.username}, "error": None}


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(_COOKIE_NAME)
    return {"data": None, "error": None}


@router.post("/setup")
async def setup(body: SetupBody, request: Request) -> dict:
    store = get_store(request)
    doc = store.read()
    if doc.get("auth", {}).get("password_hash") is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Password already set")

    hashed = _ph.hash(body.password)

    def _apply(d: dict) -> None:
        d["auth"]["username"] = body.username
        d["auth"]["password_hash"] = hashed

    store.mutate(_apply)
    return {"data": {"username": body.username}, "error": None}


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
    if len(body.new_password) < 8:
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
