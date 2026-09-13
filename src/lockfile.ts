/**
 * lockfile.ts — read/write/delete the server lockfile.
 *
 * The lockfile records the running server's { pid, port, startedAt, token } so
 * the client can reuse a live server across processes. The PATH is decided by
 * the caller (the client constructor) and passed to the server via
 * --lockfile; this module has NO hardcoded paths — it does not know about
 * ~/.mycc-store.
 *
 * `token` is a per-server random secret written by the server itself. It lets
 * the client (a) confirm that the process recorded in the lockfile is really
 * *our* server (not an unrelated process that happens to reuse the PID — see
 * isProcessAlive in client.ts) and (b) authenticate privileged requests such
 * as POST /shutdown.
 */

import { existsSync, readFileSync, writeFileSync, unlinkSync, mkdirSync, renameSync } from 'node:fs';
import { dirname } from 'node:path';

export interface LockData {
  pid: number;
  port: number;
  startedAt: number;
  /** Per-server random token; authenticates graceful shutdown and identity. */
  token?: string;
}

/** Read the lockfile. Returns null if missing or unparseable. */
export function readLock(path: string): LockData | null {
  if (!existsSync(path)) return null;
  try {
    const raw = readFileSync(path, 'utf8');
    const data = JSON.parse(raw) as LockData;
    if (typeof data.pid !== 'number' || typeof data.port !== 'number') return null;
    return data;
  } catch {
    return null;
  }
}

/**
 * Atomically write the lockfile, creating parent directories as needed.
 *
 * Writes to a unique temp file in the same directory then renames it into
 * place, so a concurrent reader never observes a half-written (truncated)
 * JSON file. A truncated read would make readLock() return null and could
 * cause a second server to start on the same lockfile.
 */
export function writeLock(path: string, data: LockData): void {
  try {
    mkdirSync(dirname(path), { recursive: true });
    const tmp = `${path}.${process.pid}.tmp`;
    writeFileSync(tmp, JSON.stringify(data), 'utf8');
    renameSync(tmp, path);
  } catch {
    // Best-effort — if we can't write the lock, the server still runs;
    // the client just can't discover it next time.
  }
}

/**
 * Delete the lockfile if it exists. Best-effort.
 *
 * When `expectedPid` is provided, the lockfile is only removed if it still
 * belongs to that PID — so a server that was replaced by a newer one cannot
 * delete the newer server's lockfile on shutdown.
 */
export function deleteLock(path: string, expectedPid?: number): void {
  try {
    if (!existsSync(path)) return;
    if (expectedPid !== undefined) {
      const data = readLock(path);
      if (data && data.pid !== expectedPid) return;
    }
    unlinkSync(path);
  } catch {
    // ignore
  }
}
