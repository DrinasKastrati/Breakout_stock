"use strict";
// GitHub Pages reads generated files; the local Python server keeps its API.
(() => {
  const isStatic = Boolean(document.querySelector('meta[name="breakout-mode"][content="static"]'));
  const site = { manifest: null, key: null, passphrase: null, scan: null };
  const utf8 = new TextEncoder();
  const base = new URL("./", window.location.href);
  async function deriveKey(passphrase, manifest) {
    if (manifest.kdf !== "PBKDF2-SHA256" || manifest.cipher !== "AES-256-GCM" || manifest.iterations !== 600000) {
      throw new Error("Okänt format för krypterad data.");
    }
    const salt = Uint8Array.from(atob(manifest.salt), c => c.charCodeAt(0));
    if (salt.length !== 16) throw new Error("Ogiltigt krypteringsformat.");
    const material = await crypto.subtle.importKey("raw", utf8.encode(passphrase), "PBKDF2", false, ["deriveKey"]);
    return crypto.subtle.deriveKey({ name: "PBKDF2", salt, iterations: manifest.iterations, hash: "SHA-256" },
      material, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
  }
  async function decryptJSON(raw, key, path) {
    const bytes = new Uint8Array(raw);
    const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: bytes.slice(0, 12),
      additionalData: utf8.encode(path), tagLength: 128 }, key, bytes.slice(12));
    return JSON.parse(new TextDecoder().decode(plain));
  }
  async function getJSON(path) {
    const response = await fetch(new URL(path, base), { cache: "no-store" });
    if (!response.ok) throw new Error("Analysen kunde inte hämtas. Försök uppdatera sidan.");
    return response.json();
  }
  async function read(path, key = site.key) {
    if (!/^data\/[0-9a-f]{24}\/(scan|backtest|charts\/[0-9a-f]{24})\.(json|bin)$/.test(path)) {
      throw new Error("Ogiltig dataadress.");
    }
    const response = await fetch(new URL(path, base), { cache: "no-store" });
    if (!response.ok) throw new Error("En ny analys kan ha publicerats. Klicka på ”Läs senaste analys”.");
    return site.manifest.mode === "encrypted" ? decryptJSON(await response.arrayBuffer(), key, path) : response.json();
  }
  function configureUI(manifest) {
    document.querySelector("#site-notice").classList.remove("hidden");
    document.querySelector("#site-status").textContent = `Automatisk dagsanalys · byggd ${new Date(manifest.built_at).toLocaleString("sv-SE")} · sidan söker ny analys var femte minut.`;
    document.querySelector("#refresh").textContent = "Läs senaste analys";
    for (const input of document.querySelectorAll("#settings-form input")) input.disabled = true;
    document.querySelector("#settings-form .form-actions").classList.add("hidden");
    document.querySelector("#settings-status").textContent = "STYRS VIA GITHUB";
    const edit = document.querySelector("#settings-edit");
    if (/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(manifest.repository)) {
      edit.href = `https://github.com/${manifest.repository}/edit/main/config.json`;
      edit.classList.remove("hidden");
    }
    for (const field of ["start", "end"]) {
      const input = document.querySelector(`#backtest-${field}`);
      input.value = manifest[`backtest_${field}`]; input.disabled = true;
    }
    document.querySelector("#backtest-run").textContent = "Visa senaste jämförelse";
    document.querySelector("#backtest-period-note").textContent = "GitHub räknar om senaste årets jämförelse tillsammans med dagsanalysen. Tidigare historik värmer upp indikatorerna.";
    document.querySelector("#data-operation-note").textContent = "GitHub Actions hämtar gratis historiska SIP-data efter avslutad handelsdag och publicerar analysen på GitHub Pages. API-nycklar finns endast i GitHub Secrets. Riktiga marknadsdata krypteras och låses upp lokalt i din webbläsare för personligt bruk.";
    const lock = document.querySelector("#lock-site");
    lock.classList.toggle("hidden", manifest.mode !== "encrypted");
    lock.onclick = () => { site.key = site.passphrase = site.scan = null; window.location.reload(); };
  }
  async function unlock() {
    if (!window.isSecureContext || !crypto.subtle) throw new Error("Personliga data kräver HTTPS eller localhost.");
    if (site.passphrase) {
      try {
        const key = await deriveKey(site.passphrase, site.manifest);
        site.scan = await read(site.manifest.scan, key); site.key = key; return;
      } catch (_) { site.passphrase = site.key = null; }
    }
    const dialog = document.querySelector("#unlock-dialog"), form = document.querySelector("#unlock-form");
    const input = document.querySelector("#unlock-passphrase"), error = document.querySelector("#unlock-error");
    error.textContent = ""; dialog.showModal(); input.focus();
    return new Promise((resolve, reject) => {
      const cancel = () => { cleanup(); reject(new Error("Data är låsta. Läs senaste analys för att låsa upp.")); };
      const cleanup = () => { form.removeEventListener("submit", submit); dialog.removeEventListener("cancel", cancel); };
      const submit = async event => {
        event.preventDefault(); const button = form.querySelector("button"); button.disabled = true; error.textContent = "";
        try {
          const phrase = input.value;
          const key = await deriveKey(phrase, site.manifest);
          const data = await read(site.manifest.scan, key);
          site.key = key; site.passphrase = phrase; site.scan = data; input.value = "";
          cleanup(); dialog.close(); resolve();
        } catch (_) { error.textContent = "Kunde inte låsa upp. Kontrollera lösenfrasen och prova igen."; }
        finally { button.disabled = false; }
      };
      form.addEventListener("submit", submit); dialog.addEventListener("cancel", cancel);
    });
  }
  async function loadManifest() {
    const manifest = await getJSON("manifest.json");
    if (manifest.schema !== 1 || !["demo", "encrypted"].includes(manifest.mode)) throw new Error("Okänt analysformat.");
    if (manifest.version !== site.manifest?.version) {
      site.manifest = manifest; site.scan = site.key = null; configureUI(manifest);
    }
    if (manifest.mode === "encrypted" && !site.key) await unlock();
    return manifest;
  }
  async function request(path, options) {
    if (options?.method && options.method !== "GET") throw new Error("Ändra strategin i config.json på GitHub och spara ändringen där.");
    const url = new URL(path, window.location.origin);
    if (url.pathname === "/api/scan") {
      const manifest = await loadManifest();
      site.scan = site.scan || await read(manifest.scan);
      return site.scan;
    }
    if (!site.manifest) await loadManifest();
    if (url.pathname === "/api/bars") {
      const id = site.scan.chart_ids[url.searchParams.get("symbol")];
      if (!id) throw new Error("Aktien saknas i denna analys.");
      return read(site.manifest.prefix + id + site.manifest.suffix);
    }
    if (url.pathname === "/api/backtest") {
      const result = await read(site.manifest.backtest);
      if (result.error) throw new Error(result.error);
      return result;
    }
    throw new Error("Okänd analysfunktion.");
  }
  async function hasUpdate() {
    if (!site.manifest || (site.manifest.mode === "encrypted" && !site.key)) return false;
    return (await getJSON("manifest.json")).version !== site.manifest.version;
  }
  function exportCSV(rows) {
    const columns = ["symbol", "date", "status", "score", "close", "resistance", "relative_volume", "entry_reference", "stop", "target", "shares", "risk_usd"];
    const cell = value => {
      let text = value === undefined || value === null ? "" : String(value);
      if (typeof value === "string" && /^[=+\-@]/.test(text)) text = "'" + text;
      return '"' + text.replaceAll('"', '""') + '"';
    };
    const csv = "\ufeff" + [columns.join(","), ...rows.map(row => columns.map(k => cell(row[k])).join(","))].join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "breakout-scan.csv"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  window.BreakoutData = { static: isStatic, request, hasUpdate, exportCSV, crypto: { deriveKey, decryptJSON } };
})();
