"""Application-side client for the authentication authority process (R4, stage 2).
The application never reads or writes credentials or sessions. It asks the authority to log in,
validate a session, log out, activate, reset, or issue an operation proof. Every reply is either the
requested value or a neutral refusal."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from webdesk.auth.service import AuthError

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})


class AuthorityUnavailable(RuntimeError):
    """The authority process could not be reached. Fail closed: no session is trusted."""


class AuthorityClient:
    def __init__(self, base_url: str, secret: str, timeout: float = 5.0) -> None:
        parts = urllib.parse.urlsplit(base_url)
        if parts.scheme != "http" or parts.hostname not in LOOPBACK_HOSTS:
            raise ValueError("the authority client accepts only loopback http URLs")
        self._base = base_url.rstrip("/")
        self._secret = secret
        self._timeout = timeout

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(  # noqa: S310 - scheme and host are validated in __init__
            f"{self._base}{path}",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._secret}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310 - scheme and host are validated in __init__
                reply: dict[str, Any] = json.loads(response.read())
                return reply
        except urllib.error.HTTPError as exc:
            raise AuthError("refused") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AuthorityUnavailable("the authentication authority is unavailable") from exc

    def login(self, email: str, password: str) -> str:
        return str(self._post("/v1/login", {"email": email, "password": password})["session_token"])

    def activate(self, token: str, password: str) -> None:
        self._post("/v1/activate", {"token": token, "password": password})

    def reset_password(self, token: str, password: str) -> None:
        self._post("/v1/reset", {"token": token, "password": password})

    def validate_session(self, session_token: str) -> uuid.UUID:
        reply = self._post("/v1/validate", {"session_token": session_token})
        return uuid.UUID(str(reply["user_id"]))

    def logout(self, session_token: str) -> None:
        self._post("/v1/logout", {"session_token": session_token})

    def issue_operation_proof(
        self, session_token: str, operation: str, resource: uuid.UUID | None
    ) -> uuid.UUID:
        reply = self._post(
            "/v1/proof",
            {
                "session_token": session_token,
                "operation": operation,
                "resource_id": None if resource is None else str(resource),
            },
        )
        return uuid.UUID(str(reply["proof_id"]))
