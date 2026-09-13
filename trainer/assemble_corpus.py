#!/usr/bin/env python
"""assemble_corpus.py — merge peer inbox batches into one curated corpus.

Each peer writes ``corpus/inbox/<session-id>/batch.jsonl`` (document-level rows
matching the corpus schema). This script:

  1. Reads every ``inbox/*/batch.jsonl`` (skips empty files).
  2. Validates each row shape minimally (required fields present).
  3. Rejects any row carrying a gate-failing flag when ``--only-pass`` is set
     (the caller passes the list of passing session-ids).
  4. De-duplicates by text across the WHOLE pool (cross-peer collisions) and by
     ``id`` (intra-batch collisions are already caught by validate_corpus.py,
     but we guard here too).
  5. Rewrites ``provenance`` to ``generated`` and stamps the originating peer
     into ``peer_session`` / ``source_model`` if missing.
  6. Writes a single JSONL ``corpus/generated.jsonl`` plus a JSON report.

Usage:
  python assemble_corpus.py --inbox corpus/inbox --out corpus/generated.jsonl \
      --report corpus/generated.stats.json
  python assemble_corpus.py --inbox corpus/inbox --out corpus/generated.jsonl \
      --only-pass 8db71d8b-... 248051be-...
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
    ap.add_argument("--inbox", required=True, help="dir containing <sid>/batch.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--only-pass", nargs="*", default=None,
                    help="session-ids (full or 8-char prefix) to include; "
                         "if omitted, include every non-empty batch")
    args = ap.parse_args()

    inbox = Path(args.inbox)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    only = None
    if args.only_pass:
        only = set()
        for tok in args.only_pass:
            t = tok.strip().lower()
            only.add(t)
        def keep(sid: str) -> bool:
            s = sid.lower()
            return any(s.startswith(o) or o.startswith(s) for o in only)
    else:
        def keep(sid: str) -> bool:
            return True

    seen_ids: set[str] = set()
    seen_text: dict[str, str] = {}  # text -> first id
    written = 0
    dropped_dup_id = 0
    dropped_dup_text = 0
    dropped_schema = 0
    dropped_lang = 0
    dropped_other = 0
    sources = Counter()
    by_lang = Counter()
    by_turn = Counter()
    by_scenario = Counter()
    pos = neg = 0
    per_peer = Counter()

    with out.open("w", encoding="utf-8", newline="\n") as fout:
        for sessdir in sorted(inbox.iterdir()):
            if not sessdir.is_dir():
                continue
            f = sessdir / "batch.jsonl"
            if not f.exists() or f.stat().st_size == 0:
                continue
            if not keep(sessdir.name):
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
                if not isinstance(row, dict):
                    dropped_schema += 1
                    continue
                # light shape guard (full validation is validate_corpus.py's job)
                if not REQUIRED.issubset(row.keys()):
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
                # reuse the same class label as bool(has_turn) for parity
                row["is_negative"] = not bool(row["has_turn"])
                # provenance hygiene
                row["provenance"] = "generated"
                if not row.get("peer_session"):
                    row["peer_session"] = sessdir.name
                row["verified_by"] = row.get("verified_by") or []
                row["verdict"] = row.get("verdict") or "pending"

                seen_ids.add(rid)
                seen_text[text] = rid
                written += 1
                per_peer[sessdir.name[:8]] += 1
                sources[row.get("source_model", "?")] += 1
                by_lang[row.get("lang", "?")] += 1
                by_turn[row.get("turn_type", "?")] += 1
                by_scenario[row.get("scenario", "?")] += 1
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
        "dropped_dup_text_cross_peer": dropped_dup_text,
        "dropped_schema": dropped_schema,
        "peers_included": len(per_peer),
        "per_peer": dict(sorted(per_peer.items())),
        "by_lang": dict(by_lang),
        "by_turn_type": dict(by_turn),
        "by_scenario": dict(by_scenario),
        "by_source_model": dict(sources),
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    if args.report:
        Path(args.report).write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
