"""Shared chunking logic for the crossroad detector.

Both gen_chunks.py (training-data derivation) and evaluate.py (inference-time
windowing) import this module so the runtime chunker and the training chunker
are the SAME code. A mismatch here would silently shift the crossroad index.

Design (machine-learning/crossroad-trainer/plan-crossroad-distilbert-chunks.md):
  - model max_position_embeddings = 512  ->  W <= 510 (hard ceiling)
  - stride = window//4  (75% overlap) so a turn near a boundary appears in the
    neighbouring window too
  - labels are CHARACTER offsets, never token indices

WHY THE DEFAULT WINDOW IS SMALLER THAN 510:
  The turn signal is LOCAL -- the classifier answers "is a direction reversal
  happening around this point?". A 510-char window spends ~all of its compute on
  context the label does not depend on, and CPU training cost grows with the
  window. Measured on this machine at batch=16 (fwd+bwd+opt): 0.97s at seq=64,
  1.80s at 128, 3.58s at 256, 7.28s at 512 -- roughly linear in window length.
  128 chars keeps a turn inside one or two windows while staying affordable.
  510 remains available (`--window 510`) for the eventual full-context model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

# DistilBERT positional budget (hard ceiling for any window).
MAX_LEN = 512
# Default working window / stride. See module docstring for the rationale.
# 128 chars = a couple of sentences: enough to contain a local turn plus its
# immediate lead-in, and ~2x cheaper per step than 256, ~4x cheaper than 512.
WINDOW = 128          # W
STRIDE = 32           # overlap = WINDOW - STRIDE = 96 (75%)

# A chunk shorter than this carries too little context to supervise reliably.
MIN_CHUNK_CHARS = 8


@dataclass
class Chunk:
    """One window over `text`, as character offsets [start, end)."""

    start: int          # inclusive char offset into the document
    end: int            # exclusive char offset into the document
    text: str
    label: int          # 1 iff first_turn_pos falls inside [start, end)
    turn_pos: Optional[int]  # absolute char offset of the turn, if inside

    @property
    def span(self) -> tuple[int, int]:
        return (self.start, self.end)


def chunk_spans(n_chars: int, window: int = WINDOW, stride: int = STRIDE) -> List[tuple[int, int]]:
    """Character-offset windows over a document of `n_chars` characters.

    Window size is expressed in CHARACTERS. That is a deliberately conservative
    over-approximation of the token budget for Latin text (a 256-char window can
    tokenize to slightly more than 256 tokens under a cased multilingual vocab),
    so `gen_chunks.py` re-checks each window against the real tokenizer and
    splits any window that exceeds `max_length`. Keeping the lattice in
    characters lets this module stay tokenizer-free and unit-testable.
    """
    if n_chars <= 0:
        return []
    if n_chars <= window:
        return [(0, n_chars)]

    spans: List[tuple[int, int]] = []
    start = 0
    while start < n_chars:
        end = min(start + window, n_chars)
        spans.append((start, end))
        if end >= n_chars:
            break
        start += stride
    return spans


def label_chunk(text: str, start: int, end: int, first_turn_pos: Optional[int]) -> int:
    """1 iff the recorded turn char-offset falls inside [start, end)."""
    if first_turn_pos is None or first_turn_pos < 0:
        return 0
    return 1 if start <= first_turn_pos < end else 0


def build_chunks(
    text: str,
    first_turn_pos: Optional[int],
    window: int = WINDOW,
    stride: int = STRIDE,
    min_chars: int = MIN_CHUNK_CHARS,
) -> List[Chunk]:
    """Derive labelled chunks for one document."""
    out: List[Chunk] = []
    n = len(text)
    spans = chunk_spans(n, window, stride)
    for i, (s, e) in enumerate(spans):
        sub = text[s:e]
        lab = label_chunk(text, s, e, first_turn_pos)
        # Drop a short trailing sliver ONLY when it carries no turn. Keeping it
        # would add a short, label-0 window on every long document and re-create
        # a (milder) length confound at chunk level. A short sliver that DOES
        # contain the turn is kept: the label is what we supervise.
        if (
            lab == 0
            and i == len(spans) - 1
            and i > 0
            and len(sub.strip()) < min_chars
        ):
            continue
        tp = first_turn_pos if (lab == 1) else None
        out.append(Chunk(start=s, end=e, text=sub, label=lab, turn_pos=tp))
    return out


def first_positive_span(chunks: List[Chunk]) -> Optional[tuple[int, int]]:
    """Inference contract: the crossroad index is the START of the first
    positive chunk (see plan doc 'Architecture')."""
    for c in chunks:
        if c.label == 1:
            return c.span
    return None
