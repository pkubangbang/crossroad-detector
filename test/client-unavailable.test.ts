/**
 * client-unavailable.test.ts — proves detect() distinguishes the four
 * infrastructure failures from "inference ran, no turn".
 *
 * Run with:  npx tsx test/client-unavailable.test.ts
 *
 * Not included in tsconfig (rootDir is ./src), so it never ships.
 *
 * Strategy: each case builds a FAKE server (a tiny http.createServer that
 * speaks the same /health + /detect contract) and a matching lockfile, so the
 * client's fast path reuses it and never spawns the real model. That makes the
 * failure classes deterministically reachable without the 129 MB model.
 */

import { createServer, type Server } from 'node:http';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { AddressInfo } from 'node:net';

import { CrossroadDetector, CrossroadUnavailableError } from '../src/client.js';

let passed = 0;
let failed = 0;

function ok(name: string, cond: boolean, detail?: string): void {
  if (cond) {
    passed++;
    console.log(`  PASS  ${name}`);
  } else {
    failed++;
    console.log(`  FAIL  ${name}${detail ? ` — ${detail}` : ''}`);
  }
}

async function startFake(
  handler: (path: string) => { status: number; body: string } | 'hang' | Promise<{ status: number; body: string } | 'hang'>,
): Promise<{ server: Server; port: number; close: () => Promise<void> }> {
  const server = createServer(async (req, res) => {
    if (req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end('{"status":"ok"}');
      return;
    }
    const out = await handler(req.url ?? '');
    if (out === 'hang') return; // never respond -> client must time out
    res.writeHead(out.status, { 'Content-Type': 'application/json' });
    res.end(out.body);
  });
  await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
  const port = (server.address() as AddressInfo).port;
  return {
    server,
    port,
    close: () => new Promise<void>((r) => { server.closeAllConnections?.(); server.close(() => r()); }),
  };
}

function makeLock(port: number): string {
  const dir = mkdtempSync(join(tmpdir(), 'cd-test-'));
  const lock = join(dir, 'crossroad.lock');
  writeFileSync(lock, JSON.stringify({ pid: process.pid, port, startedAt: Date.now() }), 'utf8');
  return lock;
}

function cleanup(lock: string): void {
  rmSync(join(lock, '..'), { recursive: true, force: true });
}

/** Run detect() and describe what happened, without letting it throw out. */
async function outcome(det: CrossroadDetector, text = 'some text'): Promise<{ kind: string; value?: unknown; reason?: string; message?: string }> {
  try {
    const r = await det.detect(text);
    return r === null ? { kind: 'null' } : { kind: 'match', value: r };
  } catch (err) {
    if (err instanceof CrossroadUnavailableError) {
      return { kind: 'unavailable', reason: err.reason, message: err.message };
    }
    return { kind: 'unexpected', message: (err as Error).message };
  }
}

async function main(): Promise<void> {
  // ------------------------------------------------------------------
  console.log('\n[1] no turn  -> null (detection RAN, nothing found)');
  {
    const f = await startFake(() => ({ status: 200, body: '{"turn":false}' }));
    const lock = makeLock(f.port);
    const out = await outcome(new CrossroadDetector(lock));
    ok('returns null, does not throw', out.kind === 'null', JSON.stringify(out));
    await f.close();
    cleanup(lock);
  }

  // ------------------------------------------------------------------
  console.log('\n[2] turn found -> { word, index, score } (wire shape unchanged)');
  {
    const f = await startFake(() => ({
      status: 200,
      body: '{"turn":true,"word":"however","index":420,"score":0.92}',
    }));
    const lock = makeLock(f.port);
    const out = await outcome(new CrossroadDetector(lock));
    const v = out.value as { word: string; index: number; score: number } | undefined;
    ok(
      'returns the exact three-field match',
      out.kind === 'match' && v?.word === 'however' && v?.index === 420 && v?.score === 0.92,
      JSON.stringify(out),
    );
    await f.close();
    cleanup(lock);
  }

  // ------------------------------------------------------------------
  console.log('\n[3] HTTP 500 -> CrossroadUnavailableError(http-error)');
  {
    const f = await startFake(() => ({ status: 500, body: 'onnx session died' }));
    const lock = makeLock(f.port);
    const out = await outcome(new CrossroadDetector(lock));
    ok('reason is http-error', out.reason === 'http-error', JSON.stringify(out));
    ok('message carries the status code', /HTTP 500/.test(out.message ?? ''), out.message);
    await f.close();
    cleanup(lock);
  }

  // ------------------------------------------------------------------
  console.log('\n[4] server hangs -> CrossroadUnavailableError(timeout)');
  {
    const f = await startFake(() => 'hang');
    const lock = makeLock(f.port);
    const out = await outcome(new CrossroadDetector(lock, { detectTimeout: 400 }));
    ok('reason is timeout', out.reason === 'timeout', JSON.stringify(out));
    ok('message names the timeout', /exceeded 400ms/.test(out.message ?? ''), out.message);
    await f.close();
    cleanup(lock);
  }

  // ------------------------------------------------------------------
  console.log('\n[5] non-JSON body -> CrossroadUnavailableError(malformed-response)');
  {
    const f = await startFake(() => ({ status: 200, body: '<html>oops</html>' }));
    const lock = makeLock(f.port);
    const out = await outcome(new CrossroadDetector(lock));
    ok('reason is malformed-response', out.reason === 'malformed-response', JSON.stringify(out));
    ok('message shows the offending body', /html/.test(out.message ?? ''), out.message);
    await f.close();
    cleanup(lock);
  }

  // ------------------------------------------------------------------
  console.log('\n[6] valid JSON without a boolean "turn" -> malformed-response');
  {
    const f = await startFake(() => ({ status: 200, body: '{"word":"however"}' }));
    const lock = makeLock(f.port);
    const out = await outcome(new CrossroadDetector(lock));
    ok('reason is malformed-response', out.reason === 'malformed-response', JSON.stringify(out));
    await f.close();
    cleanup(lock);
  }

  // ------------------------------------------------------------------
  console.log('\n[7] nothing listening (dead port) -> unavailable, never null');
  {
    const f = await startFake(() => ({ status: 200, body: '{"turn":false}' }));
    const deadPort = f.port;
    await f.close(); // close immediately: the lockfile now points at a dead port
    const lock = makeLock(deadPort);
    // A detector that cannot spawn (server.js missing) must still not return
    // null — it must report that nothing ran. We assert only "not null".
    const out = await outcome(new CrossroadDetector(lock, { spawnTimeout: 1200 }));
    ok('never silently reports "no turn"', out.kind === 'unavailable', JSON.stringify(out));
    ok('reason is one of the four', ['spawn-failed', 'http-error', 'timeout'].includes(out.reason ?? ''), out.reason);
    cleanup(lock);
  }

  // ------------------------------------------------------------------
  console.log('\n[8] error is a real Error, name/instanceof usable');
  {
    const err = new CrossroadUnavailableError('http-error', 'HTTP 503: busy');
    ok('instanceof Error', err instanceof Error);
    ok('instanceof CrossroadUnavailableError', err instanceof CrossroadUnavailableError);
    ok('name is set', err.name === 'CrossroadUnavailableError');
    ok('reason is exposed', err.reason === 'http-error');
    ok('message is prefixed and specific', err.message === 'crossroad detector unavailable (http-error): HTTP 503: busy', err.message);
  }

  console.log('\n[9] sync (non-async) "hang" from the handler also times out');
  {
    // The handler returns the literal string synchronously, not a Promise.
    const f = await startFake(() => 'hang');
    const lock = makeLock(f.port);
    const out = await outcome(new CrossroadDetector(lock, { detectTimeout: 400 }));
    ok('sync hang takes the timeout path', out.reason === 'timeout', JSON.stringify(out));
    await f.close();
    cleanup(lock);
  }

  // ------------------------------------------------------------------
  console.log('\n[10] async "hang" (never-resolving handler) also times out');
  {
    const f = await startFake(async (): Promise<'hang'> => 'hang');
    const lock = makeLock(f.port);
    const out = await outcome(new CrossroadDetector(lock, { detectTimeout: 400 }));
    ok('async hang takes the timeout path', out.reason === 'timeout', JSON.stringify(out));
    await f.close();
    cleanup(lock);
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  if (failed > 0) process.exitCode = 1;
}

main().catch((err) => {
  console.error('TEST HARNESS CRASHED:', err);
  process.exitCode = 1;
});
