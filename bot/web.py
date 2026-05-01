"""FastAPI web dashboard. Hosts the bot in the same process via lifespan."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Header, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .config import Config
from .runner import Runner
from .settings import SettingsStore

ROOT = Path(__file__).parent.parent
WEB_DIR = ROOT / "web"


def create_app(cfg: Config) -> FastAPI:
    settings_store = SettingsStore(cfg)
    runner = Runner(cfg, settings_store)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        task = asyncio.create_task(runner.run())
        try:
            yield
        finally:
            runner.stop()
            try:
                await asyncio.wait_for(task, timeout=10)
            except asyncio.TimeoutError:
                task.cancel()

    app = FastAPI(title="Trading Bot", lifespan=lifespan)

    def auth(request: Request, x_auth_token: str | None = Header(default=None)) -> None:
        if x_auth_token == cfg.web_auth_token:
            return
        client = request.client.host if request.client else None
        if client in ("127.0.0.1", "::1") and not cfg.web_auth_token:
            return
        raise HTTPException(status_code=401, detail="invalid or missing X-Auth-Token")

    @app.get("/api/status")
    async def status(_: None = Depends(auth)) -> dict[str, Any]:
        try:
            return await runner.status_payload()
        except Exception as e:
            logger.exception("status")
            raise HTTPException(500, str(e))

    @app.get("/api/settings")
    async def get_settings(_: None = Depends(auth)) -> dict[str, Any]:
        return settings_store.as_dict()

    @app.put("/api/settings")
    async def put_settings(payload: dict[str, Any], _: None = Depends(auth)) -> dict[str, Any]:
        try:
            settings_store.update(payload)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return settings_store.as_dict()

    @app.post("/api/halt")
    async def halt(_: None = Depends(auth)) -> dict[str, str]:
        return {"message": await runner._halt()}

    @app.post("/api/resume")
    async def resume(_: None = Depends(auth)) -> dict[str, str]:
        return {"message": await runner._resume()}

    @app.post("/api/closeall")
    async def closeall(_: None = Depends(auth)) -> dict[str, str]:
        return {"message": await runner._closeall()}

    @app.get("/api/signals")
    async def signals(_: None = Depends(auth)) -> list[dict[str, Any]]:
        return runner.signal_history()

    @app.get("/api/logs")
    async def logs(_: None = Depends(auth)) -> PlainTextResponse:
        log_path = ROOT / "bot.log"
        if not log_path.exists():
            return PlainTextResponse("(no log file yet)")
        text = log_path.read_text(errors="replace").splitlines()[-300:]
        return PlainTextResponse("\n".join(text))

    @app.get("/api/tutorial")
    async def tutorial() -> PlainTextResponse:
        p = ROOT / "SETUP.md"
        return PlainTextResponse(p.read_text() if p.exists() else "# Tutorial unavailable")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    return app
