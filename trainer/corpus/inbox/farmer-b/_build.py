#!/usr/bin/env python
"""Assemble farmer-b round-4 EN corpus. Computes word_count/lang/first_turn_pos
deterministically from the authored texts, then writes batch-r4.jsonl (UTF-8, no BOM).
"""
from __future__ import annotations
import importlib.util
import json
import re
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
BUCKETS = [(0, 30), (30, 100), (100, 300), (300, 1000), (1000, 10 ** 9)]


def compute_word_count(text: str):
    no_ws = re.sub(r"\s", "", text)
    if not no_ws:
        return 0, "en"
    cjk = len(CJK.findall(no_ws))
    if cjk / len(no_ws) >= 0.5:
        return len(no_ws), "zh"
    return len([t for t in re.split(r"\s+", text) if t]), "en"


def bucket_of(n):
    for lo, hi in BUCKETS:
        if lo <= n < hi:
            return f"{lo}-{hi}" if hi < 10 ** 9 else f">{lo}"
    return ">1000"


PEER = "farmer-b-r4"
MODEL = "claude-sonnet-4.5:cloud"

# Authored continuation tail for every negative: keeps the same direction (no
# reversal) and matches the positive class length distribution so the validator's
# v1 length-confounding guard passes.
TAIL = {
    "fb-neg-sp-retry-policy": "and treat the settings as provisional rather than settled.",
    "fb-neg-sp-cost-model": "The current numbers are good enough for the decision at hand.",
    "fb-neg-sp-hiring-freeze": "We should size the plan to the runway we have and revisit it quarterly.",
    "fb-neg-sp-typed-config": "Until then the types stay exactly as they are.",
    "fb-neg-sp-batch-window": "The per-consumer setting is a small change and can wait for the next release.",
    "fb-neg-sp-monorepo": "Build time is the deciding measurement, and we already collect it nightly.",
    "fb-neg-sp-readability": "A checklist that scores all three keeps the reviews consistent.",
    "fb-neg-wait-build": "That sequence is what the onboarding guide already describes.",
    "fb-neg-wait-dns": "The retry behaviour is the only thing this exercise is meant to show.",
    "fb-neg-wait-deploy": "The overnight soak is the whole point of the staging step.",
    "fb-neg-wait-lab": "The first native build is always the slow one.",
    "fb-neg-wait-index": "Recording both statistics keeps the comparison honest.",
    "fb-neg-wait-grafana": "Grouping by endpoint is what makes the panel readable.",
    "fb-neg-wait-reindex": "Running it out of band is exactly why it has its own flag.",
    "fb-neg-act-hash": "The one-line change is all this needs.",
    "fb-neg-act-latency": "The fix belongs where the serialisation happens, not here.",
    "fb-neg-act-threshold": "Leaving it alone for a quarter is the low-risk choice.",
    "fb-neg-act-copy": "Pausing on that detail is worth the five minutes it takes.",
    "fb-neg-act-cron": "Both the schedule and the report are working as intended.",
    "fb-neg-act-cache": "The namespace builder is doing its job and nothing here needs changing.",
    "fb-neg-act-replica": "Correcting the docs is the only action this finding calls for.",
    "fb-neg-act-p99": "Labelling which window each number uses removes the confusion.",
    "fb-neg-act-branch": "Keeping it open is cheap and it unblocks the partner.",
    "fb-neg-hs-runner": "Moving the release pipeline over is the obvious next step.",
    "fb-neg-hs-partition": "Folding the audit table into the same migration saves a second pass.",
    "fb-neg-hs-pairing": "Both halves of the course lean on the same fast-feedback principle.",
    "fb-neg-hs-budget": "Reserving both lines is the straightforward extension of the same idea.",
    "fb-neg-hs-retry": "The dispatcher needs the same breaker for the same reason.",
    "fb-neg-hs-types": "Typing the CLI follows from the same evidence and should come next.",
    "fb-neg-hs-scope": "Trimming further in the same direction is consistent with the launch plan.",
    "fb-neg-hs-threshold": "Treating both alerts as one change keeps the thresholds coherent.",
    "fb-neg-adv-cache-win": "Fixing invalidation is the work item, not removing the cache.",
    "fb-neg-adv-plan-speed": "Sequencing the risky items first is the mitigation, not new dates.",
    "fb-neg-adv-graph": "Mentioning the cycle alongside the trend is the honest summary.",
    "fb-neg-adv-docs": "Adding a deployment primer before the tutorials closes the gap.",
    "fb-neg-adv-license": "Pricing the whole sentence is the fair comparison.",
    "fb-neg-adv-scaling": "Correlation ids cover most of the tracing gap, so the design stands.",
    "fb-neg-adv-vendors": "A documented exit plan is the mitigation we already agreed on.",
    "fb-neg-adv-rewrite": "Module-by-module migration is the plan, and it keeps the old path alive.",
    "fb-neg-adv-naming": "Documenting the reason is the only change I would make.",
    "fb-neg-adv-verbose": "Level-based retention keeps the detail without the storage bill.",
}

RAW = []
for name in ["_chunk1", "_chunk2", "_chunk3", "_chunk4", "_chunk5"]:
    spec = importlib.util.spec_from_file_location(name, str(HERE / (name + ".py")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    RAW.extend(mod.RAW)

out, topics = [], set()
for i, (topic, scenario, ttype, marker, conj, text) in enumerate(RAW, 1):
    has = marker is not None
    if has:
        assert text.count(marker) == 1, f"{topic}: marker {marker!r} x{text.count(marker)}"
        pos = text.index(marker)
        assert 0 <= pos < len(text), topic
    else:
        pos = -1
        assert ttype == "none", topic
        assert conj is not None, f"{topic}: negative needs conjunction"
        assert topic in TAIL, f"{topic}: negative needs TAIL"
        text = text.rstrip() + " " + TAIL[topic]
    wc, lang = compute_word_count(text)
    assert lang == "en", f"{topic}: lang={lang}"
    assert topic.startswith("fb-") and topic not in topics, topic
    topics.add(topic)
    out.append({
        "id": f"en-fb4-{i:04d}",
        "text": text,
        "has_turn": has,
        "first_turn_pos": pos,
        "scenario": scenario,
        "turn_type": ttype if has else "none",
        "is_negative": not has,
        "lang": lang,
        "word_count": wc,
        "topic_id": topic,
        "source_model": MODEL,
        "peer_session": PEER,
        "provenance": "generated",
        "conjunction": conj,
        "verified_by": [],
        "verdict": "pending",
    })

p = [r["word_count"] for r in out if r["has_turn"]]
n = [r["word_count"] for r in out if not r["has_turn"]]
pm, nm = sum(p) / len(p), sum(n) / len(n)
print(f"total={len(out)} pos={len(p)} neg={len(n)} ratio={len(p)/len(out):.0%}pos")
print(f"posAvg={pm:.1f} negAvg={nm:.1f} drift={abs(pm - nm) / max(pm, nm):.1%}")
print("pos buckets:", dict(Counter(bucket_of(x) for x in p)))
print("neg buckets:", dict(Counter(bucket_of(x) for x in n)))
print("scenarios:", dict(Counter(r["scenario"] for r in out)))
print("turn_types:", dict(Counter(r["turn_type"] for r in out)))
print("conjunctions:", dict(Counter(r["conjunction"] for r in out if r["conjunction"])))
lens = [r["word_count"] for r in out]
short_pos = [r for r in out if r["has_turn"] and len(r["text"]) < 200]
print(f"min={min(lens)} max={max(lens)} short_pos(<200 chars)={len(short_pos)}")

dest = HERE / "batch-r4.jsonl"
with dest.open("w", encoding="utf-8", newline="\n") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("wrote", dest)
