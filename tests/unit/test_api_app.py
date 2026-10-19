"""Phase A (C-1): HTTP app maps domain refusals to stable reasons and keeps auth replies neutral."""

from __future__ import annotations

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from webdesk.api.app import create_app
from webdesk.auth.service import AuthError
from webdesk.config import Settings
from webdesk.projects.service import ProjectServiceError
from webdesk.tokens.service import TokenError


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("WEBDESK_"):
            monkeypatch.delenv(key, raising=False)


def _client(extra: FastAPI | None = None) -> TestClient:
    # The engine is created lazily and never connects in these tests.
    engine = create_engine("postgresql+psycopg://unused@localhost:1/none")
    app = create_app(Settings(_env_file=None, env="test"), engine)
    if extra is not None:
        app.router.routes.extend(extra.router.routes)
    return TestClient(app, raise_server_exceptions=False)


def test_health_reports_ok_without_any_database_access() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _route_raising(exc: Exception) -> FastAPI:
    app = FastAPI()

    @app.get("/boom")
    def boom() -> None:
        raise exc

    return app


def test_a_project_refusal_returns_its_status_and_reason() -> None:
    response = _client(_route_raising(ProjectServiceError(403, "role_missing"))).get("/boom")
    assert response.status_code == 403
    assert response.json() == {"error": "role_missing"}


def test_authentication_refusals_are_neutral() -> None:
    response = _client(_route_raising(AuthError("invalid_credentials"))).get("/boom")
    assert response.status_code == 401
    assert response.json() == {"error": "request_refused"}


def test_token_refusals_are_neutral_and_never_expose_the_internal_reason() -> None:
    response = _client(_route_raising(TokenError("rate_limited"))).get("/boom")
    assert response.status_code == 400
    assert "rate_limited" not in response.text
    assert response.json() == {"error": "request_refused"}


def test_unhandled_errors_are_not_converted_into_domain_replies() -> None:
    response = _client(_route_raising(RuntimeError("secret detail"))).get("/boom")
    assert response.status_code == 500
    assert "secret detail" not in response.text
