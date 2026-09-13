#!/usr/bin/env python
"""chunker_v2.py — segment-based variable-length chunker (producer-consumer,
in one script per document: text -> sub-sentences -> segments -> chunks).

Replaces the fixed 128-char/stride-32 windowing of chunking.py with
contiguous tile-by-cap chunking over segment units. Design (user spec):

  X = token capacity (distilbert max_position_embeddings = 512)
  Char approximation (measured): worst case CJK ~1.016 tok/char, so a char
  budget C with C*1.016 < 512 is safe. We use X_CHARS = 448 (=> ~454 tok).

  - segment size  < 0.5 * X_CHARS  =>  < 224 chars
  - chunk build (tile-by-cap): the FIRST chunk packs the most segments from
    segment 0 whose total span <= X_CHARS (448); each subsequent chunk packs
    the most segments <= X_CHARS starting where the previous chunk ended
    (contiguous tiling, no segment skipped); the LAST chunk therefore reads
    to the document end, bounded by X_CHARS, with no 1.5X floor requirement.
  - a chunk is labelled 1 iff the document's first_turn_pos char offset
    falls inside the chunk's [start, end) char span.

Segment construction:
  1. split text into sub-sentences by punctuation (.,;:!?\n and CJK 。，；：！？)
     — keep the delimiter attached to the preceding sub-sentence.
  2. split each sub-sentence into <=224-char segments (hard cut, no mid-word
     for latin preferred but char-exact for CJK).

Output schema matches balance_chunks.py's chunk JSONL so train.py / eval_test
/ export_misclassified consume it unchanged:
  {chunk_id, doc_id, topic_id, lang, scenario, turn_type, text,
   start, end, label, turn_offset_in_chunk, n_chars, provenance}

Usage:
  python chunker_v2.py --in corpus/balanced.jsonl --out corpus/balanced.chunks.jsonl \
      --report corpus/balanced.chunks.stats.json --seed 42
"""
from __future__ import annotations
import argparse, json, re
from collections import Counter
from pathlib import Path

# --- parameters (char approximation of token budget) ---
X_CHARS = 448          # <= 512 / 1.016, safe char budget (the chunk cap)
SEG_MAX = 224          # < 0.5 * X_CHARS

# punctuation that ends a sub-sentence (Latin + CJK), delimiter kept attached.
_SENT_SPLIT = re.compile(r'(?<=[.!?,;:\n。！？，；：])')

CJK_RE = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf]')


def split_subsentences(text: str) -> list[str]:
    """Split by sentence-ending punctuation; keep delimiters attached."""
    parts = _SENT_SPLIT.split(text)
    return [p for p in parts if p.strip()]


def split_segments(sub: str, seg_max: int = SEG_MAX) -> list[tuple[int, int]]:
    """Split one sub-sentence into <=seg_max-char segments as (start,end) char
    offsets RELATIVE to the sub-sentence. Hard char cut (CJK-safe)."""
    out = []
    i, n = 0, len(sub)
    if n == 0:
        return out
    while i < n:
        j = min(i + seg_max, n)
        out.append((i, j))
        i = j
    return out


def build_segments(text: str) -> list[tuple[int, int]]:
    """text -> list of (start, end) char offsets of segments covering text."""
    segs = []
    cursor = 0
    for sub in split_subsentences(text):
        # sub may be a slice; find its absolute start
        sub_start = text.find(sub, cursor)
        if sub_start < 0:
            sub_start = cursor
        for (a, b) in split_segments(sub):
            segs.append((sub_start + a, sub_start + b))
        cursor = sub_start + len(sub)
    # absorb any trailing residue (e.g. whitespace after the final delimiter)
    # so the last segment reaches the true document end — keeps the LAST chunk
    # reading to EOF as required.
    if cursor < len(text):
        segs.append((cursor, len(text)))
    return segs


def _grow_to_cap(segs, left, n, cap):
    """Greedily append segments from `left` while total span <= cap.
    Returns the exclusive right index (one past the last included segment)."""
    right = left + 1
    while right < n and (segs[right][1] - segs[left][0]) <= cap:
        right += 1
    return right


def build_chunks_v2(text: str, first_turn_pos):
    """Segment chunker with full, contiguous coverage (tile-by-cap).

    Semantics (user spec):
      - FIRST chunk: from segment 0, pack the MOST segments whose total span
        does not exceed X_CHARS (448). Anchored at the document start (offset 0).
      - MIDDLE chunks: each packs the most segments <= X_CHARS, starting where
        the previous chunk ended (contiguous tiling — no segment is skipped).
      - LAST chunk: the final tile reads to the document end; because it is
        bounded by X_CHARS like every other tile, it never exceeds the cap and
        need not reach any 1.5X floor.

    Every chunk is <= X_CHARS; consecutive chunks share an endpoint segment so
    coverage is contiguous from offset 0 to len(text).
    Returns list of (start, end) chunk char spans, sorted, covering the whole doc.
    """
    segs = build_segments(text)
    if not segs:
        return []
    n = len(segs)
    chunks = []
    left = 0
    while left < n:
        # pack the most segments from `left` whose total span <= X_CHARS
        right = _grow_to_cap(segs, left, n, X_CHARS)
        span = (segs[left][0], segs[right - 1][1])
        if span[1] > span[0]:
            if not chunks or chunks[-1] != span:
                chunks.append(span)
        # contiguous advance: next tile starts at this tile's end segment
        if right >= n:
            break
        left = right
    chunks = sorted(set(chunks))
    return chunks


def label_chunk(start, end, first_turn_pos):
    if first_turn_pos is None or first_turn_pos < 0:
        return 0, None
    if start <= first_turn_pos < end:
        return 1, first_turn_pos
    return 0, None


def iter_docs(path: Path):
    for line in path.open("r", encoding="utf-8"):
        line = line.strip()
        if line:
            yield json.loads(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    inp, outp = Path(args.inp), Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    by_lang = Counter(); by_scenario = Counter(); by_turn_type = Counter()
    n_docs = n_chunks = pos_chunks = neg_chunks = 0
    pos_len = neg_len = 0
    pos_lens = []; neg_lens = []

    with outp.open("w", encoding="utf-8", newline="\n") as f:
        for doc in iter_docs(inp):
            text = doc["text"]
            has_turn = bool(doc["has_turn"])
            ftp = doc.get("first_turn_pos") if has_turn else None
            if has_turn and (ftp is None or ftp < 0 or ftp >= len(text)):
                continue
            n_docs += 1
            spans = build_chunks_v2(text, ftp)
            doc_id = doc["id"]
            for ci, (s, e) in enumerate(spans):
                sub = text[s:e]
                lab, tp = label_chunk(s, e, ftp)
                n_chunks += 1
                if lab:
                    pos_chunks += 1; pos_len += len(sub); pos_lens.append(len(sub))
                else:
                    neg_chunks += 1; neg_len += len(sub); neg_lens.append(len(sub))
                by_lang[doc.get("lang", "en")] += 1
                by_scenario[doc.get("scenario", "analysis")] += 1
                by_turn_type[doc.get("turn_type", "none") if lab else "none"] += 1
                f.write(json.dumps({
                    "chunk_id": f"{doc_id}#{ci}",
                    "doc_id": doc_id,
                    "topic_id": doc.get("topic_id", doc_id),
                    "lang": doc.get("lang", "en"),
                    "scenario": doc.get("scenario", "analysis"),
                    "turn_type": doc.get("turn_type", "none") if lab else "none",
                    "text": sub,
                    "start": s,
                    "end": e,
                    "label": lab,
                    "turn_offset_in_chunk": (tp - s) if tp is not None else -1,
                    "n_chars": len(sub),
                    "provenance": doc.get("provenance", "generated"),
                }, ensure_ascii=False) + "\n")

    def avg(xs): return round(sum(xs) / len(xs), 1) if xs else 0
    stats = {
        "chunker": "v2 segment tile-by-cap (X_CHARS=448 SEG_MAX=224)",
        "documents": n_docs,
        "chunks": n_chunks,
        "pos_chunks": pos_chunks,
        "neg_chunks": neg_chunks,
        "pos_neg_ratio": round(neg_chunks / max(1, pos_chunks), 1),
        "by_lang": dict(by_lang),
        "by_scenario": dict(by_scenario),
        "by_turn_type": dict(by_turn_type),
        "pos_len_avg": avg(pos_lens), "pos_len_min": min(pos_lens) if pos_lens else 0,
        "pos_len_max": max(pos_lens) if pos_lens else 0,
        "neg_len_avg": avg(neg_lens), "neg_len_min": min(neg_lens) if neg_lens else 0,
        "neg_len_max": max(neg_lens) if neg_lens else 0,
    }
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    if args.report:
        Path(args.report).write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())