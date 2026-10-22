"""Freeze breakout demo output so other strategies cannot change it unnoticed."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from breakout_lab import demo
from breakout_lab.backtest import compare
from breakout_lab.engine import scan
from breakout_lab.models import Config

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = Path(__file__).with_name("golden") / "breakout_demo.json"


def snapshot():
    assets, histories, meta = demo.dataset()
    data = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    data.pop("metro", None)  # Metro settings cannot affect breakout output.
    config = Config.from_dict(data)
    benchmark = {b.date: b.close for b in histories.get(meta["benchmark_symbol"], [])}
    rows = scan(assets, histories, config, benchmark, meta["as_of"])
    counts = {s: sum(r["status"] == s for r in rows) for s in ("breakout", "watch", "extended", "inactive", "excluded")}
    value = {"scan": {"rows": rows, "counts": counts}, "compare": compare(assets, histories, config)}
    return json.loads(json.dumps(value, allow_nan=False))


if __name__ == "__main__":
    GOLDEN.parent.mkdir(exist_ok=True)
    GOLDEN.write_text(json.dumps(snapshot(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(GOLDEN)
