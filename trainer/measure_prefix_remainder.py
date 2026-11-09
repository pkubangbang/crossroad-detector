"""
measure_prefix_remainder.py - grid-independent "worth showing" measurement.

mycc's MIN_PREFIX_LENGTH / MIN_REMAINDER_LENGTH ask two product questions:

  prefix   - has enough been committed that replacing the rest reads as a
             pivot rather than a deletion?
  remainder- is what survives long enough to be worth keeping?

Both are measured in characters of TEXT, so they do not depend on the cut grid.
This script reports, over every POSITIVE chunk in a corpus, the prefix length
before the turn and the remainder length after it - not the gap between
adjacent cut positions (that is a grid property, and is reported separately by
measure_cut_spacing.py).

The turn position is taken from the corpus where available (`turn_pos` /
`first_turn_pos`); when absent, the first HINT marker is used as a proxy and the
row is count_as="proxy" so the two populations can be told apart.

Usage:
  python trainer/measure_prefix_remainder.py trainer/corpus/r8_combined.chunks.v3.jsonl
"""

from __future__ import annotations

import json
import re
import sys

HINT = re.compile(
    r"(\bhowever\b|\bwait\b|\bbut\b|\bactually\b|\breconsider\b|\bon second thought\b"
    r"|但|不过|其实|然而|等等|话说回来)",
    re.IGNORECASE,
)


def quantile(sorted_vals: list[int], p: float) -> int:
    if not sorted_vals:
        return 0
    return sorted_vals[min(len(sorted_vals) - 1, int(p * len(sorted_vals)))]


def summarise(label: str, vals: list[int]) -> None:
    vals.sort()
    if not vals:
        print(f"{label}: none")
        return
    print(
        f"{label}: n={len(vals)} min={vals[0]} p10={quantile(vals, .10)} "
        f"p25={quantile(vals, .25)} p50={quantile(vals, .50)} "
        f"p75={quantile(vals, .75)} p90={quantile(vals, .90)} max={vals[-1]}"
    )


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "trainer/corpus/r8_combined.chunks.v3.jsonl"
    prefixes: list[int] = []
    remainders: list[int] = []
    labels_used: list[int] = []
    proxied = 0

    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if obj.get("label") != 1:
            continue
        text = obj["text"]
        pos = obj.get("turn_offset_in_chunk")
        if pos is None:
            pos = obj.get("turn_pos", obj.get("first_turn_pos"))
        if pos is None:
            m = HINT.search(text)
            if not m:
                continue
            pos = m.start()
            proxied += 1
        prefixes.append(pos)
        remainders.append(len(text) - pos)
        labels_used.append(int(obj.get("label", 1)))

    print(f"file: {path}")
    print(f"positives measured: {len(prefixes)}  (turn position proxied from first HINT marker: {proxied})")
    print()
    summarise("prefix   (chars before the turn)", prefixes)
    summarise("remainder(chars after  the turn)", remainders)
    print()
    for t in (4, 8, 12, 15, 20, 30):
        p_below = sum(1 for v in prefixes if v < t)
        r_below = sum(1 for v in remainders if v < t)
        n = max(1, len(prefixes))
        print(
            f"  threshold {t:>3}: prefix below {100.0 * p_below / n:5.1f}%"
            f"   remainder below {100.0 * r_below / n:5.1f}%"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
