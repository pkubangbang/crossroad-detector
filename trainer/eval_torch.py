#!/usr/bin/env python
"""eval_torch.py — evaluate a fine-tuned HF model dir (fp32, no quantization).

Isolates the CORPUS effect from the INT8 quantisation effect: run this on the
same chunks and split as eval_lang.py, then compare against the INT8 artifact.

Usage:
  python eval_torch.py --chunks corpus/r4.balanced.chunks.v2.jsonl \
      --model out/r4-model --max-len 448 --seed 42
"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from evaluate import summarize
from train import load_chunks, split_by_topic


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--model", required=True, help="fine-tuned HF model dir")
    ap.add_argument("--max-len", dest="max_len", type=int, default=448)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--batch", type=int, default=32)
    args = ap.parse_args()

    rows = load_chunks(Path(args.chunks))
    _, _, test_r = split_by_topic(rows, args.seed)
    n_pos = sum(1 for r in test_r if r["label"] == 1)
    print(f"test_rows={len(test_r)} (pos={n_pos})  max_len={args.max_len}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device={device}")
    tok = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    model = AutoModelForSequenceClassification.from_pretrained(args.model).to(device)
    model.eval()

    out = []
    with torch.no_grad():
        for i in range(0, len(test_r), args.batch):
            batch = test_r[i:i + args.batch]
            enc = tok([r["text"] for r in batch], padding="max_length",
                      truncation=True, max_length=args.max_len, return_tensors="pt")
            enc = {k: v.to(device) for k, v in enc.items()}
            logits = model(**enc).logits
            probs = torch.softmax(logits, dim=-1)[:, 1].cpu().tolist()
            for r, p in zip(batch, probs):
                out.append({
                    "label": int(r["label"]),
                    "prob": float(p),
                    "n_chars": int(r.get("n_chars", 0)),
                    "turn_offset_in_chunk": int(r.get("turn_offset_in_chunk", 0)),
                    "lang": r.get("lang", "en"),
                })

    for lang in sorted({o["lang"] for o in out}):
        sub = [o for o in out if o["lang"] == lang]
        s = summarize(sub)["overall"]
        print(f"  {lang:>3}: P={s['precision']:.4f} R={s['recall']:.4f} "
              f"F1={s['f1']:.4f} (tp={s.get('tp')} fp={s.get('fp')} "
              f"fn={s.get('fn')} tn={s.get('tn')})")
    s = summarize(out)["overall"]
    print(f"  ALL: P={s['precision']:.4f} R={s['recall']:.4f} F1={s['f1']:.4f} "
          f"(tp={s.get('tp')} fp={s.get('fp')} fn={s.get('fn')} tn={s.get('tn')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
