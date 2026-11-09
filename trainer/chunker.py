#!/usr/bin/env python
"""chunker.py - the segment builder: text -> segments -> spans, adaptive overlap.

This is the current and only chunker. Consecutive spans OVERLAP: a turn near a
boundary therefore appears in more than one span, so the model sees the
reversal from more than one offset.

Design:
  SEG_MAX         = 224    # segment max chars; a longer sub-sentence is tiled
  SPAN_TARGET_MAX = 448    # span target upper bound (the "cap")
  SPAN_GROW_MAX   = 672    # buffer expansion upper bound

Segment construction:
  1. split text into sub-sentences by punctuation (.,;:!?\\n and CJK 。，；：！？)
     keeping the delimiter attached to the preceding sub-sentence.
  2. tile each sub-sentence into <= SEG_MAX-char segments (hard char cut,
     CJK-safe).

Algorithm (per document):
  Step 1 (initial buffer): from segment 0, greedily pack the MOST contiguous
    segments whose total span <= SPAN_TARGET_MAX. This is the first span. A
    short document that fits yields a single span covering it all.
  Step 3 (sliding loop, while the buffer's right edge has not reached EOF):
    a. Expand suffix: append segments while total span <= SPAN_GROW_MAX, i.e.
       until adding one more would exceed it (or EOF).
    b. Shrink prefix: drop prefix segments while total span >= SPAN_TARGET_MAX,
       stopping at the FIRST position where span < SPAN_TARGET_MAX (minimal
       drop = maximal overlap). Never shrink past a single segment.
    c. The resulting buffer [left, right) is the next span.
  Step 4 (document end): when the loop exits, the last buffer covers the tail.
    If not already emitted, emit it. A trailing remainder shorter than
    SPAN_TARGET_MAX is allowed - it must merely cover the rest.

Ambiguity resolutions:
  1. Prefix shrink stops at the FIRST span < SPAN_TARGET_MAX.
  2. Start and end are both special: the first span is the initial buffer, the
     last may be a short remainder.

Label: a span is labelled 1 iff the document's first_turn_pos falls inside the
span's [start, end) char range.

Output schema:
  {chunk_id, doc_id, topic_id, lang, scenario, turn_type, text,
   start, end, label, turn_offset_in_chunk, n_chars, provenance}

Usage:
  python chunker.py --in corpus/balanced.jsonl --out corpus/balanced.chunks.jsonl \\
      --report corpus/balanced.chunks.stats.json --seed 42
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

# --- parameters (char approximation of a token budget) ---
SEQ_LEN = 448          # <= 512 / 1.016 chars, safe char budget
SEG_MAX = 224          # < 0.5 * SEQ_LEN; a longer sub-sentence is tiled
SPAN_TARGET_MAX = 2 * SEG_MAX   # 448 - span cap / prefix-shrink target
SPAN_GROW_MAX = 3 * SEG_MAX     # 672 - buffer expansion cap

# punctuation that ends a sub-sentence (Latin + CJK); delimiter kept attached.
_SENT_SPLIT = re.compile(r"(?<=[.!?,;:\n。！？，；：])")


def split_subsentences(text: str) -> list[str]:
    """Split by sentence-ending punctuation; keep delimiters attached."""
    parts = _SENT_SPLIT.split(text)
    return [p for p in parts if p.strip()]


def split_segments(sub: str, seg_max: int = SEG_MAX) -> list[tuple[int, int]]:
    """Split one sub-sentence into <=seg_max-char segments as (start, end)
    offsets RELATIVE to the sub-sentence. Hard char cut (CJK-safe)."""
    out = []
    i, n = 0, len(sub)
    if n == 0:
        return out
    while i < n:
        j = min(i + seg_max, n)
        out.append((i, j))
        i = j
    return out


def build_segments(text: str) -> list[tuple[int, int]]:
    """text -> list of (start, end) char ranges of segments covering text."""
    segs = []
    cursor = 0
    for sub in split_subsentences(text):
        sub_start = text.find(sub, cursor)
        if sub_start < 0:
            sub_start = cursor
        for a, b in split_segments(sub):
            segs.append((sub_start + a, sub_start + b))
        cursor = sub_start + len(sub)
    # absorb trailing residue (e.g. whitespace after the final delimiter) so the
    # last segment reaches the true document end
    if cursor < len(text):
        segs.append((cursor, len(text)))
    return segs


def _grow_suffix_to(segs, left, right, n, cap):
    """Append segments from `right` while total span (segs[left][0] ..
    segs[right-1][1]) stays <= cap. Returns the new exclusive right index.
    Caller guarantees right >= left + 1."""
    while right < n and (segs[right][1] - segs[left][0]) <= cap:
        right += 1
    return right


def _shrink_prefix_below(segs, left, right, cap):
    """Drop prefix segments from `left` while the total span is >= cap, stopping
    at the FIRST position where span < cap (minimal drop). Never shrinks past a
    single segment (left + 1 < right)."""
    while left + 1 < right and (segs[right - 1][1] - segs[left][0]) >= cap:
        left += 1
    return left


def build_spans(text: str, first_turn_pos=None) -> list[tuple[int, int]]:
    """Adaptive overlapping spans. `first_turn_pos` does not affect the spans
    (labelling is done by the caller); it is accepted for signature parity."""
    segs = build_segments(text)
    if not segs:
        return []
    n = len(segs)

    spans = []

    # ---- Step 1: initial buffer, first span ----
    left = 0
    right = _grow_suffix_to(segs, left, left + 1, n, SPAN_TARGET_MAX)
    first = (segs[left][0], segs[right - 1][1])
    if first[1] > first[0]:
        spans.append(first)

    # ---- Step 3: sliding loop ----
    while right < n:
        right = _grow_suffix_to(segs, left, right, n, SPAN_GROW_MAX)
        left = _shrink_prefix_below(segs, left, right, SPAN_TARGET_MAX)
        span = (segs[left][0], segs[right - 1][1])
        if span[1] > span[0] and (not spans or spans[-1] != span):
            spans.append(span)
        # safety: force progress on a degenerate single huge segment
        if (
            right <= _grow_suffix_to(segs, left, left + 1, n, SPAN_GROW_MAX)
            and left == 0
            and right == 1
        ):
            right = min(right + 1, n)

    # ---- Step 4: document end ----
    final = (segs[left][0], segs[n - 1][1])
    if final[1] > final[0] and (not spans or spans[-1] != final):
        spans.append(final)

    # dedupe then sort
    return sorted(set(spans))


def label_span(start, end, first_turn_pos):
    """1 iff first_turn_pos falls inside [start, end); returns (label, offset)."""
    if first_turn_pos is None or first_turn_pos < 0:
        return 0, None
    if start <= first_turn_pos < end:
        return 1, first_turn_pos
    return 0, None


def iter_docs(path: Path):
    for line in path.open("r", encoding="utf-8"):
        line = line.strip()
        if line:
            yield json.loads(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    inp, outp = Path(args.inp), Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    by_lang = Counter()
    by_scenario = Counter()
    by_turn_type = Counter()
    n_docs = n_spans = pos_spans = neg_spans = 0
    pos_lens: list[int] = []
    neg_lens: list[int] = []

    with outp.open("w", encoding="utf-8", newline="\n") as f:
        for doc in iter_docs(inp):
            text = doc["text"]
            has_turn = bool(doc["has_turn"])
            ftp = doc.get("first_turn_pos") if has_turn else None
            if has_turn and (ftp is None or ftp < 0 or ftp >= len(text)):
                continue
            n_docs += 1
            spans = build_spans(text, ftp)
            doc_id = doc["id"]
            for ci, (s, e) in enumerate(spans):
                sub = text[s:e]
                lab, tp = label_span(s, e, ftp)
                n_spans += 1
                if lab:
                    pos_spans += 1
                    pos_lens.append(len(sub))
                else:
                    neg_spans += 1
                    neg_lens.append(len(sub))
                by_lang[doc.get("lang", "en")] += 1
                by_scenario[doc.get("scenario", "?")] += 1
                by_turn_type[doc.get("turn_type", "?")] += 1
                rec = {
                    "chunk_id": f"{doc_id}#{ci}",
                    "doc_id": doc_id,
                    "topic_id": doc.get("topic_id"),
                    "lang": doc.get("lang"),
                    "scenario": doc.get("scenario"),
                    "turn_type": doc.get("turn_type"),
                    "text": sub,
                    "start": s,
                    "end": e,
                    "label": lab,
                    "turn_offset_in_chunk": (tp - s) if tp is not None else -1,
                    "n_chars": len(sub),
                    "provenance": doc.get("provenance"),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    report = {
        "docs": n_docs,
        "spans": n_spans,
        "pos": pos_spans,
        "neg": neg_spans,
        "by_lang": dict(by_lang),
        "by_scenario": dict(by_scenario),
        "by_turn_type": dict(by_turn_type),
        "pos_len_avg": (sum(pos_lens) / len(pos_lens)) if pos_lens else 0,
        "pos_len_min": min(pos_lens) if pos_lens else 0,
        "pos_len_max": max(pos_lens) if pos_lens else 0,
        "neg_len_avg": (sum(neg_lens) / len(neg_lens)) if neg_lens else 0,
        "neg_len_min": min(neg_lens) if neg_lens else 0,
        "neg_len_max": max(neg_lens) if neg_lens else 0,
    }
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
