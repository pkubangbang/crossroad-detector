#!/usr/bin/env python
"""check_doc_leak.py — prove the document-level split fix in train.py.

DEFECT (before)
---------------
`train.py` used to group rows by `topic_id`. But a DOCUMENT's overlapping
windows can carry more than one topic_id (27 doc_ids in
corpus/balanced.chunks.v2.jsonl do). Grouping by topic_id therefore assigned
those windows to different splits, so the same document was torn across
train/val/test and the model was evaluated on text it had trained on.

FIX (after)
-----------
`train.split_by_doc` groups by `doc_id`, which is strictly coarser than
`topic_id` for these rows, so a document can never be torn. `split_by_topic` is
kept as an alias so the existing importers run unchanged.

WHAT THIS SCRIPT PRINTS
-----------------------
For each seed: the number of doc_ids appearing in MORE THAN ONE split, computed
two ways —
  BEFORE = legacy grouping key `topic_id`
  AFTER  = new grouping key `doc_id`  (what train.split_by_doc does)
Target for AFTER: 0.

Usage:
  python check_doc_leak.py --chunks corpus/balanced.chunks.v2.jsonl
  python check_doc_leak.py --chunks corpus/balanced.chunks.v2.jsonl --seeds 42 7
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from train import load_chunks, split_by_doc, group_atomic  # noqa: E402


def split_by_key(rows: list[dict], seed: int, key: str, val_frac=0.15, test_frac=0.15):
    """The pre-fix algorithm, parameterised by grouping key, so BEFORE and AFTER
    differ in exactly one thing: the key."""
    groups: dict[str, dict] = {}
    for r in rows:
        e = groups.setdefault(r[key], {"rows": [], "has_pos": False})
        e["rows"].append(r)
        if r["label"] == 1:
            e["has_pos"] = True

    pos = [g for g, e in groups.items() if e["has_pos"]]
    neg = [g for g, e in groups.items() if not e["has_pos"]]
    rng = random.Random(seed)
    rng.shuffle(pos)
    rng.shuffle(neg)

    def take(lst, frac):
        k = max(1, int(len(lst) * frac)) if lst else 0
        return lst[:k], lst[k:]

    pv, pos_rest = take(pos, val_frac)
    pt, pos_rest = take(pos_rest, test_frac / max(1e-9, 1 - val_frac))
    nv, neg_rest = take(neg, val_frac)
    nt, neg_rest = take(neg_rest, test_frac / max(1e-9, 1 - val_frac))

    def collect(gs):
        out = []
        for g in gs:
            out.extend(groups[g]["rows"])
        return out

    return (collect(pos_rest + neg_rest), collect(pv + nv), collect(pt + nt))


def doc_leaks(splits) -> tuple[set, int]:
    """doc_ids present in more than one split, and the chunks involved."""
    where: dict[str, set] = defaultdict(set)
    for i, rs in enumerate(splits):
        for r in rs:
            where[r["doc_id"]].add(i)
    leaked = {d for d, s in where.items() if len(s) > 1}
    n_chunks = sum(1 for rs in splits for r in rs if r["doc_id"] in leaked)
    return leaked, n_chunks


def topic_leaks(splits) -> set:
    where: dict[str, set] = defaultdict(set)
    for i, rs in enumerate(splits):
        for r in rs:
            where[r["topic_id"]].add(i)
    return {t for t, s in where.items() if len(s) > 1}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--seeds", type=int, nargs="*", default=[42, 7, 123, 2024, 99])
    args = ap.parse_args()

    rows = load_chunks(Path(args.chunks))
    n_docs = len({r["doc_id"] for r in rows})
    print(f"chunks={len(rows)}  distinct doc_ids={n_docs}  "
          f"distinct topic_ids={len({r['topic_id'] for r in rows})}")

    docs_to_topics = defaultdict(set)
    for r in rows:
        docs_to_topics[r["doc_id"]].add(r["topic_id"])
    multi = sum(1 for v in docs_to_topics.values() if len(v) > 1)
    print(f"doc_ids mapping to >1 topic_id (the tear vector): {multi}\n")

    worst_before = worst_after = 0
    print(f"{'seed':<7}{'BEFORE doc_ids>1 split':>26}{'chunks':>8}"
          f"{'AFTER doc_ids>1 split':>24}{'chunks':>8}")
    for seed in args.seeds:
        before = split_by_key(rows, seed, "topic_id")
        b_docs, b_chunks = doc_leaks(before)
        after = split_by_doc(rows, seed)
        a_docs, a_chunks = doc_leaks(after)
        a_topics = topic_leaks(after)
        worst_before = max(worst_before, len(b_docs))
        worst_after = max(worst_after, len(a_docs))
        print(f"{seed:<7}{len(b_docs):>26}{b_chunks:>8}{len(a_docs):>24}{a_chunks:>8}"
              f"   after_topic_leaks={len(a_topics)}")

    # topic-level leakage must not regress either
    topic_regressions = [s for s in args.seeds if topic_leaks(split_by_doc(rows, s))]
    print(f"\ncross-split TOPIC leakage after fix: "
          f"{'0 for every seed' if not topic_regressions else topic_regressions}")

    # granularity sanity: the fix must not collapse the corpus into a few groups
    grp = group_atomic(rows)
    sizes = sorted((len(v) for v in grp.values()), reverse=True)
    print(f"atomic groups={len(grp)} (chunks={len(rows)}), largest={sizes[0]} rows")

    print(f"\nBEFORE: up to {worst_before} doc_ids torn across splits per seed")
    print(f"AFTER:  {worst_after} doc_ids torn across splits per seed")
    ok = worst_after == 0 and not topic_regressions
    print("VERDICT:", "PASS - every document and every topic stays in exactly one split."
          if ok else f"FAIL - {worst_after} documents still torn.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
