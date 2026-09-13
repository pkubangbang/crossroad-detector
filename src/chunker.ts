/**
 * chunker.ts — segment-based tile-by-cap chunker.
 *
 * This is a 1:1 port of trainer/chunker_v2.py (build_segments / _grow_to_cap /
 * build_chunks_v2). The model was trained on windows produced by that chunker,
 * so serving MUST use the same window boundaries — a plain fixed-width tiling
 * over raw character offsets would feed the model out-of-distribution windows.
 *
 * Kept as its own module so both the server and parity tests use the exact
 * same implementation.
 */

/** Character budget approximating DistilBERT's 512-token limit (512 / 1.016). */
export const X_CHARS = 448;
/** Segment size cap; < 0.5 * X_CHARS. */
export const SEG_MAX = 224;

export interface CharSpan { start: number; end: number; }

// Sentence-ending punctuation (Latin + CJK); delimiter stays attached to the
// preceding sub-sentence. Mirrors _SENT_SPLIT in chunker_v2.py.
const SENT_SPLIT = /(?<=[.!?,;:\n。！？，；：])/;

/** Split by sentence-ending punctuation; keep delimiters attached. */
export function splitSubsentences(text: string): string[] {
  return text.split(SENT_SPLIT).filter((p: string) => p.trim().length > 0);
}

/** Split one sub-sentence into <=segMax-char segments (relative offsets). */
export function splitSegments(sub: string, segMax = SEG_MAX): CharSpan[] {
  const out: CharSpan[] = [];
  let i = 0;
  const n = sub.length;
  while (i < n) {
    const j = Math.min(i + segMax, n);
    out.push({ start: i, end: j });
    i = j;
  }
  return out;
}

/** text → list of (start, end) char offsets of segments covering text. */
export function buildSegments(text: string): CharSpan[] {
  const segs: CharSpan[] = [];
  let cursor = 0;
  for (const sub of splitSubsentences(text)) {
    let subStart = text.indexOf(sub, cursor);
    if (subStart < 0) subStart = cursor;
    for (const seg of splitSegments(sub)) {
      segs.push({ start: subStart + seg.start, end: subStart + seg.end });
    }
    cursor = subStart + sub.length;
  }
  // Absorb trailing residue so the last segment reaches the true end.
  if (cursor < text.length) segs.push({ start: cursor, end: text.length });
  return segs;
}

/**
 * Greedily append segments from `left` while total span <= cap.
 * Returns the exclusive right index (one past the last included segment).
 */
function growToCap(segs: CharSpan[], left: number, n: number, cap: number): number {
  let right = left + 1;
  while (right < n && segs[right].end - segs[left].start <= cap) right += 1;
  return right;
}

/**
 * Segment chunker with full, contiguous coverage (tile-by-cap) — mirrors
 * chunker_v2.build_chunks_v2. Returns whole-document char spans, sorted.
 */
export function buildChunksV2(text: string): CharSpan[] {
  const segs = buildSegments(text);
  if (segs.length === 0) return [];
  const n = segs.length;
  const chunks: CharSpan[] = [];
  let left = 0;
  while (left < n) {
    const right = growToCap(segs, left, n, X_CHARS);
    const span: CharSpan = { start: segs[left].start, end: segs[right - 1].end };
    if (span.end > span.start) {
      const last = chunks[chunks.length - 1];
      if (!last || last.start !== span.start || last.end !== span.end) chunks.push(span);
    }
    if (right >= n) break;
    left = right;
  }
  return chunks;
}
