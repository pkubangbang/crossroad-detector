# crossroad-trainer

Training harness for mycc's **chunk-based crossroad detector** — a DistilBERT
encoder that replaces the punctuation-sensitive FSM detector with a semantic
turn detector.

> **Status:** Phases 0–2 complete and **proven end-to-end on real data**:
> harvest → chunk → validate → train → INT8 ONNX export, verified in both
> onnxruntime (Python) and onnxruntime-node. See "Measured results" below.

## Why this exists

The previous detector (`src/loop/crossroad-fsm.ts`) is a deterministic lexicon
matcher over connective words. It is sensitive to **punctuation placement**, not
to **meaning** — a genuine semantic pivot phrased outside its lexicon is
invisible to it. This harness trains a classifier that reads meaning instead.

## Measured results (real harvested data, this machine)

| Stage | Result |
|---|---|
| Harvest (`harvest.cjs`) | 13,592 docs (548 crossroad files → 120 pos; 13,044 triologue negs; **1,328 negs suppressed** by the anti-v2 guard) |
| Chunk @128 (`gen_chunks.py`) | 206,216 windows, 457 positives |
| Chunk gate | **0 errors**; pos/neg length avgs 128 / 127 |
| Smoke train | loss 0.693 → 0.530, val F1 0.62 → 0.66 |
| ONNX export | fp32 541.4 MB → **INT8 412.3 MB**; logits `[1,2]`; parity max\|Δlogit\| = **0.035** |
| Node runtime | loads in onnxruntime-node, 13 ms latency |

## Peer-fleet generated corpus (Phase 3, 20 instances)

Real harvested positives are scarce (120 docs). A fleet of **20 headless mycc
peers** generated a complementary corpus in two rounds:

| Round | What peers produced | Gate |
|---|---|---|
| 1 | 1,470 docs (48 en/zh mix, 5 turn types, confusable negatives) | doc-level strict 0/0 (all 20/20 after 2 rounds of targeted length-bucket feedback) |
| 2 | zh docs **>=256 chars** each (`batch_zh_long.jsonl`), ~26-38/peer | doc-level strict 0/0; each yields >=2 full 128-char windows |

**Round 2 supersedes round-1 zh.** Measured: round-1 zh docs averaged ~50 chars
(the detector window is 128), so they produced only PARTIAL windows — a
provenance-shaped length confound (only 19/243 zh positives reached full-window
length). Round 2 regenerated zh at >=256 chars. Pooling both zh regimes
re-creates a within-zh confound (dir-level zh posAvg 175 vs negAvg 135 = 23%),
so the merger (`reassemble.py --supersede-zh`) keeps **round-1 EN + round-2 ZH**
and DROPS round-1 zh. Result: zh full-window positives **19 → 901**, chunk-level
zh drift **34% → 2.4%** (see below).

`validate_corpus.py --strict` on a single-language shard ALWAYS errors
`coverage: lang 'en' has zero samples` — that fleet-level invariant is
structural; gate language slices at directory / merged-corpus level.

### Final corpus (peer-fleet + harvested)

| Stage | Result |
|---|---|
| `reassemble.py --supersede-zh` | 1,393 generated docs (798 en / 595 zh); doc gate 0/0 |
| pool with harvested (`combined.jsonl`) | 14,361 docs, 638 pos, 0 id/topic collisions |
| `gen_chunks.py` | 208,863 chunks (2,188 pos / 206,675 neg = 1:94) — CPU-infeasible |
| `balance_chunks.py --neg-keep-frac 0.15` | **42,185 chunks (2,188 pos / 39,997 neg = 1:18.3)**, class weight 17.9 |
| chunk gate | **0 errors / 0 warnings**; en 127/127, zh 128/125 chars (length confound eliminated) |

Negative downsampling is done at **document** level (keep every positive doc,
sample 15% of all-negative mined docs, re-chunk) — never at window level, so the
length deconfound survives intact.


Loss moving **below** `ln(2)=0.693` is the direct evidence the signal is
learnable — the v2 failure pinned at exactly 0.693.

## The pipeline

```
peer fleet (20 mycc instances)  +   .mycc/sessions (real data)
        │  generate / harvest document-level samples
        ▼
machine-learning/crossroad-trainer/corpus/inbox/<sessionId>/*.jsonl
   (harvest.cjs → corpus/harvested.jsonl)
        │  validate_corpus.py            (doc-level gate)
        │  gen_chunks.py + chunking.py   (deterministic overlapping chunking)
        │  validate_corpus.py --level chunk   (chunk-level gate)
        ▼
   chunk-level training data (corpus/chunks.jsonl)
        │  train.py — fine-tune distilbert-base-multilingual-cased
        ▼
      checkpoint ──► export_onnx.py (fp32 + INT8) ──► ~/.mycc-store/crossroad-model/
        │
        └──► evaluate.py — held-out + real-corpus diagnostics
```

Peers produce **documents**; this harness derives **chunks**. Peers are never
asked to choose chunk boundaries — that would give 20 inconsistent chunkers.
Deriving chunks here is also what makes the deconfounding automatic (see below).

## Setup

The project's ambient Python is the **Microsoft Store (MSIX) Python**, which
cannot host native ML extensions (`import torch` fails with
`DLL load failed while importing _C`). A dedicated venv fixes this — the
resolved `torch` lives under `.venv/`, outside the MSIX sandbox.

```bash
cd machine-learning/crossroad-trainer

# 1. Create the venv
python -m venv .venv

# 2. CPU-only torch FIRST (must use the CPU index — see requirements.txt)
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu

# 3. The rest
.venv/Scripts/python.exe -m pip install -r requirements.txt

# 4. Gate — must print a version
.venv/Scripts/python.exe -c "import torch; print(torch.__version__)"
```

On Unix, substitute `.venv/Scripts/python.exe` with `.venv/bin/python`.

## Model

`distilbert-base-multilingual-cased` — **multilingual from the start**. Chinese
turning words (`然而` / `但` / `不过` / `其实` / `等等` / `话说回来`) are a
first-class target, not a later migration. `distilbert-base-uncased` was
rejected because it maps CJK to `[UNK]`.

### Windowing: W = 128 chars, stride = 32

`max_position_embeddings = 512` is the **hard ceiling**, but it is not the right
working size. The turn signal is **local**: the classifier asks "is a reversal
happening around this point?", so the window only needs to contain the turn plus
its immediate lead-in. `WINDOW`/`STRIDE` live in `chunking.py`, the single source
of truth for both training-data derivation and inference windowing.

CPU training cost is ~linear in window length (batch 16, torch 2.14+cpu, 8
threads): **0.97 s/step at seq=64, 1.80 at 128, 3.58 at 256, 7.28 at 512.**
torch already uses 8 threads and 16 is no faster, so window length (not thread
count) is the lever. 128 is chosen; 510 remains available via `--window 510`.

| Parameter | Value |
|---|---|
| `WINDOW` (chars) | 128 |
| `STRIDE` (chars) | 32 (75% overlap) |
| `--max-len` (train) | 128 (must equal `WINDOW`) |

Labels are derived from a **character offset** (`first_turn_pos`), never from
token indices — a char→token→char round-trip through `offset_mapping`
accumulates divergence and misplaces the crossroad point.

## Precision: INT8, not FP8

We ship **INT8** dynamic quantization (541.4 MB → 412.3 MB).

**FP8 is not viable on this machine** and was rejected on evidence:

- ONNX Runtime exposes only `CPUExecutionProvider` + `AzureExecutionProvider`
  (no CUDA, no TensorRT) and surfaces no FP8 symbols.
- FP8 requires accelerator tensor cores (NVIDIA Hopper/Ada/Blackwell, AMD
  MI300-class). This machine has an AMD Radeon 860M iGPU and a Ryzen AI 7
  PRO 350 (Zen 5, AVX-512 + VNNI).
- The CPU EP has no FP8 GEMM kernels, so an FP8 graph would be dequantized
  (zero benefit) or fail to load. INT8 is the CPU-correct analogue, and Zen 5
  VNNI is exactly what ORT's int8 MatMul kernels target.

### The `ShapeInferenceError` — solved, and it was never DistilBERT

A prior attempt hit `ShapeInferenceError` from `quantize_dynamic` on DistilBERT,
and it was attributed to the model. **That attribution was wrong.** Since PyTorch
2.9 the *default* ONNX exporter is the new dynamo path, which emits
`LayerNormalization` (an opset-18 op). Requesting a lower opset triggers a lossy
down-conversion that fails and leaves an **invalid graph** — visible as a tiny
0.8 MB file instead of 541 MB. `quantize_dynamic` then fails shape inference
(`dim 0: (768) vs (2)`).

**Fix:** `torch.onnx.export(..., dynamo=False, opset_version=18)` — the legacy
TorchScript exporter. INT8 then succeeds, parity max|Δlogit| = 0.035.
**File size far below the expected weight size is the tell.**

Quantization here is about **load time and distribution size**, not throughput:
inference is a few dozen calls per response while the LLM call dominates by
orders of magnitude.

## Avoiding the two historical failures

Both are recorded in the `pitfall` wiki domain and are designed out here.

**v1 — length confounding.** All negatives were <100 chars and all positives
>100 chars, so the model learned "long ⇒ turn" and scored near-random on
held-out data (acc 0.466). *Fix:* positive and negative **chunks** are the same
window size, so length carries zero label signal. Verified by a length-bucket
diagnostic that is a required build artifact.

**v2 — identical texts, contradictory labels.** Both classes were built from the
same sentence banks differing by one connector word; loss stuck at
`ln(2)=0.693`. *Fix:* labels come from the presence of a turn at a recorded
character offset, never from whole-document class identity. Template reuse is
blocked by requiring **disjoint `topic_id` sets across train/val/test**. The
harvester additionally suppresses any triologue message whose text matches a
same-session harvested positive — this caught **1,328 real contradictions**
(10% of negatives) that would otherwise have reproduced v2.

## Layout

```
machine-learning/crossroad-trainer/
  README.md                  this file
  requirements.txt           pinned Python deps
  schemas/corpus.schema.json the contract handed to the peer fleet
  chunking.py                THE chunker (shared by train-data + inference)
  test_chunking.py           chunker self-test (python test_chunking.py)
  gen_chunks.py              derive labelled chunks from documents
  validate_corpus.py         doc-level AND chunk-level gate (--level chunk)
  train.py                   fine-tune distilbert-base-multilingual-cased
  evaluate.py                metrics + length/position bucket diagnostics
  export_onnx.py             fp32 + INT8 ONNX export with parity check
  harvest.cjs                harvest real data from .mycc/sessions
  corpus/                    GITIGNORED — peer batches + harvested real data
    inbox/<sessionId>/       peers write their batches here
  out/                       GITIGNORED — checkpoints, ONNX artifacts
```

The **harness is tracked; artifacts are not.** The deployed model lives at
`~/.mycc-store/crossroad-model/`, the path `src/loop/crossroad-encoder.ts`
already reads.

## Runtime contract (must not change)

The TS loader depends on this exact ONNX wire format:

- **Inputs:** `input_ids` (int64, `[1, seq]`), `attention_mask` (int64, `[1, seq]`)
- **Output:** `logits` (float32, `[1, 2]`) — index 0 = P(no turn), index 1 = P(turn)
