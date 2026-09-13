#!/usr/bin/env python
"""balance_chunks.py — shrink the negative side without touching length.

The combined corpus is ~1:94 positive:negative because the mined triologue
negatives outnumber the generated positives. CPU training on 208k chunks is
infeasible, and an unweighted 1:94 set collapses to the majority class.

The plan's rule is: NEVER resample at the WINDOW level (that would re-couple
class to length). So we downsample at the DOCUMENT level:

  * Keep every POSITIVE document (all its windows).
  * Keep a deterministic, topic-diverse random sample of NEGATIVE documents.
  * Regenerate chunks from the reduced document set.

Because every window is still exactly 128 chars (or a short doc's tail), the
chunk-length distribution stays class-independent BY CONSTRUCTION.

The selection is done on the SOURCE document files (harvested.jsonl holds the
bulk of negatives; generated.jsonl provides the positives + zh balance), then
chunks are re-derived with gen_chunks.build_chunks so the windowing code stays
single-source.

Usage:
  python balance_chunks.py --harvested corpus/harvested.jsonl \
      --extra corpus/generated.jsonl --out-docs corpus/balanced.jsonl \
      --out-chunks corpus/balanced.chunks.jsonl --neg-keep-frac 0.15 --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from chunking import build_chunks


def iter_docs(path: Path):
    for line in path.open("r", encoding="utf-8"):
        line = line.strip()
        if line:
            yield json.loads(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--harvested", required=True, help="bulk negative source")
    ap.add_argument("--extra", required=True, help="positives + zh balance source")
    ap.add_argument("--out-docs", required=True)
    ap.add_argument("--out-chunks", required=True)
    ap.add_argument("--neg-keep-frac", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)

    # 1. keep every positive doc + every doc from the 'extra' (generated) source,
    #    and a random fraction of the harvested NEGATIVE docs.
    kept_docs = []
    n_pos = n_neg_kept = n_neg_dropped = 0
    for d in iter_docs(Path(args.extra)):
        kept_docs.append(d)
        if d.get("has_turn"):
            n_pos += 1
        else:
            n_neg_kept += 1
    for d in iter_docs(Path(args.harvested)):
        if d.get("has_turn"):
            kept_docs.append(d)
            n_pos += 1
        elif rng.random() < args.neg_keep_frac:
            kept_docs.append(d)
            n_neg_kept += 1
        else:
            n_neg_dropped += 1

    rng.shuffle(kept_docs)

    outd = Path(args.out_docs)
    outd.parent.mkdir(parents=True, exist_ok=True)
    with outd.open("w", encoding="utf-8", newline="\n") as f:
        for d in kept_docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    # 2. re-derive chunks from the reduced docs (same chunking code path)
    outc = Path(args.out_chunks)
    outc.parent.mkdir(parents=True, exist_ok=True)
    n_chunks = pos_chunks = neg_chunks = 0
    pos_len = neg_len = 0
    with outc.open("w", encoding="utf-8", newline="\n") as f:
        for d in kept_docs:
            text = d["text"]
            has_turn = bool(d["has_turn"])
            ftp = d.get("first_turn_pos") if has_turn else None
            if has_turn and (ftp is None or ftp < 0 or ftp >= len(text)):
                continue
            for ci, ch in enumerate(build_chunks(text, ftp)):
                n_chunks += 1
                if ch.label:
                    pos_chunks += 1
                    pos_len += len(ch.text)
                else:
                    neg_chunks += 1
                    neg_len += len(ch.text)
                f.write(json.dumps({
                    "chunk_id": f"{d['id']}#{ci}",
                    "doc_id": d["id"],
                    "topic_id": d.get("topic_id", d["id"]),
                    "lang": d.get("lang", "en"),
                    "scenario": d.get("scenario", "analysis"),
                    "turn_type": d.get("turn_type", "none") if ch.label else "none",
                    "text": ch.text,
                    "start": ch.start,
                    "end": ch.end,
                    "label": ch.label,
                    "turn_offset_in_chunk": (ch.turn_pos - ch.start) if ch.turn_pos is not None else -1,
                    "n_chars": len(ch.text),
                    "provenance": d.get("provenance", "generated"),
                }, ensure_ascii=False) + "\n")

    stats = {
        "docs_kept": len(kept_docs),
        "pos_docs": n_pos,
        "neg_docs_kept": n_neg_kept,
        "neg_docs_dropped": n_neg_dropped,
        "chunks": n_chunks,
        "pos_chunks": pos_chunks,
        "neg_chunks": neg_chunks,
        "pos_neg_ratio": round(neg_chunks / max(1, pos_chunks), 1),
        "pos_len_avg": round(pos_len / max(1, pos_chunks), 1),
        "neg_len_avg": round(neg_len / max(1, neg_chunks), 1),
    }
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
