#!/usr/bin/env python
"""test_chunker_v2.py — verify chunker_v2 on short/long/edge-turn docs."""
from chunker_v2 import build_chunks_v2, build_segments

def check(text, ftp, label):
    segs = build_segments(text)
    spans = build_chunks_v2(text, ftp)
    covered = set()
    maxlen = 0
    for s, e in spans:
        for i in range(s, e):
            covered.add(i)
        maxlen = max(maxlen, e - s)
    cov = len(covered) / len(text) if text else 0
    turn_cov = ftp is not None and ftp in covered
    print(f"\n[{label}] doc_len={len(text)} segs={len(segs)} chunks={len(spans)} "
          f"maxlen={maxlen} coverage={cov:.3f} turn@{ftp}_covered={turn_cov}")
    for s, e in spans:
        has = ftp is not None and s <= ftp < e
        print(f"    [{s:>4},{e:>4}) len={e-s:>3} {'TURN' if has else '    '}")

text1 = ('Let me refactor the login path in place since it is the smallest change. '
         'However, tracing the call sites I now think the session store is the real problem, '
         'so we should fix that first. The caching layer looks harmless. On reflection, '
         'though, it is not invalidating correctly.')
check(text1, 83, "SHORT 275 chars, turn@83")

text2 = (('Let me explain the architecture in detail. ' * 25)
         + ('However, on reflection this whole approach is wrong and we must pivot. ')
         + ('So let us redesign from scratch now. ' * 25))
check(text2, 1000, "LONG 2071 chars, turn@1000")

text3 = ('However, pivot now. ' * 5) + ('normal continuation text here. ' * 30)
check(text3, 0, "EDGE-TURN@0")

text4 = 'short.'
check(text4, None, "TINY 6 chars, no turn")

text5 = ('A. ' * 200)  # 400 chars, many tiny segments
check(text5, 100, "MANY-TINY-SEGS 400 chars, turn@100")