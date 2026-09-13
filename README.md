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
│   ├── client.ts         #   CrossroadDetector class — lazy spawn + HTTP detect
│   ├── lockfile.ts       #   lockfile utility (path passed by caller)
│   └── index.ts          #   public exports
├── model/                # vendored model artifacts (shipped with the package)
│   ├── model.onnx        #   v6 INT8 DistilBERT (~393 MB)
│   └── tokenizer.json    #   WordPiece tokenizer
├── dist/                 # compiled JS (gitignored in dev, shipped when published)
└── .mycc/skills/         # project-level skills for mycc
    └── crossroad-corpus-farmer/
```

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

**v6** — fine-tuned multilingual DistilBERT, trained on 448-char contiguous tiles
(chunker v2). Test F1 = 0.9050 (torch) / 0.8786 (ONNX INT8). See `trainer/README.md`
for training details and measured results.

## License

MIT