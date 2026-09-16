# crossroad-detector

Semantic crossroad (turning-word) detector for [mycc](https://github.com/pkubangbang/mycc) —
a DistilBERT classifier that detects when an LLM changes direction mid-response,
replacing the punctuation-sensitive regex matcher.

This package owns the **full lifecycle**: training harness (Python) → ONNX export →
serving (Node.js HTTP server) → client SDK consumed by mycc.

## Repository layout

```
crossroad-detector/
├── trainer/              # Python training harness (was mycc/machine-learning/crossroad-trainer/)
│   ├── train.py          #   fine-tune DistilBERT
│   ├── chunker_v3.py     #   v3 segment adaptive-overlap chunker (active)
│   ├── chunker_v2.py     #   v2 contiguous tile-by-cap chunker (superseded)
│   ├── export_onnx.py    #   export to ONNX (INT8)
│   ├── validate_corpus.py#   corpus schema validation
│   └── ...               #   see trainer/README.md
├── src/                  # Node.js server + client SDK (TypeScript)
│   ├── server.ts         #   HTTP server: ONNX inference + WordPiece tokenizer
│   ├── chunker.ts        #   segment adaptive-overlap chunker (1:1 port of trainer/chunker_v3.py)
│   ├── client.ts         #   CrossroadDetector class — lazy spawn + HTTP detect
│   ├── lockfile.ts       #   lockfile utility (path passed by caller)
│   └── index.ts          #   public exports
├── model/                # model artifacts
│   ├── model.onnx        #   v1.3 INT8 DistilBERT (~129 MB) — GitHub Release asset, NOT in git
│   ├── model.lock.json   #   pinned release tag + size + SHA256 for model.onnx
│   └── tokenizer.json    #   WordPiece tokenizer (tracked in git)
├── scripts/              # dev/ops scripts
│   └── fetch-model.mjs   #   download model.onnx from the GitHub Release
├── dist/                 # compiled JS (gitignored in dev, shipped when published)
└── .mycc/skills/         # project-level skills for mycc
    └── crossroad-corpus-farmer/
```

## Getting the model

`model/model.onnx` (~129 MB) exceeds GitHub's 100 MiB git file limit, so it is
**not tracked in git**. It is published as an asset on the
[GitHub Release](https://github.com/pkubangbang/crossroad-detector/releases).
After cloning, fetch it once:

```bash
npm run fetch-model            # downloads to model/model.onnx and verifies SHA256
npm run fetch-model -- --verify  # offline: hash the local copy against the lockfile
npm run verify-model           # alias for the offline verification above
```

Set `HTTPS_PROXY=http://127.0.0.1:7777` if you need a proxy. The npm-published
package bundles the model directly, so `npm install @pkubangbang/crossroad-detector`
needs no extra step.

`model/model.lock.json` is the tracked source of truth for the binary: it pins the
release tag, exact byte size, and SHA256, so the repo always records which model
it expects without carrying the 129 MB file itself.

**The fetched artifact must match the lockfile.** Both `fetch-model` (after a
download) and `verify-model` hash the bytes and compare them against the SHA256
in `model/model.lock.json`; any mismatch aborts with a non-zero exit. `prepack`
runs the same check (`--verify --if-present`) before publishing, so a model that
does not match the lockfile can never ship — while a dev clone without the model
still packs (the check is skipped when no `model.onnx` is present).

## Release workflow

Model releases MUST follow this order — the lockfile is the anchor every later
step is validated against:

1. **Register the SHA256 in `model/model.lock.json`.** Produce the ONNX artifact
   (`trainer/export_onnx.py`), compute its `sha256` and byte size, and commit
   them (with the new `tag` and `modelVersion`) into `model/model.lock.json`
   *first*. Everything downstream is checked against this pinned hash.
2. **Push the source to GitHub.** Push the commit whose lockfile already names
   the new artifact (including the version bump in `package.json`).
3. **Upload the model to the GitHub Release** for the tag named in the lockfile,
   as the asset `model.onnx` (the lockfile's `asset` field). `npm run fetch-model`
   then delivers exactly the pinned bytes.
4. **npm publish.** `prepack` re-verifies the bundled `model/` against the
   lockfile before the tarball is built; publish only if that check passes.

Verifying at each boundary: `npm run verify-model` after step 1/3 (offline hash),
and `npm run fetch-model` on a clean clone after step 3.

## Usage (from mycc)

```typescript
import { CrossroadDetector } from '@pkubangbang/crossroad-detector';
import { homedir } from 'node:os';
import { join } from 'node:path';

const detector = new CrossroadDetector(
  join(homedir(), '.mycc-store', 'crossroad.lock'),
  { threshold: 0.5 }
);

const result = await detector.detect(text);
// → { word: "however", index: 420, score: 0.92 } | null
```

The client lazily spawns a detached HTTP server (localhost, random port) on first
use, managed via a lockfile at the path you provide. The server auto-shuts-down
after 15 min idle.

## Model

**v1.3** — fine-tuned multilingual DistilBERT, trained on the **v3 segment-level
adaptive overlapping chunker** (`trainer/chunker_v3.py`, `TWO_X=448` window cap,
`THREE_X=672` expansion cap), with the word-embeddings table INT8-quantized
(541 MB → 136 MB). v3 restores **overlap** between consecutive windows (v2 was a
non-overlapping tile-by-cap), so a turn near a window boundary appears in ≥2
windows and is seen from more than one offset. Design + rationale:
`trainer/chunker_v3.md`.

Model versions track the npm release: **v1.3** ships with npm **v0.1.3** and is
published as the release asset **`model.onnx`** (`model/model.lock.json` pins its
`tag: v0.1.3`, `modelVersion: v1.3`). Round 4 (v8)
expanded the peer-generated corpus (638 → 794 positive chunks) and fixed a
document-level split leak in `trainer/train.py` (splits are grouped by the
`doc_id`/`topic_id` connected component). v1.3 keeps that corpus and split and
only changes the chunker (v2 → v3: 5,823 → 7,069 chunks, 794 → 868 positive
chunks, +27%/+36%).

Measured on the **v3 test split** (n=1161, 134 positives, seed 42, ONNX INT8):

| artifact | en F1 | zh F1 | ALL F1 |
|---|---|---|---|
| v8 INT8 (v2 chunks) | 0.8409 | 0.9167 | 0.8629 |
| **v1.3 INT8** (v3 chunks) | **0.8913** | 0.8767 | **0.8872** |

Like-for-like on the identical split, v3 chunking improves overall F1 by +0.024
and English F1 by +0.050 (the overlap benefit is largest where window boundaries
cut turns); Chinese is within noise at n=36. The trainer's own val F1 was 0.9266.
See `trainer/README.md` for training details and `trainer/chunker_v3.md` for the
chunker design.

### Serving parity

`src/chunker.ts` is a **1:1 port** of `trainer/chunker_v3.py` — the server must
produce the exact same windows the model was trained on, or it feeds
out-of-distribution input. Parity is machine-checked:

```bash
# regenerate the Python reference, then diff the TS port against it
trainer/.venv/Scripts/python.exe trainer/dump_v3_spans.py \
    --in trainer/corpus/r4.balanced.jsonl --out trainer/out/v3spans.jsonl --limit 5000
node scripts/check_v3_parity.mjs trainer/corpus/r4.balanced.jsonl trainer/out/v3spans.jsonl
# → checked=3919 mismatches=0
```

Both sides index strings by **code point**, not UTF-16 unit: an astral character
(emoji) is 1 code point in Python but 2 units in JS, so the TS chunker works over
`Array.from(text)` and the server slices windows with `sliceCodePoints`.

## License

MIT