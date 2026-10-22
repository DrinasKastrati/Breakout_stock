"""Free sentiment proxy: how the market received a news item, measured from daily bars."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
# Fixed before any data was examined; not user settings.
EXCESS_THRESHOLD = 0.02
RVOL_THRESHOLD = 1.5
VOLUME_LOOKBACK = 20


def reaction_day(created_at, sessions):
    local = datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone(NY)
    day = local.date().isoformat()
    if day in sessions and local.time() < time(16):
        return day
    later = [s for s in sessions if s > day]
    return min(later) if later else None


def day_reaction(bars, index_bars, day):
    k = next((n for n, b in enumerate(bars) if b.date == day), None)
    if k is None or k < VOLUME_LOOKBACK:
        return None
    previous = bars[k-1]
    now_index, then_index = index_bars.get(day), index_bars.get(previous.date)
    if not now_index or not then_index:
        return None
    excess = bars[k].close / previous.close - 1 - (now_index / then_index - 1)
    average = sum(b.volume for b in bars[k-VOLUME_LOOKBACK:k]) / VOLUME_LOOKBACK
    rvol = bars[k].volume / average if average else 0
    label = "none"
    if rvol >= RVOL_THRESHOLD and excess >= EXCESS_THRESHOLD:
        label = "positive"
    elif rvol >= RVOL_THRESHOLD and excess <= -EXCESS_THRESHOLD:
        label = "negative"
    return {"day": day, "excess": excess, "rvol": rvol, "label": label}


def symbol_reactions(articles, bars, index_bars):
    sessions = [b.date for b in bars]
    enriched = []
    for article in articles:
        day = reaction_day(article["created_at"], sessions)
        enriched.append({**article, "reaction_day": day, "reaction": day_reaction(bars, index_bars, day) if day else None})
    clear = [a["reaction"] for a in enriched if a["reaction"] and a["reaction"]["label"] != "none"]
    summary = max(clear, key=lambda r: r["day"]) if clear else {"label": "none"}
    return {"articles": enriched, "summary": dict(summary)}
