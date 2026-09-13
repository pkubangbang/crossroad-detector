from pathlib import Path
p = Path("_gen3.py")
s = p.read_text(encoding="utf-8")
# extract EXT block
start = s.index("EXT = {}")
end = s.index("for _scen, _topic, _text in NEG:", start)
ext_block = s[start:end]
# remove it
s2 = s[:start] + s[end:]
# insert EXT block right before the NEG loop
anchor = "for _scen, _topic, _text in NEG:"
idx = s2.index(anchor)
s2 = s2[:idx] + ext_block + s2[idx:]
p.write_text(s2, encoding="utf-8", newline="\n")
print("reordered, len", len(s2))
