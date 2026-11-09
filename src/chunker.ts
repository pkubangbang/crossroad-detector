/**
 * chunker.ts - the current segment builder (adaptive overlapping).
 *
 * uildSpans is a 1:1 port of trainer/chunker.py. The model was trained on
 * the spans it produces, so serving MUST use the same boundaries - a
 * fixed-width tiling over raw character offsets would feed the model
 * out-of-distribution input.
 *
 * These spans OVERLAP. Consecutive spans deliberately share text so a turn near
 * a boundary is seen from more than one offset. Because they overlap they are
 * NOT cut positions: at a given offset two spans can both contain the text.
 * Cut positions must be a partition, and createSegmenter (segmenter.ts)
 * produces those.
 *
 * All offsets in this module are CODE POINTS, not UTF-16 code units.
 */

/**
 * The input sequence length, and the target upper bound for one span.
 * They are equal (448), so a span fits the model's fixed sequence without
 * truncation.
 */
export const SEQ_LEN = 448;
/** Segment size cap: a longer sub-sentence is tiled; < 0.5 * SEQ_LEN. */
export const CLAUSE_TILE_MAX = 224;

// --- adaptive-overlap parameters ---
/** Segment max size = SEG_MAX. In the Python spec this is `X`. */
export const GROW_UNIT = CLAUSE_TILE_MAX; // 224
/** Input-span target upper bound (the span "cap"). */
export const SPAN_TARGET_MAX = 2 * GROW_UNIT; // 448
/** Buffer expansion upper bound during the suffix-growth step. */
export const SPAN_GROW_MAX = 3 * GROW_UNIT; // 672

export interface CharSpan { start: number; end: number; }

// Sentence-ending punctuation (Latin + CJK); delimiter stays attached to the
// preceding sub-sentence. Mirrors _SENT_SPLIT in chunker.py.
const SENT_SPLIT = /(?<=[.!?,;:\n。！？，；：])/;

/**
 * Convert a JS string to an array of Unicode code points.
 *
 * Python strings index by CODE POINT; JS strings index by UTF-16 code unit.
 * An astral character (emoji, e.g. U+1F310) is 1 code point in Python but 2
 * units in JS, so the two engines disagree on every offset after the first
 * astral char. The training corpus offsets are Python (code-point) offsets, so
 * the serving chunker MUST also work in code points or the windows drift
 * (verified: 4/3919 docs diverged before this fix, e.g. ref end 900 vs 902).
 */
export function toCodePoints(text: string): string[] {
  return Array.from(text);
}

/** Split code points by sentence-ending punctuation; keep delimiters attached.
 *  Mirrors `[p for p in _SENT_SPLIT.split(text) if p.strip()]` but returns
 *  absolute code-point spans directly. */
function splitSubsentencesCp(cp: string[]): CharSpan[] {
  const spans: CharSpan[] = [];
  let start = 0;
  for (let i = 0; i < cp.length; i++) {
    if (SENT_SPLIT.test(cp[i])) {
      // delimiter ends the sub-sentence at i (inclusive)
      const end = i + 1;
      if (nonBlank(cp, start, end)) spans.push({ start, end });
      start = end;
    }
  }
  if (start < cp.length && nonBlank(cp, start, cp.length)) {
    spans.push({ start, end: cp.length });
  }
  return spans;
}

function nonBlank(cp: string[], start: number, end: number): boolean {
  for (let i = start; i < end; i++) if (!isWhitespace(cp[i])) return true;
  return false;
}

function isWhitespace(ch: string): boolean {
  return /\s/.test(ch);
}

/** Split one sub-sentence span into <=segMax-code-point segments. */
function splitSegmentsCp(start: number, end: number, segMax = CLAUSE_TILE_MAX): CharSpan[] {
  const out: CharSpan[] = [];
  let i = start;
  while (i < end) {
    const j = Math.min(i + segMax, end);
    out.push({ start: i, end: j });
    i = j;
  }
  return out;
}

/** text → list of (start, end) CODE-POINT offsets of segments covering text. */
export function buildSegments(text: string): CharSpan[] {
  const cp = toCodePoints(text);
  const segs: CharSpan[] = [];
  for (const sub of splitSubsentencesCp(cp)) {
    for (const seg of splitSegmentsCp(sub.start, sub.end)) segs.push(seg);
  }
  // Absorb trailing residue so the last segment reaches the true end.
  const covered = segs.length ? segs[segs.length - 1].end : 0;
  if (covered < cp.length) segs.push({ start: covered, end: cp.length });
  return segs;
}

/** Keep splitSubsentences/splitSegments as back-compat aliases. */
export function splitSubsentences(text: string): string[] {
  const cp = toCodePoints(text);
  return splitSubsentencesCp(cp).map((s) => cp.slice(s.start, s.end).join(''));
}
export function splitSegments(sub: string, segMax = CLAUSE_TILE_MAX): CharSpan[] {
  return splitSegmentsCp(0, toCodePoints(sub).length, segMax);
}

/** Slice `text` by CODE-POINT offsets [start, end) — the offsets produced by
 *  buildSegments/buildSpans. Do NOT use String.prototype.slice on these
 *  offsets: it indexes UTF-16 units and will misalign on astral characters. */
export function sliceCodePoints(cp: string[], start: number, end: number): string {
  return cp.slice(start, end).join('');
}

// ============================================================================
// Adaptive overlapping segment builder
// (1:1 port of trainer/chunker.py: build_spans)
// ============================================================================

/**
 * Append segments from `right` while total span (segs[left].start ..
 * segs[right-1].end) stays <= cap. Returns the new exclusive right index.
 * Caller guarantees `right` is a valid start (right >= left + 1).
 */
function growSuffixTo(segs: CharSpan[], left: number, right: number, n: number, cap: number): number {
  while (right < n && segs[right].end - segs[left].start <= cap) right += 1;
  return right;
}

/**
 * Drop prefix segments from `left` while the total span is >= cap, but stop at
 * the FIRST position where span < cap (minimal drop = maximal overlap).
 * Never shrinks past a single segment (left + 1 < right).
 */
function shrinkPrefixBelow(segs: CharSpan[], left: number, right: number, cap: number): number {
  while (left + 1 < right && segs[right - 1].end - segs[left].start >= cap) left += 1;
  return left;
}

/**
 * Segment-level adaptive overlapping sliding window — mirrors
 * chunker.build_spans. Returns whole-document char spans, sorted, with
 * overlap between consecutive chunks so a turn near a boundary appears in >= 2
 * windows. Chunks other than the first/last special cases are bounded by
 * SPAN_GROW_MAX after suffix growth and by < SPAN_TARGET_MAX after prefix shrink.
 *
 * The `firstTurnPos` argument mirrors the Python signature; it does not affect
 * the spans (labelling is done by the caller / training harness).
 */
export function buildSpans(text: string, firstTurnPos?: number | null): CharSpan[] {
  void firstTurnPos; // spans are independent of the turn position, as in Python
  const segs = buildSegments(text);
  if (segs.length === 0) return [];
  const n = segs.length;

  const chunks: CharSpan[] = [];
  const same = (a: CharSpan, b: CharSpan): boolean => a.start === b.start && a.end === b.end;

  // ---- Step 1: initial buffer, first chunk (start special handling) ----
  let left = 0;
  let right = growSuffixTo(segs, left, left + 1, n, SPAN_TARGET_MAX);
  const first: CharSpan = { start: segs[left].start, end: segs[right - 1].end };
  if (first.end > first.start) chunks.push(first);

  // ---- Step 3: sliding loop ----
  while (right < n) {
    // (a) expand suffix to <= SPAN_GROW_MAX
    right = growSuffixTo(segs, left, right, n, SPAN_GROW_MAX);
    // (b) shrink prefix to first < SPAN_TARGET_MAX (minimal drop = maximal overlap)
    left = shrinkPrefixBelow(segs, left, right, SPAN_TARGET_MAX);
    // (c) emit chunk
    const span: CharSpan = { start: segs[left].start, end: segs[right - 1].end };
    if (span.end > span.start && (chunks.length === 0 || !same(chunks[chunks.length - 1], span))) {
      chunks.push(span);
    }
    // Safety: if the window did not advance (degenerate single huge segment),
    // force right forward to guarantee progress. Mirrors the Python guard.
    if (right <= growSuffixTo(segs, left, left + 1, n, SPAN_GROW_MAX) && left === 0 && right === 1) {
      right = Math.min(right + 1, n);
    }
  }

  // ---- Step 4: document end (special handling) ----
  const finalSpan: CharSpan = { start: segs[left].start, end: segs[n - 1].end };
  if (finalSpan.end > finalSpan.start && (chunks.length === 0 || !same(chunks[chunks.length - 1], finalSpan))) {
    chunks.push(finalSpan);
  }

  // Mirror Python `sorted(set(chunks))`: dedupe identical spans then sort.
  // JS objects compare by reference, so dedupe on (start,end) explicitly.
  const seen = new Set<string>();
  const unique: CharSpan[] = [];
  for (const c of chunks) {
    const k = `${c.start}:${c.end}`;
    if (!seen.has(k)) { seen.add(k); unique.push(c); }
  }
  unique.sort((a, b) => (a.start - b.start) || (a.end - b.end));
  return unique;
}
