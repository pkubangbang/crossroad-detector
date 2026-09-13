#!/usr/bin/env python
"""doc_leak_check.py — measure whether a single DOCUMENT is torn across splits.

WHY
---
`train.py`'s `split_by_topic` groups rows by `topic_id`. But a `doc_id` can map
to more than one `topic_id` (27 such docs exist in the v2 chunk corpus), so one
document's windows can land in different splits — overlapping windows of the
same text then appear in both train and test. That is genuine leakage, and a
topic-level check cannot see it: `check_topic_leak.py` compares topic_id SETS
per split and therefore reports 0.

Fix direction: the document is the atomic unit; group by `doc_id`.

Usage:
  python doc_leak_check.py --chunks corpus/balanced.chunks.v2.jsonl
  python doc_leak_check.py --chunks corpus/balanced.chunks.v2.jsonl --seeds 42 7
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from train import load_chunks, split_by_topic  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--seeds", type=int, nargs="*", default=[42, 7, 123, 2024, 99])
    args = ap.parse_args()

    rows = load_chunks(Path(args.chunks))

    # docs whose rows carry more than one topic_id
    d2t: dict[str, set] = defaultdict(set)
    for r in rows:
        d2t[r["doc_id"]].add(r["topic_id"])
    multi = {d for d, t in d2t.items() if len(t) > 1}
    print(f"chunks={len(rows)}  docs={len(d2t)}  docs_with_multiple_topic_ids={len(multi)}")
    for d in sorted(multi)[:5]:
        print(f"   {d[:40]:42s} -> {len(d2t[d])} topic_ids")
    if len(multi) > 5:
        print(f"   ... and {len(multi) - 5} more")

    print("\nper-seed document leakage (a doc_id appearing in >1 split):")
    total = 0
    for seed in args.seeds:
        tr, va, te = split_by_topic(rows, seed)
        where: dict[str, set] = defaultdict(set)
        for name, part in (("train", tr), ("val", va), ("test", te)):
            for r in part:
                where[r["doc_id"]].add(name)
        torn = {d for d, s in where.items() if len(s) > 1}
        chunks = sum(1 for r in rows if r["doc_id"] in torn)
        total += len(torn)
        print(f"  seed={seed:<6d} docs_torn={len(torn):<3d} chunks_involved={chunks}")

    print()
    if total == 0:
        print("VERDICT: 0 documents torn across splits — split unit is correct.")
    else:
        print(f"VERDICT: {total} doc-leak occurrences across seeds — leak present; "
              f"group by doc_id to fix.")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
