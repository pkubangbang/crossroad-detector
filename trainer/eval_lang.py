#!/usr/bin/env python
"""eval_lang.py — per-language comparison of two ONNX artifacts on one chunk set.

Reports precision / recall / F1 for each language plus overall, so an English-
targeted corpus round can be judged on the metric it was meant to move rather
than only the pooled number.

Usage:
  python eval_lang.py --chunks corpus/r4.balanced.chunks.v2.jsonl \
      --a ../model/model.onnx --tag-a baseline --b out/r4-model.onnx --tag-b r4
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

from evaluate import summarize
from train import load_chunks, split_by_topic


def score(onnx: str, test_r, tok, max_len: int):
    sess = ort.InferenceSession(onnx, providers=["CPUExecutionProvider"])
    in_names = {i.name for i in sess.get_inputs()}
    out = []
    for r in test_r:
        enc = tok([r["text"]], padding="max_length", truncation=True,
                  max_length=max_len, return_tensors="np")
        feeds = {
            "input_ids": enc["input_ids"].astype(np.int64),
            "attention_mask": enc["attention_mask"].astype(np.int64),
        }
        feeds = {k: v for k, v in feeds.items() if k in in_names}
        logits = sess.run(None, feeds)[0]
        e = np.exp(logits[0] - logits[0].max())
        p = e / e.sum()
        out.append({
            "label": int(r["label"]),
            "prob": float(p[1]),
            "n_chars": int(r.get("n_chars", 0)),
            "turn_offset_in_chunk": int(r.get("turn_offset_in_chunk", 0)),
            "lang": r.get("lang", "en"),
        })
    return out


def report(tag: str, rows):
    print(f"=== {tag} ===")
    for lang in sorted({o["lang"] for o in rows}):
        sub = [o for o in rows if o["lang"] == lang]
        s = summarize(sub)["overall"]
        print(f"  {lang:>3}: P={s['precision']:.4f} R={s['recall']:.4f} "
              f"F1={s['f1']:.4f} (tp={s.get('tp')} fp={s.get('fp')} "
              f"fn={s.get('fn')} tn={s.get('tn')})")
    s = summarize(rows)["overall"]
    print(f"  ALL: P={s['precision']:.4f} R={s['recall']:.4f} F1={s['f1']:.4f} "
          f"(tp={s.get('tp')} fp={s.get('fp')} fn={s.get('fn')} tn={s.get('tn')})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--a", required=True, help="artifact A path")
    ap.add_argument("--tag-a", default="A")
    ap.add_argument("--b", required=True, help="artifact B path")
    ap.add_argument("--tag-b", default="B")
    ap.add_argument("--max-len", dest="max_len", type=int, default=448)
    ap.add_argument("--tokenizer", default="../model")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rows = load_chunks(Path(args.chunks))
    _, _, test_r = split_by_topic(rows, args.seed)
    n_pos = sum(1 for r in test_r if r["label"] == 1)
    print(f"test_rows={len(test_r)} (pos={n_pos})  max_len={args.max_len}\n")
    tok = AutoTokenizer.from_pretrained(args.tokenizer, use_fast=True)
    report(args.tag_a, score(args.a, test_r, tok, args.max_len))
    print()
    report(args.tag_b, score(args.b, test_r, tok, args.max_len))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
