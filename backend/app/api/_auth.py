"""Env-gated HTTP basic auth.

The production threat model puts auth at Caddy (PR 11). This module is the
in-process fallback so accidentally running the bare backend on a LAN doesn't
leave write endpoints wide open.

Off by default — set `WHOHOLDS_REQUIRE_AUTH=1` to turn on, with credentials
in `WHOHOLDS_AUTH_USER` / `WHOHOLDS_AUTH_PASS`.
"""
from __future__ import annotations

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_security = HTTPBasic(auto_error=False)


def require_auth(
    credentials: HTTPBasicCredentials | None = Depends(_security),  # noqa: B008
) -> str | None:
    if os.environ.get("WHOHOLDS_REQUIRE_AUTH") != "1":
        return None
    user = os.environ.get("WHOHOLDS_AUTH_USER", "")
    pwd = os.environ.get("WHOHOLDS_AUTH_PASS", "")
    if not user or not pwd:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="auth enabled but credentials env not set",
        )
    if credentials is None or not (
        secrets.compare_digest(credentials.username, user)
        and secrets.compare_digest(credentials.password, pwd)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username
