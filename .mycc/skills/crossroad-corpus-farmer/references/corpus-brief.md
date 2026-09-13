# Crossroad corpus — generation brief

You are producing training data for a **semantic** crossroad detector: a model
that reads meaning and decides whether a response *changes its mind* mid-way.

## The core idea: what counts as a turn

A turn is a **genuine direction reversal**. The response commits to a position
and then, in its own voice, pivots to contradict or abandon it.

**Positive (a turn exists):**
> Let me refactor the login path in place — it is the smallest change and the
> risk is contained. **However**, tracing the call sites I now think the session
> store is the real problem, so patching login would just hide it. We should fix
> the store first.

The first sentence commits to direction A. The second abandons A for B. The
speaker changes their mind. `first_turn_pos` points at the `H` of "However".

**Negative (no turn):**
> The refactoring approach is cleaner but it requires more upfront work. We
> should weigh the tradeoffs before deciding.

"But" here joins two halves of **one** balanced assessment. Nothing is
reversed. This is the most common false positive — get it right.

**Also negative (no turn):**
> First we need to compile the project. Wait for the build to complete before
> running the tests.

"Wait for" is an instruction, not a change of mind.

## The five turn types

| turn_type | marker | EN example | ZH example |
|---|---|---|---|
| `strong-phrase` | explicit reversal phrase | "However,", "Having said that,", "On the other hand," | 然而，/ 话说回来， |
| `interjection` | a sudden exclamation cutting in | "Wait —", "Hold on," | 等等，/ 等一下， |
| `clausal-adversative` | a bare adversative at a clause/sentence start | "But ...", "Yet ..." | 但…/ 不过… |
| `self-correction` | revising one's own claim | "Actually,", "I realize now that ..." | 其实， |
| `hedged-return` | partial retreat then return to the original | "That said," | 话虽如此， |

## Mandatory confusable negatives

For each turn type, produce **negatives that use the same surface form** but do
not reverse. These are what teach the model semantics rather than vocabulary.
Record which one you used in the `conjunction` field.

| Surface form | Negative usage (NO turn) |
|---|---|
| however / but / yet | mid-sentence or joining two halves of one balanced argument |
| wait | "wait for", "wait until", "wait to" — an instruction |
| actually | a mid-sentence clarification ("the function is actually quite simple") |
| 然而 / 但 / 不过 / 其实 | mid-sentence conjunction inside one clause |
| 等等 | as "etc." — a list terminator, never followed by a comma |
| that said / having said that | used while *continuing* the same direction |

## Length and balance rules

- **Mix lengths deliberately** across your batch — short (30–100 words),
  medium (100–300), long (300–1000). Do not make every sample the same size.
- **Keep positives and negatives the same average length.** This is a hard
  requirement. If your negatives average 20 words and your positives average 60,
  the batch is rejected for length confounding and the model learns the wrong
  signal entirely.
- Aim for a **50/50 positive/negative split** overall.

## Language rules

- `lang` = `"zh"` when the CJK character ratio (ignoring whitespace) is ≥ 0.5,
  otherwise `"en"`. The validator recomputes this — do not guess.
- `word_count`: for `en` it is the whitespace-separated token count; for `zh` it
  is the non-whitespace character count. The validator recomputes both `lang`
  and `word_count`, so a mismatch is an error.
- Write natural text in the target language. Do not translate word-for-word.

## Record format

One JSON object per line. See `schemas/corpus.schema.json` for the full
definition. Example:

```json
{"id":"en-p07-0001","text":"Let me refactor the login path in place since it is the smallest change. However, tracing the call sites I now think the session store is the real problem, so we should fix that first.","has_turn":true,"first_turn_pos":83,"scenario":"coding","turn_type":"strong-phrase","is_negative":false,"lang":"en","word_count":37,"topic_id":"p07-login-session-store","conjunction":null,"source_model":"deepseek-v4-flash:cloud","peer_session":"<yourSessionId>","provenance":"generated","verified_by":[],"verdict":"pending"}
```

## Verification (when asked to check a peer's batch)

You will be given another peer's batch, produced by a **different model** than
yours. For each sample answer three questions:

1. **Schema** — does the record satisfy the contract? (the validator covers this;
   spot-check only)
2. **Semantics** — if `has_turn=true`, is there a genuine reversal, and does
   `first_turn_pos` point at it? If `has_turn=false`, is it genuinely free of a
   reversal?
3. **Novelty** — is it a near-duplicate of an earlier sample, or a template with
   a swapped noun?

Report per sample: `approve`, or `reject` with a one-line reason. Disagreements
go to a second verifier. Your job is to reject bad data, not to be agreeable —
a wrongly approved sample silently degrades the trained model.

