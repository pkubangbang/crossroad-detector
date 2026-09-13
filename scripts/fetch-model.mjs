#!/usr/bin/env node
/**
 * fetch-model.mjs — download model/model.onnx from the GitHub Release.
 *
 * The 129 MB ONNX binary is NOT tracked in git (see .gitignore); it is
 * published as an asset on the repo's GitHub Release. Everything that
 * describes the binary — its release tag, exact size and SHA256 — is pinned
 * in the tracked manifest model/model.lock.json, so the repo always records
 * which binary it expects. This script downloads it into model/model.onnx
 * and verifies it against that manifest, so a fresh clone can become
 * runnable with:
 *
 *   npm run fetch-model
 *
 * Modes:
 *   (default)        download if missing/stale, then verify
 *   --verify, -c     hash the on-disk model against the manifest; no network
 *
 * Env:
 *   HTTPS_PROXY   optional proxy URL (e.g. http://127.0.0.1:7777)
 *   GITHUB_REPO   optional "owner/repo" override
 *   MODEL_TAG     optional release tag override
 */

import { createHash } from 'node:crypto';
import { createWriteStream, createReadStream, existsSync, readFileSync, renameSync, rmSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const MODEL_DIR = join(ROOT, 'model');
const DEST = join(MODEL_DIR, 'model.onnx');
const MANIFEST = join(MODEL_DIR, 'model.lock.json');

const VERIFY_ONLY = process.argv.includes('--verify') || process.argv.includes('-c');

/**
 * Read model/model.lock.json — the tracked source of truth for the model
 * artifact. It pins the release coordinates and the expected sha256/size.
 */
function readManifest() {
  if (!existsSync(MANIFEST)) {
    throw new Error(
      `manifest not found at ${MANIFEST}. It must be tracked in git — ` +
      `it is the pointer to the out-of-repo model binary.`
    );
  }
  const raw = JSON.parse(readFileSync(MANIFEST, 'utf8'));
  const m = {
    asset: raw.asset || 'model.onnx',
    repo: process.env.GITHUB_REPO || raw.repo,
    tag: process.env.MODEL_TAG || raw.tag,
    modelVersion: raw.modelVersion || 'unknown',
    bytes: raw.bytes,
    sha256: raw.sha256 || '',
  };
  if (!m.repo || !m.tag) {
    throw new Error('manifest is missing "repo" or "tag"; cannot build the download URL.');
  }
  return m;
}

/** Stream a large file through sha256 without buffering it in memory. */
function hashFile(path) {
  return new Promise((resolve, reject) => {
    const hash = createHash('sha256');
    createReadStream(path)
      .on('data', (chunk) => hash.update(chunk))
      .on('end', () => resolve(hash.digest('hex')))
      .on('error', reject);
  });
}

async function download(url, dest, proxy) {
  const headers = { 'User-Agent': 'crossroad-detector-fetch-model' };
  const opts = { headers, redirect: 'follow' };
  if (proxy) opts.dispatcher = undefined; // node fetch uses global proxy via env; keep simple

  const res = await fetch(url, opts);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} ${res.statusText} for ${url}`);
  }
  const total = Number(res.headers.get('content-length') || 0);
  const hash = createHash('sha256');
  let seen = 0;
  let lastPct = -1;

  const tmp = `${dest}.part`;
  const out = createWriteStream(tmp);

  const source = Readable.fromWeb(res.body);
  source.on('data', (chunk) => {
    seen += chunk.length;
    hash.update(chunk);
    if (total > 0) {
      const pct = Math.floor((seen / total) * 100);
      if (pct !== lastPct && pct % 5 === 0) {
        lastPct = pct;
        process.stderr.write(`\r  downloading… ${pct}% (${(seen / 1048576).toFixed(1)} MB)`);
      }
    }
  });

  await pipeline(source, out);
  process.stderr.write(`\r  downloaded ${(seen / 1048576).toFixed(1)} MB            \n`);
  return { sha256: hash.digest('hex'), bytes: seen, tmp };
}

/** Hash the on-disk model and compare against the manifest. No network. */
async function verifyOnly(manifest) {
  if (!existsSync(DEST)) {
    console.error(`✗ ${DEST} is missing. Run "npm run fetch-model" to download it.`);
    process.exit(1);
  }
  const st = statSync(DEST);
  const sha256 = await hashFile(DEST);
  const sizeOk = manifest.bytes ? st.size === manifest.bytes : true;
  const hashOk = manifest.sha256 ? sha256 === manifest.sha256 : true;

  console.log(`crossroad-detector: verifying model (offline)`);
  console.log(`  file:  ${DEST}`);
  console.log(`  model: ${manifest.modelVersion} (release ${manifest.tag})`);
  console.log(`  size:  ${st.size} bytes ${sizeOk ? '✓' : `✗ (manifest: ${manifest.bytes})`}`);
  console.log(`  sha256: ${sha256} ${hashOk ? '✓' : `✗ (manifest: ${manifest.sha256})`}`);

  if (sizeOk && hashOk) {
    console.log(`\n✓ model.onnx matches model/model.lock.json.`);
    return;
  }
  console.error(`\n✗ model.onnx does NOT match model/model.lock.json.`);
  process.exit(1);
}

async function main() {
  const manifest = readManifest();

  if (VERIFY_ONLY) {
    await verifyOnly(manifest);
    return;
  }

  const url = `https://github.com/${manifest.repo}/releases/download/${manifest.tag}/${manifest.asset}`;
  const proxy = process.env.HTTPS_PROXY || process.env.https_proxy || '';

  console.log(`crossroad-detector: fetching model`);
  console.log(`  repo:  ${manifest.repo}`);
  console.log(`  tag:   ${manifest.tag}`);
  console.log(`  asset: ${manifest.asset}`);
  console.log(`  model: ${manifest.modelVersion}`);
  if (proxy) console.log(`  proxy: ${proxy}`);

  if (existsSync(DEST)) {
    const st = statSync(DEST);
    // Fast path: cheap size probe first, then stream-hash to confirm.
    if (!manifest.bytes || st.size === manifest.bytes) {
      const hash = await hashFile(DEST);
      if (!manifest.sha256 || hash === manifest.sha256) {
        console.log(`\nmodel.onnx already present and verified (${st.size} bytes). Nothing to do.`);
        return;
      }
    }
    console.log(`  existing model.onnx will be replaced.`);
  }

  const { sha256, tmp } = await download(url, DEST, proxy);

  if (manifest.sha256 && sha256 !== manifest.sha256) {
    rmSync(tmp, { force: true });
    throw new Error(
      `SHA256 mismatch!\n  expected: ${manifest.sha256}\n  got:      ${sha256}\n` +
      `The download was discarded. If the model was intentionally updated, ` +
      `update model/model.lock.json.`
    );
  }

  renameSync(tmp, DEST);
  console.log(`\n✓ model.onnx saved to ${DEST}`);
  console.log(`  sha256: ${sha256}`);
  console.log(`  size:   ${(statSync(DEST).size / 1048576).toFixed(1)} MB`);
}

main().catch((err) => {
  console.error(`\n✗ ${err.message}`);
  process.exit(1);
});
