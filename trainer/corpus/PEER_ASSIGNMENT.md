# Crossroad corpus — peer assignment (READ THIS FIRST)

You are one of **20 peer instances** producing training data for a
**chunk-based DistilBERT "crossroad" detector** that mycc uses to decide when an
assistant has *turned* (reversed direction) mid-response. Your OUTPUT is a
JSONL file of **document-level** samples. Do NOT chunk — the harness chunks.

## Where to write

Write your batch to this EXACT absolute path (create dirs as needed):

```
C:\Proj\mycc\tools\crossroad-trainer\corpus\inbox\<YOUR-SESSION-ID>\batch.jsonl
```

Replace `<YOUR-SESSION-ID>` with your own session-id (you were told it in the
mail). One JSON object per line. UTF-8, **no BOM**.

## The exact schema (every field required)

```json
{
  "id": "zh-<your-session-8>-0001",
  "text": "<the full response text, >= 40 chars>",
  "has_turn": true,
  "first_turn_pos": 123,
  "scenario": "coding",
  "turn_type": "clausal-adversative",
  "is_negative": false,
  "lang": "zh",
  "word_count": 55,
  "topic_id": "auth-oauth-saml",
  "source_model": "<your model name>",
  "peer_session": "<your full session-id>",
  "provenance": "generated",
  "conjunction": null,
  "verified_by": [],
  "verdict": "pending"
}
```

Field rules (the harness VALIDATES these mechanically; a violation rejects the
batch):

- `has_turn`: true iff `text` contains a genuine semantic **direction reversal**.
- `first_turn_pos`: **CHARACTER offset** (0-based) into `text` of the FIRST
  genuine turning point. `-1` when `has_turn=false`. Must satisfy
  `0 <= first_turn_pos < len(text)` when true. Never a token index.
- `is_negative` MUST equal `!has_turn` (redundant on purpose).
- `turn_type`: one of `strong-phrase`, `interjection`, `clausal-adversative`,
  `self-correction`, `hedged-return`; **must be `"none"` when `has_turn=false`**.
- `scenario`: one of `coding`, `planning`, `debugging`, `analysis`, `teaching`.
- `lang`: `"zh"` if the CJK-char ratio (ignoring whitespace) is >= 0.5, else `"en"`.
- `word_count`: EN = whitespace-separated tokens; ZH = non-whitespace char count.
  **The validator recomputes this and rejects a mismatch.**
- `topic_id`: identifies the topic/template family. **Each distinct topic needs
  a distinct id.** Explainers below.
- `conjunction`: for negatives, the confusable surface form you are exercising
  (e.g. `"wait for"`, `"等等"`) or `null`.

## THE TWO FAILURES YOU MUST AVOID (this is the whole point)

Two prior attempts failed on **data**, not model capacity. Your batch is
rejected if it reproduces either.

**v1 — length confounding.** If all your positives are long and all your
negatives are short, the model learns "long ⇒ turn". So:

> **Every positive and every negative must come from the same length
> distribution.** A 2-sentence positive needs a 2-sentence negative on a
> similar topic. Do not make all positives long paragraphs.

**v2 — contradictory labels.** If the same (or near-identical) text appears once
as a positive and once as a negative, the loss pins at `ln(2)=0.693` and the
model learns nothing. So:

> **Never emit the same text with both labels.** If you reuse a sentence bank,
> the positive and negative variants must differ in SUBSTANCE, not just one
> connector word. Prefer wholly distinct texts.

## What a "turn" is (the positive class)

A turn = the response **changes direction**: it concedes, retracts, corrects
itself, or pivots to an opposing conclusion. Five types:

| turn_type | what it looks like (EN / ZH) |
|---|---|
| `strong-phrase` | "Actually, no." / "其实不对。" / "On second thought…" / "等等。" |
| `interjection` | "Wait —" / "等等，" / "Hold on," / "不过，" |
| `clausal-adversative` | "That works, but it breaks X." / "这样可以，但会破坏 X。" |
| `self-correction` | "I said read it synchronously — that's wrong, it must be async." / "我刚才说同步读，其实错了，必须异步。" |
| `hedged-return` | "That seems fine… then again, it doesn't." / "看起来没问题……不过想想也不对。" |

**The turn must be SEMANTIC, not merely lexical.** Just containing the word
"but" is not a turn. `"I like tea but coffee is fine too"` is NOT a turn (no
reversal of direction). `"I like tea — but honestly coffee is better"` IS.

## Negatives: confusable traps (this is the HARD part — most of your budget)

Negatives are responses that **look like** they might turn but do NOT. Generate
these deliberately, using the exact confusable forms:

- `"wait for"` / `"等待"` — e.g. "We must wait for the lock." (NOT a turn)
- `"but"` used additively — "It's fast but also cheap." (NOT a reversal)
- `"however"` listing a minor aside — "However, there is also a Python version." (NOT a reversal)
- `"等"` meaning "etc." — "水果、蔬菜等" (NOT "wait")
- `"不过"` as "merely" — "这不过是个小问题。" (NOT "however")
- `"其实"` stating a fact with no reversal — "其实是这样的。" (NOT a turn)
- `"first/second"` enumerations that never reverse
- hedged phrasing that stays on one side throughout
- a summary that restates the SAME direction

Set `conjunction` to the form you exercised so the gate can verify coverage.

## Language requirement

Produce **both English and Chinese**. Target roughly **40% zh / 60% en**.
Chinese turning words (然而 / 但 / 不过 / 其实 / 等等 / 话说回来) are first-class.

## Your quota and how to produce it

Produce **at least 60 documents** (aim 60-80): roughly **20 positives**
(spread across the 5 turn types) and **40-50 negatives** (mostly confusable
traps). Mixed EN/ZH, mixed scenarios, mixed lengths.

Generate the text yourself (you are an LLM — write plausible assistant-style
responses). Do not copy from mycc source. Each `topic_id` should be unique per
distinct topic; do not reuse one topic_id across many unrelated docs.

## Self-check BEFORE you finish (the harness runs the same checks)

1. Every line parses as JSON; all required fields present.
2. `is_negative == !has_turn`; `turn_type=="none"` iff `has_turn==false`.
3. `first_turn_pos` is `-1` for negatives, in-range for positives.
4. `word_count` matches the rule above (recount it).
5. `lang` matches the CJK-ratio rule.
6. **No duplicate `text` across classes.**
7. **Positive and negative length distributions are similar** (don't make all
   positives long).

If `C:\Proj\mycc\tools\crossroad-trainer\.venv\Scripts\python.exe` exists you
can run the real gate on your own file:

```
C:\Proj\mycc\tools\crossroad-trainer\.venv\Scripts\python.exe ^
  C:\Proj\mycc\tools\crossroad-trainer\validate_corpus.py ^
  C:\Proj\mycc\tools\crossroad-trainer\corpus\inbox\<YOUR-SESSION-ID>\batch.jsonl
```

Fix every ERROR before reporting done.

## When done

Reply to the lead with `mail_to(name="97a6d678-8f39-4ebb-b1cd-5ea9021d8992/lead",
title="corpus-done: <your-session-8>", ...)` containing: your session-id, the
absolute path you wrote, and the counts (pos/neg, en/zh). Do NOT paste the whole
batch into mail.

## Cross-check phase (the lead will mail you a follow-up)

After you submit, you will receive a `cross-check` mail naming another peer's
batch path. Read it, verify: schema validity, that labels are semantically
correct (spot-check ~15 lines), no cross-class duplicates, and length parity.
Reply `approve` or `reject` with specific line numbers for any rejection.
