#!/usr/bin/env node
/*
 * harvest.cjs — mine REAL crossroad material from .mycc/sessions.
 *
 * Two sources (plan doc "Acceptance gate", sets 2 and 3):
 *   1. crossroad-*.json   -> the response text + the old regex's chosen index.
 *      These labels are WEAK (old FSM/regex). We emit them as `harvested` +
 *      `first_turn_pos` = the recorded candidate's char offset, and mark
 *      provenance so the gate treats them as a diagnostic, never as gold.
 *   2. triologue-*.jsonl  -> assistant messages that were NOT a crossroad
 *      (no sibling crossroad-*.json in the same session/prefix). These are
 *      REAL NEGATIVES: genuine model output that did not turn.
 *
 * Output: one JSONL stream of *document-level* rows matching
 * schemas/corpus.schema.json (minus fields the gate fills later). Chunking is
 * NOT done here — gen_chunks.py owns boundaries.
 *
 * Usage:
 *   node harvest.cjs --root ..\..\..\.mycc\sessions --out corpus\harvested.jsonl
 */

const fs = require('fs');
const path = require('path');

function arg(name, def) {
  const i = process.argv.indexOf('--' + name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def;
}

const ROOT = path.resolve(arg('root', path.join(process.cwd(), '..', '..', '..', '.mycc', 'sessions')));
const OUT = path.resolve(arg('out', path.join(process.cwd(), 'corpus', 'harvested.jsonl')));

const CJK = /[\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff]/;

function langOf(text) {
  const noWs = text.replace(/\s+/g, '');
  if (!noWs.length) return 'en';
  const cjk = (noWs.match(new RegExp(CJK, 'g')) || []).length;
  return cjk / noWs.length >= 0.5 ? 'zh' : 'en';
}

function wordCountOf(text, lang) {
  if (lang === 'zh') return text.replace(/\s+/g, '').length;
  return text.trim().split(/\s+/).filter(Boolean).length;
}

// Deterministic 8-hex topic id from a string (stable across runs).
function topicHash(s) {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = (h * 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, '0');
}

const rows = [];
let skipped = 0;
// Per-session: positive-document texts, used to suppress contradicting negatives.
const posTextsBySession = new Map();   // sessionId -> [normalized text]
let suppressed = 0;

function normText(t) {
  return t.replace(/\s+/g, ' ').trim().toLowerCase();
}

function emitDocument(doc) {
  const text = doc.text;
  if (!text || text.length < 40) { skipped++; return; }
  const lang = langOf(text);
  const wc = wordCountOf(text, lang);
  if (wc < 1) { skipped++; return; }
  rows.push({
    id: doc.id,
    text,
    has_turn: doc.has_turn,
    first_turn_pos: doc.first_turn_pos,
    scenario: doc.scenario || 'analysis',
    turn_type: doc.turn_type || (doc.has_turn ? 'clausal-adversative' : 'none'),
    is_negative: !doc.has_turn,
    lang,
    word_count: wc,
    topic_id: doc.topic_id,
    provenance: 'harvested',
    source_model: doc.source_model || 'unknown',
    peer_session: doc.peer_session || '',
    conjunction: null,
    verified_by: [],
    verdict: 'pending',
  });
}

function scenarioGuess(text) {
  const t = text.toLowerCase();
  if (/\b(code|function|bug|compile|refactor|typescript|python|test)\b/.test(t)) return 'coding';
  if (/\b(plan|step|roadmap|approach|design|strategy)\b/.test(t)) return 'planning';
  if (/\b(error|failed|traceback|exception|debug|reproduce)\b/.test(t)) return 'debugging';
  return 'analysis';
}

// ---- Source 1: crossroad-*.json -----------------------------------------
function harvestCrossroadFiles() {
  let n = 0;
  const dirs = fs.readdirSync(ROOT, { withFileTypes: true }).filter((d) => d.isDirectory());
  for (const d of dirs) {
    const sessionDir = path.join(ROOT, d.name);
    let files;
    try { files = fs.readdirSync(sessionDir); } catch { continue; }
    for (const f of files) {
      if (!/^crossroad-\d+\.json$/.test(f)) continue;
      let rec;
      try { rec = JSON.parse(fs.readFileSync(path.join(sessionDir, f), 'utf8')); } catch { continue; }
      const candidates = Array.isArray(rec.candidates) ? rec.candidates : [];
      const prefix = typeof rec.prefix === 'string' ? rec.prefix : '';
      const continuation = typeof rec.continuation === 'string' ? rec.continuation : '';
      // The weak label: the old detector picked `continuation`; find where it
      // starts inside the reconstructed text.
      const text = (prefix + (candidates[0] || continuation)).trim();
      if (!text || text.length < 40) { skipped++; continue; }
      const cont = continuation.trim();
      let idx = cont ? text.indexOf(cont) : -1;
      const hasTurn = idx >= 0;
      if (hasTurn) {
        // remember the prefix (everything before the turn) — a triologue
        // assistant message equal to it is the SAME text and must not be
        // emitted as a negative (that was the v2 identical-text failure).
        if (!posTextsBySession.has(d.name)) posTextsBySession.set(d.name, []);
        posTextsBySession.get(d.name).push(normText(prefix));
        posTextsBySession.get(d.name).push(normText(text));
      }
      emitDocument({
        id: `hv-${d.name.slice(0, 8)}-${f.replace(/\D/g, '').slice(-6)}`,
        text,
        has_turn: hasTurn,
        first_turn_pos: hasTurn ? idx : -1,
        scenario: scenarioGuess(text),
        turn_type: hasTurn ? 'clausal-adversative' : 'none',
        topic_id: 'hv-' + topicHash(text.slice(0, 64)),
        source_model: 'fsm-weak',
        peer_session: d.name,
      });
      n++;
    }
  }
  return n;
}

// ---- Source 2: triologue-*.jsonl (real negatives) ------------------------
function harvestTriologueNegatives() {
  let n = 0;
  const dirs = fs.readdirSync(ROOT, { withFileTypes: true }).filter((d) => d.isDirectory());
  for (const d of dirs) {
    const sessionDir = path.join(ROOT, d.name);
    let files;
    try { files = fs.readdirSync(sessionDir); } catch { continue; }
    const crossroadFiles = files.filter((f) => /^crossroad-\d+\.json$/.test(f));
    for (const f of files) {
      if (!/^triologue.*\.jsonl$/.test(f)) continue;
      let lines;
      try { lines = fs.readFileSync(path.join(sessionDir, f), 'utf8').split('\n'); } catch { continue; }
      let seq = 0;
      for (const line of lines) {
        if (!line.trim()) continue;
        let r;
        try { r = JSON.parse(line); } catch { continue; }
        if (r.role !== 'assistant') continue;
        const content = typeof r.content === 'string' ? r.content : '';
        if (content.length < 80) continue;          // too short to judge
        if (/\[HINT\]|\[REMINDER\]|\[System/.test(content)) continue;

        // ── anti-v2: never emit as a negative any text that a crossroad record
        // in THIS session already emitted as a positive. The crossroad's
        // `prefix` is literally prior assistant text, so without this guard the
        // same string lands in both classes and the loss pins at ln(2).
        const nNorm = normText(content);
        const posTexts = posTextsBySession.get(d.name);
        if (posTexts) {
          let clash = false;
          for (const pt of posTexts) {
            if (pt === nNorm || pt.includes(nNorm) || nNorm.includes(pt)) { clash = true; break; }
          }
          if (clash) { suppressed++; continue; }
        }

        emitDocument({
          id: `tn-${d.name.slice(0, 8)}-${seq++}`,
          text: content,
          has_turn: false,
          first_turn_pos: -1,
          scenario: scenarioGuess(content),
          turn_type: 'none',
          topic_id: 'tn-' + topicHash(content.slice(0, 96)),
          source_model: 'harvested-real',
          peer_session: d.name,
          _crossroadSiblings: crossroadFiles.length, // informational only
        });
        n++;
      }
    }
  }
  return n;
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
const a = harvestCrossroadFiles();
const b = harvestTriologueNegatives();
fs.writeFileSync(OUT, rows.map((r) => JSON.stringify(r)).join('\n') + '\n', 'utf8');

const pos = rows.filter((r) => r.has_turn).length;
const neg = rows.length - pos;
console.log(`harvest: ${rows.length} docs (pos=${pos} neg=${neg}) -> ${OUT}`);
console.log(`  crossroad-*.json  : ${a}`);
console.log(`  triologue negs    : ${b}`);
console.log(`  suppressed (v2 anti-leak): ${suppressed}`);
console.log(`  skipped (too short): ${skipped}`);
