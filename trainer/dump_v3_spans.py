#!/usr/bin/env python
"""dump_v3_spans.py — emit v3 chunk spans for a corpus so the TS port can be
diffed 1:1 against chunker_v3.py (parity harness, not a shipped artifact).

Usage:
  python dump_v3_spans.py --in corpus/r4.balanced.jsonl --out /tmp/v3spans.jsonl --limit 500
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from chunker_v2 import iter_docs, build_segments
from chunker_v3 import build_chunks_v3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()

    n = 0
    with Path(args.out).open("w", encoding="utf-8", newline="\n") as f:
        for doc in iter_docs(Path(args.inp)):
            if n >= args.limit:
                break
            text = doc["text"]
            spans = build_chunks_v3(text, doc.get("first_turn_pos"))
            f.write(json.dumps({
                "id": doc["id"],
                # text hash is the real join key: the corpus has duplicate ids
                "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
                "nseg": len(build_segments(text)),
                "spans": [[s, e] for (s, e) in spans],
            }, ensure_ascii=False) + "\n")
            n += 1
    print(f"dumped {n} docs -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
