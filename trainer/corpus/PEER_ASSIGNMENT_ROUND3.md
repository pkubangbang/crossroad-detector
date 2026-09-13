# Round 3 — targeted corpus to fix model-v3 weaknesses

You already produced round-1 (`batch.jsonl`) and round-2 (`batch_zh_long.jsonl`).
The harness reassembled, chunked, and trained **model-v3** on that corpus. This
round is **not** a redo — it is a **targeted top-up** to close measured gaps.

## Why (the measurements on model-v3)

The trained detector runs on **128-char windows**. On the held-out test set
(`out/test-report.json`, n=7318):

| metric | value | note |
|---|---|---|
| precision | 0.760 | OK |
| **recall** | **0.691** | **bottleneck — 99 false negatives (31% of turns missed)** |
| F1 | 0.723 | |

The misses are **not random**. They cluster in four places:

1. **Teaching scenario is starved.** Only **90 positive chunks** are
   `teaching` (vs 415–778 for coding/planning/debugging/analysis) and only
   **690 negative chunks**. The model barely sees teaching turns → it misses
   them at inference.
2. **interjection + self-correction are the weakest turn types.** Positive
   chunk counts: clausal-adversative 808, strong-phrase 398, hedged-return 347,
   interjection **328**, self-correction **307**. The sudden-pivot types
   ("Wait —", "Actually, no", 等等，/ 其实不对) are exactly what the detector
   must catch and exactly what it under-trains on.
3. **Mid-document turns (25–50% position) recall = 0.669** — the worst
   position bucket. A turn with substantial lead-in before it is harder than
   one near the start.
4. **Left-edge turns (turn at the very start of its 128-char window, little or
   no left context) recall ≈ 0.69** — only 113 positive chunks have the turn in
   the first 5 chars of the window.
5. **zh negatives are thin.** Only **6,374 zh negative chunks** vs 200,301 en
   negatives. zh false-positive control is under-trained in absolute volume.

## Your role this round (read carefully)

**The LLM is the teacher for the target model.** Your own semantic judgement of
what counts as a genuine **direction reversal** IS the ground-truth label that
teaches the DistilBERT detector. So author documents where the turn/no-turn
decision reflects *your reading of meaning*, not surface vocabulary. This is
the same `crossroad-corpus-farmer` workflow — the only change is the **quota is
targeted** at the gaps above instead of a uniform spread.

## The quota (each selected peer fills ONE of the role-bands below)

Each peer is assigned **one role-band** — a focused slice of the gap space.
Produce **20 documents** for your band (10 positives + 10 confusable
negatives), written as genuine assistant-style responses. Every doc is a
**whole document** (≥256 chars so it yields ≥2 full 128-char windows after
chunking; 300–600 ideal). The harness chunks; you never choose boundaries.

### Shared rules for every band

- Same 16-field schema as round 1/2 (see `schemas/corpus.schema.json`).
- `id`: `<lang>-<peer8>-<seq>` (e.g. `zh-0af261a7-0003`).
- `topic_id`: prefix with your peer8 and make every doc's topic distinct:
  `<peer8>-<topic>` (e.g. `0af261a7-recursion-vs-iteration`). **No topic_id may
  be reused by another peer** — the trainer splits train/val/test by topic.
- `first_turn_pos`: 0-based **character** offset into `text` of the FIRST
  genuine turn; `-1` for negatives.
- `turn_type`: one of the five real types for positives, **`"none"`** for
  negatives. `is_negative == !has_turn` (redundant on purpose).
- `lang`/`word_count`: the validator recomputes both — match the CJK-ratio rule.
- **Length parity is mandatory.** Keep your positives' and negatives' mean
  lengths within 20% of each other (drift ≤ 20%). Vary lengths across your 20
  docs (some ~300, some ~450, some ~600 chars). A length confound is rejected.
- **No duplicate text across classes** (the v2 failure). Each doc must differ
  in substance, not by one swapped connector.
- Positives: place the turn **in the middle** of the document (between 25% and
  75% of the text), NOT at the very start or end, so its window(s) contain real
  lead-in and follow-through. **For at least 3 of your 10 positives, start the
  turn within the first 5 characters of a natural sentence/clause boundary** so
  the chunker produces a left-edge positive window (gap #4).
- Negatives: confusable traps using the **same surface form** as the turn type
  but with no genuine reversal. Set `conjunction` to the form exercised.

### The 10 role-bands (assigned one-per-peer)

| band | focus (turn_type priority + scenario + lang) | pos spread | neg confusable focus |
|---|---|---|---|
| A | **interjection** positives, **teaching** scenario, **en** | 10 interjection pos, teaching | "wait for" / "hold on" instructions, additive "but", aside "however" |
| B | **interjection** positives, **teaching** scenario, **zh** | 10 interjection pos, teaching | 等等=etc., 等待=instruction, 其实=factual, 不过=merely |
| C | **self-correction** positives, **teaching** scenario, **en** | 10 self-correction pos, teaching | "actually" mid-sentence clarification, "that said" same-direction |
| D | **self-correction** positives, **teaching** scenario, **zh** | 10 self-correction pos, teaching | 其实 factual, 不过 merely, 第一/第二 enumeration, 然而 mid-clause |
| E | **interjection + self-correction** mix, **debugging** scenario, **en** | 5 interjection + 5 self-correction, debugging | "wait for"/"wait until" instructions, "actually" clarification |
| F | **interjection + self-correction** mix, **debugging** scenario, **zh** | 5 interjection + 5 self-correction, debugging | 等等/等待/其实 confusables, mid-clause 然/但/不过 |
| G | **mid-document strong-phrase** positives (turn at 40–70% of text), **analysis** scenario, **en** | 10 strong-phrase pos, analysis | "however" minor aside, "having said that" continuing |
| H | **mid-document strong-phrase** positives (turn at 40–70% of text), **analysis** scenario, **zh** | 10 strong-phrase pos, analysis | 然/但/不过 mid-sentence, 话虽如此 same-direction |
| I | **long zh confusable negatives**, mixed turn-type surfaces, **zh** | 0 pos, 20 neg | 20 distinct long zh negatives exercising every confusable form (wait/等待, 等=etc., 但/不过 additive, 其实 factual, 第一/第二 enum, 然 mid-clause, hedged same-direction, summary restating) |
| J | **left-edge turn positives** (turn starts a sentence near char 0 of its window), mixed scenarios, **en+zh** | 10 pos (mix turn types, turn near a sentence start so a window begins at the turn), mixed en/zh | 10 matching confusable negs at similar positions |

> Bands A–H each give 10 pos + 10 neg = 20 docs; band I gives 0 pos + 20 neg;
> band J gives 10 pos + 10 neg = 20. Total across 10 peers ≈ 190 docs
> (≈ 90 positives, ≈ 100 negatives), weighted toward the gaps.

## Peer → band assignment

| peer8 | model | band |
|---|---|---|
| 23094189 | glm-5.3-flash:cloud | A |
| 3485a258 | glm-5.3-flash:cloud | B |
| 2314d059 | glm-5.3-flash:cloud | C |
| 949727ba | glm-5.3-flash:cloud | D |
| 0af261a7 | glm-5.3-flash:cloud | E |
| f9851472 | deepseek-v4-flash:cloud | F |
| 1bca1b4c | deepseek-v4-flash:cloud | G |
| b8867fde | deepseek-v4-flash:cloud | H |
| 248051be | deepseek-v4-flash:cloud | I |
| 437b47c6 | deepseek-v4-flash:cloud | J |

## Where to write

Write to the EXACT path (create dirs as needed), UTF-8, no BOM, one JSON per
line:

```
C:\Proj\mycc\machine-learning\crossroad-trainer\corpus\inbox\<YOUR-SESSION-ID>\batch_round3.jsonl
```

Use your **full** session-id for the directory name (same dir as your round-1/2
files). Do NOT overwrite your earlier batches — write a new `batch_round3.jsonl`.

## Validate before submitting

```
cd C:\Proj\mycc\machine-learning\crossroad-trainer
.venv\Scripts\python.exe validate_corpus.py "corpus\inbox\<YOUR-SESSION-ID>\batch_round3.jsonl"
```

(Use non-`--strict` for a single-band file — `--strict` requires both langs and
all scenarios, which a single-band shard will not satisfy by design. The harness
validates the merged directory under `--strict` after reassembly.) Target
**errors: 0, warnings: 0** on the doc-level checks (schema, v1 length parity,
v2 no cross-class duplicate text, offset in-range).

## Report

Reply to the lead via `mail_to(name="lead", title="round3-done: <your-8char>")`
with: session, path, band, n_pos, n_neg, min_chars, validator summary. Do NOT
paste the batch into mail.

## After all 10 report

The lead reassembles all round-3 batches into the corpus (superseding nothing —
round 3 is additive), re-chunks, re-balances, and **retrains from the
distilbert-base-multilingual-cased checkpoint** (warm-starting from model-v3 is
optional and will be decided after seeing the new chunk counts). The goal:
lift test **recall toward 0.80+** while keeping precision ≥ 0.75, especially on
teaching/interjection/self-correction and mid-document turns.