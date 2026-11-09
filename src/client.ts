/**
 * client.ts — CrossroadDetector client SDK.
 *
 * Usage:
 *   const detector = new CrossroadDetector('/path/to/crossroad.lock', { threshold: 0.5 });
 *   const result = await detector.detect(text);
 *   // → { word, index, score } | null
 *
 * The client lazily spawns a detached HTTP server on first use, managed via
 * the lockfile at the path passed to the constructor. The server auto-shuts-
 * down after 15 min idle.
 *
 * detect() distinguishes two outcomes that used to be collapsed into null:
 *   - `null`                          → inference RAN and found no turn.
 *   - `CrossroadUnavailableError`     → infrastructure failure (spawn failed,
 *                                       HTTP error, timeout, malformed
 *                                       response). The detection did not run;
 *                                       the caller may fall back.
 * The error message always names which of those happened, because "the model
 * server is gone" and "the server answered garbage" need different fixes.
 *
 * Spawn uses detached:true + windowsHide:true — on Windows, without
 * detached:true the child shares the parent's console group and is silently
 * killed when the parent process group exits (CTRL_CLOSE_EVENT).
 */

import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { kill } from 'node:process';

import { readLock, writeLock, deleteLock } from './lockfile.js';

// ============================================================================
// Public types
// ============================================================================

export interface TurningWordMatch {
  /** A human-readable anchor word (best-effort lexical hint near the turn). */
  word: string;
  /**
   * Character offset of the detected turn in the ORIGINAL content. This is the
   * position of the anchor word inside the winning window when one is found,
   * otherwise the start of the winning window.
   */
  index: number;
  /** The model's P(turn) for the winning window. */
  score: number;
}

export interface CrossroadDetectorOptions {
  /** Decision threshold on P(turn). Default 0.5. */
  threshold?: number;
  /** Timeout for server spawn + health check (ms). Default 15000. */
  spawnTimeout?: number;
  /** Timeout for a single /detect request (ms). Default 30000. */
  detectTimeout?: number;
}

/** Which kind of infrastructure failure kept the detection from running. */
export type CrossroadUnavailableReason = 'spawn-failed' | 'http-error' | 'timeout' | 'malformed-response';

/**
 * Thrown by detect() when the detection could NOT run — as opposed to
 * returning null, which means it ran and found no turn.
 *
 * The message always names the specific failure, e.g.
 *   "crossroad detector unavailable (spawn-failed): server script not found: …"
 *   "crossroad detector unavailable (http-error): HTTP 500: …"
 *   "crossroad detector unavailable (timeout): /detect exceeded 30000ms"
 *   "crossroad detector unavailable (malformed-response): expected JSON …"
 */
export class CrossroadUnavailableError extends Error {
  readonly reason: CrossroadUnavailableReason;

  constructor(reason: CrossroadUnavailableReason, detail: string, options?: { cause?: unknown }) {
    super(`crossroad detector unavailable (${reason}): ${detail}`, options);
    this.name = 'CrossroadUnavailableError';
    this.reason = reason;
  }
}

// ============================================================================
// Resolve server script path (dist/server.js relative to this file)
// ============================================================================

const __dirname = dirname(fileURLToPath(import.meta.url));
// client.js is in dist/; server.js is in dist/ too
const SERVER_SCRIPT = join(__dirname, 'server.js');

// ============================================================================
// Process-alive check (no signal sent)
// ============================================================================

function isProcessAlive(pid: number): boolean {
  try {
    kill(pid, 0);
    return true;
  } catch (err) {
    // EPERM means the process exists but belongs to another user — still alive.
    return (err as NodeJS.ErrnoException).code === 'EPERM';
  }
}

// ============================================================================
// HTTP helpers
// ============================================================================

function httpGet(url: string, timeoutMs: number): Promise<string> {
  return fetchUrl('GET', url, undefined, undefined, timeoutMs);
}

function httpPostJson(url: string, body: unknown, timeoutMs: number, headers?: Record<string, string>): Promise<string> {
  return fetchUrl('POST', url, JSON.stringify(body), headers, timeoutMs);
}

function fetchUrl(
  method: string,
  url: string,
  body: string | undefined,
  headers: Record<string, string> | undefined,
  timeoutMs: number,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const init: RequestInit = { method, signal: controller.signal };
    if (body !== undefined) {
      init.headers = { 'Content-Type': 'application/json', ...(headers ?? {}) };
      init.body = body;
    }
    fetch(url, init)
      .then(async (res) => {
        clearTimeout(timer);
        const text = await res.text();
        if (!res.ok) reject(new Error(`HTTP ${res.status}: ${text}`));
        else resolve(text);
      })
      .catch((err) => {
        clearTimeout(timer);
        reject(err);
      });
  });
}

// ============================================================================
// CrossroadDetector
// ============================================================================

export class CrossroadDetector {
  private readonly lockfilePath: string;
  private readonly threshold: number;
  private readonly spawnTimeout: number;
  private readonly detectTimeout: number;
  private cachedPort: number | null = null;
  /** In-flight spawn so concurrent detect() calls share ONE server. */
  private spawnPromise: Promise<number> | null = null;

  constructor(lockfilePath: string, options?: CrossroadDetectorOptions) {
    this.lockfilePath = lockfilePath;
    this.threshold = options?.threshold ?? 0.5;
    this.spawnTimeout = options?.spawnTimeout ?? 15000;
    this.detectTimeout = options?.detectTimeout ?? 30000;
  }

  /**
   * Detect a turning word in the given text.
   *
   * @returns the match, or `null` when inference ran and found no turn.
   * @throws  {@link CrossroadUnavailableError} when the detection could not
   *          run at all (spawn failure, HTTP error, timeout, malformed
   *          response). The error's `reason` and message identify which.
   */
  async detect(content: string): Promise<TurningWordMatch | null> {
    const port = await this.ensureServer();
    const url = `http://127.0.0.1:${port}/detect`;

    let resp: string;
    try {
      resp = await httpPostJson(url, { text: content, threshold: this.threshold }, this.detectTimeout);
    } catch (err) {
      throw this.asUnavailable(err, `/detect request to 127.0.0.1:${port}`);
    }

    let data: { turn?: unknown; word?: unknown; index?: unknown; score?: unknown };
    try {
      data = JSON.parse(resp) as typeof data;
    } catch (err) {
      throw new CrossroadUnavailableError(
        'malformed-response',
        `/detect returned non-JSON (${resp.slice(0, 120)})`,
        { cause: err },
      );
    }
    if (typeof data?.turn !== 'boolean') {
      throw new CrossroadUnavailableError(
        'malformed-response',
        `/detect response has no boolean "turn" field (${resp.slice(0, 120)})`,
      );
    }

    if (!data.turn) return null;
    return {
      word: typeof data.word === 'string' ? data.word : '',
      index: typeof data.index === 'number' ? data.index : 0,
      score: typeof data.score === 'number' ? data.score : 0,
    };
  }

  /**
   * Map a low-level request failure onto a CrossroadUnavailableError whose
   * message names the actual cause (timeout vs HTTP status vs transport).
   */
  private asUnavailable(err: unknown, what: string): CrossroadUnavailableError {
    if (err instanceof CrossroadUnavailableError) return err;
    const e = err as { name?: string; message?: string };
    if (e?.name === 'AbortError') {
      return new CrossroadUnavailableError('timeout', `${what} exceeded ${this.detectTimeout}ms`, { cause: err });
    }
    const message = e?.message ?? String(err);
    if (/^HTTP \d{3}/.test(message)) {
      return new CrossroadUnavailableError('http-error', message, { cause: err });
    }
    return new CrossroadUnavailableError('http-error', `${what} failed: ${message}`, { cause: err });
  }

  /**
   * Shut down the managed server if one is running via our lockfile.
   * Optional — the idle timer handles shutdown automatically.
   */
  async dispose(): Promise<void> {
    const lock = readLock(this.lockfilePath);
    if (lock && isProcessAlive(lock.pid)) {
      // Prefer a graceful, authenticated HTTP shutdown: on Windows
      // kill(pid, 'SIGTERM') is TerminateProcess (no IPC), so the server's
      // signal handlers never run and it cannot clean up its own lockfile.
      let graceful = false;
      if (lock.token) {
        try {
          await httpPostJson(`http://127.0.0.1:${lock.port}/shutdown`, { token: lock.token }, 3000);
          graceful = true;
        } catch {
          /* fall through to the signal path */
        }
      }
      if (!graceful) {
        try { kill(lock.pid, 'SIGTERM'); } catch { /* ignore */ }
      }
    }
    // Only remove our own lockfile (never a newer server's).
    deleteLock(this.lockfilePath, lock?.pid);
    this.cachedPort = null;
  }

  // ------------------------------------------------------------------
  // Internal: ensure a server is running and return its port
  // ------------------------------------------------------------------

  private async ensureServer(): Promise<number> {
    // Fast path: cached port still alive
    if (this.cachedPort !== null) {
      if (await this.isHealthy(this.cachedPort)) return this.cachedPort;
      this.cachedPort = null;
    }

    // Check lockfile for an existing server
    const lock = readLock(this.lockfilePath);
    if (lock && isProcessAlive(lock.pid)) {
      if (await this.isHealthy(lock.port)) {
        this.cachedPort = lock.port;
        return lock.port;
      }
    }

    // No usable server — spawn one. Concurrent callers share a single spawn.
    if (this.spawnPromise === null) {
      this.spawnPromise = this.spawnServer().finally(() => {
        this.spawnPromise = null;
      });
    }
    return this.spawnPromise;
  }

  private async isHealthy(port: number): Promise<boolean> {
    try {
      const resp = await httpGet(`http://127.0.0.1:${port}/health`, 3000);
      const data = JSON.parse(resp) as { status: string };
      return data.status === 'ok';
    } catch {
      return false;
    }
  }

  private async spawnServer(): Promise<number> {
    if (!existsSync(SERVER_SCRIPT)) {
      throw new CrossroadUnavailableError('spawn-failed', `server script not found: ${SERVER_SCRIPT}`);
    }

    // Clean a stale lockfile — but only if no live server owns it. A live
    // server may have been started by another process between our earlier
    // check and now; deleting would orphan it.
    const existing = readLock(this.lockfilePath);
    if (!(existing && isProcessAlive(existing.pid) && (await this.isHealthy(existing.port)))) {
      deleteLock(this.lockfilePath, existing?.pid);
    } else {
      this.cachedPort = existing.port;
      return existing.port;
    }

    const child = spawn(process.execPath, [SERVER_SCRIPT, '--lockfile', this.lockfilePath], {
      detached: true,
      windowsHide: true,
      stdio: 'ignore',
    });

    // CRITICAL: without an 'error' listener, a failed spawn (ENOENT on the
    // runtime, missing script, EACCES) emits an unhandled 'error' event that
    // aborts the HOST process. Attach a listener so the failure is contained
    // and surfaced as a CrossroadUnavailableError instead.
    let spawnFailed = false;
    let spawnError: unknown = null;
    child.on('error', (err) => { spawnFailed = true; spawnError = err; });

    // A synchronous spawn failure leaves child.pid undefined.
    if (child.pid === undefined) {
      throw new CrossroadUnavailableError(
        'spawn-failed',
        `could not start ${process.execPath} ${SERVER_SCRIPT}` +
          (spawnError ? `: ${(spawnError as Error).message}` : ''),
        { cause: spawnError ?? undefined },
      );
    }
    child.unref();

    // Poll health until ready or timeout
    const deadline = Date.now() + this.spawnTimeout;
    while (Date.now() < deadline) {
      await sleep(300);
      if (spawnFailed) {
        throw new CrossroadUnavailableError(
          'spawn-failed',
          `server process failed to start: ${(spawnError as Error | null)?.message ?? 'unknown error'}`,
          { cause: spawnError ?? undefined },
        );
      }
      const lock = readLock(this.lockfilePath);
      if (lock && isProcessAlive(lock.pid)) {
        if (await this.isHealthy(lock.port)) {
          this.cachedPort = lock.port;
          return lock.port;
        }
      }
    }
    throw new CrossroadUnavailableError(
      'timeout',
      `server did not become healthy within ${this.spawnTimeout}ms`,
    );
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
