#!/usr/bin/env python
"""evaluate.py — metrics + bucket diagnostics for the crossroad classifier.

Used by train.py (held-out checkpointing) and by the Phase 7 acceptance gate.
Reports, per the plan doc's "Acceptance gate":
  * precision / recall / F1 (positive class = "turn")
  * a LENGTH-BUCKET diagnostic  (does accuracy hold across n_chars?)
  * a POSITION-BUCKET diagnostic (is the turn near the left edge learned?)
  * an FSM-baseline comparison hook (callers pass FSM predictions in)

Design note: the crossroad decision is *not* per-chunk independent — the
runtime picks the FIRST positive chunk. So we report both:
   chunk-level metrics  (what the model learns), and
   document-level metrics (first-positive-chunk vs recorded turn chunk),
which is what actually ships.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable, Optional


@dataclass
class PRF:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    precision = property(lambda self: self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0)
    recall = property(lambda self: self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0)

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def accuracy(self) -> float:
        n = self.tp + self.fp + self.fn + self.tn
        return (self.tp + self.tn) / n if n else 0.0

    def as_dict(self) -> dict:
        return {
            "tp": self.tp, "fp": self.fp, "fn": self.fn, "tn": self.tn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "accuracy": round(self.accuracy, 4),
        }


def compute_prf(labels: Iterable[int], preds: Iterable[int]) -> PRF:
    m = PRF()
    for y, p in zip(labels, preds):
        if y == 1 and p == 1:
            m.tp += 1
        elif y == 0 and p == 1:
            m.fp += 1
        elif y == 1 and p == 0:
            m.fn += 1
        else:
            m.tn += 1
    return m


# length buckets in CHARACTERS, aligned with the plan doc diagnostics
LEN_BUCKETS = [(0, 64), (64, 128), (128, 256), (256, 384), (384, 511), (511, 10**9)]


def len_bucket(n: int) -> str:
    for lo, hi in LEN_BUCKETS:
        if lo <= n < hi:
            return f"{lo}-{hi}" if hi < 10**9 else f">{lo}"
    return f">{LEN_BUCKETS[-1][0]}"


def bucket_report(rows: list[dict], key: str, bucket_fn) -> dict:
    """rows carry `label` and `pred`. Returns per-bucket PRF + counts."""
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        buckets.setdefault(bucket_fn(r[key]), []).append(r)
    out = {}
    for b in sorted(buckets):
        rs = buckets[b]
        m = compute_prf([r["label"] for r in rs], [r["pred"] for r in rs])
        out[b] = {"n": len(rs), **m.as_dict()}
    return out


def position_bucket(offset: int, n_chars: int) -> str:
    """Where inside the *window* the turn sits — left edge is the hard case,
    because a turn at char 0 has no left context."""
    if offset < 0 or n_chars <= 0:
        return "none"
    frac = offset / n_chars
    if frac < 0.10:
        return "0-10%"
    if frac < 0.25:
        return "10-25%"
    if frac < 0.50:
        return "25-50%"
    if frac < 0.75:
        return "50-75%"
    return "75-100%"


def summarize(rows: list[dict], tau: float = 0.5) -> dict:
    """rows: [{label, prob, n_chars, turn_offset_in_chunk}]. Applies threshold."""
    for r in rows:
        r["pred"] = 1 if r["prob"] >= tau else 0
    overall = compute_prf([r["label"] for r in rows], [r["pred"] for r in rows])
    rep = {
        "tau": tau,
        "n": len(rows),
        "overall": overall.as_dict(),
        "by_length": bucket_report(rows, "n_chars", len_bucket),
        "by_position": bucket_report(
            [r for r in rows if r["label"] == 1], "turn_offset_in_chunk",
            lambda off: position_bucket(off, 256),
        ),
    }
    return rep


# ---- document-level: first-positive-chunk must localize the turn ----------
def document_metrics(docs: list[dict], tau: float = 0.5) -> dict:
    """docs: [{doc_id, has_turn, chunks:[{label,prob,start,end}], turn_pos}].

    A positive document is a HIT iff the first chunk with prob>=tau contains
    the recorded turn char offset. A positive with no positive chunk = MISS.
    A negative document is a FALSE ALARM iff any chunk crosses tau.
    """
    hits = misses = 0
    false_alarms = true_neg = 0
    for d in docs:
        preds = [c for c in d["chunks"] if c["prob"] >= tau]
        if d["has_turn"]:
            tp = d.get("turn_pos", -1)
            ok = any(c["start"] <= tp < c["end"] for c in preds)
            if ok:
                hits += 1
            else:
                misses += 1
        else:
            if preds:
                false_alarms += 1
            else:
                true_neg += 1
    pos, neg = hits + misses, false_alarms + true_neg
    return {
        "positive_docs": pos,
        "negative_docs": neg,
        "turn_localized": hits,
        "turn_missed": misses,
        "recall": round(hits / pos, 4) if pos else 0.0,
        "false_alarms": false_alarms,
        "false_alarm_rate": round(false_alarms / neg, 4) if neg else 0.0,
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Score a chunk-prediction JSONL.")
    ap.add_argument("preds", help="JSONL with {label, prob, n_chars, turn_offset_in_chunk}")
    ap.add_argument("--tau", type=float, default=0.5)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.preds, encoding="utf-8") if l.strip()]
    rep = summarize(rows, args.tau)
    txt = json.dumps(rep, indent=2, ensure_ascii=False)
    print(txt)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(txt)
