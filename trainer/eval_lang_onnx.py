#!/usr/bin/env python
"""eval_lang_onnx.py — per-language P/R/F1 for a shipped ONNX artifact on the
v3 test split. Mirrors eval_test_onnx.py exactly (same split, same tokenizer,
same summarize) but groups rows by `lang` so the README's en/zh/all table can be
reproduced for any model.

Usage:
  python eval_lang_onnx.py --chunks corpus/r4.balanced.chunks.v3.jsonl \
      --onnx out/r4-v3-model.onnx --tokenizer out/r4-v3-model --max-len 448
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

from evaluate import summarize
from train import load_chunks, split_by_topic


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--onnx", required=True)
    ap.add_argument("--tokenizer", required=True)
    ap.add_argument("--max-len", dest="max_len", type=int, default=448)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rows = load_chunks(Path(args.chunks))
    _, _, test_r = split_by_topic(rows, args.seed)

    tok = AutoTokenizer.from_pretrained(args.tokenizer, use_fast=True)
    sess = ort.InferenceSession(args.onnx, providers=["CPUExecutionProvider"])
    in_names = {i.name for i in sess.get_inputs()}

    by_lang = defaultdict(list)
    for r in test_r:
        enc = tok([r["text"]], padding="max_length", truncation=True,
                  max_length=args.max_len, return_tensors="np")
        feeds = {"input_ids": enc["input_ids"].astype(np.int64),
                 "attention_mask": enc["attention_mask"].astype(np.int64)}
        feeds = {k: v for k, v in feeds.items() if k in in_names}
        logits = sess.run(None, feeds)[0]
        e = np.exp(logits[0] - logits[0].max())
        prob = float((e / e.sum())[1])
        by_lang[r.get("lang", "en")].append({
            "label": int(r["label"]), "prob": prob,
            "n_chars": int(r.get("n_chars", 0)),
            "turn_offset_in_chunk": int(r.get("turn_offset_in_chunk", 0)),
        })

    print(f"{'lang':6} {'n':>5} {'pos':>4} {'P':>7} {'R':>7} {'F1':>7}")
    all_rows = []
    for lang in sorted(by_lang):
        rs = by_lang[lang]
        all_rows.extend(rs)
        rep = summarize(rs)["overall"]
        npos = sum(1 for r in rs if r["label"] == 1)
        print(f"{lang:6} {len(rs):5d} {npos:4d} {rep['precision']:7.4f} "
              f"{rep['recall']:7.4f} {rep['f1']:7.4f}")
    rep = summarize(all_rows)["overall"]
    print(f"{'ALL':6} {len(all_rows):5d} "
          f"{sum(1 for r in all_rows if r['label']==1):4d} {rep['precision']:7.4f} "
          f"{rep['recall']:7.4f} {rep['f1']:7.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
