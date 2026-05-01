import os
import secrets
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


@dataclass(frozen=True)
class Config:
    # Credentials (env-only)
    alpaca_key: str
    alpaca_secret: str
    alpaca_base_url: str
    telegram_token: str
    telegram_chat_id: int

    # Defaults for runtime settings (overridable from web UI)
    watchlist: list[str]
    timeframe: str
    risk_per_trade: float
    max_open_positions: int
    max_daily_loss: float
    execution_mode: str

    # Web server
    web_host: str
    web_port: int
    web_auth_token: str
    web_auth_token_was_generated: bool

    @classmethod
    def load(cls) -> "Config":
        token = os.getenv("WEB_AUTH_TOKEN", "").strip()
        generated = False
        if not token:
            token = secrets.token_urlsafe(24)
            generated = True
        return cls(
            alpaca_key=_req("ALPACA_API_KEY"),
            alpaca_secret=_req("ALPACA_API_SECRET"),
            alpaca_base_url=os.getenv(
                "ALPACA_BASE_URL", "https://paper-api.alpaca.markets"
            ),
            telegram_token=_req("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=int(_req("TELEGRAM_CHAT_ID")),
            watchlist=[s.strip().upper() for s in _req("WATCHLIST").split(",") if s.strip()],
            timeframe=os.getenv("TIMEFRAME", "15Min"),
            risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.01")),
            max_open_positions=int(os.getenv("MAX_OPEN_POSITIONS", "5")),
            max_daily_loss=float(os.getenv("MAX_DAILY_LOSS", "0.03")),
            execution_mode=os.getenv("EXECUTION_MODE", "manual").lower(),
            web_host=os.getenv("WEB_HOST", "127.0.0.1"),
            web_port=int(os.getenv("WEB_PORT", "8787")),
            web_auth_token=token,
            web_auth_token_was_generated=generated,
        )

    @property
    def is_paper(self) -> bool:
        return "paper" in self.alpaca_base_url
