"""Build batch-r4.jsonl from part*.json (farmer-a, round 4).

Each part entry: {topic, scenario, turn_type, marker, text, conjunction}
- positive rows: turn_type in the 5 real types, marker = exact substring that is
  the FIRST genuine turning point (must occur exactly once).
- negative rows: turn_type="none", marker=null.

first_turn_pos / word_count / lang are DERIVED here, never typed by hand.
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
parts = sorted(HERE.glob("part*.json"))
assert parts, "no part*.json found"

rows = []
seq = 0
for pf in parts:
    for s in json.loads(pf.read_text(encoding="utf-8")):
        seq += 1
        text = s["text"]
        tt = s["turn_type"]
        if tt == "none":
            has, pos = False, -1
        else:
            has = True
            m = s["marker"]
            assert text.count(m) == 1, (s["topic"], repr(m), text.count(m))
            pos = text.index(m)
            assert 0 <= pos < len(text)
        assert len(text) >= 40
        wc = len(text.split())
        rows.append({
            "id": "en-fa4-%04d" % seq,
            "text": text,
            "has_turn": has,
            "first_turn_pos": pos,
            "scenario": s["scenario"],
            "turn_type": tt,
            "is_negative": not has,
            "lang": "en",
            "word_count": wc,
            "topic_id": "fa-" + s["topic"],
            "source_model": "farmer-a-llm:r4",
            "peer_session": "farmer-a-r4",
            "provenance": "generated",
            "conjunction": s.get("conjunction"),
            "verified_by": [],
            "verdict": "pending",
        })

topics = [r["topic_id"] for r in rows]
assert len(set(topics)) == len(topics), "duplicate topic_id"
texts = [re.sub(r"\s+", " ", r["text"].strip().lower()) for r in rows]
assert len(set(texts)) == len(texts), "duplicate text"

out = HERE / "batch-r4.jsonl"
out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
               encoding="utf-8")

pos = [r["word_count"] for r in rows if r["has_turn"]]
neg = [r["word_count"] for r in rows if not r["has_turn"]]
print("wrote", out, "rows:", len(rows))
print("pos:", len(pos), "neg:", len(neg))
if pos and neg:
    print("posAvg=%.1f negAvg=%.1f drift=%.1f%%" % (
        sum(pos) / len(pos), sum(neg) / len(neg),
        100.0 * abs(sum(pos) / len(pos) - sum(neg) / len(neg)) / max(sum(pos) / len(pos), sum(neg) / len(neg))))
from collections import Counter
print("scenario:", dict(Counter(r["scenario"] for r in rows)))
print("turn_type:", dict(Counter(r["turn_type"] for r in rows)))
