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
│   ├── chunker_v2.py     #   v2 contiguous tile-by-cap chunker (448 chars)
│   ├── export_onnx.py    #   export to ONNX (INT8)
│   ├── validate_corpus.py#   corpus schema validation
│   └── ...               #   see trainer/README.md
├── src/                  # Node.js server + client SDK (TypeScript)
│   ├── server.ts         #   HTTP server: ONNX inference + WordPiece tokenizer
│   ├── chunker.ts        #   segment tile-by-cap chunker (1:1 port of trainer/chunker_v2.py)
│   ├── client.ts         #   CrossroadDetector class — lazy spawn + HTTP detect
│   ├── lockfile.ts       #   lockfile utility (path passed by caller)
│   └── index.ts          #   public exports
├── model/                # model artifacts
│   ├── model.onnx        #   v7 INT8 DistilBERT (~129 MB) — GitHub Release asset, NOT in git
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
   as the asset `model.onnx`. `npm run fetch-model` then delivers exactly the
   pinned bytes.
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

**v7** — fine-tuned multilingual DistilBERT, trained on 448-char contiguous tiles
(chunker v2), with the word-embeddings table INT8-quantized (412 MB → 136 MB at
F1 0.8772 vs the 0.8786 baseline). Test F1 = 0.9050 (torch) / 0.8772 (ONNX INT8).
See `trainer/README.md` for training details and measured results.

## License

MIT