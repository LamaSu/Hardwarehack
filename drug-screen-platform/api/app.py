"""
FastAPI app for the web UI. Loopback only: start it with ``scripts/serve.py``.
"""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.apothecary import router as apothecary_router
from api.routes import router
from api.schemas import RobotConfig
from flex_client import DEFAULT_PORT, FlexError
from protocol_generator import ProtocolError

LOCAL_ORIGINS = ["http://127.0.0.1:3000", "http://localhost:3000"]
LOCAL_HOSTS = {"127.0.0.1", "localhost"}


def create_app() -> FastAPI:
    """Build the app; robot settings start from FLEX_HOST / FLEX_PORT / FLEX_MOCK."""
    app = FastAPI(title="Drug screen platform", version="0.3.0")
    app.state.robot = RobotConfig(
        host=os.environ.get("FLEX_HOST", ""),
        port=int(os.environ.get("FLEX_PORT", DEFAULT_PORT)),
        mock=os.environ.get("FLEX_MOCK") == "1",
    )
    app.add_middleware(CORSMiddleware, allow_origins=LOCAL_ORIGINS, allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def local_browser_only(request: Request, call_next):
        # This API moves a robot, so other websites must not reach it through the
        # user's browser: a foreign Host means DNS rebinding, a foreign Origin or a
        # cross-site fetch means CSRF.
        # Requests proxied by the Next.js app carry the browser's Host in X-Forwarded-Host.
        forwarded = request.headers.get("x-forwarded-host", "").split(",")[0].strip()
        forwarded_host = forwarded.rsplit(":", 1)[0] if forwarded else None
        if request.url.hostname not in LOCAL_HOSTS or (forwarded_host and forwarded_host not in LOCAL_HOSTS):
            return JSONResponse({"detail": "Host not allowed"}, status_code=400)
        origin = request.headers.get("origin")
        if (origin and origin not in LOCAL_ORIGINS) or request.headers.get("sec-fetch-site") in ("cross-site", "same-site"):
            return JSONResponse({"detail": "Cross-site request refused"}, status_code=403)
        return await call_next(request)

    def error(status: int):
        async def handler(_request: Request, exc: Exception) -> JSONResponse:
            return JSONResponse({"detail": str(exc.args[0]) if exc.args else str(exc)}, status_code=status)
        return handler

    app.add_exception_handler(FlexError, error(502))
    app.add_exception_handler(ProtocolError, error(422))
    app.add_exception_handler(ValueError, error(422))
    app.add_exception_handler(FileNotFoundError, error(404))
    app.include_router(router)
    app.include_router(apothecary_router)
    return app


app = create_app()
