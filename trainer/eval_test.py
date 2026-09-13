#!/usr/bin/env python
"""eval_test.py — evaluate a trained checkpoint on the held-out TEST split.

train.py only writes val_report.json (it checkpoints on val F1). This script
re-runs the SAME topic-disjoint split (same seed) so the test split is
identical, then reports precision/recall/F1/confusion on TEST via the shared
evaluate.summarize (which also gives length/position bucket diagnostics).

Usage:
  python eval_test.py --chunks corpus/balanced.chunks.jsonl --model out/model-v3 \
      --split onnx-test-report.json --seed 42
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from evaluate import summarize
from train import ChunkDataset, load_chunks, split_by_topic


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--max-len", dest="max_len", type=int, default=128)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    rows = load_chunks(Path(args.chunks))
    _, _, test_r = split_by_topic(rows, args.seed)
    n_pos = sum(1 for r in test_r if r["label"] == 1)
    print(f"device={device}  test_rows={len(test_r)} (pos={n_pos})")

    tok = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    model = AutoModelForSequenceClassification.from_pretrained(args.model).to(device)
    model.eval()

    loader = DataLoader(ChunkDataset(test_r, tok, args.max_len), batch_size=args.batch)
    out = []
    with torch.no_grad():
        for batch in loader:
            ids = batch["input_ids"].to(device)
            am = batch["attention_mask"].to(device)
            logits = model(input_ids=ids, attention_mask=am).logits
            probs = torch.softmax(logits, dim=-1)[:, 1].cpu().numpy()
            labels = batch["labels"].cpu().tolist()
            nchars = batch["n_chars"].cpu().tolist()
            offs = batch["turn_offset_in_chunk"].cpu().tolist()
            for k in range(len(probs)):
                out.append({
                    "label": int(labels[k]),
                    "prob": float(probs[k]),
                    "n_chars": int(nchars[k]),
                    "turn_offset_in_chunk": int(offs[k]),
                })

    rep = summarize(out)
    Path(args.report).write_text(json.dumps(rep, indent=2), encoding="utf-8")
    o = rep["overall"]
    print(f"TEST  P={o['precision']:.4f}  R={o['recall']:.4f}  F1={o['f1']:.4f}  "
          f"(tp={o.get('tp')} fp={o.get('fp')} fn={o.get('fn')} tn={o.get('tn')})")
    print(f"report -> {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
