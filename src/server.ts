/**
 * server.ts — HTTP server hosting the v7 ONNX DistilBERT crossroad detector.
 *
 * Loads the vendored model from ../model/ (relative to dist/), exposes:
 *   GET  /health    → { status: "ok" }
 *   POST /detect    → { text, threshold } → { turn, word?, index?, score? }
 *   POST /shutdown  → { token } → 204 (graceful exit; 403 on bad token)
 *
 * The lockfile path is received via --lockfile <path> CLI arg (the caller
 * decides where it lives; this server has no knowledge of ~/.mycc-store).
 *
 * Lifecycle:
 *   - Binds 127.0.0.1:0 (random ephemeral port, localhost-only)
 *   - Writes { pid, port, startedAt, token } to the lockfile on startup
 *   - Idle timer: 15 min since last request → exit + delete lockfile
 *   - SIGTERM/SIGINT → exit + delete lockfile
 *   - POST /shutdown (with the lockfile token) → same graceful path
 *
 * Ported 1:1 from mycc's crossroad-encoder.ts (tokenizer + chunking + ONNX
 * inference), with the in-process detectTurn replaced by the HTTP handler.
 */

import { createServer, IncomingMessage } from 'node:http';
import type { AddressInfo } from 'node:net';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { argv, exit } from 'node:process';
import { randomBytes } from 'node:crypto';

import { writeLock, deleteLock } from './lockfile.js';
import { buildChunksV3, toCodePoints, sliceCodePoints, X_CHARS, type CharSpan } from './chunker.js';

// ============================================================================
// CLI args
// ============================================================================

function parseLockfilePath(): string | null {
  for (let i = 2; i < argv.length - 1; i++) {
    if (argv[i] === '--lockfile') return argv[i + 1];
  }
  return null;
}

const lockfilePath = parseLockfilePath();
if (!lockfilePath) {
  console.error('Usage: node dist/server.js --lockfile <path>');
  exit(1);
}
// After the exit(1) guard, narrow to string for the rest of the module.
const LOCKFILE: string = lockfilePath;

// Per-server secret: authenticates graceful /shutdown and lets the client
// confirm PID identity via the lockfile.
const TOKEN: string = randomBytes(24).toString('hex');

// ============================================================================
// Windowing constants — MUST mirror trainer/chunker_v3.py
// (X_CHARS == TWO_X == 448 == the ONNX sequence length)
// ============================================================================

const MIN_CHUNK_CHARS = 8;
const DEFAULT_THRESHOLD = 0.5;
const IDLE_TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes
const MAX_BODY_BYTES = 8 * 1024 * 1024; // 8 MiB request body cap

// ============================================================================
// Model path — vendored in ../model/ relative to this compiled file
// ============================================================================

const __dirname = dirname(fileURLToPath(import.meta.url));
// dist/ is one level below package root; model/ is at package root
const MODEL_DIR = join(__dirname, '..', 'model');
const ONNX_PATH = join(MODEL_DIR, 'model.onnx');
const TOK_PATH = join(MODEL_DIR, 'tokenizer.json');

// ============================================================================
// Types
// ============================================================================




interface EncoderState {
  session: import('onnxruntime-node').InferenceSession;
  vocab: Map<string, number>;
  unkId: number;
  clsId: number;
  sepId: number;
  padId: number;
  doLowerCase: boolean;
  seqLen: number;
}

// ============================================================================
// WordPiece tokenizer (ported from crossroad-encoder.ts)
// ============================================================================

function loadVocab(dir: string): Pick<EncoderState, 'vocab' | 'unkId' | 'clsId' | 'sepId' | 'padId' | 'doLowerCase'> {
  const tokPath = join(dir, 'tokenizer.json');
  const raw = JSON.parse(readFileSync(tokPath, 'utf8'));
  const model = raw.model ?? {};
  const vocab = new Map<string, number>();
  const v: Record<string, number> = model.vocab ?? {};
  for (const [tok, id] of Object.entries(v)) vocab.set(tok, id);
  const unk = vocab.get('[UNK]') ?? 100;
  const cls = vocab.get('[CLS]') ?? 101;
  const sep = vocab.get('[SEP]') ?? 102;
  const pad = vocab.get('[PAD]') ?? 0;
  // The tokenizer.json normalizer sets lowercase:false (model is *-cased), so
  // doLowerCase stays false unless the file explicitly opts in.
  const doLowerCase = Boolean(model.do_lower_case);
  return { vocab, unkId: unk, clsId: cls, sepId: sep, padId: pad, doLowerCase };
}

const CJK = /[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF]/;

function basicTokenize(text: string): string[] {
  const out: string[] = [];
  let buf = '';
  const flush = (): void => { if (buf) { out.push(buf); buf = ''; } };
  for (const ch of text) {
    if (/\s/.test(ch)) { flush(); continue; }
    if (CJK.test(ch) || /[!-/:-@[-`{-~]/.test(ch) || /[\u3000-\u303F\uFF00-\uFFEF]/.test(ch)) {
      flush();
      out.push(ch);
    } else {
      buf += ch;
    }
  }
  flush();
  return out;
}

function wordpiece(token: string, st: EncoderState): number[] {
  const t = st.doLowerCase ? token.toLowerCase() : token;
  const ids: number[] = [];
  let start = 0;
  while (start < t.length) {
    let end = t.length;
    let matched = -1;
    while (end > start) {
      const sub = (start === 0 ? '' : '##') + t.slice(start, end);
      const id = st.vocab.get(sub);
      if (id !== undefined) { matched = id; break; }
      end -= 1;
    }
    if (matched === -1) { ids.push(st.unkId); break; }
    ids.push(matched);
    start = end;
  }
  return ids;
}

function encodeWindow(text: string, st: EncoderState): { inputIds: BigInt64Array; attentionMask: BigInt64Array } {
  const content: number[] = [];
  for (const tok of basicTokenize(text)) {
    for (const id of wordpiece(tok, st)) content.push(id);
  }
  const maxContent = st.seqLen - 2;
  const clipped = content.slice(0, maxContent);
  const seq = [st.clsId, ...clipped, st.sepId];
  const inputIds = new BigInt64Array(st.seqLen);
  const attentionMask = new BigInt64Array(st.seqLen);
  for (let i = 0; i < st.seqLen; i++) {
    if (i < seq.length) {
      inputIds[i] = BigInt(seq[i]);
      attentionMask[i] = 1n;
    } else {
      inputIds[i] = BigInt(st.padId);
      attentionMask[i] = 0n;
    }
  }
  return { inputIds, attentionMask };
}

// ============================================================================
// ONNX inference
// ============================================================================

let state: EncoderState | null = null;
let loadPromise: Promise<EncoderState> | null = null;

async function ensureLoaded(): Promise<EncoderState> {
  if (state) return state;
  // Coalesce concurrent first-use loads into ONE InferenceSession.create.
  if (loadPromise === null) {
    loadPromise = doLoad().finally(() => { loadPromise = null; });
  }
  return loadPromise;
}

async function doLoad(): Promise<EncoderState> {
  if (!existsSync(ONNX_PATH) || !existsSync(TOK_PATH)) {
    throw new Error(`Model artifacts missing at ${MODEL_DIR}`);
  }
  const ort: typeof import('onnxruntime-node') = await import('onnxruntime-node');
  const session = await ort.InferenceSession.create(ONNX_PATH, {
    executionProviders: ['cpu'],
    graphOptimizationLevel: 'all',
  });
  const tok = loadVocab(MODEL_DIR);
  state = { session, seqLen: X_CHARS, ...tok };
  return state;
}

async function scoreWindow(text: string, st: EncoderState): Promise<number> {
  const ort = await import('onnxruntime-node');
  const { inputIds, attentionMask } = encodeWindow(text, st);
  const feeds: Record<string, import('onnxruntime-node').Tensor> = {
    input_ids: new ort.Tensor('int64', inputIds, [1, st.seqLen]),
    attention_mask: new ort.Tensor('int64', attentionMask, [1, st.seqLen]),
  };
  const out = await st.session.run(feeds);
  const logits = out.logits?.data as Float32Array | undefined;
  if (!logits || logits.length < 2) return NaN;
  const [a, b] = [logits[0], logits[1]];
  const m = Math.max(a, b);
  const ea = Math.exp(a - m);
  const eb = Math.exp(b - m);
  return eb / (ea + eb);
}

const HINT = /(\bhowever\b|\bwait\b|\bbut\b|\bactually\b|\breconsider\b|\bon second thought\b|但|不过|其实|然而|等等|话说回来)/i;
/** Returns the matched word and its CODE-POINT offset within `win`. */
function lexicalHint(win: string): { word: string; offset: number } | null {
  const m = win.match(HINT);
  if (!m || m.index === undefined) return null;
  // m.index is a UTF-16 offset; convert the prefix length to code points so
  // the returned offset aligns with the code-point spans.
  const offset = toCodePoints(win.slice(0, m.index)).length;
  return { word: m[0], offset };
}

// ============================================================================
// Detection
// ============================================================================

interface DetectResult {
  turn: boolean;
  word?: string;
  index?: number;
  score?: number;
}

async function detect(text: string, threshold: number): Promise<DetectResult> {
  const st = await ensureLoaded();
  const spans = buildChunksV3(text);
  // Spans are CODE-POINT offsets (matching trainer/chunker_v3.py). To extract
  // the window text we must slice the code-point array, not the raw string —
  // String.slice indexes UTF-16 units and misaligns on astral characters.
  const cp = toCodePoints(text);
  let best: { score: number; span: CharSpan } | null = null;
  for (const span of spans) {
    const win = sliceCodePoints(cp, span.start, span.end);
    if (win.trim().length < MIN_CHUNK_CHARS) continue;
    const score = await scoreWindow(win, st);
    if (Number.isNaN(score)) continue;
    // Track the highest-scoring window so a later, stronger signal is not
    // masked by an earlier weaker one crossing the threshold.
    if (best === null || score > best.score) best = { score, span };
  }
  if (best === null || best.score < threshold) return { turn: false };
  const win = sliceCodePoints(cp, best.span.start, best.span.end);
  const hint = lexicalHint(win);
  // hint.offset is a code-point index within `win`; best.span.start is a
  // code-point offset into the whole text, so the sum is a code-point index
  // into `text` — which is what callers index by (e.g. for slicing words).
  return {
    turn: true,
    word: hint?.word ?? '',
    index: best.span.start + (hint?.offset ?? 0),
    score: best.score,
  };
}

// ============================================================================
// HTTP server
// ============================================================================

let idleTimer: ReturnType<typeof setTimeout> | null = null;
let shuttingDown = false;

function resetIdleTimer(): void {
  if (idleTimer) clearTimeout(idleTimer);
  idleTimer = setTimeout(shutdown, IDLE_TIMEOUT_MS);
  // Don't let the idle timer keep the event loop alive on its own.
  if (typeof idleTimer.unref === 'function') idleTimer.unref();
}

function shutdown(): void {
  if (shuttingDown) return;
  shuttingDown = true;
  if (idleTimer) clearTimeout(idleTimer);
  deleteLock(LOCKFILE, process.pid);
  try { server.close(); } catch { /* ignore */ }
  exit(0);
}

function readBody(req: IncomingMessage, limit = MAX_BODY_BYTES): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = '';
    let size = 0;
    req.on('data', (chunk: Buffer) => {
      size += chunk.length;
      if (size > limit) {
        reject(new Error('request body too large'));
        req.destroy();
        return;
      }
      data += chunk;
    });
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}

function sendJson(res: import('node:http').ServerResponse, status: number, obj: unknown): void {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(obj));
}

const server = createServer(async (req, res) => {
  resetIdleTimer();

  // Compare on path only, so a query string does not 404 the route.
  const path = (req.url ?? '').split('?')[0];

  if (path === '/health') {
    if (req.method !== 'GET') { sendJson(res, 405, { error: 'method not allowed' }); return; }
    sendJson(res, 200, { status: 'ok' });
    return;
  }

  if (path === '/detect') {
    if (req.method !== 'POST') { sendJson(res, 405, { error: 'method not allowed' }); return; }
    try {
      const raw = await readBody(req);
      let body: { text?: unknown; threshold?: unknown };
      try {
        body = JSON.parse(raw) as { text?: unknown; threshold?: unknown };
      } catch {
        sendJson(res, 400, { error: 'invalid JSON body' });
        return;
      }
      if (typeof body.text !== 'string') {
        sendJson(res, 400, { error: 'missing "text" field' });
        return;
      }
      let threshold = DEFAULT_THRESHOLD;
      if (body.threshold !== undefined) {
        if (typeof body.threshold !== 'number' || !Number.isFinite(body.threshold) || body.threshold < 0 || body.threshold > 1) {
          sendJson(res, 400, { error: 'threshold must be a finite number in [0, 1]' });
          return;
        }
        threshold = body.threshold;
      }
      const result = await detect(body.text, threshold);
      sendJson(res, 200, result);
    } catch (err) {
      // Do not leak internal error strings (paths, stack shapes) to callers.
      console.error('detect error:', err);
      sendJson(res, 500, { error: 'internal error' });
    }
    return;
  }

  if (path === '/shutdown') {
    if (req.method !== 'POST') { sendJson(res, 405, { error: 'method not allowed' }); return; }
    let body: { token?: unknown };
    try {
      body = JSON.parse(await readBody(req)) as { token?: unknown };
    } catch {
      sendJson(res, 400, { error: 'invalid JSON body' });
      return;
    }
    if (body.token !== TOKEN) {
      sendJson(res, 403, { error: 'forbidden' });
      return;
    }
    sendJson(res, 204, {});
    // Give the response a tick to flush, then exit gracefully.
    setImmediate(shutdown);
    return;
  }

  sendJson(res, 404, { error: 'not found' });
});

server.on('error', (err) => {
  console.error('server error:', err);
  deleteLock(LOCKFILE, process.pid);
  exit(1);
});

// Bind localhost-only, random ephemeral port
server.listen(0, '127.0.0.1', () => {
  const addr = server.address();
  if (addr && typeof addr === 'object' && 'port' in addr) {
    const port = (addr as AddressInfo).port;
    writeLock(LOCKFILE, { pid: process.pid, port, startedAt: Date.now(), token: TOKEN });
    // Signal readiness on stderr (stdout stays clean for potential piping)
    console.error(`crossroad-detector server listening on 127.0.0.1:${port}`);
  }
  resetIdleTimer();
});

// Graceful shutdown on signals (POSIX). On Windows these may not fire for an
// external kill; the client uses POST /shutdown there instead.
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
