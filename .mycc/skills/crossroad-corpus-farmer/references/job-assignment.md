# Crossroad corpus — peer job assignment

**Read this together with `corpus-brief.md`.** This file says *what to produce*;
the brief says *how*.

## Your shard

Your assignment is mailed to you as a table. Each row is one **quota**: you must
produce exactly that many samples for that (scenario, turn_type, lang, class)
cell. Do not invent your own distribution and do not skip cells — the trainer
depends on every cell being filled.

```

scenario | turn_type          | lang | class | count
---------|--------------------|------|-------|------
coding   | strong-phrase      | en   | pos   | 5
coding   | none (confusable)  | en   | neg   | 5
...      | ...                | ...  | ...   | ...
```

## Hard rules

1. **Disjoint topic_ids.** Your `topic_id` values must never be reused by
   another peer. Prefix every topic_id with your peer id:
   `<yourId>-<topic>`, e.g. `p07-auth-oauth-saml`. The trainer splits
   train/val/test by topic_id; a reused topic across splits is the single
   failure that destroys the whole run.
2. **Do not reuse a template within your own batch.** Each sample must have its
   own topic_id. Eight samples that differ by one word will be rejected as
   duplicates.
3. **Both classes must share a length distribution.** Produce roughly the same
   word counts for positives and negatives. If you write 20-word negatives and
   60-word positives, the validator rejects the batch for **length
   confounding** — the model would learn "long means turn" instead of reading
   meaning. Vary lengths across your batch, and keep the pos/neg averages close.
4. **Confusable negatives are mandatory.** A negative is not simply "a text
   without a turn". For every real turn type, produce a matching negative that
   uses the *same surface form* without a genuine reversal. See the brief.
5. **Character offsets.** `first_turn_pos` is a **character offset** into
   `text`, 0-based. Not a byte offset, not a token index. `-1` when
   `has_turn=false`.

## Workflow

1. Read `corpus-brief.md`.
2. Generate your samples with your own LLM. Write one JSON object per line
   (JSONL), UTF-8, no BOM.
3. Write the batch to **your own inbox directory**:
   `C:\Proj\crossroad-detector\trainer\corpus\inbox\<yourSessionId>\batch-<NNN>.jsonl`
   Use an absolute path. Do not write anywhere else.
4. **Self-validate before submitting.** Run:
   ```
   cd C:\Proj\crossroad-detector\trainer
   .venv/Scripts/python.exe validate_corpus.py "corpus/inbox/<yourSessionId>" --strict
   ```
   Fix every ERROR and re-run until it exits clean. A batch with errors is
   rejected and wastes the whole cycle.
5. Mail the lead: batch path, sample count, and the validator's summary line.
6. If asked to verify another peer's batch, follow the verification section of
   the brief, then mail the lead your verdict per sample.
7. Stop. Do not generate beyond your assigned quota.

## Do not

- Do not choose chunk boundaries or window sizes. You produce whole documents;
  the trainer derives overlapping chunks deterministically. Your document just
  needs a correct `first_turn_pos`.
- Do not submit a sample you are unsure about in order to hit the quota. Mail
  the shortfall instead — a missing sample costs one data point, a wrong label
  costs training quality.
- Do not use `--disable-crossroad` when launching.

