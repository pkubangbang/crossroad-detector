#!/usr/bin/env python
"""eval_v7.py — evaluate the SHIPPED v7 ONNX artifact with correct v7 defaults.

Why this exists
---------------
`eval_test_onnx.py` is v6-era: it defaults to `--max-len 128` (the 128-char /
stride-32 `chunking.py` world) and its usage example points at a v3 ONNX.
The shipped artifact is v7 — 448-char contiguous tiles (`chunker_v2.py`,
`X_CHARS=448`) — and its graph is EXPORTED WITH A FIXED SEQUENCE LENGTH OF 448.
Running the old defaults against it fails loudly:

    onnxruntime...InvalidArgument: Got invalid dimensions for input:
    attention_mask ... index: 1 Got: 512 Expected: 448

so the correct invocation is `--max-len 448` over v2 chunks. This script makes
that the default instead of tribal knowledge, so the ship-gate is reproducible
from a clean checkout:

    python eval_v7.py --chunks corpus/balanced.chunks.v2.jsonl \
        --onnx ../model/model.onnx --tokenizer ../model

Deriving the chunks is a separate, documented step:

    python chunker_v2.py --in corpus/balanced.jsonl \
        --out corpus/balanced.chunks.v2.jsonl

The scoring path is otherwise identical to eval_test_onnx.py (same
topic-disjoint split via train.split_by_topic, same evaluate.summarize, so the
number is directly comparable to out/test-report-onnx*.json).
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

# v7 is 448-char contiguous tiles; the exported graph is fixed at 448.
V7_MAX_LEN = 448


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--onnx", required=True)
    ap.add_argument("--tokenizer", required=True, help="HF dir holding tokenizer.json")
    ap.add_argument("--report", required=True)
    # 448 is the v7 default; override only with a matching artifact.
    ap.add_argument("--max-len", dest="max_len", type=int, default=V7_MAX_LEN)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if args.max_len != V7_MAX_LEN:
        print(f"warning: --max-len {args.max_len} != v7 default {V7_MAX_LEN}; "
              f"only correct if the graph was exported at that length")

    rows = load_chunks(Path(args.chunks))
    _, _, test_r = split_by_topic(rows, args.seed)
    n_pos = sum(1 for r in test_r if r["label"] == 1)
    print(f"onnx={args.onnx}  max_len={args.max_len}  test_rows={len(test_r)} (pos={n_pos})")

    tok = AutoTokenizer.from_pretrained(args.tokenizer, use_fast=True)
    sess = ort.InferenceSession(args.onnx, providers=["CPUExecutionProvider"])
    in_names = {i.name for i in sess.get_inputs()}

    # Confirm the graph's expected length rather than trusting the flag.
    for i in sess.get_inputs():
        dims = [d for d in i.shape if isinstance(d, int)]
        if len(dims) >= 2 and dims[1] != args.max_len:
            raise SystemExit(
                f"artifact/graph mismatch: graph input '{i.name}' has fixed "
                f"seq len {dims[1]}, but --max-len is {args.max_len}. "
                f"Re-run with --max-len {dims[1]}."
            )

    out = []
    for i, r in enumerate(test_r):
        enc = tok(
            [r["text"]],
            padding="max_length",
            truncation=True,
            max_length=args.max_len,
            return_tensors="np",
        )
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
        if (i + 1) % 500 == 0:
            print(f"  scored {i + 1}/{len(test_r)}")

    rep = summarize(out)
    Path(args.report).write_text(json.dumps(rep, indent=2), encoding="utf-8")
    o = rep["overall"]
    print(f"ONNX v7 TEST  P={o['precision']:.4f}  R={o['recall']:.4f}  F1={o['f1']:.4f}  "
          f"(tp={o.get('tp')} fp={o.get('fp')} fn={o.get('fn')} tn={o.get('tn')})")
    print(f"report -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
