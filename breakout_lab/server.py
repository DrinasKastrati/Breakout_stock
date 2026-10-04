from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from dataclasses import asdict
import csv
import io
import json
import threading

from .backtest import compare
from .engine import scan
from .indicators import calculate
from .models import Config

STATIC = Path(__file__).parent / "static"


class Application:
    def __init__(self, store, config, config_path=None):
        self.store, self.config, self.config_path = store, config, config_path
        self.lock = threading.Lock()

    def snapshot(self):
        assets, histories, meta = self.store.load()
        with self.lock:
            config = self.config
        return assets, histories, meta, config

    def scan(self):
        assets, histories, meta, config = self.snapshot()
        benchmark = {b.date: b.close for b in histories.get(meta.get("benchmark_symbol", "SPY"), [])}
        rows = scan(assets, histories, config, benchmark, meta.get("as_of"))
        counts = {status: sum(r["status"] == status for r in rows) for status in ("breakout", "watch", "extended", "inactive", "excluded")}
        return {"rows": rows, "counts": counts, "metadata": meta, "config": config.to_dict()}

    def update_config(self, changes):
        with self.lock:
            config = Config.from_dict({**self.config.to_dict(), **changes})
            if self.config_path:
                path = Path(self.config_path)
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps(config.to_dict(), indent=2)+"\n", encoding="utf-8")
                tmp.replace(path)
            self.config = config
        return config


def handler(app):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(STATIC), **kwargs)

        def end_headers(self):
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            super().end_headers()

        def send_json(self, data, status=200):
            raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def safe_request(self):
            host = self.headers.get("Host", "")
            expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if host not in expected:
                self.send_json({"error": "Local host required"}, 403)
                return False
            origin = self.headers.get("Origin")
            if origin and origin not in {f"http://{h}" for h in expected}:
                self.send_json({"error": "Same-origin request required"}, 403)
                return False
            return True

        def do_GET(self):
            if not self.safe_request():
                return
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            try:
                if parsed.path == "/api/health":
                    from . import __version__
                    self.send_json({"status": "ok", "version": __version__})
                elif parsed.path == "/api/scan":
                    self.send_json(app.scan())
                elif parsed.path == "/api/bars":
                    symbol = params.get("symbol", [""])[0]
                    _, histories, _, _ = app.snapshot()
                    if symbol not in histories:
                        self.send_json({"error": "Unknown symbol"}, 404)
                        return
                    bars = histories[symbol]
                    ind = calculate(bars)
                    self.send_json({"symbol": symbol, "bars": [asdict(b) for b in bars[-100:]],
                                    "indicators": {k: v[-100:] for k, v in ind.items()}})
                elif parsed.path == "/api/backtest":
                    assets, histories, meta, config = app.snapshot()
                    start, end = params.get("start", [None])[0], params.get("end", [None])[0]
                    from datetime import date
                    for value in (start, end):
                        if value:
                            date.fromisoformat(value)
                    self.send_json({"variants": compare(assets, histories, config, start, end), "metadata": meta})
                elif parsed.path == "/api/export":
                    buffer = io.StringIO(newline="")
                    columns = ["symbol", "date", "status", "score", "close", "resistance", "relative_volume", "entry_reference", "stop", "target", "shares", "risk_usd"]
                    writer = csv.DictWriter(buffer, columns, extrasaction="ignore")
                    writer.writeheader()
                    for row in app.scan()["rows"]:
                        clean = {k: ("'"+v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v) for k, v in row.items()}
                        writer.writerow(clean)
                    raw = buffer.getvalue().encode("utf-8-sig")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition", 'attachment; filename="breakout-scan.csv"')
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                elif parsed.path in ("/", "/index.html", "/app.js", "/data-client.js", "/style.css"):
                    super().do_GET()
                else:
                    self.send_json({"error": "Not found"}, 404)
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
            except Exception:
                self.send_json({"error": "Internal server error; check dataset and server log"}, 500)
                raise

        def do_HEAD(self):
            if not self.safe_request():
                return
            if urlparse(self.path).path not in ("/", "/index.html", "/app.js", "/data-client.js", "/style.css"):
                self.send_error(404)
                return
            super().do_HEAD()

        def do_POST(self):
            if not self.safe_request():
                return
            if self.path != "/api/config":
                self.send_json({"error": "Not found"}, 404)
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.send_json({"error": "JSON content type required"}, 415)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 16384:
                    raise ValueError("Invalid request size")
                changes = json.loads(self.rfile.read(size))
                if not isinstance(changes, dict):
                    raise ValueError("Settings must be an object")
                config = app.update_config(changes)
                self.send_json(config.to_dict())
            except (ValueError, TypeError) as error:
                self.send_json({"error": str(error)}, 400)

    return Handler


def serve(store, config, port=8000, config_path=None):
    app = Application(store, config, config_path)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler(app))
    print(f"Breakout Lab: http://127.0.0.1:{server.server_port} — Ctrl+C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
