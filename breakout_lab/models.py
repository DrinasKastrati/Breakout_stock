from dataclasses import asdict, dataclass, fields
from datetime import date
import math


@dataclass(frozen=True)
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self):
        date.fromisoformat(self.date)
        values = (self.open, self.high, self.low, self.close, self.volume)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Bar contains non-finite values")
        if min(values[:4]) <= 0 or self.volume < 0:
            raise ValueError("Invalid price or volume")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("OHLC prices lie outside high/low")


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str
    exchange: str = "NASDAQ"
    kind: str = "common"
    sector: str | None = None
    market_cap: float | None = None
    earnings_date: str | None = None
    classification: str = "curated"


@dataclass(frozen=True)
class Config:
    lookback: int = 20
    min_history: int = 250
    min_price: float = 5
    min_dollar_volume: float = 20_000_000
    min_market_cap: float = 0
    allowed_sectors: tuple[str, ...] = ()
    excluded_symbols: tuple[str, ...] = ()
    earnings_blackout_days: int = 0
    volume_multiplier: float = 1.5
    breakout_atr_buffer: float = 0.1
    max_extension_atr: float = 1
    watch_distance_atr: float = 1
    max_base_width_atr: float = 8
    require_volume: bool = True
    require_macd: bool = True
    account_equity: float = 100_000
    risk_fraction: float = 0.005
    max_position_fraction: float = 0.15
    reward_risk: float = 2
    slippage_bps: float = 10
    commission_per_share: float = 0.005
    max_holding_bars: int = 20

    @classmethod
    def from_dict(cls, data):
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"Unknown settings: {', '.join(sorted(unknown))}")
        values = dict(data)
        for key in ("allowed_sectors", "excluded_symbols"):
            if key in values:
                if not isinstance(values[key], (list, tuple)) or not all(isinstance(x, str) for x in values[key]):
                    raise ValueError(f"{key} must be a list of strings")
                values[key] = tuple(values[key])
        c = cls(**values)
        ints = ("lookback", "min_history", "earnings_blackout_days", "max_holding_bars")
        bools = ("require_macd", "require_volume")
        for f in fields(cls):
            v = getattr(c, f.name)
            if f.name in bools:
                if type(v) is not bool:
                    raise ValueError(f"{f.name} must be boolean")
            elif f.name in ints:
                if type(v) is not int or v < 0:
                    raise ValueError(f"{f.name} must be a non-negative integer")
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                if not math.isfinite(v) or v < 0:
                    raise ValueError(f"{f.name} must be finite and non-negative")
            elif f.name not in ("allowed_sectors", "excluded_symbols"):
                raise ValueError(f"Invalid numeric setting: {f.name}")
        if c.lookback < 2 or c.min_history < max(60, c.lookback + 15) or c.max_holding_bars < 1:
            raise ValueError("Not enough indicator history or invalid holding period")
        if not 0 < c.risk_fraction <= 0.02 or not 0 < c.max_position_fraction <= 1:
            raise ValueError("Risk fraction must be in (0, .02]; position cap in (0, 1]")
        if c.account_equity <= 0 or c.reward_risk <= 0 or c.volume_multiplier <= 0:
            raise ValueError("Equity, reward/risk and volume multiplier must be positive")
        return c

    def to_dict(self):
        return asdict(self)
