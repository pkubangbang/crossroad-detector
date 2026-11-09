"""
measure_cut_spacing.py - cut-position spacing distribution over the training corpus.

mycc needs p10/p50/p90 of the gap between adjacent cut positions to re-derive
MIN_PREFIX_LENGTH / MIN_REMAINDER_LENGTH after it switches to this package's
segmenter. The corpus is what the model was trained against, so it is the right
population to measure - not mycc's own transcripts.

The cut grid is reconstructed here with the SAME rule as src/segmenter.ts:
SENT_SPLIT punctuation ('.!?,;:{}' + CJK), a '.' followed by a digit is NOT a
boundary, and a run longer than TILE_MAX is tiled.

Only positive chunks are measured: negatives contain no turn, so no cut is ever
placed in them.

Usage:
  python trainer/measure_cut_spacing.py trainer/corpus/r8_combined.chunks.v3.jsonl
"""

from __future__ import annotations

import json
import sys

TILE_MAX = 224
SENT_TERMINATORS = set(".!?。！？")
CLAUSE_PUNCT = set(",;:，；：")


def cut_positions(text: str) -> list[int]:
    """Reconstruct the cut grid: absolute code-point end offsets, ascending."""
    cp = list(text)  # Python str is already code points
    ends: list[int] = []
    start = 0
    i = 0
    n = len(cp)
    while i < n:
        ch = cp[i]
        kind_sentence = False
        kind_clause = False
        if ch == "\n":
            kind_sentence = True
        elif ch == "\r":
            nxt = cp[i + 1] if i + 1 < n else None
            kind_sentence = nxt is not None and nxt != "\n"
        elif ch in SENT_TERMINATORS:
            nxt = cp[i + 1] if i + 1 < n else None
            if nxt is None:
                kind_sentence = False  # ambiguous tail; flush closes it
            elif nxt.isspace():
                kind_sentence = True
            elif nxt == "." or nxt.isdigit():
                kind_sentence = False  # decimal: "3.14"
            else:
                kind_clause = True
        elif ch in CLAUSE_PUNCT:
            if i + 1 < n:
                kind_clause = True

        if kind_sentence or kind_clause:
            # tile any over-long run, then close at i+1
            while (i + 1) - start > TILE_MAX:
                ends.append(start + TILE_MAX)
                start += TILE_MAX
            ends.append(i + 1)
            start = i + 1
        i += 1

    # flush: trailing text
    if start < n:
        while n - start > TILE_MAX:
            ends.append(start + TILE_MAX)
            start += TILE_MAX
        if n > start:
            ends.append(n)
    return ends


def quantile(sorted_vals: list[int], p: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, int(p * len(sorted_vals)))
    return sorted_vals[idx]


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "trainer/corpus/r8_combined.chunks.v3.jsonl"
    gaps: list[int] = []
    docs = 0
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("label") != 1:
            continue
        docs += 1
        text = obj["text"]
        ends = cut_positions(text)
        gaps.extend(b - a for a, b in zip(ends, ends[1:]))

    gaps.sort()
    print(f"file: {path}")
    print(f"positive chunks: {docs}")
    print(f"gaps measured  : {len(gaps)}")
    if not gaps:
        print("no gaps (each positive is a single cut unit)")
        return 0
    print(
        "min {0} | p10 {1} | p25 {2} | p50 {3} | p75 {4} | p90 {5} | max {6}".format(
            gaps[0],
            quantile(gaps, 0.10),
            quantile(gaps, 0.25),
            quantile(gaps, 0.50),
            quantile(gaps, 0.75),
            quantile(gaps, 0.90),
            gaps[-1],
        )
    )
    for threshold in (15, 30):
        below = sum(1 for g in gaps if g < threshold)
        print(f"  gaps < {threshold}: {below} ({100.0 * below / len(gaps):.1f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
