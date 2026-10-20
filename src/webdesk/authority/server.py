"""Authentication authority process (R4, stage 2).
Run as a separate operating-system process: ``python -m webdesk.authority.server``. It connects with
its own restricted login role (``WEBDESK_AUTHORITY_DATABASE_URL``, a member of ``webdesk_authority``
only) and serves only the authentication and operation-proof operations over loopback HTTP.

Boundaries enforced here:
- Refuses to start when ``WEBDESK_ENV`` is ``production``. This process and its shared secret are
for local,
  non-production integration only; a production authority needs its own approved deployment and
  keys.
- Refuses any bind address other than loopback.
- Every request must carry the shared bearer secret (``WEBDESK_AUTHORITY_SECRET``, at least 32
characters).
- Accepts no user identifier from the caller. Identity is derived from the credential, the session
token or
  the proof, never from a supplied user ID.
- Refusals are neutral (HTTP 401, ``{"error": "refused"}``). Denial audits are committed; other work
rolls back.

This is a local integration transport. It is not a production authentication service."""

from __future__ import annotations

import hmac
import json
import os
import sys
import uuid
from collections.abc import Callable
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

from webdesk.auth.service import AuthError
from webdesk.authority import service as authority
from webdesk.identity.email import ContactEmailPolicy
from webdesk.ratelimit.limiter import Limit

ENV_DATABASE = "WEBDESK_AUTHORITY_DATABASE_URL"
ENV_SECRET = "WEBDESK_AUTHORITY_SECRET"  # noqa: S105 - the name of an environment variable
ENV_BIND = "WEBDESK_AUTHORITY_BIND"
ENV_PROFILE = "WEBDESK_ENV"
DEFAULT_BIND = "127.0.0.1:8766"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})
MAX_BODY_BYTES = 4096
MIN_SECRET_LENGTH = 32

LOGIN_LIMITS = authority.LoginLimits(
    account_ip_failures=Limit("login:account_ip", 10, timedelta(minutes=15)),
    ip_requests=Limit("login:ip", 200, timedelta(minutes=15)),
)


class ConfigurationError(RuntimeError):
    pass


def _policy() -> ContactEmailPolicy:
    allowed = os.environ.get("WEBDESK_EMAIL_DOMAIN_ALLOWLIST", "")
    denied = os.environ.get("WEBDESK_EMAIL_ALIAS_DENYLIST", "")
    return ContactEmailPolicy(
        allowed_domains=frozenset(d.strip().lower() for d in allowed.split(",") if d.strip()),
        alias_denylist=frozenset(a.strip().lower() for a in denied.split(",") if a.strip()),
    )


def _body_field(body: dict[str, Any], name: str) -> str:
    value = body.get(name)
    if not isinstance(value, str) or not value:
        raise AuthError("malformed_request")
    return value


def _login(conn: Connection, body: dict[str, Any], client_ip: str) -> dict[str, Any]:
    token = authority.login(
        conn,
        email=_body_field(body, "email"),
        password=_body_field(body, "password"),
        client_ip=client_ip,
        policy=_policy(),
        limits=LOGIN_LIMITS,
    )
    return {"session_token": token}


def _activate(conn: Connection, body: dict[str, Any], _ip: str) -> dict[str, Any]:
    authority.activate(
        conn, token=_body_field(body, "token"), password=_body_field(body, "password")
    )
    return {"ok": True}


def _reset(conn: Connection, body: dict[str, Any], _ip: str) -> dict[str, Any]:
    authority.reset_password(
        conn, token=_body_field(body, "token"), password=_body_field(body, "password")
    )
    return {"ok": True}


def _validate(conn: Connection, body: dict[str, Any], _ip: str) -> dict[str, Any]:
    user = authority.validate_session(conn, _body_field(body, "session_token"))
    return {"user_id": str(user)}


def _logout(conn: Connection, body: dict[str, Any], _ip: str) -> dict[str, Any]:
    authority.logout(conn, _body_field(body, "session_token"))
    return {"ok": True}


def _proof(conn: Connection, body: dict[str, Any], _ip: str) -> dict[str, Any]:
    resource_raw = body.get("resource_id")
    resource = None if resource_raw is None else uuid.UUID(_body_field(body, "resource_id"))
    proof = authority.issue_operation_proof(
        conn,
        session_token=_body_field(body, "session_token"),
        operation=_body_field(body, "operation"),
        resource=resource,
    )
    return {"proof_id": str(proof)}


ROUTES: dict[str, Callable[[Connection, dict[str, Any], str], dict[str, Any]]] = {
    "/v1/login": _login,
    "/v1/activate": _activate,
    "/v1/reset": _reset,
    "/v1/validate": _validate,
    "/v1/logout": _logout,
    "/v1/proof": _proof,
}


class AuthorityServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], engine: Engine, secret: str) -> None:
        super().__init__(address, _Handler)
        self.engine = engine
        self.secret = secret


class _Handler(BaseHTTPRequestHandler):
    server: AuthorityServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def _reply(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        expected = f"Bearer {self.server.secret}"
        supplied = self.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied.encode(), expected.encode()):
            self._reply(401, {"error": "refused"})
            return
        route = ROUTES.get(self.path)
        if route is None:
            self._reply(404, {"error": "refused"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._reply(400, {"error": "refused"})
            return
        if length < 0 or length > MAX_BODY_BYTES:
            self._reply(413, {"error": "refused"})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("body must be an object")
        except ValueError:
            self._reply(400, {"error": "refused"})
            return
        try:
            payload = _run(
                self.server.engine, lambda conn: route(conn, body, self.client_address[0])
            )
        except AuthError as exc:
            # Denial audits were written in the same transaction and are committed by _run.
            cause = (
                ""
                if exc.__cause__ is None
                else f" cause={str(exc.__cause__).splitlines()[0][:300]}"
            )
            _diagnose(self.path, f"refused: {exc.reason}{cause}")
            self._reply(401, {"error": "refused"})
            return
        except (ValueError, KeyError, DBAPIError) as exc:
            # Malformed input, or a database refusal (for example a session that is not live).
            _diagnose(self.path, f"{type(exc).__name__}: {str(exc).splitlines()[0]}")
            self._reply(401, {"error": "refused"})
            return
        self._reply(200, payload)


def _diagnose(path: str, detail: str) -> None:
    """Operator diagnostics on stderr: the route and the refusal class only, never credentials or
    tokens."""
    sys.stderr.write(f"authority {path} {detail}\n")
    sys.stderr.flush()


def _run(engine: Engine, operation: Callable[[Connection], dict[str, Any]]) -> dict[str, Any]:
    """Commit on success and on a neutral refusal (so denial audits persist); roll back
    otherwise."""
    connection = engine.connect()
    transaction = connection.begin()
    try:
        result = operation(connection)
    except AuthError:
        transaction.commit()
        raise
    except BaseException:
        transaction.rollback()
        raise
    else:
        transaction.commit()
        return result
    finally:
        connection.close()


def build_server(bind: str, database_url: str, secret: str) -> AuthorityServer:
    host, _, port_text = bind.rpartition(":")
    if host not in LOOPBACK_HOSTS:
        raise ConfigurationError("the authority binds to loopback only in this increment")
    if len(secret) < MIN_SECRET_LENGTH:
        raise ConfigurationError(f"{ENV_SECRET} must be at least {MIN_SECRET_LENGTH} characters")
    engine = create_engine(database_url)
    return AuthorityServer((host, int(port_text)), engine, secret)


def main() -> None:
    if os.environ.get(ENV_PROFILE, "").lower() == "production":
        raise ConfigurationError("the test authority process must not run in production")
    database_url = os.environ.get(ENV_DATABASE)
    secret = os.environ.get(ENV_SECRET)
    if not database_url or not secret:
        raise ConfigurationError(f"{ENV_DATABASE} and {ENV_SECRET} are required")
    server = build_server(os.environ.get(ENV_BIND, DEFAULT_BIND), database_url, secret)
    sys.stdout.write(f"authority listening on {server.server_address}\n")
    sys.stdout.flush()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        server.engine.dispose()


if __name__ == "__main__":
    main()
