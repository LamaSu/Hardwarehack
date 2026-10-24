"""
FastAPI app for the web UI. Loopback only: start it with ``scripts/serve.py``.
"""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import router
from api.schemas import RobotConfig
from flex_client import DEFAULT_PORT, FlexError
from protocol_generator import ProtocolError

LOCAL_ORIGINS = ["http://127.0.0.1:3000", "http://localhost:3000"]


def create_app() -> FastAPI:
    """Build the app; robot settings start from FLEX_HOST / FLEX_PORT / FLEX_MOCK."""
    app = FastAPI(title="Drug screen platform", version="0.3.0")
    app.state.robot = RobotConfig(
        host=os.environ.get("FLEX_HOST", ""),
        port=int(os.environ.get("FLEX_PORT", DEFAULT_PORT)),
        mock=os.environ.get("FLEX_MOCK") == "1",
    )
    app.add_middleware(CORSMiddleware, allow_origins=LOCAL_ORIGINS, allow_methods=["*"], allow_headers=["*"])

    def error(status: int):
        async def handler(_request: Request, exc: Exception) -> JSONResponse:
            return JSONResponse({"detail": str(exc.args[0]) if exc.args else str(exc)}, status_code=status)
        return handler

    app.add_exception_handler(FlexError, error(502))
    app.add_exception_handler(ProtocolError, error(422))
    app.add_exception_handler(ValueError, error(422))
    app.add_exception_handler(FileNotFoundError, error(404))
    app.include_router(router)
    return app


app = create_app()
