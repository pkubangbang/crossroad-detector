#!/usr/bin/env python
"""why_doc_leak.py — reconcile the two conflicting measurements of doc leakage.

CLAIM UNDER TEST
The verifier reported "doc_ids appearing in >1 split, per seed: 42=17, 7=11,
123=9, 2024=13, 99=16". My own doc_leak_check.py reports 0 for all seeds.

Both cannot be right. The likely difference: WHERE the doc->split decision is
made. `split_by_topic` assigns by topic_id, but a doc_id with several topic_ids
has its windows assigned per TOPIC, so a doc can plausibly be torn. My checker
may be measuring the right thing for the wrong reason, or the verifier may have
counted something subtly different (e.g. rows with no label, or docs appearing in
a split merely because an overlapping topic appears there).

This script prints the raw evidence so the truth is visible:
  * how many doc_ids have >1 topic_id (27)
  * for each such doc, which topic_id went to which split, and therefore whether
    the DOC appears in >1 split
  * both counts (all docs; restricted to the 27 multi-topic docs)
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from train import load_chunks, split_by_topic  # noqa: E402

CHUNKS = Path("corpus/balanced.chunks.v2.jsonl")
SEEDS = [42, 7, 123, 2024, 99]


def main() -> int:
    rows = load_chunks(CHUNKS)

    d2t: dict[str, set] = defaultdict(set)
    for r in rows:
        d2t[r["doc_id"]].add(r["topic_id"])
    multi = {d for d, t in d2t.items() if len(t) > 1}
    print(f"docs total={len(d2t)}  docs with >1 topic_id={len(multi)}\n")

    for seed in SEEDS:
        tr, va, te = split_by_topic(rows, seed)

        # topic -> split
        tsplit = {}
        for name, part in (("train", tr), ("val", va), ("test", te)):
            for r in part:
                tsplit[r["topic_id"]] = name

        # doc -> splits, via the splits of ALL its topics
        dsplits: dict[str, set] = defaultdict(set)
        # doc -> splits, via only the rows that were actually placed
        dsplits_rows: dict[str, set] = defaultdict(set)
        for name, part in (("train", tr), ("val", va), ("test", te)):
            for r in part:
                dsplits_rows[r["doc_id"]].add(name)
        for d, ts in d2t.items():
            for t in ts:
                if t in tsplit:
                    dsplits[d].add(tsplit[t])

        torn_all = {d for d, s in dsplits_rows.items() if len(s) > 1}
        torn_multi = {d for d in multi if len(dsplits.get(d, set())) > 1}

        print(f"seed={seed}")
        print(f"  docs torn (rows actually placed in >1 split) : {len(torn_all)}")
        print(f"  docs torn (among the 27 multi-topic docs)    : {len(torn_multi)}")
        if torn_multi:
            for d in sorted(torn_multi)[:4]:
                ts = sorted(d2t[d])
                print(f"      {d[:34]:36s} topics={[(t[:18], tsplit.get(t)) for t in ts]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
