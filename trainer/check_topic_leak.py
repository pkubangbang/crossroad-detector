#!/usr/bin/env python
"""check_topic_leak.py — audit topic_id hygiene across the chunk corpus.

WHY THIS EXISTS
---------------
`train.py` splits train/val/test by `topic_id` (train.py:6-7 calls a reused
topic across splits "exactly the v2 failure"). Peers are told their topic_ids
must be globally unique, but duplicates appear in practice, so the invariant
needs to be checkable rather than assumed.

WHAT A DUPLICATED topic_id DOES *NOT* CAUSE (measured, not assumed):
`split_by_topic` first groups rows by topic_id into a dict, THEN assigns whole
TOPICS to splits. A duplicated topic_id maps to ONE dict entry, so all of its
rows always travel into the SAME split. Measured across 5 seeds: 0 cross-split
topic leakage. This is the opposite of the intuitive reading, so it is asserted
here as a checked invariant rather than left to memory.

WHAT IT *DOES* CAUSE:
  (a) hygiene noise — 728 duplicated topic_ids / ~47% of rows, mostly because
      each harvested doc's windows share one `tn-<hash>` / `hv-<hash>` topic.
  (b) the real defect: a topic_id whose rows carry BOTH labels ("MULTI-CLASS").
      That is not split leakage, but it contradicts the labelling rule
      (one topic => one direction) and couples the split boundary to a mixed
      signal. This script counts and lists those.

Usage:
  python check_topic_leak.py --chunks corpus/balanced.chunks.v2.jsonl
  python check_topic_leak.py --chunks corpus/balanced.chunks.v2.jsonl --seeds 42 7
  python check_topic_leak.py --chunks corpus/balanced.chunks.v2.jsonl --quiet
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from train import load_chunks, split_by_topic  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--seeds", type=int, nargs="*", default=[42, 7, 123, 2024, 99])
    ap.add_argument("--quiet", action="store_true",
                    help="print only the summary + verdict, not every topic")
    args = ap.parse_args()

    rows = load_chunks(Path(args.chunks))
    all_topics = {r["topic_id"] for r in rows}
    print(f"chunks={len(rows)}  distinct topic_ids={len(all_topics)}")

    by_topic = defaultdict(list)
    for r in rows:
        by_topic[r["topic_id"]].append(r)

    counts = Counter(r["topic_id"] for r in rows)
    dups = {k: c for k, c in counts.items() if c > 1}
    dup_rows = sum(dups.values())
    print(f"duplicated topic_ids: {len(dups)}  (rows involved: {dup_rows}, "
          f"{100 * dup_rows / max(1, len(rows)):.0f}% of corpus)")

    # --- (b) the defect that matters: one topic, both labels ---
    mixed = {k: by_topic[k] for k in dups if len({r["label"] for r in by_topic[k]}) > 1}
    mixed_rows = sum(len(v) for v in mixed.values())
    print(f"\nMULTI-CLASS topic_ids (same topic_id, both labels): {len(mixed)}  "
          f"(rows: {mixed_rows})")
    if mixed and not args.quiet:
        for k, rs in sorted(mixed.items(), key=lambda kv: -len(kv[1])):
            npos = sum(1 for r in rs if r["label"] == 1)
            docs = sorted({str(r.get("doc_id", ""))[:24] for r in rs})
            print(f"  {k:42s} chunks={len(rs):2d} pos={npos} docs={docs}")

    if not args.quiet:
        print(f"\ntop duplicated topic_ids by size:")
        for k, c in sorted(dups.items(), key=lambda kv: -kv[1])[:15]:
            rs = by_topic[k]
            print(f"  {k:34s} chunks={c:3d} labels={sorted({r['label'] for r in rs})}")

    # --- (a) actual split leakage, across seeds ---
    print("\nsplit leakage across seeds (topics shared by two splits):")
    worst = 0
    for seed in args.seeds:
        tr, va, te = split_by_topic(rows, seed)
        T, V, E = ({r["topic_id"] for r in x} for x in (tr, va, te))
        leak = (T & E) | (T & V) | (V & E)
        leaked_rows = sum(1 for r in tr + va + te if r["topic_id"] in leak)
        worst = max(worst, len(leak))
        print(f"  seed={seed:<6d} leak_topics={len(leak):<3d} leaked_chunks={leaked_rows}")

    print()
    if worst == 0:
        print("VERDICT: 0 cross-split topic leakage (duplicated topic_ids travel "
              "together, so they do not leak).")
    else:
        print(f"VERDICT: {worst} leaked topics — investigate before training.")
    if mixed:
        print(f"ACTION: {len(mixed)} topic_ids mix both labels ({mixed_rows} rows) — "
              f"label-inconsistent; consider splitting/renaming them.")
    return 0 if worst == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
