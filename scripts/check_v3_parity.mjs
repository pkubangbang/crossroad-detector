/**
 * check_v3_parity.mjs — diff the TS buildChunksV3 port against the Python
 * reference spans emitted by trainer/dump_v3_spans.py.
 *
 * Usage: node scripts/check_v3_parity.mjs <corpus.jsonl> <refspans.jsonl>
 * Exit 0 iff every doc's spans match exactly.
 */
import { readFileSync } from 'node:fs';
import { buildChunksV3 } from '../dist/chunker.js';

const [, , corpusPath, refPath] = process.argv;
if (!corpusPath || !refPath) {
  console.error('usage: node scripts/check_v3_parity.mjs <corpus.jsonl> <refspans.jsonl>');
  process.exit(2);
}

import { createHash } from 'node:crypto';
const h = (s) => createHash('sha256').update(s).digest('hex').slice(0, 16);

const corpus = readFileSync(corpusPath, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l));
// Join on the TEXT hash, not on `id` — the corpus contains duplicate ids
// (3919 lines / 3886 distinct ids), so id is not a valid join key.
const refs = new Map();
for (const l of readFileSync(refPath, 'utf8').split('\n')) {
  if (!l.trim()) continue;
  const r = JSON.parse(l);
  refs.set(r.text_hash, r.spans);
}

let checked = 0, missing = 0, mismatches = 0;
for (const doc of corpus) {
  const key = h(doc.text);
  const ref = refs.get(key);
  if (!ref) { missing += 1; continue; }
  checked += 1;
  const got = buildChunksV3(doc.text, doc.first_turn_pos).map((s) => [s.start, s.end]);
  if (JSON.stringify(got) !== JSON.stringify(ref)) {
    mismatches += 1;
    if (mismatches <= 3) {
      console.error(`MISMATCH doc=${doc.id}`);
      console.error(`  ref (${ref.length}): ${JSON.stringify(ref.slice(0, 8))}`);
      console.error(`  got (${got.length}): ${JSON.stringify(got.slice(0, 8))}`);
    }
  }
}
console.log(`checked=${checked} mismatches=${mismatches} (refs not matching any corpus text: ${missing})`);
process.exit(mismatches === 0 ? 0 : 1);

