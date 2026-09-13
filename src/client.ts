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
  /** Character offset of the detected turn in the ORIGINAL content. */
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
  } catch {
    return false;
  }
}

// ============================================================================
// HTTP helpers
// ============================================================================

function httpGet(url: string, timeoutMs: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const req = fetchUrl('GET', url, undefined, timeoutMs);
    req.then(resolve).catch(reject);
  });
}

function httpPostJson(url: string, body: unknown, timeoutMs: number): Promise<string> {
  return fetchUrl('POST', url, JSON.stringify(body), timeoutMs);
}

function fetchUrl(method: string, url: string, body: string | undefined, timeoutMs: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const init: RequestInit = { method, signal: controller.signal };
    if (body !== undefined) {
      init.headers = { 'Content-Type': 'application/json' };
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
        word: data.word ?? '',
        index: data.index ?? 0,
        score: data.score ?? 0,
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
      try { kill(lock.pid, 'SIGTERM'); } catch { /* ignore */ }
    }
    deleteLock(this.lockfilePath);
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

    // No usable server — spawn one
    return this.spawnServer();
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

    // Clean stale lockfile
    deleteLock(this.lockfilePath);

    const child = spawn(process.execPath, [SERVER_SCRIPT, '--lockfile', this.lockfilePath], {
      detached: true,
      windowsHide: true,
      stdio: 'ignore',
    });
    child.unref();

    // Poll health until ready or timeout
    const deadline = Date.now() + this.spawnTimeout;
    while (Date.now() < deadline) {
      await sleep(300);
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