#!/usr/bin/env python
"""validate_corpus.py - enforce the corpus contract on peer-produced batches.

The schema (schemas/corpus.schema.json) is only a contract if something checks
it. This module is used in two places:

  1. By the peer fleet (Phase 3) to self-check a batch before submitting, so bad
     batches are rejected at the source rather than discovered during training.
  2. By the harness (Phase 2) as the import gate, so nothing unvalidated can
     reach the training set.

It checks the field-level schema AND the distribution invariants that the two
historical failures violated:

  v1  length confounding  -> positives and negatives must share one length
                             distribution (measured per language)
  v2  contradictory labels -> identical/near-identical text across classes

Also enforces topic_id disjointness help (per split assignment is checked in
gen_chunks.py, but duplicates within a batch are caught here).

Usage:
    python validate_corpus.py <file-or-dir> [--strict] [--json-report PATH]

Exit code 0 = pass, 1 = errors found.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCENARIOS = {"coding", "planning", "debugging", "analysis", "teaching"}
TURN_TYPES_REAL = {
    "strong-phrase",
    "interjection",
    "clausal-adversative",
    "self-correction",
    "hedged-return",
}
TURN_TYPES_ALL = TURN_TYPES_REAL | {"none"}
LANGS = {"en", "zh"}

REQUIRED = [
    "id", "text", "has_turn", "first_turn_pos", "scenario",
    "turn_type", "is_negative", "lang", "word_count", "topic_id",
]

CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

# Length buckets shared with C:/Proj/turning-word-detection/validate-distribution.ps1
LENGTH_BUCKETS = [(0, 30), (30, 100), (100, 300), (300, 1000), (1000, 10**9)]


def bucket_of(n: int) -> str:
    for lo, hi in LENGTH_BUCKETS:
        if lo <= n < hi:
            return f"{lo}-{hi}" if hi < 10**9 else f">{lo}"
    return f">{LENGTH_BUCKETS[-1][0]}"


def compute_word_count(text: str) -> tuple[int, str]:
    """Replicate validate-distribution.ps1 exactly.

    ZH (CJK ratio >= 0.5 of non-whitespace chars): non-whitespace char count.
    EN otherwise: whitespace-separated token count.
    """
    no_ws = re.sub(r"\s", "", text)
    if not no_ws:
        return 0, "en"
    cjk_count = len(CJK.findall(no_ws))
    ratio = cjk_count / len(no_ws)
    if ratio >= 0.5:
        return len(no_ws), "zh"
    return len([t for t in re.split(r"\s+", text) if t]), "en"


@dataclass
class Report:
    total: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    by_lang: Counter = field(default_factory=Counter)
    by_scenario: Counter = field(default_factory=Counter)
    by_turn_type: Counter = field(default_factory=Counter)
    pos_lens: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    neg_lens: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    seen_text_norm: dict[str, tuple[str, str]] = field(default_factory=dict)  # norm -> (id, label)
    topic_classes: dict[str, set] = field(default_factory=lambda: defaultdict(set))

    def err(self, msg: str) -> None:
        if len(self.errors) < 200:
            self.errors.append(msg)

    def warn(self, msg: str) -> None:
        if len(self.warnings) < 200:
            self.warnings.append(msg)


def norm_text(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip().lower())


def validate_sample(o: dict[str, Any], where: str, rep: Report) -> bool:
    ok = True

    for f in REQUIRED:
        if f not in o:
            rep.err(f"{where}: missing required field '{f}'")
            ok = False
    if not ok:
        return False

    # --- types ---
    if not isinstance(o["text"], str) or len(o["text"]) < 40:
        rep.err(f"{where}: text too short (<40 chars) or not a string")
        ok = False
    for bf in ("has_turn", "is_negative"):
        if not isinstance(o[bf], bool):
            rep.err(f"{where}: '{bf}' must be a boolean")
            ok = False
    if not isinstance(o["first_turn_pos"], int) or isinstance(o["first_turn_pos"], bool):
        rep.err(f"{where}: first_turn_pos must be an integer")
        ok = False
    if not isinstance(o["word_count"], int) or isinstance(o["word_count"], bool):
        rep.err(f"{where}: word_count must be an integer")
        ok = False

    text = o["text"] if isinstance(o["text"], str) else ""
    has_turn = o["has_turn"] is True
    is_neg = o["is_negative"] is True
    pos = o["first_turn_pos"] if isinstance(o["first_turn_pos"], int) else -1

    # --- enum + cross-field consistency (the redundant fields are the point) ---
    if o["scenario"] not in SCENARIOS:
        rep.err(f"{where}: bad scenario '{o['scenario']}'")
        ok = False
    if o["turn_type"] not in TURN_TYPES_ALL:
        rep.err(f"{where}: bad turn_type '{o['turn_type']}'")
        ok = False
    if o["lang"] not in LANGS:
        rep.err(f"{where}: bad lang '{o['lang']}'")
        ok = False

    if has_turn == is_neg:
        rep.err(f"{where}: has_turn={has_turn} contradicts is_negative={is_neg}")
        ok = False

    if has_turn:
        if o["turn_type"] not in TURN_TYPES_REAL:
            rep.err(f"{where}: has_turn=true but turn_type='{o['turn_type']}'")
            ok = False
        # first_turn_pos must point at a real char in text
        if not (0 <= pos < len(text)):
            rep.err(f"{where}: has_turn=true but first_turn_pos={pos} out of range [0,{len(text)})")
            ok = False
    else:
        if o["turn_type"] != "none":
            rep.err(f"{where}: has_turn=false but turn_type='{o['turn_type']}' (must be 'none')")
            ok = False
        if pos != -1:
            rep.err(f"{where}: has_turn=false but first_turn_pos={pos} (must be -1)")
            ok = False

    # --- word_count + lang recomputed, not trusted ---
    wc, lang = compute_word_count(text)
    if isinstance(o["word_count"], int) and o["word_count"] != wc:
        rep.err(f"{where}: word_count={o['word_count']} but computed {wc}")
        ok = False
    if o["lang"] != lang:
        rep.err(f"{where}: lang='{o['lang']}' but computed '{lang}' (CJK-ratio rule)")
        ok = False

    if not isinstance(o["topic_id"], str) or len(o["topic_id"]) < 3:
        rep.err(f"{where}: topic_id missing or too short")
        ok = False

    # --- v2 guard: identical text across opposite classes ---
    n = norm_text(text)
    label = "pos" if has_turn else "neg"
    if n in rep.seen_text_norm:
        prev_id, prev_label = rep.seen_text_norm[n]
        if prev_label != label:
            rep.err(
                f"{where}: IDENTICAL text appears in BOTH classes "
                f"(id={o['id']} label={label} vs id={prev_id} label={prev_label}) "
                f"-> this is the v2 failure, loss will pin at ln(2)"
            )
            ok = False
        else:
            rep.warn(f"{where}: duplicate text within the same class (id={o['id']} ~ id={prev_id})")
    else:
        rep.seen_text_norm[n] = (o["id"], label)

    # --- bookkeeping ---
    rep.by_lang[o["lang"]] += 1
    rep.by_scenario[o["scenario"]] += 1
    rep.by_turn_type[o["turn_type"]] += 1
    if isinstance(o.get("topic_id"), str):
        rep.topic_classes[o["topic_id"]].add(label)
    if isinstance(wc, int):
        (rep.pos_lens if has_turn else rep.neg_lens)[o["lang"]].append(wc)

    return ok


def check_distribution(rep: Report) -> None:
    """The v1 guard: positives and negatives must share one length distribution."""
    for lang in sorted(rep.pos_lens.keys() | rep.neg_lens.keys()):
        p, n = rep.pos_lens.get(lang, []), rep.neg_lens.get(lang, [])
        if not p or not n:
            rep.warn(f"lang={lang}: only one class present (pos={len(p)} neg={len(n)})")
            continue
        pm, nm = sum(p) / len(p), sum(n) / len(n)
        denom = max(pm, nm) or 1
        drift = abs(pm - nm) / denom
        if drift > 0.20:
            rep.err(
                f"LENGTH CONFOUNDING lang={lang}: posAvg={pm:.0f} negAvg={nm:.0f} "
                f"(drift {drift:.0%} > 20%) -> this is the v1 failure, "
                f"the model will learn 'long => turn'"
            )
        pb = Counter(bucket_of(x) for x in p)
        nb = Counter(bucket_of(x) for x in n)
        for b in sorted(set(pb) | set(nb)):
            ps, ns = pb.get(b, 0) / len(p), nb.get(b, 0) / len(n)
            if abs(ps - ns) > 0.25:
                rep.warn(
                    f"bucket skew lang={lang} bucket={b}: pos={ps:.0%} neg={ns:.0%}"
                )


def check_coverage(rep: Report, strict: bool) -> None:
    if strict:
        for s in sorted(SCENARIOS):
            if rep.by_scenario.get(s, 0) == 0:
                rep.err(f"coverage: scenario '{s}' has zero samples")
        for t in sorted(TURN_TYPES_REAL):
            if rep.by_turn_type.get(t, 0) == 0:
                rep.err(f"coverage: turn_type '{t}' has zero samples")
        for l in sorted(LANGS):
            if rep.by_lang.get(l, 0) == 0:
                rep.err(f"coverage: lang '{l}' has zero samples")


def load_jsonl(path: Path, rep: Report) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        rep.err(f"{path.name}: cannot read ({e})")
        return out
    if raw.startswith("\ufeff"):
        rep.err(f"{path.name}: HAS UTF-8 BOM (strip it)")
    for i, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            rep.err(f"{path.name}:{i}: JSON parse error: {e}")
            continue
        if not isinstance(obj, dict):
            rep.err(f"{path.name}:{i}: not a JSON object")
            continue
        out.append(obj)
    return out


CHUNK_REQUIRED = [
    "chunk_id", "doc_id", "topic_id", "lang", "scenario", "turn_type",
    "text", "start", "end", "label", "turn_offset_in_chunk", "n_chars", "provenance",
]


def validate_chunk(o: dict[str, Any], where: str, rep: Report) -> bool:
    """Chunk-level contract. Same v1/v2 intent as validate_sample, but the
    length signal is `n_chars` and identity is (doc_id, start, end)."""
    ok = True
    for f in CHUNK_REQUIRED:
        if f not in o:
            rep.err(f"{where}: missing required field '{f}'")
            ok = False
    if not ok:
        return False

    text = o["text"] if isinstance(o["text"], str) else ""
    lab = o["label"]
    if lab not in (0, 1):
        rep.err(f"{where}: label must be 0/1, got {lab!r}")
        ok = False
    if not isinstance(o["n_chars"], int) or o["n_chars"] != len(text):
        rep.err(f"{where}: n_chars={o.get('n_chars')} != len(text)={len(text)}")
        ok = False
    if o["lang"] not in LANGS:
        rep.err(f"{where}: bad lang '{o['lang']}'")
        ok = False
    off = o.get("turn_offset_in_chunk", -1)
    if lab == 1 and not (0 <= off < len(text)):
        rep.err(f"{where}: label=1 but turn_offset_in_chunk={off} out of range [0,{len(text)})")
        ok = False
    if lab == 0 and off != -1:
        rep.err(f"{where}: label=0 but turn_offset_in_chunk={off} (must be -1)")
        ok = False

    # v2 guard at chunk level: identical chunk text in both classes
    n = norm_text(text)
    label = "pos" if lab == 1 else "neg"
    if n in rep.seen_text_norm:
        prev_id, prev_label = rep.seen_text_norm[n]
        if prev_label != label:
            rep.err(
                f"{where}: IDENTICAL chunk text in BOTH classes "
                f"(chunk_id={o.get('chunk_id')} {label} vs {prev_id} {prev_label})"
            )
            ok = False
    else:
        rep.seen_text_norm[n] = (o.get("chunk_id", "?"), label)

    rep.by_lang[o["lang"]] += 1
    rep.by_scenario[o.get("scenario", "analysis")] += 1
    rep.by_turn_type[o.get("turn_type", "none")] += 1
    rep.pos_lens if lab == 1 else rep.neg_lens
    (rep.pos_lens if lab == 1 else rep.neg_lens)[o["lang"]].append(len(text))
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate crossroad corpus batches.")
    ap.add_argument("path", help="JSONL file or directory of JSONL files")
    ap.add_argument("--strict", action="store_true",
                    help="require every scenario/turn_type/lang to be represented")
    ap.add_argument("--level", choices=["doc", "chunk"], default="doc",
                    help="contract layer to validate (default: doc)")
    ap.add_argument("--json-report", dest="json_report", default=None,
                    help="write a machine-readable report to this path")
    args = ap.parse_args()

    root = Path(args.path)
    files = sorted(root.rglob("*.jsonl")) if root.is_dir() else [root]
    if not files:
        print(f"No .jsonl files found under {root}", file=sys.stderr)
        return 1

    rep = Report()
    for f in files:
        samples = load_jsonl(f, rep)
        for o in samples:
            rep.total += 1
            if args.level == "chunk":
                validate_chunk(o, f"{f.name}:{o.get('chunk_id', '?')}", rep)
            else:
                validate_sample(o, f"{f.name}:{o.get('id', '?')}", rep)

    check_distribution(rep)
    check_coverage(rep, args.strict)

    # --- report ---
    print(f"files: {len(files)}   samples: {rep.total}")
    print(f"by lang:      {dict(sorted(rep.by_lang.items()))}")
    print(f"by scenario:  {dict(sorted(rep.by_scenario.items()))}")
    print(f"by turn_type: {dict(sorted(rep.by_turn_type.items()))}")
    for lang in sorted(rep.pos_lens.keys() | rep.neg_lens.keys()):
        p, n = rep.pos_lens.get(lang, []), rep.neg_lens.get(lang, [])
        if p and n:
            print(f"lang={lang}: posAvg={sum(p)/len(p):.0f} negAvg={sum(n)/len(n):.0f} "
                  f"(pos={len(p)} neg={len(n)})")
    print(f"errors: {len(rep.errors)}   warnings: {len(rep.warnings)}")
    for e in rep.errors[:40]:
        print(f"  ERROR   {e}")
    if len(rep.errors) > 40:
        print(f"  ... and {len(rep.errors) - 40} more errors")
    for w in rep.warnings[:20]:
        print(f"  WARN    {w}")
    if len(rep.warnings) > 20:
        print(f"  ... and {len(rep.warnings) - 20} more warnings")

    if args.json_report:
        Path(args.json_report).write_text(json.dumps({
            "files": [str(f) for f in files],
            "total": rep.total,
            "errors": rep.errors,
            "warnings": rep.warnings,
            "by_lang": dict(rep.by_lang),
            "by_scenario": dict(rep.by_scenario),
            "by_turn_type": dict(rep.by_turn_type),
            "length_avgs": {
                lang: {
                    "pos": (sum(rep.pos_lens[lang]) / len(rep.pos_lens[lang])) if rep.pos_lens.get(lang) else None,
                    "neg": (sum(rep.neg_lens[lang]) / len(rep.neg_lens[lang])) if rep.neg_lens.get(lang) else None,
                }
                for lang in sorted(rep.pos_lens.keys() | rep.neg_lens.keys())
            },
        }, indent=2), encoding="utf-8")

    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
