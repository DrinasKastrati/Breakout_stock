from pathlib import Path
import argparse
import json
import sys

from . import demo
from .backtest import compare
from .engine import scan
from .models import Config
from .providers import Alpaca, import_csv
from .server import serve
from .storage import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description="Breakout Lab — 1D US-equity research screener")
    parser.add_argument("--db", help="Use a separate DB for each source/feed; demo DB is default for analysis")
    parser.add_argument("--config", default="config.json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="Load reproducible synthetic data")
    web = sub.add_parser("serve", help="Start local dashboard")
    web.add_argument("--port", type=int, default=8000)
    sync = sub.add_parser("sync", help="Download active US equities from Alpaca")
    sync.add_argument("--feed", choices=("sip", "iex"))
    sync.add_argument("--metadata", help="Optional curated instrument/sector/earnings CSV")
    sync.add_argument("--limit", type=int, help="Optional smoke-test sample; omit for full discovered universe")
    sync.add_argument("--years", type=int, default=3)
    importer = sub.add_parser("import", help="Import finalized daily OHLCV CSV")
    importer.add_argument("csv")
    importer.add_argument("--metadata", required=True)
    sub.add_parser("scan", help="Print current scan as JSON")
    bt = sub.add_parser("backtest", help="Compare breakout / volume / MACD variants")
    bt.add_argument("--start")
    bt.add_argument("--end")
    args = parser.parse_args(argv)
    try:
        path = Path(args.config)
        config = Config.from_dict(json.loads(path.read_text())) if path.exists() else Config()
        default_db = "data/alpaca.sqlite" if args.command == "sync" else "data/csv.sqlite" if args.command == "import" else "data/demo.sqlite"
        store = Store(args.db or default_db)
        if args.command == "demo":
            store.replace_dataset(*demo.dataset())
            print("Synthetic demo loaded. Run: python -m breakout_lab serve")
        elif args.command == "sync":
            if (args.limit is not None and args.limit < 1) or args.years < 1:
                raise ValueError("Limit and years must be positive")
            print("Downloading finalized daily history; refresh is committed atomically.", file=sys.stderr)
            store.replace_dataset(*Alpaca(args.feed).dataset(args.metadata, args.limit, args.years))
            print("Sync complete.")
        elif args.command == "import":
            store.replace_dataset(*import_csv(args.csv, args.metadata))
            print("CSV import complete.")
        elif args.command == "serve":
            assets, _, _ = store.load()
            if not assets:
                raise ValueError("No dataset. Run demo, sync or import first.")
            serve(store, config, args.port, path)
        else:
            assets, histories, metadata = store.load()
            if not assets:
                raise ValueError("No dataset. Run demo, sync or import first.")
            if args.command == "scan":
                benchmark = {b.date: b.close for b in histories.get(metadata.get("benchmark_symbol", "SPY"), [])}
                data = {"metadata": metadata, "rows": scan(assets, histories, config, benchmark, metadata.get("as_of"))}
            else:
                data = {"metadata": metadata, "variants": compare(assets, histories, config, args.start, args.end)}
            print(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
