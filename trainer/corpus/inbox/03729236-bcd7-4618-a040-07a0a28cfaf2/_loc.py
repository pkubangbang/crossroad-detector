from pathlib import Path
s = Path("_gen3.py").read_text(encoding="utf-8")
print("EXT at", s.index("EXT = {}"))
print("NEG loop at", s.index("for _scen, _topic, _text in NEG"))
print("EN append at", s.index("EN = []"))
print("OUT at", s.index("OUT = []"))
print("---- region 130-175 ----")
for i,l in enumerate(s.splitlines()[130:175],131):
    print(i, l[:70])
