#!/usr/bin/env python
"""train.py — fine-tune distilbert-base-multilingual-cased on chunk JSONL.

Key correctness requirements (see machine-learning/crossroad-trainer/plan-crossroad-distilbert-chunks.md):

  * SPLIT BY topic_id, NOT by row. topic_id must be disjoint across
    train/val/test. Reusing a topic across splits is exactly the v2 failure.
  * CLASS WEIGHTING from the observed pos:neg ratio. Harvested data is
    ~1:150, so unweighted training collapses to the majority class. We do NOT
    duplicate windows (that would re-couple class to length); we weight the
    loss.
  * MAX_LEN 512, matching the chunker's W=510 window.

Usage:
  python train.py --chunks corpus/chunks.jsonl --out out/model \
      --epochs 3 --seed 42
"""
from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

from evaluate import summarize

BASE = "distilbert-base-multilingual-cased"
DEFAULT_MAX_LEN = 128  # matches chunking.WINDOW; override with --max-len


class ChunkDataset(Dataset):
    def __init__(self, rows, tokenizer, max_len=DEFAULT_MAX_LEN):
        self.rows = rows
        self.tok = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        enc = self.tok(
            r["text"], truncation=True, max_length=self.max_len, padding="max_length"
        )
        return {
            "input_ids": torch.tensor(enc["input_ids"], dtype=torch.long),
            "attention_mask": torch.tensor(enc["attention_mask"], dtype=torch.long),
            "labels": torch.tensor(r["label"], dtype=torch.long),
            "n_chars": torch.tensor(len(r["text"]), dtype=torch.long),
            "turn_offset_in_chunk": torch.tensor(
                r.get("turn_offset_in_chunk", -1), dtype=torch.long
            ),
        }


def load_chunks(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def split_by_topic(rows: list[dict], seed: int, val_frac=0.15, test_frac=0.15):
    """Disjoint topic_id split. Positives are rare, so we stratify by whether
    the topic contains a positive chunk."""
    topics: dict[str, dict] = {}
    for r in rows:
        t = r["topic_id"]
        e = topics.setdefault(t, {"rows": [], "has_pos": False})
        e["rows"].append(r)
        if r["label"] == 1:
            e["has_pos"] = True

    pos_topics = [t for t, e in topics.items() if e["has_pos"]]
    neg_topics = [t for t, e in topics.items() if not e["has_pos"]]
    rng = random.Random(seed)
    rng.shuffle(pos_topics)
    rng.shuffle(neg_topics)

    def take(lst, frac):
        k = max(1, int(len(lst) * frac)) if lst else 0
        return lst[:k], lst[k:]

    pv, pos_rest = take(pos_topics, val_frac)
    pt, pos_rest = take(pos_rest, test_frac / max(1e-9, 1 - val_frac))
    nv, neg_rest = take(neg_topics, val_frac)
    nt, neg_rest = take(neg_rest, test_frac / max(1e-9, 1 - val_frac))

    def collect(ts):
        out = []
        for t in ts:
            out.extend(topics[t]["rows"])
        return out

    return (
        collect(pos_rest + neg_rest),
        collect(pv + nv),
        collect(pt + nt),
    )


def eval_rows(model, loader, device) -> list[dict]:
    """Run the model over a loader. Carries the bucket-diagnostic keys
    (`n_chars`, `turn_offset_in_chunk`) through so summarize() can bucket."""
    model.eval()
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
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--max-len", dest="max_len", type=int, default=DEFAULT_MAX_LEN)
    ap.add_argument("--lr", type=float, default=3e-5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--log-every", type=int, default=10)
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    rows = load_chunks(Path(args.chunks))
    train_r, val_r, test_r = split_by_topic(rows, args.seed)

    def ratio(rs):
        c = Counter(r["label"] for r in rs)
        return c

    print(f"device={device}  train={len(train_r)} {dict(ratio(train_r))}")
    print(f"           val={len(val_r)} {dict(ratio(val_r))}  test={len(test_r)} {dict(ratio(test_r))}")

    tok = AutoTokenizer.from_pretrained(BASE, use_fast=True)
    model = AutoModelForSequenceClassification.from_pretrained(BASE, num_labels=2).to(device)

    tr_loader = DataLoader(ChunkDataset(train_r, tok, args.max_len), batch_size=args.batch, shuffle=True)
    va_loader = DataLoader(ChunkDataset(val_r, tok, args.max_len), batch_size=args.batch)
    print(f"max_len={args.max_len}  steps/epoch={len(tr_loader)}  log_every={args.log_every}", flush=True)

    # class weight = n_neg / n_pos on the TRAIN split (inverse frequency)
    c = ratio(train_r)
    w_pos = (c.get(0, 1) / max(1, c.get(1, 1)))
    weights = torch.tensor([1.0, float(w_pos)], dtype=torch.float, device=device)
    print(f"class weights: neg=1.0 pos={w_pos:.2f}")

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total = len(tr_loader) * args.epochs
    sched = get_linear_schedule_with_warmup(opt, int(total * 0.1), total)

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    best_f1 = -1.0

    for ep in range(args.epochs):
        model.train()
        running = 0.0
        t_ep = time.time()
        for i, batch in enumerate(tr_loader):
            opt.zero_grad()
            logits = model(
                input_ids=batch["input_ids"].to(device),
                attention_mask=batch["attention_mask"].to(device),
            ).logits
            loss = torch.nn.functional.cross_entropy(
                logits, batch["labels"].to(device), weight=weights
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            running += loss.item()
            if (i + 1) % args.log_every == 0:
                el = time.time() - t_ep
                print(f"  ep{ep+1} step {i+1}/{len(tr_loader)} "
                      f"loss={running/(i+1):.4f} {el:.0f}s "
                      f"({(i+1)/el:.1f} steps/s)", flush=True)
        vr = eval_rows(model, va_loader, device)
        rep = summarize(vr)
        f1 = rep["overall"]["f1"]
        print(f"epoch {ep+1}: train_loss={running/len(tr_loader):.4f} "
              f"val_f1={f1:.4f} val_P={rep['overall']['precision']:.4f} "
              f"val_R={rep['overall']['recall']:.4f}")
        if f1 > best_f1:
            best_f1 = f1
            model.save_pretrained(outdir)
            tok.save_pretrained(outdir)
            (outdir / "val_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
            print(f"  -> saved best (f1={f1:.4f}) to {outdir}")

    print(f"done. best val F1 = {best_f1:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
