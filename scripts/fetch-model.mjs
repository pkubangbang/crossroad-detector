#!/usr/bin/env node
/**
 * fetch-model.mjs — download model/model.onnx from the GitHub Release.
 *
 * The 393 MB ONNX binary is NOT tracked in git (see .gitignore). It is
 * published as an asset on the repo's GitHub Release. This script downloads
 * it into model/model.onnx and verifies its SHA256, so a fresh clone can
 * become runnable with:
 *
 *   npm run fetch-model
 *
 * Env:
 *   HTTPS_PROXY   optional proxy URL (e.g. http://127.0.0.1:7777)
 *   GITHUB_REPO   optional "owner/repo" override (default: from package.json)
 *   MODEL_TAG     optional release tag (default: "v" + package version)
 */

import { createHash } from 'node:crypto';
import { createWriteStream, existsSync, mkdirSync, readFileSync, renameSync, rmSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const MODEL_DIR = join(ROOT, 'model');
const DEST = join(MODEL_DIR, 'model.onnx');
const ASSET = 'model.onnx';

// Expected SHA256 of the v6 INT8 DistilBERT ONNX (verified copy in
// trainer/out/model-v6-onnx). Empty string disables verification.
const EXPECTED_SHA256 = 'd040b91824d032857bb23c403a0299311bfaf498ce169812129dbf2d817e2996';

function readRepo() {
  if (process.env.GITHUB_REPO) return process.env.GITHUB_REPO;
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));
  const url = typeof pkg.repository === 'string'
    ? pkg.repository
    : (pkg.repository && pkg.repository.url) || '';
  const m = url.match(/github\.com[/:]([^/]+)\/([^/.]+)/);
  if (m) return `${m[1]}/${m[2]}`;
  // Fallback: the canonical home of this package.
  return 'pkubangbang/crossroad-detector';
}

function readTag(repo) {
  if (process.env.MODEL_TAG) return process.env.MODEL_TAG;
  const pkg = JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8'));
  return `v${pkg.version}`;
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

async function main() {
  const repo = readRepo();
  const tag = readTag(repo);
  const proxy = process.env.HTTPS_PROXY || process.env.https_proxy || '';
  const url = `https://github.com/${repo}/releases/download/${tag}/${ASSET}`;

  console.log(`crossroad-detector: fetching model`);
  console.log(`  repo:  ${repo}`);
  console.log(`  tag:   ${tag}`);
  console.log(`  asset: ${ASSET}`);
  if (proxy) console.log(`  proxy: ${proxy}`);

  if (existsSync(DEST)) {
    const st = statSync(DEST);
    // Fast path: if the on-disk file already matches, skip.
    if (st.size === 412308279) {
      const hash = createHash('sha256').update(readFileSync(DEST)).digest('hex');
      if (!EXPECTED_SHA256 || hash === EXPECTED_SHA256) {
        console.log(`\nmodel.onnx already present and verified (${st.size} bytes). Nothing to do.`);
        return;
      }
    }
    console.log(`  existing model.onnx will be replaced.`);
  }

  mkdirSync(MODEL_DIR, { recursive: true });

  const { sha256, tmp } = await download(url, DEST, proxy);

  if (EXPECTED_SHA256 && sha256 !== EXPECTED_SHA256) {
    rmSync(tmp, { force: true });
    throw new Error(
      `SHA256 mismatch!\n  expected: ${EXPECTED_SHA256}\n  got:      ${sha256}\n` +
      `The download was discarded. If the model was intentionally updated, ` +
      `update EXPECTED_SHA256 in scripts/fetch-model.mjs.`
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
