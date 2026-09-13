#!/usr/bin/env python
"""reassemble.py — merge ALL peer JSONL files, both rounds, into one corpus.

Unlike assemble_corpus.py (which globs inbox/<sid>/batch.jsonl only), this
script collects EVERY *.jsonl inside each peer inbox dir — i.e. round-1
``batch.jsonl`` plus round-2 ``batch_zh_long.jsonl`` — and concatenates them
with global id/text de-duplication, then normalizes provenance.

Usage:
  python reassemble.py --inbox corpus/inbox --out corpus/all.jsonl \
      --report corpus/all.stats.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

REQUIRED = {
    "id", "text", "has_turn", "first_turn_pos", "scenario", "turn_type",
    "is_negative", "lang", "word_count", "topic_id", "source_model",
    "peer_session", "provenance", "conjunction", "verified_by", "verdict",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inbox", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--supersede-zh", action="store_true",
                    help="round-2 supersedes round-1 zh: from batch.jsonl keep ONLY en "
                         "rows; from batch_zh_long.jsonl keep ALL rows. Prevents the "
                         "within-zh length confound (round-1 zh ~50 chars vs round-2 ~280).")
    args = ap.parse_args()

    def select(fname: str, row: dict) -> bool:
        """Return True iff this row should be kept under the selection rule."""
        if not args.supersede_zh:
            return True
        if fname == "batch_zh_long.jsonl":
            return True
        if fname == "batch.jsonl":
            return row.get("lang") == "en"
        return True

    inbox = Path(args.inbox)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    seen_ids: set[str] = set()
    seen_text: dict[str, str] = {}
    written = 0
    dropped_dup_id = dropped_dup_text = dropped_schema = dropped_superseded = 0
    per_peer = Counter()
    per_file = Counter()
    by_lang = Counter()
    by_turn = Counter()
    pos = neg = 0

    with out.open("w", encoding="utf-8", newline="\n") as fout:
        for sessdir in sorted(inbox.iterdir()):
            if not sessdir.is_dir():
                continue
            for f in sorted(sessdir.glob("*.jsonl")):
                if f.stat().st_size == 0:
                    continue
                for line in f.open("r", encoding="utf-8"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        dropped_schema += 1
                        continue
                    if not isinstance(row, dict) or not REQUIRED.issubset(row.keys()):
                        dropped_schema += 1
                        continue
                    text = row.get("text")
                    if not isinstance(text, str) or len(text) < 40:
                        dropped_schema += 1
                        continue
                    rid = row.get("id")
                    if not isinstance(rid, str) or rid in seen_ids:
                        dropped_dup_id += 1
                        continue
                    if text in seen_text:
                        dropped_dup_text += 1
                        continue
                    row["is_negative"] = not bool(row["has_turn"])
                    row["provenance"] = "generated"
                    row["peer_session"] = row.get("peer_session") or sessdir.name
                    row["verified_by"] = row.get("verified_by") or []
                    row["verdict"] = row.get("verdict") or "pending"

                    if not select(f.name, row):
                        dropped_superseded += 1
                        continue

                    seen_ids.add(rid)
                    seen_text[text] = rid
                    written += 1
                    per_peer[sessdir.name[:8]] += 1
                    per_file[f.name] += 1
                    by_lang[row.get("lang", "?")] += 1
                    by_turn[row.get("turn_type", "?")] += 1
                    if row["has_turn"]:
                        pos += 1
                    else:
                        neg += 1
                    fout.write(json.dumps(row, ensure_ascii=False) + "\n")

    stats = {
        "written": written,
        "positives": pos,
        "negatives": neg,
        "dropped_dup_id": dropped_dup_id,
        "dropped_dup_text": dropped_dup_text,
        "dropped_schema": dropped_schema,
        "dropped_superseded": dropped_superseded,
        "peers_included": len(per_peer),
        "by_file": dict(per_file),
        "by_lang": dict(by_lang),
        "by_turn_type": dict(by_turn),
        "per_peer": dict(sorted(per_peer.items())),
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    if args.report:
        Path(args.report).write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
