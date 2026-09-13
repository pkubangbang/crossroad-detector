from pathlib import Path
p = Path("_gen3.py")
s = p.read_text(encoding="utf-8")
start = s.index("EXT = {}")
ext_block = s[start:]
# strip trailing whitespace-only
ext_block = ext_block.rstrip() + "\n"
s2 = s[:start].rstrip() + "\n"
loop_anchor = "for _scen, _topic, _text in NEG:"
idx = s2.index(loop_anchor)
s2 = s2[:idx] + ext_block + "\n" + s2[idx:]
p.write_text(s2, encoding="utf-8", newline="\n")
print("done len", len(s2))
import py_compile
py_compile.compile("_gen3.py", doraise=True)
print("compiles OK")
