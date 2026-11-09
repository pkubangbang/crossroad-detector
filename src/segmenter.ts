/**
 * segmenter.ts — incremental iterator over where a cut may land.
 *
 * Vocabulary (settled 2026-11):  token ≪ word ≪ chunk ≪ segment ≪ stream
 *
 * `segment` is the only structural noun. Two properties are stated as
 * sentences rather than as new nouns, because inventing a sixth term is how
 * the confusion started:
 *
 *   - Segments OVERLAP. The classifier is fed from more than one offset
 *     (trainer/chunker.py, and `buildSpans` here), so the same turn can
 *     appear in >= 2 of them.
 *   - Cut positions must be a PARTITION. At a given offset exactly one unit is
 *     being replaced, so cut positions cannot overlap.
 *
 * Those two statements are incompatible with a single span set, which is why
 * this module exists separately from `buildSpans`. It does not name a new
 * level in the vocabulary — it returns segments, contiguous and
 * non-overlapping, each carrying the kind of boundary that closed it.
 *
 * A cut unit can legitimately be finer than CLAUSE_TILE_MAX (224): it ends at the
 * first permitted punctuation boundary OR at the cap, so a 9-code-point
 * `" However,"` is a valid cut candidate. Adjacent cut positions are therefore
 * at LEAST one punctuation mark apart and AT MOST `segMax` apart — do not
 * assume a uniform spacing.
 *
 * Two guarantees consumers depend on:
 *   1. Offsets are ABSOLUTE and CUMULATIVE code-point offsets into everything
 *      pushed so far — push("abc") then push("def") yields offsets into
 *      "abcdef".
 *   2. A returned segment is FINAL: never re-emitted, never amended. Only
 *      `pending` (the uncommitted tail) can still change.
 *
 * `push` may therefore return []: a segment ending in '.' is ambiguous, since
 * "3." may become "3.14" on the next delta. The boundary is not confirmed
 * until the following character is known (or `flush` is called).
 */

import { CLAUSE_TILE_MAX, toCodePoints } from './chunker.js';

/** How a segment's right boundary was chosen. */
export type SegmentCutKind =
  /** Ended at a newline, or a terminator followed by whitespace/EOL. */
  | 'sentence'
  /** Ended at clause punctuation (',' ';' ':' '，' '；' '：'). */
  | 'clause'
  /** Hit CLAUSE_TILE_MAX mid-clause (the tiler). NOT a safe cutpoint. */
  | 'forced';

export interface Segment {
  /** Code-point offset, absolute, inclusive. */
  start: number;
  /** Code-point offset, absolute, exclusive. */
  end: number;
  /** How this segment's right boundary was chosen. `'forced'` means the
   *  boundary is the tiler cap, so it may fall mid-word — a consumer that
   *  shows the cut to a user should refuse it. */
  cutKind: SegmentCutKind;
}

export interface SegmenterOptions {
  /** Hard cap on a segment, mirroring CLAUSE_TILE_MAX. Default 224. */
  segMax?: number;
  /**
   * Which punctuation may OPEN a boundary. This restricts *where* a boundary
   * may fall; it does NOT change segment width, and it cannot produce a
   * sub-`segMax` segment on its own (a segment ends only at a permitted
   * boundary or at the cap).
   *
   *  - 'trained' (default): every SENT_SPLIT punctuation mark — the rule the
   *    model's training segments were built from, so boundaries align.
   *  - 'sentence': newline / terminator+whitespace only. A SUBSET of the
   *    trained set, so it never introduces a boundary training does not have.
   *
   * The model's own segment set (`buildSpans`) takes no split policy — it
   * must match training exactly.
   */
  splitPolicy?: 'trained' | 'sentence';
}

export interface Segmenter {
  /** Feed a delta; returns segments whose boundaries are now FINAL. */
  push(delta: string): Segment[];
  /** Emit the trailing partial segment (end of input). */
  flush(): Segment[];
  /** Text held back awaiting more input (the uncommitted tail). */
  readonly pending: string;
}

const SENTENCE_TERMINATORS = new Set(['.', '!', '?', '。', '！', '？']);
const CLAUSE_PUNCT = new Set([',', ';', ':', '，', '；', '：']);

function isSpace(ch: string): boolean {
  return /\s/.test(ch);
}

export function createSegmenter(options?: SegmenterOptions): Segmenter {
  const segMax = options?.segMax ?? CLAUSE_TILE_MAX;
  const policy = options?.splitPolicy ?? 'trained';

  /** All code points pushed so far — the absolute offset frame. */
  const frame: string[] = [];
  /** Index in `frame` of the first code point not yet emitted. */
  let emitted = 0;

  /** Does `ch` end a segment under the current policy? */
  function isBoundaryAt(i: number): SegmentCutKind | null {
    const ch = frame[i];
    if (ch === '\n') return 'sentence';
    // '\r' only ends a segment when it is NOT part of a CRLF pair. A bare
    // "\r\n" would otherwise emit two sentences ("…\r" and "\n"), producing a
    // degenerate one-character segment that is not a real boundary.
    if (ch === '\r') {
      const next = i + 1 < frame.length ? frame[i + 1] : undefined;
      if (next === undefined) return null; // may become CRLF
      return next === '\n' ? null : 'sentence';
    }
    if (SENTENCE_TERMINATORS.has(ch)) {
      const next = i + 1 < frame.length ? frame[i + 1] : undefined;
      if (next === undefined) return null; // ambiguous until next char
      // '.' followed by a digit is a decimal ("3.14"), not a sentence end —
      // the same rule firstSentenceEnd enforces on mycc's side.
      if (isSpace(next)) return 'sentence';
      if (next === '.' || /\d/.test(next)) return null;
      return 'clause';
    }
    if (policy === 'trained' && CLAUSE_PUNCT.has(ch)) {
      const next = i + 1 < frame.length ? frame[i + 1] : undefined;
      if (next === undefined) return null;
      return 'clause';
    }
    return null;
  }

  /** Emit one confirmed run [start,end) as segments, tiling if too long. */
  function emitRun(out: Segment[], start: number, end: number, kind: SegmentCutKind): void {
    let cursor = start;
    // Tile only when the run exceeds the cap; tiled pieces are 'forced', and
    // the final piece keeps whatever the run was closed by.
    while (end - cursor > segMax) {
      out.push({ start: cursor, end: cursor + segMax, cutKind: 'forced' });
      cursor += segMax;
    }
    if (end > cursor) out.push({ start: cursor, end, cutKind: kind });
  }

  function drain(final: boolean): Segment[] {
    const out: Segment[] = [];
    let start = emitted;

    for (let i = emitted; i < frame.length; i++) {
      const ch = frame[i];

      // A terminator at the very end is AMBIGUOUS: "3." may still become
      // "3.14". Stop here and leave the rest pending, unless this is the end
      // of input (flush), where nothing more can arrive.
      const isTerminator = SENTENCE_TERMINATORS.has(ch);
      if (isTerminator && i === frame.length - 1 && !final) break;

      const kind = isBoundaryAt(i);
      if (kind === null) continue;

      emitRun(out, start, i + 1, kind);
      start = i + 1;
    }

    if (final && start < frame.length) {
      emitRun(out, start, frame.length, 'sentence');
      start = frame.length;
    } else if (!final) {
      // Steady progress for a very long unpunctuated run: emit forced pieces
      // but keep the remainder (< segMax) pending.
      while (frame.length - start > segMax) {
        out.push({ start, end: start + segMax, cutKind: 'forced' });
        start += segMax;
      }
    }

    emitted = start;
    return out;
  }

  return {
    push(delta: string): Segment[] {
      if (delta.length === 0) return [];
      for (const ch of toCodePoints(delta)) frame.push(ch);
      return drain(false);
    },
    flush(): Segment[] {
      return drain(true);
    },
    get pending(): string {
      return frame.slice(emitted).join('');
    },
  };
}

/** One-shot convenience: buffer the whole text and segment it. */
export function segmentsOf(text: string, options?: SegmenterOptions): Segment[] {
  const s = createSegmenter(options);
  return [...s.push(text), ...s.flush()];
}
