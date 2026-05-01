"""Entrypoint: starts the FastAPI dashboard, which runs the bot in-process."""
from __future__ import annotations

import uvicorn
from loguru import logger

from bot.config import Config
from bot.web import create_app


def main() -> None:
    cfg = Config.load()
    logger.add("bot.log", rotation="10 MB", retention=5)

    if cfg.web_auth_token_was_generated:
        logger.warning("=" * 60)
        logger.warning("WEB_AUTH_TOKEN not set — generated one for this run:")
        logger.warning(f"  {cfg.web_auth_token}")
        logger.warning("Add it to .env to keep it stable across restarts.")
        logger.warning("=" * 60)

    logger.info(f"Dashboard: http://{cfg.web_host}:{cfg.web_port}")
    app = create_app(cfg)
    uvicorn.run(app, host=cfg.web_host, port=cfg.web_port, log_level="info")


if __name__ == "__main__":
    main()
