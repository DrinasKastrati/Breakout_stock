"""Static, personal dashboard. Real market data is always encrypted before export."""
from base64 import b64encode, b64decode
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from hashlib import pbkdf2_hmac, sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import re
import shutil

from . import demo
from .backtest import compare
from .engine import scan
from .indicators import calculate
from .providers import Alpaca

STATIC = Path(__file__).parent / "static"
ITERATIONS = 600_000
SCHEMA = 1


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def derive_key(passphrase, salt):
    if len(passphrase) < 20:
        raise ValueError("DASHBOARD_PASSPHRASE must contain at least 20 characters; use a randomly generated passphrase")
    return pbkdf2_hmac("sha256", passphrase.encode(), salt, ITERATIONS, 32)


def decrypt_file(root, manifest, path, passphrase):
    """Used only to validate a cached snapshot, never to persist plaintext."""
    if not re.fullmatch(r"data/[0-9a-f]{24}/(scan|backtest|charts/[0-9a-f]{24})\.bin", path):
        raise ValueError("Invalid encrypted snapshot path")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = derive_key(passphrase, b64decode(manifest["salt"]))
    raw = (Path(root) / path).read_bytes()
    return json.loads(AESGCM(key).decrypt(raw[:12], raw[12:], path.encode()))


def export_site(assets, histories, metadata, config, output, passphrase=None, repository=""):
    """Build in a temporary directory; leave the last good site intact on any failure."""
    if type(metadata.get("synthetic")) is not bool:
        raise ValueError("Dataset must explicitly identify synthetic or real data")
    encrypted = not metadata["synthetic"]
    if encrypted and not passphrase:
        raise ValueError("Real data requires DASHBOARD_PASSPHRASE; public plaintext export is disabled")
    if repository and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid GitHub repository name")
    salt = os.urandom(16) if encrypted else None
    if encrypted:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        cipher = AESGCM(derive_key(passphrase, salt))
    benchmark = {b.date: b.close for b in histories.get(metadata.get("benchmark_symbol", "SPY"), [])}
    rows = scan(assets, histories, config, benchmark, metadata.get("as_of"))
    counts = {s: sum(r["status"] == s for r in rows) for s in ("breakout", "watch", "extended", "inactive", "excluded")}
    # Synced_at changes on every request; don't let it cause a redundant deployment.
    meta = {k: v for k, v in metadata.items() if k != "synced_at"}
    start = (date.fromisoformat(metadata["as_of"]) - timedelta(days=365)).isoformat()
    payloads = {}
    for asset in assets:
        bars = histories.get(asset.symbol, [])
        path = "charts/" + sha256(asset.symbol.encode()).hexdigest()[:24]
        ind = calculate(bars)
        # Six decimals are ample for chart pixels; signals still use full precision.
        payloads[path] = {"symbol": asset.symbol,
                          "bars": [{k: round(v, 6) if isinstance(v, float) else v for k, v in asdict(b).items()} for b in bars[-100:]],
                          "indicators": {k: [round(x, 6) if x is not None else None for x in ind[k][-100:]]
                                         for k in ("sma50", "macd", "signal", "histogram")}}
    chart_ids = {a.symbol: "charts/" + sha256(a.symbol.encode()).hexdigest()[:24] for a in assets}
    payloads["scan"] = {"rows": rows, "counts": counts, "metadata": meta, "config": config.to_dict(),
                        "chart_ids": chart_ids}
    try:
        variants = compare(assets, histories, config, start, metadata["as_of"])
        # Summary covers every trade; only the latest 100 details are sent to the browser.
        for variant in variants:
            variant["trades"] = variant["trades"][-100:]
        payloads["backtest"] = {"variants": variants, "metadata": meta, "start": start, "end": metadata["as_of"]}
    except ValueError as error:
        payloads["backtest"] = {"error": str(error), "start": start, "end": metadata["as_of"]}
    digest = sha256(json_bytes({"schema": SCHEMA, "repository": repository, "encrypted": encrypted}))
    digest.update(static_hash().encode())
    for path, value in sorted(payloads.items()):
        digest.update(path.encode()); digest.update(json_bytes(value))
    for path in sorted(STATIC.iterdir()):
        if path.is_file():
            digest.update(path.name.encode()); digest.update(path.read_bytes())
    # Passphrase rotation also requires a new deployment, without exposing the passphrase.
    if encrypted:
        import hmac
        digest.update(hmac.new(passphrase.encode(), digest.digest(), "sha256").digest())
    version = digest.hexdigest()
    output = Path(output)
    old = output / "manifest.json"
    if old.exists():
        previous = json.loads(old.read_text())
        if previous.get("version") == version:
            # Check the cached payload before accepting it as usable.
            if encrypted:
                decrypt_file(output, previous, previous["scan"], passphrase)
            else:
                json.loads((output / previous["scan"]).read_text())
            return {"changed": False, "version": version, "as_of": metadata["as_of"], "mode": previous["mode"]}
    suffix = ".bin" if encrypted else ".json"
    prefix = "data/" + version[:24] + "/"
    manifest = {"schema": SCHEMA, "version": version, "mode": "encrypted" if encrypted else "demo",
                "as_of": metadata["as_of"], "built_at": datetime.now(timezone.utc).isoformat(),
                "repository": repository, "prefix": prefix, "suffix": suffix,
                "scan": prefix + "scan" + suffix, "backtest": prefix + "backtest" + suffix,
                "backtest_start": start, "backtest_end": metadata["as_of"]}
    if encrypted:
        manifest.update({"cipher": "AES-256-GCM", "kdf": "PBKDF2-SHA256", "iterations": ITERATIONS,
                         "salt": b64encode(salt).decode()})
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent, prefix="site-build-") as tmp:
        stage = Path(tmp) / "site"
        shutil.copytree(STATIC, stage)
        index = stage / "index.html"
        index.write_text(index.read_text().replace("<head>", '<head>\n  <meta name="breakout-mode" content="static">'), encoding="utf-8")
        (stage / ".nojekyll").touch()
        for name, value in payloads.items():
            path = prefix + name + suffix
            raw = json_bytes(value)
            if encrypted:
                nonce = os.urandom(12)
                raw = nonce + cipher.encrypt(nonce, raw, path.encode())
            destination = stage / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        (stage / "manifest.json").write_bytes(json_bytes(manifest))
        # Keep one previous generation so a browser can finish reading an older snapshot.
        previous_prefix = None
        if old.exists():
            previous = json.loads(old.read_text())
            old_prefix = previous.get("prefix", "")
            if re.fullmatch(r"data/[0-9a-f]{24}/", old_prefix) and (output / old_prefix).is_dir():
                shutil.copytree(output / old_prefix, stage / old_prefix)
                previous_prefix = old_prefix
        # Bound artifact storage; the currently published deployment is unaffected.
        if sum(p.stat().st_size for p in stage.rglob("*") if p.is_file()) > 180_000_000:
            if previous_prefix:
                shutil.rmtree(stage / previous_prefix)
            if sum(p.stat().st_size for p in stage.rglob("*") if p.is_file()) > 180_000_000:
                raise ValueError("Site exceeds the 180 MB artifact budget")
        backup = Path(tmp) / "previous"
        if output.exists():
            output.rename(backup)
        try:
            stage.rename(output)
        except OSError:
            if backup.exists():
                backup.rename(output)
            raise
    return {"changed": True, "version": version, "as_of": metadata["as_of"], "mode": manifest["mode"]}


def build_site(config, output, source="auto", repository="", limit=None, years=2, force=False):
    key, secret = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_API_SECRET")
    if source == "auto":
        if bool(key) != bool(secret):
            raise ValueError("Both Alpaca API secrets are required")
        source = "alpaca" if key and secret else "demo"
    passphrase = os.environ.get("DASHBOARD_PASSPHRASE")
    if source == "alpaca":
        # Fail before downloading if encryption is not configured.
        derive_key(passphrase or "", b"validation-only!")
        client = Alpaca("sip")
        # Holiday/retry runs need only a calendar call when the session is unchanged.
        old_path = Path(output) / "manifest.json"
        if old_path.exists() and not force:
            old = json.loads(old_path.read_text())
            if old.get("mode") == "encrypted" and old.get("schema") == SCHEMA:
                try:
                    previous_scan = decrypt_file(output, old, old["scan"], passphrase)
                except (ValueError, KeyError, OSError):
                    previous_scan = None
                except Exception as error:
                    from cryptography.exceptions import InvalidTag
                    if not isinstance(error, InvalidTag):
                        raise
                    previous_scan = None
                code_hash = static_hash()
                if (previous_scan and old.get("repository") == repository
                        and previous_scan["config"] == json.loads(json_bytes(config.to_dict()))
                        and old.get("code_hash") == code_hash and old.get("years") == years
                        and old.get("sample_limit") == limit and client.completed_session() == old["as_of"]):
                    return {"changed": False, "version": old["version"], "as_of": old["as_of"], "mode": old["mode"]}
        assets, histories, metadata = client.dataset(limit=limit, years=years)
        spy = histories.get("SPY", [])
        current = sum(bool(histories.get(a.symbol)) and histories[a.symbol][-1].date == metadata["as_of"] for a in assets)
        if not spy or spy[-1].date != metadata["as_of"] or current < len(assets) * 0.9:
            raise ValueError("Latest session is incomplete in the response; retaining the last published site")
    elif source == "demo":
        if (Path(output) / "manifest.json").exists():
            old = json.loads((Path(output) / "manifest.json").read_text())
            if old.get("mode") == "encrypted" and not force:
                raise ValueError("Refusing to replace real data with demo; use --force for an intentional reset")
        assets, histories, metadata = demo.dataset()
    else:
        raise ValueError("Unsupported site data source")
    result = export_site(assets, histories, metadata, config, output, passphrase, repository)
    if result["changed"]:
        path = Path(output) / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest.update({"code_hash": static_hash(), "years": years, "sample_limit": limit})
        path.write_bytes(json_bytes(manifest))
    return result


def static_hash():
    """A strategy/provider code change must invalidate the holiday/session shortcut."""
    digest = sha256()
    root = Path(__file__).parent
    for path in sorted(list(root.glob("*.py")) + list(STATIC.glob("*"))):
        if path.is_file():
            digest.update(path.name.encode()); digest.update(path.read_bytes())
    return digest.hexdigest()
