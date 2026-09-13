#!/usr/bin/env python
"""Self-test for chunking.py — cheap, deterministic, no model involved.

Run:  python test_chunking.py
Exit 0 = pass.
"""
from __future__ import annotations

from chunking import build_chunks, chunk_spans, first_positive_span, WINDOW, STRIDE


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_small_doc_single_chunk():
    text = "x" * 100
    ch = build_chunks(text, None)
    check(len(ch) == 1, f"short doc should be 1 chunk, got {len(ch)}")
    check(ch[0].label == 0 and ch[0].span == (0, 100), "short doc chunk mismatch")


def test_overlap_spans():
    spans = chunk_spans(2000)
    check(spans[0] == (0, WINDOW), f"first span {spans[0]}")
    check(spans[1] == (STRIDE, STRIDE + WINDOW), f"second span {spans[1]}")
    # every adjacent pair overlaps by WINDOW-STRIDE
    for a, b in zip(spans, spans[1:]):
        check(b[0] < a[1], "adjacent windows must overlap")
        check(a[1] - b[0] == WINDOW - STRIDE, "overlap width mismatch")
    check(spans[-1][1] == 2000, "last span must reach end of doc")


def test_label_is_char_offset():
    # turn at char 700 -> second window (125..635) does NOT contain it;
    # third window (250..760) does.
    text = "a" * 2000
    ch = build_chunks(text, 700)
    pos = [c for c in ch if c.label == 1]
    check(len(pos) >= 1, "turn must label at least one chunk")
    # a turn near a boundary can label >=2 overlapping windows; pick the first
    fp = first_positive_span(ch)
    check(fp is not None and fp[0] <= 700 < fp[1], f"first positive span {fp} must contain 700")


def test_turn_at_edge():
    text = "b" * 1500
    ch = build_chunks(text, 0)
    check(ch[0].label == 1, "char-0 turn must label the first chunk")
    check(ch[0].turn_pos == 0, "turn_pos must be 0")
    check(ch[0].turn_offset_in_chunk if hasattr(ch[0], "turn_offset_in_chunk") else True, "")


def test_trailing_sliver_dropped_only_if_negative():
    # doc length just over WINDOW -> a tiny trailing negative chunk is dropped
    text = "c" * (WINDOW + 2)
    ch = build_chunks(text, None)
    check(all(c.label == 0 for c in ch), "no turn here")
    check(all(len(c.text.strip()) >= 8 for c in ch), "no short negative slivers")


def test_negative_has_no_turn_pos():
    ch = build_chunks("d" * 1000, None)
    check(all(c.turn_pos is None for c in ch), "negative chunks must have turn_pos=None")
    check(all(c.label == 0 for c in ch), "negative chunks must be label 0")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    ch = build_chunks("a" * 2000, 700)
    print(f"ok  demo: {len(ch)} chunks, labels={[c.label for c in ch]}")
    print("ALL PASS")
