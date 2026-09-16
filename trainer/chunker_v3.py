#!/usr/bin/env python
"""chunker_v3.py — segment-based ADAPTIVE OVERLAPPING chunker.

Supersedes chunker_v2.py (which is non-overlapping tile-by-cap) with a
segment-level sliding window that OVERLAPS between consecutive chunks, so a
turn near a boundary appears in >=2 windows. chunker_v2.py is left untouched.

Design (user spec, confirmed 2026-09-16):
  X = SEG_MAX = 224         # segment max chars; calculateToken(2X) <= ctx
  TWO_X  = 2 * X = 448     # window target upper bound (chunk "cap")
  THREE_X = 3 * X = 672    # buffer expansion upper bound

  Segment construction is identical to v2 (sub-sentence split + hard 224-char
  cap). build_segments is imported from chunker_v2 to guarantee the two
  chunkers share the exact same segment lattice.

  Algorithm (per document):
    Step 1 (initial buffer): from segment 0, greedily pack the MOST contiguous
      segments whose total span <= TWO_X (448). This is the first chunk. A short
      document that fits in <= TWO_X yields a single chunk covering it all
      (special handling at the start).
    Step 3 (sliding loop, while the buffer's right edge has not reached EOF):
      a. Expand suffix: append segments while total span <= THREE_X (672), such
         that adding one more would exceed it (or EOF reached).
      b. Shrink prefix: drop prefix segments while total span >= TWO_X (448),
         stopping at the FIRST position where span < TWO_X (i.e. minimal drop —
         maximal overlap). Do not shrink past a single segment.
      c. The resulting buffer [left, right) is the next chunk.
    Step 4 (document end, special handling): when the loop exits because right
      reached EOF, the last buffer already covers the document tail. If its span
      has not already been emitted as a chunk, emit it. A trailing remainder may
      be shorter than TWO_X; that is allowed — it must merely cover the rest.

  Ambiguity resolutions (confirmed by user):
    1. Prefix shrink stops at the FIRST span < TWO_X (not the shortest possible).
    2. The start and the end are both specially handled: the first chunk is the
       initial <= TWO_X buffer; the last chunk may be a < TWO_X remainder.

  Label: a chunk is labelled 1 iff the document's first_turn_pos falls inside
         the chunk's [start, end) char span.

Output schema matches chunker_v2.py exactly so train.py / eval_test /
export_misclassified consume it unchanged:
  {chunk_id, doc_id, topic_id, lang, scenario, turn_type, text,
   start, end, label, turn_offset_in_chunk, n_chars, provenance}

Usage:
  python chunker_v3.py --in corpus/balanced.jsonl --out corpus/balanced.chunks.v3.jsonl \
      --report corpus/balanced.chunks.v3.stats.json --seed 42
"""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path

# --- segment lattice shared with v2 (same sub-sentence + 224-char cap) ---
from chunker_v2 import build_segments, label_chunk, iter_docs, SEG_MAX

# --- adaptive overlap parameters ---
X = SEG_MAX            # 224
TWO_X = 2 * X          # 448  — window cap / shrink target
THREE_X = 3 * X        # 672  — buffer expansion cap


def _grow_suffix_to(segs, left, right, n, cap):
    """Append segments from `right` while total span (segs[left].start ..
    segs[right-1].end) stays <= cap. Returns the new exclusive right index.
    Grows by at least zero (caller guarantees right is a valid start)."""
    while right < n and (segs[right][1] - segs[left][0]) <= cap:
        right += 1
    return right


def _shrink_prefix_below(segs, left, right, cap):
    """Drop prefix segments from `left` while the total span is >= cap, but
    stop at the FIRST position where span < cap (minimal drop = maximal
    overlap). Never shrinks past a single segment (left+1 < right)."""
    while (left + 1 < right) and (segs[right - 1][1] - segs[left][0]) >= cap:
        left += 1
    return left


def build_chunks_v3(text: str, first_turn_pos):
    """Segment-level adaptive overlapping sliding window.

    Returns a list of (start, end) char spans covering the whole document,
    sorted, with overlap between consecutive chunks. Chunks other than the
    first/last special cases are bounded by THREE_X (672) after suffix growth
    and by < TWO_X (448) after prefix shrink.
    """
    segs = build_segments(text)
    if not segs:
        return []
    n = len(segs)

    chunks = []

    # ---- Step 1: initial buffer, first chunk (start special handling) ----
    left = 0
    right = _grow_suffix_to(segs, left, left + 1, n, TWO_X)
    span = (segs[left][0], segs[right - 1][1])
    if span[1] > span[0]:
        chunks.append(span)

    # ---- Step 3: sliding loop ----
    while right < n:
        # (a) expand suffix to <= THREE_X
        right = _grow_suffix_to(segs, left, right, n, THREE_X)
        # (b) shrink prefix to first < TWO_X (minimal drop)
        left = _shrink_prefix_below(segs, left, right, TWO_X)
        # (c) emit chunk
        span = (segs[left][0], segs[right - 1][1])
        if span[1] > span[0] and (not chunks or chunks[-1] != span):
            chunks.append(span)
        # Safety: if the window did not advance (degenerate single huge segment),
        # force right forward to guarantee progress.
        if right <= _grow_suffix_to(segs, left, left + 1, n, THREE_X) and left == 0 and right == 1:
            right = min(right + 1, n)

    # ---- Step 4: document end (special handling) ----
    # When the loop exited, right == n (EOF). The last buffer [left, n) already
    # covers the tail. If its span was not emitted (e.g. the final iteration's
    # emit was skipped because it duplicated the previous chunk), emit it now.
    final_span = (segs[left][0], segs[n - 1][1])
    if final_span[1] > final_span[0] and (not chunks or chunks[-1] != final_span):
        chunks.append(final_span)

    chunks = sorted(set(chunks))
    return chunks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    inp, outp = Path(args.inp), Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    by_lang = Counter(); by_scenario = Counter(); by_turn_type = Counter()
    n_docs = n_chunks = pos_chunks = neg_chunks = 0
    pos_len = neg_len = 0
    pos_lens = []; neg_lens = []

    with outp.open("w", encoding="utf-8", newline="\n") as f:
        for doc in iter_docs(inp):
            text = doc["text"]
            has_turn = bool(doc["has_turn"])
            ftp = doc.get("first_turn_pos") if has_turn else None
            if has_turn and (ftp is None or ftp < 0 or ftp >= len(text)):
                continue
            n_docs += 1
            spans = build_chunks_v3(text, ftp)
            doc_id = doc["id"]
            for ci, (s, e) in enumerate(spans):
                sub = text[s:e]
                lab, tp = label_chunk(s, e, ftp)
                n_chunks += 1
                if lab:
                    pos_chunks += 1; pos_len += len(sub); pos_lens.append(len(sub))
                else:
                    neg_chunks += 1; neg_len += len(sub); neg_lens.append(len(sub))
                by_lang[doc.get("lang", "en")] += 1
                by_scenario[doc.get("scenario", "analysis")] += 1
                by_turn_type[doc.get("turn_type", "none") if lab else "none"] += 1
                f.write(json.dumps({
                    "chunk_id": f"{doc_id}#{ci}",
                    "doc_id": doc_id,
                    "topic_id": doc.get("topic_id", doc_id),
                    "lang": doc.get("lang", "en"),
                    "scenario": doc.get("scenario", "analysis"),
                    "turn_type": doc.get("turn_type", "none") if lab else "none",
                    "text": sub,
                    "start": s,
                    "end": e,
                    "label": lab,
                    "turn_offset_in_chunk": (tp - s) if tp is not None else -1,
                    "n_chars": len(sub),
                    "provenance": doc.get("provenance", "generated"),
                }, ensure_ascii=False) + "\n")

    def avg(xs): return round(sum(xs) / len(xs), 1) if xs else 0
    stats = {
        "chunker": "v3 segment adaptive overlap (X=224 TWO_X=448 THREE_X=672)",
        "documents": n_docs,
        "chunks": n_chunks,
        "pos_chunks": pos_chunks,
        "neg_chunks": neg_chunks,
        "pos_neg_ratio": round(neg_chunks / max(1, pos_chunks), 1),
        "by_lang": dict(by_lang),
        "by_scenario": dict(by_scenario),
        "by_turn_type": dict(by_turn_type),
        "pos_len_avg": avg(pos_lens), "pos_len_min": min(pos_lens) if pos_lens else 0,
        "pos_len_max": max(pos_lens) if pos_lens else 0,
        "neg_len_avg": avg(neg_lens), "neg_len_min": min(neg_lens) if neg_lens else 0,
        "neg_len_max": max(neg_lens) if neg_lens else 0,
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    if args.report:
        Path(args.report).write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())