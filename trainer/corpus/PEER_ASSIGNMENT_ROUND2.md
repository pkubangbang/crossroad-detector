# Round 2 — zh documents must be LONG (>= 256 chars)

Your round-1 batch passed the doc-level gate. Thank you. One measured issue
remains and it is a REAL one, so this round is required.

## Why (the measurement)

The detector runs on **character windows of WINDOW=128** (stride 32). At real
inference time the assistant's output is long: **96% of real crossroad
positives are >= 128 characters** (median 953 chars). So the model is almost
always fed a **FULL 128-char window**.

Your zh documents averaged only ~70 characters. A document shorter than 128
chars yields a single PARTIAL window — and because your zh positives are short
documents, at chunk level the class correlates with window length. That is the
v1 confound in disguise. We measured it: only **19 zh positives** out of 243
currently reach full-window length = not trainable for Chinese.

## Your task this round

Produce a SECOND file: zh documents that are **>= 256 characters each** (so each
document yields at least two full 128-char windows after chunking).

- Write to: `C:\Proj\mycc\tools\crossroad-trainer\corpus\inbox\<YOUR-SESSION-ID>\batch_zh_long.jsonl`
- Aim for **>= 24 zh documents**: **>= 10 positives** and **>= 14 confusable negatives**.
- Each `text` MUST be **>= 256 chars** (verify: `len(text) >= 256`). Longer is fine (300-600 is ideal).
- Keep the SAME 16-field schema and the SAME rules as round 1 (is_negative==!has_turn,
  turn_type "none" iff negative, first_turn_pos = 0-based CHARACTER offset,
  no cross-class duplicate text, UTF-8 no BOM).
- Positives: the turn must sit somewhere in the MIDDLE of the long text (not at
  the very start/end), so its window(s) contain real lead-in and follow-through.
  Spread the 5 turn types (strong-phrase / interjection / clausal-adversative /
  self-correction / hedged-return).
- Negatives: confusable traps (wait for / 等待, additive 但/but, aside 不过/however,
  等=etc., 其实=factual, 第一/第二 enumeration, same-direction hedges, summaries).
- Length parity still matters: keep zh pos and neg MEAN lengths within 20% of
  each other, and avoid a bucket where one class is ~all and the other ~none.

## Validate before submitting

Run the validator on the new file (it must be UTF-8 no BOM, one JSON object per line):

```
C:\Proj\mycc\tools\crossroad-trainer\.venv\Scripts\python.exe C:\Proj\mycc\tools\crossroad-trainer\validate_corpus.py --strict <your batch_zh_long.jsonl>
```

Target: `errors: 0   warnings: 0`. The `--strict` mode still enforces the doc
length-parity rule; since ALL your zh docs are now long, parity should hold
easily. If the validator flags a bucket skew, adjust lengths of a few rows.

## Report

Reply to the lead when done:
`mail_to(name="97a6d678-8f39-4ebb-b1cd-5ea9021d8992/lead", ...)`
title: `zh-long-done: <your-8char>`
body: session=..., path=..., n_zh=..., pos=..., neg=..., min_chars=..., validator result.

NOTE: if write_file/read_file are denied for the out-of-workspace inbox path,
fall back to bash (`Set-Content`/`Out-File` with `-Encoding utf8NoBOM`).
