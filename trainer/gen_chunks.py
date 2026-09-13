#!/usr/bin/env python
"""gen_chunks.py — derive labelled training chunks from document-level JSONL.

Input : document rows matching schemas/corpus.schema.json
Output: chunk-level JSONL, one row per (document, window)

  {chunk_id, doc_id, topic_id, lang, scenario, turn_type, text,
   start, end, label, turn_offset_in_chunk, n_chars, provenance}

Why chunking is the deconfounding step (plan doc):
  * Every window has the SAME character size -> length carries zero label
    signal BY CONSTRUCTION. This is what kills the v1 "long => turn" confound
    that the document-level validator flags.
  * A positive document's non-turn windows become free, on-topic, same-length
    negatives. Negatives are therefore never a separate, shorter distribution.
  * `topic_id` is carried through so train/val/test can be split disjointly.

Class imbalance: harvested real data is ~120 pos vs ~14_765 neg documents.
We do NOT resample here (that would correlate class with length again among
duplicated windows); instead we (a) emit `class_weight` for the trainer and
(b) keep every positive window, which multiplies positives by the overlap
factor. train.py consumes `--class-weight-from-file`.

Usage:
  python gen_chunks.py --in corpus/harvested.jsonl --out corpus/chunks.jsonl
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from chunking import WINDOW, STRIDE, build_chunks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--window", type=int, default=WINDOW)
    ap.add_argument("--stride", type=int, default=STRIDE)
    ap.add_argument("--report", default=None, help="optional JSON stats report path")
    args = ap.parse_args()

    inp = Path(args.inp)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    n_docs = n_chunks = 0
    pos_chunks = 0
    seen_doc_ids: Counter[str] = Counter()
    by_lang = Counter()
    by_scenario = Counter()
    by_turn_type = Counter()
    char_lens_pos: list[int] = []
    char_lens_neg: list[int] = []
    topics: set[str] = set()

    with inp.open("r", encoding="utf-8") as fin, out.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            text = doc["text"]
            has_turn = bool(doc["has_turn"])
            ftp = doc.get("first_turn_pos")
            if not has_turn:
                ftp = None
            elif ftp is None or ftp < 0 or ftp >= len(text):
                # malformed positive: skip rather than poison the labels
                continue

            doc_id = doc["id"]
            seen_doc_ids[doc_id] += 1
            chunks = build_chunks(text, ftp, window=args.window, stride=args.stride)
            if not chunks:
                continue
            n_docs += 1
            topics.add(doc.get("topic_id", doc_id))

            for ci, ch in enumerate(chunks):
                n_chunks += 1
                if ch.label:
                    pos_chunks += 1
                    char_lens_pos.append(len(ch.text))
                else:
                    char_lens_neg.append(len(ch.text))
                by_lang[doc.get("lang", "en")] += 1
                by_scenario[doc.get("scenario", "analysis")] += 1
                by_turn_type[doc.get("turn_type", "none")] += 1

                row = {
                    "chunk_id": f"{doc_id}#{ci}",
                    "doc_id": doc_id,
                    "topic_id": doc.get("topic_id", doc_id),
                    "lang": doc.get("lang", "en"),
                    "scenario": doc.get("scenario", "analysis"),
                    "turn_type": doc.get("turn_type", "none") if ch.label else "none",
                    "text": ch.text,
                    "start": ch.start,
                    "end": ch.end,
                    "label": ch.label,
                    "turn_offset_in_chunk": (ch.turn_pos - ch.start) if ch.turn_pos is not None else -1,
                    "n_chars": len(ch.text),
                    "provenance": doc.get("provenance", "generated"),
                }
                fout.write(json.dumps(row, ensure_ascii=False) + "\n")

    dupes = {k: v for k, v in seen_doc_ids.items() if v > 1}
    n_neg = len(char_lens_neg)
    stats = {
        "documents": n_docs,
        "chunks": n_chunks,
        "pos_chunks": pos_chunks,
        "neg_chunks": n_neg,
        "topics": len(topics),
        "duplicate_doc_ids": len(dupes),
        "by_lang": dict(by_lang),
        "by_scenario": dict(by_scenario),
        "by_turn_type": dict(by_turn_type),
        "pos_len_avg": (sum(char_lens_pos) / len(char_lens_pos)) if char_lens_pos else 0,
        "neg_len_avg": (sum(char_lens_neg) / len(char_lens_neg)) if char_lens_neg else 0,
        "pos_len_min": min(char_lens_pos) if char_lens_pos else 0,
        "pos_len_max": max(char_lens_pos) if char_lens_pos else 0,
        "neg_len_min": min(char_lens_neg) if char_lens_neg else 0,
        "neg_len_max": max(char_lens_neg) if char_lens_neg else 0,
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    if args.report:
        Path(args.report).write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
