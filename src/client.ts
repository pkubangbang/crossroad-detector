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
 * down after 15 min idle. If the package is not installed, the server fails
 * to start, or any error occurs, detect() returns null so the caller can fall
 * back (e.g. to a regex detector).
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
  private cachedPort: number | null = null;
  /** In-flight spawn so concurrent detect() calls share ONE server. */
  private spawnPromise: Promise<number | null> | null = null;

  constructor(lockfilePath: string, options?: CrossroadDetectorOptions) {
    this.lockfilePath = lockfilePath;
    this.threshold = options?.threshold ?? 0.5;
    this.spawnTimeout = options?.spawnTimeout ?? 15000;
  }

  /**
   * Detect a turning word in the given text.
   * Returns the match, or null if no turn is detected or the server is
   * unavailable (caller should fall back).
   */
  async detect(content: string): Promise<TurningWordMatch | null> {
    try {
      const port = await this.ensureServer();
      if (port === null) return null;
      const url = `http://127.0.0.1:${port}/detect`;
      const resp = await httpPostJson(url, { text: content, threshold: this.threshold }, 30000);
      const data = JSON.parse(resp) as { turn: boolean; word?: string; index?: number; score?: number };
      if (!data.turn) return null;
      return {
        word: typeof data.word === 'string' ? data.word : '',
        index: typeof data.index === 'number' ? data.index : 0,
        score: typeof data.score === 'number' ? data.score : 0,
      };
    } catch {
      return null;
    }
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

  private async ensureServer(): Promise<number | null> {
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

  private async spawnServer(): Promise<number | null> {
    if (!existsSync(SERVER_SCRIPT)) return null;

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
    // aborts the HOST process — violating this SDK's "return null on any
    // error" contract. Attach a no-op listener so the failure is contained.
    let spawnFailed = false;
    child.on('error', () => { spawnFailed = true; });

    // A synchronous spawn failure leaves child.pid undefined.
    if (child.pid === undefined) {
      return null;
    }
    child.unref();

    // Poll health until ready or timeout
    const deadline = Date.now() + this.spawnTimeout;
    while (Date.now() < deadline) {
      await sleep(300);
      if (spawnFailed) return null;
      const lock = readLock(this.lockfilePath);
      if (lock && isProcessAlive(lock.pid)) {
        if (await this.isHealthy(lock.port)) {
          this.cachedPort = lock.port;
          return lock.port;
        }
      }
    }
    return null;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
