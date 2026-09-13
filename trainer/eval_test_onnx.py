#!/usr/bin/env python
"""eval_test_onnx.py — evaluate the SHIPPED ONNX artifact (INT8) on the TEST split.

train.py records val F1 for the PyTorch model; export_onnx.py reports a raw
logit parity delta. Neither answers the question the ship-gate actually asks:
does the quantized graph still DETECT correctly? A large max|Δlogit| can be
harmless (both sides agree on argmax) or harmful (decision flips).

This script runs the identical topic-disjoint TEST split (seed 42) through the
ONNX graph via onnxruntime — no torch model in the loop — and reports
P/R/F1/confusion with the same evaluate.summarize used everywhere else, so the
number is directly comparable to out/test-report.json (the fp32/torch number).

Usage:
  python eval_test_onnx.py --chunks corpus/balanced.chunks.jsonl \
      --onnx out/model-v3/model.onnx --tokenizer out/model-v3 \
      --report out/test-report-onnx.json
"""
from __future__ import annotations

import argparse
import json
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
    ap.add_argument("--tokenizer", required=True, help="HF dir holding tokenizer.json")
    ap.add_argument("--report", required=True)
    ap.add_argument("--max-len", dest="max_len", type=int, default=128)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rows = load_chunks(Path(args.chunks))
    _, _, test_r = split_by_topic(rows, args.seed)
    n_pos = sum(1 for r in test_r if r["label"] == 1)
    print(f"onnx={args.onnx}  test_rows={len(test_r)} (pos={n_pos})")

    tok = AutoTokenizer.from_pretrained(args.tokenizer, use_fast=True)
    sess = ort.InferenceSession(args.onnx, providers=["CPUExecutionProvider"])
    in_names = {i.name for i in sess.get_inputs()}

    # The shipped graph is exported with dynamic_axes=None => FIXED batch=1
    # (the runtime encoder feeds exactly one window at a time). Evaluate one
    # row per ORT call; --batch is ignored for the graph, kept for tokenizer
    # batching only.
    out = []
    total = len(test_r)
    for i, r in enumerate(test_r):
        enc = tok(
            [r["text"]],
            padding="max_length",
            truncation=True,
            max_length=args.max_len,
            return_tensors="np",
        )
        # onnxruntime needs int64; tokenizers hand back int32
        feeds = {
            "input_ids": enc["input_ids"].astype(np.int64),
            "attention_mask": enc["attention_mask"].astype(np.int64),
        }
        feeds = {k: v for k, v in feeds.items() if k in in_names}
        logits = sess.run(None, feeds)[0]  # [1, 2]
        e = np.exp(logits[0] - logits[0].max())
        probs = e / e.sum()
        out.append({
            "label": int(r["label"]),
            "prob": float(probs[1]),
            "n_chars": int(r.get("n_chars", 0)),
            "turn_offset_in_chunk": int(r.get("turn_offset_in_chunk", 0)),
        })
        if (i + 1) % 1000 == 0:
            print(f"  scored {i + 1}/{total}")

    rep = summarize(out)
    Path(args.report).write_text(json.dumps(rep, indent=2), encoding="utf-8")
    o = rep["overall"]
    print(f"ONNX TEST  P={o['precision']:.4f}  R={o['recall']:.4f}  F1={o['f1']:.4f}  "
          f"(tp={o.get('tp')} fp={o.get('fp')} fn={o.get('fn')} tn={o.get('tn')})")
    print(f"report -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
