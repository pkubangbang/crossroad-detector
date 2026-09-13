/**
 * lockfile.ts — read/write/delete the server lockfile.
 *
 * The lockfile records the running server's { pid, port, startedAt } so the
 * client can reuse a live server across processes. The PATH is decided by the
 * caller (the client constructor) and passed to the server via --lockfile; this
 * module has NO hardcoded paths — it does not know about ~/.mycc-store.
 */

import { existsSync, readFileSync, writeFileSync, unlinkSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

export interface LockData {
  pid: number;
  port: number;
  startedAt: number;
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

/** Write the lockfile, creating parent directories as needed. */
export function writeLock(path: string, data: LockData): void {
  try {
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, JSON.stringify(data), 'utf8');
  } catch {
    // Best-effort — if we can't write the lock, the server still runs;
    // the client just can't discover it next time.
  }
}

/** Delete the lockfile if it exists. Best-effort. */
export function deleteLock(path: string): void {
  try {
    if (existsSync(path)) unlinkSync(path);
  } catch {
    // ignore
  }
}