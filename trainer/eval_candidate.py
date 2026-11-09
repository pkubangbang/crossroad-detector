#!/usr/bin/env python
"""Evaluate frozen TEST, weak slices, and option-b document false alarms.

All offsets and lengths are Unicode code points. No split is recomputed when
--test-manifest is supplied: the exact original chunk IDs are scored verbatim.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

from chunker import build_spans
from evaluate import document_metrics, summarize
from train import load_chunks


def wilson(successes: int, n: int, z: float = 1.959963984540054) -> list[float]:
    if not n:
        return [0.0, 0.0]
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [round(center - half, 4), round(center + half, 4)]


def score_rows(sess, tok, rows, max_len):
    names = {i.name for i in sess.get_inputs()}
    results = []
    for i, row in enumerate(rows):
        enc = tok([row["text"]], padding="max_length", truncation=True,
                  max_length=max_len, return_tensors="np")
        feeds = {"input_ids": enc["input_ids"].astype(np.int64),
                 "attention_mask": enc["attention_mask"].astype(np.int64)}
        logits = sess.run(None, {k: v for k, v in feeds.items() if k in names})[0][0]
        e = np.exp(logits - logits.max())
        results.append({**row, "prob": float((e / e.sum())[1])})
        if (i + 1) % 500 == 0:
            print(f"scored {i + 1}/{len(rows)}", flush=True)
    return results


def enrich(records):
    return [{"label": int(r["label"]), "prob": r["prob"],
             "n_chars": r.get("n_chars", len(r["text"])),
             "turn_offset_in_chunk": r.get("turn_offset_in_chunk", -1),
             "doc_id": r["doc_id"], "chunk_id": r["chunk_id"]}
            for r in records]


def compare_slices(records):
    base = summarize([dict(r) for r in records])
    base["recall_wilson_95"] = wilson(base["overall"]["tp"],
        base["overall"]["tp"] + base["overall"]["fn"])
    for group in ("by_length", "by_position"):
        for report in base[group].values():
            report["recall_wilson_95"] = wilson(report["tp"], report["tp"] + report["fn"])
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--onnx", required=True)
    ap.add_argument("--tokenizer", required=True)
    ap.add_argument("--test-chunks", required=True)
    ap.add_argument("--test-manifest", required=True)
    ap.add_argument("--dropped-docs", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--predictions")
    ap.add_argument("--max-len", type=int, default=448)
    args = ap.parse_args()
    tok = AutoTokenizer.from_pretrained(args.tokenizer, use_fast=True)
    sess = ort.InferenceSession(args.onnx, providers=["CPUExecutionProvider"])
    rows = load_chunks(Path(args.test_chunks))
    ids = set(json.loads(Path(args.test_manifest).read_text(encoding="utf-8"))["test_chunk_ids"])
    test = [r for r in rows if r["chunk_id"] in ids]
    assert {r["chunk_id"] for r in test} == ids
    scored = enrich(score_rows(sess, tok, test, args.max_len))
    report = {"onnx": args.onnx, "max_len": args.max_len,
              "test": compare_slices(scored)}

    docs = [json.loads(line) for line in Path(args.dropped_docs).read_text(encoding="utf-8").splitlines() if line.strip()]
    dropped_chunks = []
    for doc in docs:
        assert not doc["has_turn"]
        for ci, (start, end) in enumerate(build_spans(doc["text"], None)):
            dropped_chunks.append({"chunk_id": f"{doc['id']}#{ci}", "doc_id": doc["id"],
                "topic_id": doc["topic_id"], "text": doc["text"][start:end],
                "label": 0, "n_chars": end - start, "turn_offset_in_chunk": -1,
                "start": start, "end": end})
    dropped = score_rows(sess, tok, dropped_chunks, args.max_len)
    by_doc = defaultdict(list)
    for row in dropped:
        by_doc[row["doc_id"]].append(row)
    doc_rows = [{"doc_id": doc_id, "has_turn": False,
                 "chunks": [{"prob": r["prob"], "start": r["start"], "end": r["end"]} for r in rs]}
                for doc_id, rs in by_doc.items()]
    report["dropped_optionb"] = {
        "documents": len(docs), "chunks": len(dropped),
        "positive_chunks": sum(r["prob"] >= 0.5 for r in dropped),
        "chunk_false_positive_rate": round(sum(r["prob"] >= 0.5 for r in dropped) / max(1, len(dropped)), 4),
        "document": document_metrics(doc_rows),
    }
    Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.predictions:
        Path(args.predictions).write_text("\n".join(json.dumps(r) for r in scored) + "\n", encoding="utf-8")
    print(json.dumps({"overall": report["test"]["overall"],
                      "recall_wilson_95": report["test"]["recall_wilson_95"],
                      "length_384_511": report["test"]["by_length"].get("384-511"),
                      "dropped_optionb": report["dropped_optionb"]}, indent=2))


if __name__ == "__main__":
    main()
