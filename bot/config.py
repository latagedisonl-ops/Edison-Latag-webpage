import os
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
    alpaca_key: str
    alpaca_secret: str
    alpaca_base_url: str
    telegram_token: str
    telegram_chat_id: int
    watchlist: list[str]
    timeframe: str
    risk_per_trade: float
    max_open_positions: int
    max_daily_loss: float
    execution_mode: str

    @classmethod
    def load(cls) -> "Config":
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
        )

    @property
    def is_paper(self) -> bool:
        return "paper" in self.alpaca_base_url
