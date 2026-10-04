// Test the actual frontend decryption against a snapshot produced by Python.
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
global.window = {location:{href:"https://example.github.io/Breakout_stock/",origin:"https://example.github.io"}};
global.document = {querySelector:() => null};
require("../breakout_lab/static/data-client.js");
(async () => {
  const [root, phrase] = process.argv.slice(2);
  const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json")));
  const raw = fs.readFileSync(path.join(root, manifest.scan));
  const {deriveKey,decryptJSON} = window.BreakoutData.crypto;
  const key = await deriveKey(phrase, manifest);
  const data = await decryptJSON(raw, key, manifest.scan);
  await assert.rejects(async () => decryptJSON(raw, await deriveKey(phrase + "wrong", manifest), manifest.scan));
  const tampered = Buffer.from(raw); tampered[tampered.length - 1] ^= 1;
  await assert.rejects(async () => decryptJSON(tampered, key, manifest.scan));
  console.log(JSON.stringify({rows:data.rows.length,wrong_passphrase_rejected:true,tamper_rejected:true}));
})().catch(error => {console.error(error.message);process.exit(1);});
