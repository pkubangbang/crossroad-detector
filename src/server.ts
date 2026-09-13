/**
 * server.ts — HTTP server hosting the v6 ONNX DistilBERT crossroad detector.
 *
 * Loads the vendored model from ../model/ (relative to dist/), exposes:
 *   GET  /health  → { status: "ok" }
 *   POST /detect  → { text, threshold } → { turn, word?, index?, score? }
 *
 * The lockfile path is received via --lockfile <path> CLI arg (the caller
 * decides where it lives; this server has no knowledge of ~/.mycc-store).
 *
 * Lifecycle:
 *   - Binds 127.0.0.1:0 (random ephemeral port, localhost-only)
 *   - Writes { pid, port, startedAt } to the lockfile on startup
 *   - Idle timer: 15 min since last request → exit + delete lockfile
 *   - SIGTERM/SIGINT → exit + delete lockfile
 *
 * Ported 1:1 from mycc's crossroad-encoder.ts (tokenizer + chunkSpans + ONNX
 * inference), with the in-process detectTurn replaced by the HTTP handler.
 */

import { createServer, IncomingMessage } from 'node:http';
import type { AddressInfo } from 'node:net';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { argv, exit } from 'node:process';

import { writeLock, deleteLock } from './lockfile.js';

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

// ============================================================================
// Windowing constants — MUST mirror trainer/chunker_v2.py (X_CHARS=448)
// ============================================================================

const WINDOW = 448;
const MIN_CHUNK_CHARS = 8;
const DEFAULT_THRESHOLD = 0.5;
const IDLE_TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes

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

interface CharSpan { start: number; end: number; }

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
// Window lattice (character offsets) — mirrors chunker_v2.build_chunks_v2
// ============================================================================

function chunkSpans(nChars: number, window = WINDOW): CharSpan[] {
  if (nChars <= 0) return [];
  if (nChars <= window) return [{ start: 0, end: nChars }];
  const spans: CharSpan[] = [];
  let start = 0;
  while (start < nChars) {
    const end = Math.min(start + window, nChars);
    spans.push({ start, end });
    if (end >= nChars) break;
    start = end; // contiguous advance — no overlap, no gap
  }
  return spans;
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

async function ensureLoaded(): Promise<EncoderState> {
  if (state) return state;
  if (!existsSync(ONNX_PATH) || !existsSync(TOK_PATH)) {
    throw new Error(`Model artifacts missing at ${MODEL_DIR}`);
  }
  const ort: typeof import('onnxruntime-node') = await import('onnxruntime-node');
  const session = await ort.InferenceSession.create(ONNX_PATH, {
    executionProviders: ['cpu'],
    graphOptimizationLevel: 'all',
  });
  const tok = loadVocab(MODEL_DIR);
  state = { session, seqLen: WINDOW, ...tok };
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
function lexicalHint(win: string): string | null {
  const m = win.match(HINT);
  return m ? m[0] : null;
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
  const spans = chunkSpans(text.length);
  for (const span of spans) {
    const win = text.slice(span.start, span.end);
    if (win.trim().length < MIN_CHUNK_CHARS) continue;
    const score = await scoreWindow(win, st);
    if (Number.isNaN(score)) continue;
    if (score >= threshold) {
      return { turn: true, word: lexicalHint(win) ?? '', index: span.start, score };
    }
  }
  return { turn: false };
}

// ============================================================================
// HTTP server
// ============================================================================

let idleTimer: ReturnType<typeof setTimeout> | null = null;

function resetIdleTimer(): void {
  if (idleTimer) clearTimeout(idleTimer);
  idleTimer = setTimeout(() => {
    shutdown();
  }, IDLE_TIMEOUT_MS);
}

function shutdown(): void {
  if (idleTimer) clearTimeout(idleTimer);
  deleteLock(LOCKFILE);
  server.close();
  exit(0);
}

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (chunk) => { data += chunk; });
    req.on('end', () => resolve(data));
    req.on('error', reject);
  });
}

const server = createServer(async (req, res) => {
  resetIdleTimer();

  if (req.method === 'GET' && req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok' }));
    return;
  }

  if (req.method === 'POST' && req.url === '/detect') {
    try {
      const body = JSON.parse(await readBody(req)) as { text: string; threshold?: number };
      if (typeof body.text !== 'string') {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'missing "text" field' }));
        return;
      }
      const threshold = typeof body.threshold === 'number' ? body.threshold : DEFAULT_THRESHOLD;
      const result = await detect(body.text, threshold);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    } catch (err) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: String(err) }));
    }
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ error: 'not found' }));
});

server.on('error', (err) => {
  console.error('server error:', err);
  deleteLock(LOCKFILE);
  exit(1);
});

// Bind localhost-only, random ephemeral port
server.listen(0, '127.0.0.1', () => {
  const addr = server.address();
  if (addr && typeof addr === 'object' && 'port' in addr) {
    const port = (addr as AddressInfo).port;
    writeLock(LOCKFILE, { pid: process.pid, port, startedAt: Date.now() });
    // Signal readiness on stderr (stdout stays clean for potential piping)
    console.error(`crossroad-detector server listening on 127.0.0.1:${port}`);
  }
  resetIdleTimer();
});

// Graceful shutdown on signals
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);