from datetime import date, timedelta
import random

from .models import Asset, Bar


def dataset():
    """Deterministic fictitious securities, no fabricated quotes for real tickers."""
    rng = random.Random(2026)
    days, d = [], date(2024, 1, 2)
    while len(days) < 650:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += timedelta(days=1)
    names = [("DEMO-A", "Aurora Systems", "Teknik"), ("DEMO-B", "Beacon Energy", "Energi"),
             ("DEMO-C", "Cobalt Health", "Hälsovård"), ("DEMO-D", "Delta Robotics", "Industri"),
             ("DEMO-E", "Ember Retail", "Konsument"), ("DEMO-F", "Fjord Software", "Teknik"),
             ("DEMO-G", "Granite Materials", "Material"), ("DEMO-H", "Harbor Networks", "Teknik")]
    assets, histories = [], {}
    for s, (symbol, name, sector) in enumerate(names):
        assets.append(Asset(symbol, name, sector=sector, market_cap=(s+1)*1_500_000_000,
                            earnings_date=(d+timedelta(days=15)).isoformat()))
        bars, price = [], 35+s*9
        for i, day in enumerate(days):
            opening = price * (1+rng.gauss(0, .002))
            move = rng.gauss(.001, .007)
            # Periodic bases and expansion create reproducible historical test signals.
            cycle = i % 70
            if cycle in range(40, 60):
                move = rng.gauss(0, .0015)
            volume = 1_200_000 * rng.uniform(.8, 1.2)
            if cycle == 60:
                move, volume = .028, volume*2.5
            price = opening*(1+move)
            spread = opening*rng.uniform(.003, .007)
            bars.append(Bar(day, opening, max(opening, price)+spread, min(opening, price)-spread, price, volume))
        if s in (0, 1, 2):
            # Give the dashboard a breakout, a near-breakout and an overextended example.
            base_price = bars[-26].close
            for j in range(len(bars)-25, len(bars)-1):
                p = base_price * (1 + (j-(len(bars)-25))*.0002)
                bars[j] = Bar(days[j], p, p*1.004, p*.996, p, 1_200_000)
            resistance = max(b.high for b in bars[-21:-1])
            if s == 0:
                p, vol = resistance*1.008, 3_000_000
            elif s == 1:
                p, vol = resistance*.997, 1_000_000
            else:
                p, vol = resistance*1.06, 3_000_000
            bars[-1] = Bar(days[-1], resistance*.998, p*1.002, min(p, resistance)*.995, p, vol)
        histories[symbol] = bars
    benchmark, p = [], 100
    for day in days:
        opening = p
        p *= 1+rng.gauss(.0004, .004)
        benchmark.append(Bar(day, opening, max(opening,p)*1.003, min(opening,p)*.997, p, 5_000_000))
    histories["BENCHMARK"] = benchmark
    return assets, histories, {"source": "demo", "feed": "synthetic", "as_of": days[-1],
                                "benchmark_symbol": "BENCHMARK", "synthetic": True,
                                "notes": ["Fiktiva aktier och syntetiska priser. Ingen livehandel.",
                                          "Demokalendern innehåller vardagar, inte börsens helgdagar."]}
