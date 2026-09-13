"""Build batch-r4b.jsonl from partb*.json (farmer-a, round 4, absorbed shard)."""
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
parts = sorted(HERE.glob("partb*.json"))
assert parts, "no partb*.json found"

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
        rows.append({
            "id": "en-fa4b-%04d" % seq,
            "text": text,
            "has_turn": has,
            "first_turn_pos": pos,
            "scenario": s["scenario"],
            "turn_type": tt,
            "is_negative": not has,
            "lang": "en",
            "word_count": len(text.split()),
            "topic_id": "fa-" + s["topic"],
            "source_model": "farmer-a-llm:r4",
            "peer_session": "farmer-a-r4",
            "provenance": "generated",
            "conjunction": s.get("conjunction"),
            "verified_by": [],
            "verdict": "pending",
        })

# cross-batch invariants: no topic/text reuse against batch-r4.jsonl either
prev = []
p0 = HERE / "batch-r4.jsonl"
if p0.exists():
    prev = [json.loads(l) for l in p0.read_text(encoding="utf-8").splitlines() if l.strip()]

all_topics = [r["topic_id"] for r in rows + prev]
assert len(set(all_topics)) == len(all_topics), "duplicate topic_id across batches"
all_texts = [re.sub(r"\s+", " ", r["text"].strip().lower()) for r in rows + prev]
assert len(set(all_texts)) == len(all_texts), "duplicate text across batches"
all_ids = [r["id"] for r in rows + prev]
assert len(set(all_ids)) == len(all_ids), "duplicate id"

out = HERE / "batch-r4b.jsonl"
out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
               encoding="utf-8")

pos = [r["word_count"] for r in rows if r["has_turn"]]
neg = [r["word_count"] for r in rows if not r["has_turn"]]
print("wrote", out, "rows:", len(rows))
print("pos:", len(pos), "neg:", len(neg))
if pos and neg:
    pa, na = sum(pos) / len(pos), sum(neg) / len(neg)
    print("posAvg=%.1f negAvg=%.1f drift=%.1f%%" % (pa, na, 100.0 * abs(pa - na) / max(pa, na)))
short_early = [r for r in rows if r["has_turn"] and len(r["text"]) < 200 and r["first_turn_pos"] < 130]
print("short early-turn docs:", len(short_early))
print("scenario:", dict(Counter(r["scenario"] for r in rows)))
print("turn_type:", dict(Counter(r["turn_type"] for r in rows)))
