#!/usr/bin/env python
"""export_misclassified.py — dump v4 FN/FP test chunks with metadata.

Replicates eval_test.py's split + inference, but carries the row's
lang/scenario/turn_type/text through and writes the misclassified chunks
(label != prediction) to a JSON for morphological analysis.
"""
from __future__ import annotations
import argparse, json
from collections import Counter
from pathlib import Path
import torch
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from train import ChunkDataset, load_chunks, split_by_topic


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-len", dest="max_len", type=int, default=128)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    rows = load_chunks(Path(args.chunks))
    _, _, test_r = split_by_topic(rows, args.seed)
    print(f"device={device}  test_rows={len(test_r)}")

    tok = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    model = AutoModelForSequenceClassification.from_pretrained(args.model).to(device)
    model.eval()

    loader = DataLoader(ChunkDataset(test_r, tok, args.max_len), batch_size=args.batch)
    mis = []
    with torch.no_grad():
        for i, batch in enumerate(loader):
            ids = batch["input_ids"].to(device)
            am = batch["attention_mask"].to(device)
            logits = model(input_ids=ids, attention_mask=am).logits
            probs = torch.softmax(logits, dim=-1)[:, 1].cpu().numpy()
            labels = batch["labels"].cpu().tolist()
            base = i * args.batch
            for k in range(len(probs)):
                pred = 1 if float(probs[k]) >= 0.5 else 0
                lab = int(labels[k])
                if pred != lab:
                    r = test_r[base + k]
                    mis.append({
                        "kind": "FP" if pred == 1 and lab == 0 else "FN",
                        "label": lab,
                        "pred": pred,
                        "prob": round(float(probs[k]), 4),
                        "lang": r.get("lang"),
                        "scenario": r.get("scenario"),
                        "turn_type": r.get("turn_type"),
                        "n_chars": int(r.get("n_chars", 0)),
                        "turn_offset_in_chunk": int(r.get("turn_offset_in_chunk", -1)),
                        "provenance": r.get("provenance"),
                        "doc_id": r.get("doc_id"),
                        "text": r["text"],
                    })

    # summary by kind x lang x turn_type x scenario
    fn = [m for m in mis if m["kind"] == "FN"]
    fp = [m for m in mis if m["kind"] == "FP"]
    summary = {
        "model": args.model,
        "n_test": len(test_r),
        "n_fn": len(fn),
        "n_fp": len(fp),
        "fn_by_turn_type": dict(Counter(m["turn_type"] for m in fn)),
        "fn_by_scenario": dict(Counter(m["scenario"] for m in fn)),
        "fn_by_lang": dict(Counter(m["lang"] for m in fn)),
        "fn_by_provenance": dict(Counter(m["provenance"] for m in fn)),
        "fp_by_lang": dict(Counter(m["lang"] for m in fp)),
        "fp_by_scenario": dict(Counter(m["scenario"] for m in fp)),
        "fp_by_provenance": dict(Counter(m["provenance"] for m in fp)),
        "fn_lowest_prob": sorted(fn, key=lambda m: m["prob"])[:30],
        "fp_highest_prob": sorted(fp, key=lambda m: -m["prob"])[:30],
    }
    Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"FN={len(fn)}  FP={len(fp)}")
    print(f"FN by turn_type: {summary['fn_by_turn_type']}")
    print(f"FN by scenario:  {summary['fn_by_scenario']}")
    print(f"FN by lang:      {summary['fn_by_lang']}")
    print(f"FP by lang:      {summary['fp_by_lang']}")
    print(f"FP by provenance:{summary['fp_by_provenance']}")
    print(f"report -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())