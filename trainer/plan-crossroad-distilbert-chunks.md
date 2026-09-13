# Crossroad detector: chunk-based DistilBERT (design)

**Status:** Phase 0 (environment) and Phase 1 (corpus contract) complete.
**Supersedes:** `docs/plan-fsm-crossroad.md` (the FSM detector this replaces).

## Goal

Replace the punctuation-sensitive FSM turning-word detector with a **semantic**
classifier. The current detector (`src/loop/crossroad-fsm.ts`) is a deterministic
lexicon matcher over connective words: it reacts to where punctuation falls, not
to what the text means. A genuine reversal phrased outside its lexicon is
invisible to it.

The new detector reads a window of text and answers one question: *is a direction
reversal happening here?*

## Why the previous ML attempt was abandoned — and why that reason is dead

`docs/plan-fsm-crossroad.md` records a DistilBERT attempt (branch
`feat/crossroad-encoder-and-regex-fallback`) that failed, and the wiki `pitfall`
domain holds the post-mortem. Critically, **the failure was in the data, not the
architecture**:

1. **Length confounding.** All `label=0` samples were 0–99 chars; most `label=1`
   samples were 100–2000+ chars. The model learned *"long ⇒ turn"* and scored
   near-random on held-out data (acc 0.466, F1 0.519). The diagnostic that caught
   it: at 200+ chars it predicted turn ~98% regardless of label.
2. **Identical texts, opposite labels.** v2 built both classes from the same
   sentence banks, differing by one connector word. The same text appeared in
   both classes, so the signal-to-noise ratio was too low to learn — loss stuck
   at `ln(2)=0.693`.

A v3 deconfounded dataset dropped loss to 0.031 with ~100% held-out accuracy —
i.e. the model was never the problem. The branch was still not merged (main went
FSM), and per the plan doc its corpus-level numbers were never produced: *"do not
cite numbers that no artifact backs."*

This design keeps that lesson: every claim is backed by a committed artifact, and
the acceptance gate explicitly fails if the encoder does not beat the FSM on real
records.

## Architecture

```
response text
   │  overlapping windows (W ≤ 510 tokens, stride 125 = 75% overlap)
   ▼
[chunk_i | chunk_i+1 | ...]  ──► DistilBERT classifier ──► P(turn) per chunk
   ▼
first chunk with P(turn) > τ   ──► crossroad index = START of that chunk
```

Detection is **post-hoc on the complete response**. `retryChat` forces
`stream:false`, so the response is already fully materialized when
`handleCrossroad` runs — no streaming detector is needed.

### Model

`distilbert-base-multilingual-cased`. **Multilingual from the start** — Chinese
turning words (然而 / 但 / 不过 / 其实 / 等等 / 话说回来) are a first-class target,
not a later migration. `distilbert-base-uncased` was rejected: it maps CJK to
`[UNK]`.

### Windowing

`max_position_embeddings = 512`, so `W ≤ 510` leaving room for `[CLS]`/`[SEP]`.
Windows overlap so a turn near a boundary still appears in ≥ 2 windows.

**Labels use a CHARACTER offset**, never a token index. A char→token→char
round-trip through `offset_mapping` accumulates divergence and misplaces the
crossroad point.

### Why chunking removes both historical failures

- **v1 length confounding:** positive and negative *chunks* are the same window
  size, so length carries zero label signal by construction.
- **v2 contradictory labels:** the label is the presence of a turn at a recorded
  character offset — a function of content, not of whole-document class identity.
- **Truncation loss:** the old approach truncated long responses at 512 tokens,
  silently dropping the turn. Sliding windows never truncate.

## Data pipeline

Peers produce **documents**; this harness derives **chunks**. Peers never choose
boundaries — that would give 20 inconsistent chunkers. Deriving chunks here is
also what makes the deconfounding automatic: a positive document's non-turn
chunks are free, on-topic, same-length negatives.

| Stage | Artefact | File |
|---|---|---|
| Peer fleet (20 mycc instances) | `corpus/inbox/<sessionId>/*.jsonl` | — |
| Import gate | `validate_corpus.py --strict` (doc level) | `validate_corpus.py` |
| Harvest real data | `corpus/harvested.jsonl` | `harvest.cjs` |
| Chunking | `corpus/chunks.jsonl` | `gen_chunks.py` + `chunking.py` |
| Chunk gate | `validate_corpus.py --level chunk` | `validate_corpus.py` |
| Training | `out/model/` | `train.py` |
| Evaluation | `evaluate.py` + bucket diagnostics | `evaluate.py` |
| Export | `out/model/model.onnx` (INT8) | `export_onnx.py` |

### Windowing: W = 128 chars, stride = 32

The turn signal is **local**, so the window only needs to *contain* a turn plus
its immediate lead-in — not the model's full positional budget. Measured turn
offset inside a sliding window is uniform (median 116 of 256), confirming there
is no positional bias to exploit.

CPU training cost is ~linear in window length (batch 16, torch 2.14+cpu, 8
threads): 0.97 s/step at seq=64, 1.80 at 128, 3.58 at 256, 7.28 at 512. **128 is
the chosen working window** (≈2× cheaper than 256, ≈4× cheaper than 512); 510
remains available for a later full-context model. `chunking.py` is the single
source of truth for both training data derivation and inference windowing.

### Measured results (real harvested data, this machine)

- Harvest: 13,592 documents (548 `crossroad-*.json` → 120 positives; 13,044
  triologue assistant messages → negatives; **1,328 negatives suppressed** by the
  anti-v2 guard).
- Chunks @128: **206,216** windows, 457 positives; 0 validator errors; pos/neg
  length averages 128 / 127 (v1 confound eliminated by construction).
- Smoke train (504 samples, 2 epochs): loss 0.693 → 0.530, val F1 0.62 → 0.66.
  Loss moving *below* ln(2)=0.693 is the direct evidence that the signal is
  learnable — the v2 failure pinned at exactly 0.693.
- ONNX export: fp32 541.4 MB → **INT8 412.3 MB**, logits `[1,2]` verified in both
  onnxruntime (Python) and onnxruntime-node; parity max|Δlogit| = 0.035; 13 ms
  inference latency in Node.

**CRITICAL export note:** torch ≥ 2.9 defaults to the new dynamo ONNX exporter,
which emits an **invalid** graph for this model (0.8 MB instead of 541 MB) and
makes `quantize_dynamic` fail with `ShapeInferenceError … (768) vs (2)`. This was
the true root cause of the historical failure, previously mis-attributed to
DistilBERT. The fix is `torch.onnx.export(..., dynamo=False, opset_version=18)`.

### Anti-leakage

`topic_id` must be **disjoint across train/val/test**. Topic reuse across splits
is precisely what produced the v2 failure; it is enforced programmatically, not
by convention.

## Precision

**INT8** dynamic quantization (~135 MB vs ~541 MB fp32).

**FP8 was rejected on evidence.** ONNX Runtime here exposes only
`CPUExecutionProvider` + `AzureExecutionProvider` (no CUDA, no TensorRT) and
surfaces no FP8 symbols. FP8 requires accelerator tensor cores (NVIDIA
Hopper/Ada/Blackwell, AMD MI300-class); this machine has an AMD Radeon 860M iGPU
and a Ryzen AI 7 PRO 350 (Zen 5, AVX-512 + VNNI). The CPU EP has no FP8 GEMM
kernels, so an FP8 graph would be dequantized (zero benefit) or fail to load.
INT8 is the CPU-correct analogue and Zen 5 VNNI is what ORT's int8 kernels
target.

Caveat: a prior attempt hit `ShapeInferenceError` from `quantize_dynamic` on
DistilBERT. **This was diagnosed during Phase 2: the cause was the exporter, not
the model** — torch ≥ 2.9's default dynamo exporter emits an invalid graph (see
"CRITICAL export note" above). With `dynamo=False` + opset 18, INT8 succeeds.
Which precision ships is still decided by measurement at the eval gate.

## Runtime contract (unchanged)

- `detectTurningWord(content): { word: string; index: number } | null` — the
  public API is preserved so `handleCrossroad` and `llm.ts` are untouched.
- `index` = char offset of the crossroad point; `word` = the turning phrase
  sliced at that offset.
- ONNX wire format: `input_ids`/`attention_mask` (int64 `[1, seq]`) →
  `logits` (float32 `[1, 2]`), index 1 = P(turn).

**Fail loud:** as a pure replacement there is no fallback, so a missing model
must emit a startup healthcheck warning rather than silently disabling the
feature.

## Acceptance gate

Evaluated on three sets, in order:

1. **Held-out synthetic** — disjoint `topic_id`.
2. **Real session records** — the 548 `crossroad-*.json` under `.mycc/sessions/`.
   Weak labels from the old regex; must be re-labelled before scoring, used as a
   diagnostic and not as gold.
3. **Harvested real negatives** — assistant messages in the 296 triologue
   transcripts with no crossroad sibling.

Required artifacts: precision/recall/F1 per set, a **length-bucket** diagnostic
and a **position-bucket** diagnostic, and a **comparison against the FSM baseline
on the same corpus**. Ship only if the encoder is not a regression. If it is, say
so and stop.
