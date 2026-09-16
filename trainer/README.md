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
| Chunk @128 (`gen_chunks.py`, v1 era) | 206,216 windows, 457 positives |
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

## Retraining workflow

The chunker is the only thing that changed for v1.3. To retrain from the R4 corpus:

```powershell
# 1. (re)generate v3 chunks from the balanced corpus
trainer/.venv/Scripts/python.exe trainer/chunker_v3.py `
    --in trainer/corpus/r4.balanced.jsonl `
    --out trainer/corpus/r4.balanced.chunks.v3.jsonl `
    --report trainer/corpus/r4.balanced.chunks.v3.stats.json --seed 42

# 2. (optional) prove the doc/topic split is leak-free
trainer/.venv/Scripts/python.exe trainer/check_doc_leak.py --chunks trainer/corpus/r4.balanced.chunks.v3.jsonl

# 3. train on the GPU (ROCm env; --max-len 448 == TWO_X)
$py = "C:\Users\admin\miniconda3\envs\crossroad-rocm\python.exe"
& $py trainer/train.py --chunks trainer/corpus/r4.balanced.chunks.v3.jsonl `
    --out trainer/out/r4-v3-model --epochs 3 --batch 16 --max-len 448 --lr 3e-5 --seed 42

# 4. export INT8 ONNX (fixed seq 448)
& $py trainer/export_onnx.py --model trainer/out/r4-v3-model --out trainer/out/r4-v3-model.onnx --seq 448

# 5. score the TEST split (ONNX INT8, the shipped artifact)
& $py trainer/eval_test_onnx.py --chunks trainer/corpus/r4.balanced.chunks.v3.jsonl `
    --onnx trainer/out/r4-v3-model.onnx --tokenizer trainer/out/r4-v3-model `
    --report trainer/out/test-report-r4-v3-onnx.json --max-len 448
```

### v1.3 measured results (v3 chunks, seed 42)

Trained on the R4 corpus (7,069 chunks: 868 pos / 6,201 neg, class weight 6.98),
ROCm GPU, 3 epochs. Val F1 **0.9266**. Test split (n=1161, 134 pos), INT8 ONNX:

| artifact | en F1 | zh F1 | ALL F1 |
|---|---|---|---|
| v8 INT8 (v2 chunks) | 0.8409 | 0.9167 | 0.8629 |
| **v1.3 INT8** (v3 chunks) | **0.8913** | 0.8767 | **0.8872** |

Like-for-like on the identical split, v3 chunking buys **+0.024 overall** and
**+0.050 English** F1; Chinese is within noise (n=36). The English gain is the
overlap working as designed — English turns were the ones landing on window
boundaries under v2's non-overlapping tiling.

## The pipeline

```
peer fleet (20 mycc instances)  +   .mycc/sessions (real data)
        │  generate / harvest document-level samples
        ▼
trainer/corpus/inbox/<sessionId>/*.jsonl
   (harvest.cjs → corpus/harvested.jsonl)
        │  validate_corpus.py            (doc-level gate)
        │  chunker_v3.py                 (deterministic OVERLAPPING chunking)
        │  validate_corpus.py --level chunk   (chunk-level gate)
        ▼
   chunk-level training data (corpus/r4.balanced.chunks.v3.jsonl)
        │  train.py — fine-tune distilbert-base-multilingual-cased
        ▼
      checkpoint ──► export_onnx.py (fp32 + INT8) ──► model/model.onnx
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
cd trainer

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

### Windowing: chunker v3 (segment-level adaptive overlap)

`max_position_embeddings = 512` is the **hard ceiling**, but it is not the right
working size. The turn signal is **local**: the classifier asks "is a reversal
happening around this point?", so the window only needs to contain the turn plus
its immediate lead-in.

The active chunker is **v3** (`chunker_v3.py`) — a segment-level adaptive
**overlapping** sliding window. It supersedes v2 (`chunker_v2.py`, a
non-overlapping tile-by-cap) and v1 (`chunking.py`, fixed 128/32 char windows).
Both old chunkers are kept in-tree but are no longer used.

The core principle: **windows overlap**, so a turn near a boundary appears in
≥2 windows and is seen from more than one offset — the property v2 lost.

| Parameter | Value | Meaning |
|---|---|---|
| `X` = `SEG_MAX` | 224 | max chars per segment (`2X ≈ 454 tok < 512`) |
| `TWO_X` | 448 | window target upper bound (chunk "cap") |
| `THREE_X` | 672 | buffer expansion cap during suffix growth |
| `--max-len` (train) | 448 | must equal `TWO_X` |

Segment construction (shared with v2): split into sub-sentences by punctuation
(`.!?,;:\n` + CJK `。！？，；：`, delimiter attached), then hard-cap each at 224
chars. On those segments the v3 window slides: expand the suffix to ≤ `THREE_X`,
shrink the prefix to the FIRST span < `TWO_X` (minimal drop = maximal overlap),
emit. See `chunker_v3.md` for the full spec and rationale.

R4 corpus effect: **5,823 → 7,069 chunks** (v2 → v3), **794 → 868** positive
chunks (+27% / +36%) — the quantification of "a boundary turn appears in ≥2
windows". Positive/negative lengths stay matched (298.9 / 339.4 chars), so
length carries no label signal.

**Code-point offsets.** Labels are derived from a **character offset**
(`first_turn_pos`), never from token indices. All chunk offsets are **Python
code-point** offsets; the serving port (`src/chunker.ts`) must reproduce them
exactly (see "Serving parity" in the root README) — JS `String` indexes UTF-16
units, so an astral char would misalign every later window if the port used
`String.prototype.slice`.

### Current model: v1.3 (npm v0.1.3, release asset `model.onnx`)

Model versions track the npm release. **v1.3** ships with npm **v0.1.3**; it is
published as the GitHub Release asset **`model.onnx`** and pinned in
`model/model.lock.json` (`tag: "v0.1.3"`, `modelVersion: "v1.3"`). It is trained
on the v3 chunks.

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
crossroad-detector/trainer/
  README.md                  this file
  requirements.txt           pinned Python deps
  schemas/corpus.schema.json the contract handed to the peer fleet
  chunker_v3.py              THE chunker (segment adaptive overlap) — active
  chunker_v2.py              superseded tile-by-cap chunker (segment lattice reused)
  chunking.py                superseded fixed 128/32 window chunker (v1)
  chunker_v3.md              v3 design spec + rationale
  check_doc_leak.py          doc/topic-level split-leak proof
  dump_v3_spans.py           emit v3 spans for TS parity (scripts/check_v3_parity.mjs)
  gen_chunks.py              derive labelled chunks from documents (legacy driver)
  validate_corpus.py         doc-level AND chunk-level gate (--level chunk)
  train.py                   fine-tune distilbert-base-multilingual-cased
  evaluate.py                metrics + length/position bucket diagnostics
  export_onnx.py             fp32 + INT8 ONNX export with parity check
  harvest.cjs                harvest real data from .mycc/sessions
  corpus/                    GITIGNORED — peer batches + harvested real data
    inbox/<sessionId>/       peers write their batches here
  out/                       GITIGNORED — checkpoints, ONNX artifacts
```

The **harness is tracked; artifacts are not.** The deployed model is
`model/model.onnx` at the repo root (fetched from the GitHub Release via
`npm run fetch-model`, verified against `model/model.lock.json`), the path
`src/server.ts` reads.

## Runtime contract (must not change)

The TS loader depends on this exact ONNX wire format:

- **Inputs:** `input_ids` (int64, `[1, seq]`), `attention_mask` (int64, `[1, seq]`)
- **Output:** `logits` (float32, `[1, 2]`) — index 0 = P(no turn), index 1 = P(turn)
