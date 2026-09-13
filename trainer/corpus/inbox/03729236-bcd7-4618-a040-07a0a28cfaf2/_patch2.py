from pathlib import Path
p = Path("_gen3.py")
s = p.read_text(encoding="utf-8")
old = "for _scen, _topic, _text in NEG:\n    ROWS.append((_scen, _topic, \"none\", \"\", _text))"
new = "for _scen, _topic, _text in NEG:\n    _text = _text + EXT[_topic]\n    ROWS.append((_scen, _topic, \"none\", \"\", _text))"
assert old in s, "anchor missing"
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8", newline="\n")
print("patched")
