"""HTTP application (C-1, F05; ARCH §2, §11; D-6).

Error bodies carry a stable reason code. Authentication and token replies are neutral and never
reveal whether an account exists. Each request runs in one transaction through the runner (C-2),
so denial audits survive the refusal.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine

from webdesk.api.errors import DOMAIN_ERRORS, body_for, status_for
from webdesk.api.routes import router
from webdesk.config import Settings
from webdesk.storage.content_store import ContentStore


def create_app(settings: Settings, engine: Engine, store: ContentStore | None = None) -> FastAPI:
    app = FastAPI(title="WebDesk Gate 1 API", version="0.3.10.0", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.engine = engine
    app.state.store = store

    def _handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_for(exc), content=body_for(exc))

    for error_type in DOMAIN_ERRORS:
        app.add_exception_handler(error_type, _handler)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router)
    return app
