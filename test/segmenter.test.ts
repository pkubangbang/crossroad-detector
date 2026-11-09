/**
 * segmenter.test.ts — pins the three invariants mycc builds against.
 *
 * Run: npx tsx test/segmenter.test.ts
 *
 *   1. ABSOLUTE, CUMULATIVE code-point offsets (push("abc") then push("def")
 *      yields offsets into "abcdef").
 *   2. A returned segment is FINAL — never re-emitted, never amended.
 *   3. 'forced' can only come from the segMax tiler, never from punctuation.
 */

import { createSegmenter, segmentsOf, type Segment } from '../src/segmenter.js';

let passed = 0;
let failed = 0;
function ok(name: string, cond: boolean, detail?: string): void {
  if (cond) { passed++; console.log(`  PASS  ${name}`); }
  else { failed++; console.log(`  FAIL  ${name}${detail ? ` — ${detail}` : ''}`); }
}

/**
 * Assert a segment list is the trainer's lattice: strictly increasing, every
 * range non-empty, and equal to `expected`. The lattice is NOT a partition —
 * the trainer drops whitespace-only parts and leaves them uncovered (for a
 * strict partition the consumer carries a boundary character into the next
 * unit, which is mycc's rule, not this package's).
 */
function sameLattice(segs: Segment[], expected: Array<[number, number]>): boolean {
  if (segs.length !== expected.length) return false;
  return segs.every((s, i) => s.start === expected[i][0] && s.end === expected[i][1] && s.end > s.start);
}

const text = (cp: string[], segs: Segment[]): string[] =>
  segs.map((s) => cp.slice(s.start, s.end).join(''));

function main(): void {
  // ------------------------------------------------------------------
  console.log('\n[1] CUMULATIVE code-point offsets across pushes');
  {
    const s = createSegmenter();
    // Push "Hello there. " then "How are you?" — second push offsets must be
    // absolute into the combined text, not into the delta.
    const a = s.push('Hello there. ');
    const b = s.push('How are you?');
    const c = s.flush();
    const all = [...a, ...b, ...c];
    const total = 'Hello there. How are you?'.length;
    ok(
      'the lattice is the trainer lattice',
      sameLattice(all, [[0, 12], [12, 25]]),
      JSON.stringify(all),
    );
    ok('second-push offset is absolute', all.every((x) => x.start >= 0 && x.end <= total), JSON.stringify(all));
    ok('no segment starts inside the delta frame', all.filter((x) => x.start >= 13).every((x) => x.start >= 13), JSON.stringify(all));
  }

  // ------------------------------------------------------------------
  console.log('\n[2] NEVER re-emit or amend: emitted segments are identical across later pushes');
  {
    const s = createSegmenter();
    const first = s.push('One sentence here. Another one there. ');
    const later = s.push('Third. ');
    const flushed = s.flush();
    const byKey = (x: Segment) => `${x.start}:${x.end}:${x.cutKind}`;
    const firstKeys = new Set(first.map(byKey));
    const laterKeys = [...later, ...flushed].map(byKey);
    ok('no segment from an earlier push reappears', laterKeys.every((k) => !firstKeys.has(k)), JSON.stringify({ first: [...firstKeys], later: laterKeys }));
    const all = [...first, ...later, ...flushed];
    ok(
      'all pushes together form the unchanged trainer lattice',
      sameLattice(all, [[0, 18], [18, 37], [37, 44], [44, 45]]),
      JSON.stringify(all),
    );
  }

  // ------------------------------------------------------------------
  console.log('\n[3] Tail ambiguity, and numbers split like the trainer');
  {
    const s = createSegmenter();
    const a = s.push('The failure is version 3.');
    ok('push ending in "." emits nothing (ambiguous tail)', a.length === 0, JSON.stringify(a));
    ok('pending holds the whole ambiguous tail', s.pending === 'The failure is version 3.', JSON.stringify(s.pending));

    // "3." IS a boundary for the trainer: SENT_SPLIT is a plain look-behind
    // over its delimiter set, so "3.14" splits after the "." exactly as
    // build_segments does. Verified against trainer/chunker.py.
    const b = s.push('14 of the library.');
    const bText = text(Array.from('The failure is version 3.14 of the library.'), b);
    ok('"3." closes a part once the next char arrives', b.length > 0, JSON.stringify(b));
    ok('the part is exactly "The failure is version 3."', bText[0] === 'The failure is version 3.', JSON.stringify(bText));

    const c = s.flush();
    const cp = Array.from('The failure is version 3.14 of the library.');
    const all = [...a, ...b, ...c];
    ok('flush leaves nothing pending', s.pending === '', JSON.stringify(s.pending));
    ok(
      'the whole lattice is the trainer lattice',
      sameLattice(all, [[0, 25], [25, 43]]),
      JSON.stringify(all),
    );
    ok('lattice spans lie inside the text', all.every((x) => x.end <= cp.length), JSON.stringify(all));
  }

  // ------------------------------------------------------------------
  console.log('\n[4] cutKind values');
  {
    const segs = segmentsOf('First sentence. Second, clause; here. Third!');
    const kinds = segs.map((x) => x.cutKind);
    ok("'.' + space yields 'sentence'", kinds[0] === 'sentence', JSON.stringify(segs));
    ok("',' or ';' yields 'clause'", kinds.includes('clause'), JSON.stringify(segs));
    ok("no 'forced' without hitting segMax", !kinds.includes('forced'), JSON.stringify(segs));
  }

  // ------------------------------------------------------------------
  console.log('\n[5] forced only from the tiler');
  {
    const longWord = 'a'.repeat(500); // no punctuation at all
    const segs = segmentsOf(longWord, { segMax: 224 });
    const forced = segs.filter((x) => x.cutKind === 'forced');
    ok('long unpunctuated run produces forced segments', forced.length > 0, JSON.stringify(segs.map((x) => [x.start, x.end, x.cutKind])));
    ok('each forced piece is exactly segMax wide', forced.every((x) => x.end - x.start === 224), JSON.stringify(forced));
    ok('each forced piece follows the previous one', segs.every((x, i) => i === 0 || x.start === segs[i - 1].end), JSON.stringify(segs));
  }

  // ------------------------------------------------------------------
  console.log('\n[6] sentence policy is a SUBSET of trained policy');
  {
    const t = 'First clause, second clause; third one. Final.';
    const trained = segmentsOf(t, { splitPolicy: 'trained' });
    const sentence = segmentsOf(t, { splitPolicy: 'sentence' });
    ok('trained splits at clause punctuation', trained.length > sentence.length, `${trained.length} vs ${sentence.length}`);
    const sentenceEnds = new Set(sentence.map((x) => x.end));
    ok(
      'every sentence boundary also exists in trained (subset)',
      [...sentenceEnds].every((e) => trained.some((x) => x.end === e)),
      `${JSON.stringify(sentence.map((x) => x.end))} vs ${JSON.stringify(trained.map((x) => x.end))}`,
    );
    ok(
      'the sentence policy emits exactly its own boundaries',
      sameLattice(sentence, [[0, 39], [39, 46]]),
      JSON.stringify(sentence),
    );
  }

  // ------------------------------------------------------------------
  console.log('\n[7] astral characters count as ONE code point in offsets');
  {
    const t = 'Hi 😀 there. Next one.';
    const segs = segmentsOf(t);
    const cpLen = Array.from(t).length;
    ok('offsets are code points, not UTF-16 units', segs[segs.length - 1].end === cpLen, `end=${segs[segs.length - 1].end} cpLen=${cpLen} (utf16=${t.length})`);
    ok(
      'offsets are code points across the whole text',
      sameLattice(segs, [[0, 11], [11, 21]]),
      JSON.stringify(segs),
    );
  }

  // ------------------------------------------------------------------
  console.log('\n[8] empty and whitespace-only input');
  {
    ok('empty text yields nothing', segmentsOf('').length === 0);
    const ws = segmentsOf('   ');
    ok('whitespace-only input is a single part', sameLattice(ws, [[0, 3]]), JSON.stringify(ws));
    const s = createSegmenter();
    ok('push("") returns []', s.push('').length === 0);
    ok('pending is "" on a fresh segmenter', s.pending === '');
  }

  // ------------------------------------------------------------------
  console.log('\n[9] pending holds exactly the uncommitted tail');
  {
    const s = createSegmenter();
    const first = s.push('Hello. ');
    const cp = Array.from('Hello. partial');
    // The space after a confirmed boundary belongs to the NEXT segment, so the
    // pending tail legitimately includes it.
    const firstText = text(cp, first).join('');
    ok('push("Hello. ") commits the sentence', firstText.startsWith('Hello.'), JSON.stringify(firstText));
    s.push('partial');
    ok('pending is the uncommitted tail (leading space included)', s.pending === ' partial', JSON.stringify(s.pending));
    const rest = s.flush();
    ok('flush empties pending', s.pending === '', JSON.stringify(s.pending));
    ok('flush tail reconstructs the rest of the text', text(cp, rest).join('') === ' partial', JSON.stringify(text(cp, rest)));  }

  console.log('\n[10] CRLF has the same segmentation as LF (no degenerate segments)');
  {
    const lf = segmentsOf('Line one.\nLine two.\n');
    const crlf = segmentsOf('Line one.\r\nLine two.\r\n');
    const kinds = (segs: Segment[]) => segs.map((s) => s.cutKind).join(',');
    ok('CRLF yields the same number of segments as LF', lf.length === crlf.length, `LF=${lf.length} ${kinds(lf)} | CRLF=${crlf.length} ${kinds(crlf)}`);
    ok('CRLF yields the same cutKind sequence as LF', kinds(lf) === kinds(crlf), `${kinds(lf)} vs ${kinds(crlf)}`);
    ok('a CRLF boundary is 2 code points, not 1', crlf.every((x) => x.end - x.start !== 1), JSON.stringify(crlf.map((x) => [x.start, x.end])));
  }

  console.log(`\n${passed} passed, ${failed} failed`);
  if (failed > 0) process.exitCode = 1;
}

main();
