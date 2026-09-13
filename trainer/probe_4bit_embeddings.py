"""probe_4bit_embeddings.py — rewrite word_embeddings to 4-bit GatherBlockQuantized.

Embedding lookup in out/model-v7/model.onnx:
    Gather(weight_quantized[119547,768] UINT8, input_ids) -> *_quantized
    DequantizeLinear(*_quantized, weight_scale, weight_zero_point) -> embeddings

That table is 91.8 MB of the 129 MB file. This replaces it with a 4-bit
block-quantized table via ORT's com.microsoft::GatherBlockQuantized.

Empirically discovered schema (ORT 1.29, onnxruntime-node-compatible):
  - domain "com.microsoft", opset 1
  - inputs: (data, indices, scales [, zero_points])
  - attributes: block_size (power of 2, >= 16), bits (default 4)
  - NO "axis" attribute
  - scales must have the SAME RANK as data
  - data is int4-packed along the last dim: K int4 values -> K/2 bytes
  - output value count per row = K (unpacked)

Usage: python probe_4bit_embeddings.py
"""
from __future__ import annotations

import os
import numpy as np
import onnx
import onnxruntime as ort
from onnx import helper, numpy_helper

SRC = "out/model-v7/model.onnx"
DST = "out/p-4bit-emb.onnx"
BITS = 4
BLOCK = 16  # must be a power of two >= 16


def quantize_blockwise(w: np.ndarray, bits: int = BITS, block: int = BLOCK):
    """Symmetric block-wise int4 quantization along axis 1. scales shape [N, K/block]."""
    n, k = w.shape
    assert k % block == 0, f"{k} not divisible by {block}"
    wb = w.reshape(n, k // block, block)
    qmax = (1 << (bits - 1)) - 1
    amax = np.max(np.abs(wb), axis=2, keepdims=True)
    scales = np.where(amax == 0, 1e-8, amax / qmax)
    q = np.round(wb / scales).clip(-qmax - 1, qmax).astype(np.int16).reshape(n, k)
    return q, scales.reshape(n, k // block).astype(np.float32)


def pack_last_dim_int4(q: np.ndarray) -> np.ndarray:
    """Pack int4 along the last dim: [N,K] -> [N,K/2] uint8 (low nibble first)."""
    n, k = q.shape
    assert k % 2 == 0
    lo = (q[:, 0::2] & 0xF).astype(np.uint8)
    hi = (q[:, 1::2] & 0xF).astype(np.uint8)
    return (lo | (hi << 4)).astype(np.uint8)


def main() -> int:
    from safetensors.numpy import load_file

    m = onnx.load(SRC, load_external_data=True)
    we_q = "model.distilbert.embeddings.word_embeddings.weight_quantized"
    we_s = "model.distilbert.embeddings.word_embeddings.weight_scale"
    we_z = "model.distilbert.embeddings.word_embeddings.weight_zero_point"

    w = load_file("out/model-v6/model.safetensors")[
        "distilbert.embeddings.word_embeddings.weight"].astype(np.float32)
    n, k = w.shape
    print(f"fp32 embeddings {w.shape} {w.nbytes/1e6:.1f} MB")

    q, scales = quantize_blockwise(w, BITS, BLOCK)
    packed = pack_last_dim_int4(q)
    print(f"data  {packed.shape} uint8 = {packed.nbytes/1e6:.1f} MB")
    print(f"scales {scales.shape} float32 = {scales.nbytes/1e6:.3f} MB")

    # swap initializers
    keep = [i for i in m.graph.initializer if i.name not in (we_q, we_s, we_z)]
    keep.append(numpy_helper.from_array(packed, name=we_q))
    keep.append(numpy_helper.from_array(scales, name=we_s))
    del m.graph.initializer[:]
    m.graph.initializer.extend(keep)

    # add com.microsoft opset
    if not any(i.domain == "com.microsoft" for i in m.opset_import):
        m.opset_import.append(helper.make_opsetid("com.microsoft", 1))

    gather = next(n_ for n_ in m.graph.node if n_.op_type == "Gather" and we_q in n_.input)
    deq = next(n_ for n_ in m.graph.node if n_.op_type == "DequantizeLinear" and we_s in n_.input)

    gather.op_type = "GatherBlockQuantized"
    gather.domain = "com.microsoft"
    del gather.attribute[:]
    gather.input[:] = [we_q, gather.input[1], we_s]
    gather.attribute.extend([
        helper.make_attribute("block_size", BLOCK),
        helper.make_attribute("bits", BITS),
    ])
    gather.output[0] = deq.output[0]  # becomes the real embeddings tensor
    m.graph.node.remove(deq)
    print(f"rewrote Gather -> GatherBlockQuantized (block_size={BLOCK}, bits={BITS})")

    try:
        onnx.checker.check_model(m)
        print("onnx.checker: OK")
    except Exception as e:
        print(f"onnx.checker: FAIL {str(e)[:160]}")

    onnx.save(m, DST)
    print(f"saved {DST}  {os.path.getsize(DST)/1e6:.1f} MB")

    ids = np.ones((1, 448), dtype=np.int64)
    mask = np.ones((1, 448), dtype=np.int64)
    try:
        got = ort.InferenceSession(DST, providers=["CPUExecutionProvider"]).run(
            None, {"input_ids": ids, "attention_mask": mask})[0]
        ref = ort.InferenceSession(SRC, providers=["CPUExecutionProvider"]).run(
            None, {"input_ids": ids, "attention_mask": mask})[0]
        print(f"ORT load OK  logits {got.shape}  "
              f"max|d| vs int8 = {float(np.max(np.abs(ref - got))):.4f}")
    except Exception as e:
        print(f"ORT load FAIL: {str(e).split('Error')[-1][:300]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
