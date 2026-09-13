import re
from pathlib import Path
p = Path("_gen3.py")
s = p.read_text(encoding="utf-8")
old = """    has_turn = (MARK in text) or (turn != "none")
    if has_turn:
        assert MARK in text, ("positive row without marker", topic)
        fpos = text.index(MARK)"""
new = """    has_turn = (MARK in text) or (turn != "none")
    if has_turn:
        if MARK not in text:
            assert conj and conj in text, ("en positive needs conj anchor", topic, conj)
            text = text.replace(conj, MARK + conj, 1)
        fpos = text.index(MARK)"""
assert old in s, "anchor not found"
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8", newline="\n")
print("patched")
