---
name: crossroad-corpus-farmer
keywords:
  - crossroad
  - corpus
  - training-data
  - data-generation
  - turning-word
  - dataset
description: >
  Generate a shard of training data for mycc's semantic crossroad detector — the
  model that detects when an LLM changes direction mid-response. Use when you are
  assigned a corpus quota (a table of scenario x turn_type x lang x class counts),
  or asked to verify another peer's corpus batch. Covers producing document-level
  JSONL samples with correct character offsets, the five turn types, mandatory
  confusable negatives, length-balance and topic_id disjointness rules, self-
  validation with validate_corpus.py, writing batches to the shared inbox, and
  cross-model cross-checking of a peer's batch.
---

# crossroad-corpus-farmer

You are producing labelled training data for a **semantic** crossroad detector:
a classifier that decides whether a response genuinely **changes its mind**
part-way through. This replaces a punctuation-sensitive lexicon matcher, so the
data must teach *meaning*, not vocabulary.

> **This is a progressive-disclosure skill.** Read the referenced files when you
> reach the relevant step — do not act from the backbone alone.
>
> - `references/corpus-brief.md` — what a turn IS, the five turn types, the
>   mandatory confusable negatives, and the length/language rules. **Read this
>   before generating anything.**
> - `references/job-assignment.md` — how to read your quota, the hard rules, the
>   submission workflow, and what not to do.

## The task in one paragraph

You are mailed a shard: a table of quotas like
`coding | strong-phrase | en | pos | 5`. For each row you write that many
samples as one JSON object per line (JSONL). You write whole **documents** with a
correct `first_turn_pos` character offset — you do NOT choose chunk boundaries;
the trainer derives overlapping chunks itself. When your quota is filled, you
self-validate, write the batch to your inbox, and mail the lead.

## Method

1. **Read `references/corpus-brief.md`** — the definition of a turn, the five
   turn types, and the confusable-negative table. This is the part that
   determines whether the data is useful.
2. **Read `references/job-assignment.md`** — your quota, the hard rules
   (disjoint `topic_id`s, length balance, character offsets), and the exact
   submission path.
3. Generate your samples using your own LLM, covering every quota row.
4. **Self-validate — this is not optional:**
   ```
   cd C:\Proj\crossroad-detector\trainer
   .venv/Scripts/python.exe validate_corpus.py "corpus/inbox/<yourSessionId>" --strict
   ```
   Fix every ERROR and re-run until it exits clean. The validator independently
   recomputes `lang` and `word_count`, detects identical text across opposite
   classes, and rejects batches whose positives and negatives have different
   length distributions. A batch that fails is wasted work.
5. Write the batch to
   `C:\Proj\crossroad-detector\trainer\corpus\inbox\<yourSessionId>\batch-<NNN>.jsonl`
   (absolute path, UTF-8, no BOM), then mail the lead the path, the sample count,
   and the validator summary.
6. Stop at your quota.

## The two mistakes that ruin the dataset

These are the recorded failures of previous attempts, and both are mechanically
checked — a batch containing either is rejected.

- **Length confounding.** If your negatives average 20 words and your positives
  average 60, the model learns *"long ⇒ turn"* and scores near-random on real
  text. Keep the two classes' length distributions matched.
- **Template reuse.** If two samples differ by one swapped noun, the model
  cannot learn from them, and if a whole text appears in both classes the loss
  pins at `ln(2)` and nothing is learned at all. Every sample needs its own
  `topic_id`, and **no `topic_id` may be shared across peers** — the trainer
  splits train/val/test by topic.

## Verifying a peer's batch

When asked, you check a batch produced by a **different model** than yours (this
cross-model agreement is the quality signal). For each sample decide:

- `has_turn=true` → is there a genuine reversal, and does `first_turn_pos` point
  at it?
- `has_turn=false` → is it genuinely free of a reversal? Watch for the confusable
  traps (mid-sentence "but", instructional "wait for", 等等 as "etc.").

Reply `approve`, or `reject` with a one-line reason. Reject bad data rather than
being agreeable — a wrongly approved sample silently degrades the model. Mail
the lead your per-sample verdicts.

