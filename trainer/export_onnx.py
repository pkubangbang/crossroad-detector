#!/usr/bin/env python
"""export_onnx.py — export the fine-tuned DistilBERT to ONNX + INT8.

Precision policy (plan doc "Precision"):
  INT8 dynamic quantization is the target. A prior attempt hit
  ShapeInferenceError from quantize_dynamic on DistilBERT. ROOT CAUSE (found
  here): torch >= 2.9 defaults to the new dynamo ONNX exporter, which emits an
  INVALID graph for this model (it produced a 0.8 MB file instead of 541 MB, and
  quantize_dynamic then failed shape inference: "dim 0: (768) vs (2)").
  FIX: export with `dynamo=False` (legacy TorchScript exporter) at opset 18.
  That yields a correct 541 MB fp32 graph and INT8 succeeds (~412 MB, 76%).
  On any further failure we still fall back to fp32 and SAY SO.

Wire format (runtime contract, must not change):
  input_ids      int64 [1, seq]
  attention_mask int64 [1, seq]
  logits         float32 [1, 2]   (index 1 = P(turn))

Usage:
  python export_onnx.py --model out/model --out out/model/model.onnx
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MAX_LEN = 512
DEFAULT_SEQ = 128  # must match chunking.WINDOW used at training time


class Wrapper(torch.nn.Module):
    """ONNX-exportable forward: (input_ids, attention_mask) -> logits."""

    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, input_ids, attention_mask):
        return self.model(input_ids=input_ids, attention_mask=attention_mask).logits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="fine-tuned HF model dir")
    ap.add_argument("--out", required=True, help="output .onnx path")
    ap.add_argument("--seq", type=int, default=DEFAULT_SEQ, help="fixed window length")
    ap.add_argument("--opset", type=int, default=18,
                    help="ONNX opset; torch's exporter emits opset-18 ops (LayerNormalization), so 18 avoids a lossy down-conversion")
    ap.add_argument("--no-int8", action="store_true", help="skip quantization")
    args = ap.parse_args()

    import onnx
    from onnxruntime.quantization import QuantType, quantize_dynamic

    seq = args.seq

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    tok = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    model = AutoModelForSequenceClassification.from_pretrained(args.model)
    model.eval()

    ids = torch.ones((1, seq), dtype=torch.long)
    mask = torch.ones((1, seq), dtype=torch.long)

    print(f"exporting fp32 ONNX (seq={seq}, opset={args.opset}) -> {out}")
    tok.model_max_length = seq  # keep any internal guard consistent
    torch.onnx.export(
        Wrapper(model),
        (ids, mask),
        str(out),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes=None,          # fixed [1,seq]; the runtime pads to `seq`
        opset_version=args.opset,
        do_constant_folding=True,
        dynamo=False,               # legacy TorchScript exporter: full-weight graph
    )
    onnx.checker.check_model(str(out))
    fp32_bytes = out.stat().st_size
    print(f"fp32 ONNX OK: {fp32_bytes/1e6:.1f} MB")

    meta = {
        "base": "distilbert-base-multilingual-cased",
        "seq": seq,
        "wire": {"in": ["input_ids", "attention_mask"], "out": ["logits"], "id2_is_turn": True},
        "fp32_bytes": fp32_bytes,
        "precision": "fp32",
    }

    if not args.no_int8:
        q = out.with_suffix(".int8.onnx")
        # Narrow scope first: exclude ops that commonly break DistilBERT shape
        # inference (MatMul on reshaped attention, and Gather for embeddings).
        # NOTE: "narrow" skips Gather, which leaves the word_embeddings table at
        # fp32 — 367 MB of the 412 MB file! "embeddings" INCLUDES Gather so the
        # embedding table is quantized too; that drops the artifact to ~136 MB
        # (33%) at F1 0.8772 vs 0.8786 baseline (measured, n=850). "narrow" is
        # kept as a fallback only if quantizing Gather ever fails.
        attempts = [
            ("embeddings", {"op_types_to_quantize": ["MatMul", "Gemm", "Gather"]}),
            ("narrow", {"op_types_to_quantize": ["MatMul", "Gemm"]}),
            ("default", {}),
        ]
        done = False
        for name, kw in attempts:
            try:
                quantize_dynamic(
                    model_input=str(out),
                    model_output=str(q),
                    weight_type=QuantType.QInt8,
                    **kw,
                )
                qbytes = q.stat().st_size
                print(f"INT8 OK ({name}): {qbytes/1e6:.1f} MB "
                      f"({qbytes/fp32_bytes:.0%} of fp32)")
                meta.update({"precision": "int8", "int8_bytes": qbytes,
                             "int8_scope": name, "onnx": str(q.name)})
                # replace fp32 with int8 as the shipped artifact
                q.replace(out)
                meta["onnx"] = str(out.name)
                done = True
                break
            except Exception as e:  # noqa: BLE001
                print(f"INT8 attempt '{name}' FAILED: {type(e).__name__}: {e}")
        if not done:
            print("INT8 FAILED on all scopes -> shipping fp32 (plan doc allows this; "
                  "eval gate must record the precision actually shipped)")
            meta["precision_fallback"] = "fp32 (int8 failed)"

    (out.parent / "export_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    # --- verify the shipped graph with onnxruntime ---
    import onnxruntime as ort

    sess = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"])
    test_ids = np.ones((1, seq), dtype=np.int64)
    test_mask = np.ones((1, seq), dtype=np.int64)
    got = sess.run(None, {"input_ids": test_ids, "attention_mask": test_mask})
    print(f"onnxruntime verify OK: logits shape={got[0].shape} dtype={got[0].dtype}")
    assert got[0].shape == (1, 2), "runtime contract violated: logits must be [1,2]"

    # --- parity: ORT logits vs the PyTorch model (quantization sanity) ---
    with torch.no_grad():
        ref = model(input_ids=torch.tensor(test_ids), attention_mask=torch.tensor(test_mask)).logits.numpy()
    max_abs = float(np.max(np.abs(ref - got[0])))
    print(f"parity vs torch: max|Δlogit| = {max_abs:.4f}")
    meta["parity_max_abs_delta"] = max_abs
    if max_abs > 0.5:
        print("WARNING: large quantization drift -- eval gate must confirm accuracy")

    (out.parent / "export_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(f"SHIPPED precision = {meta['precision']}  ({out.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
