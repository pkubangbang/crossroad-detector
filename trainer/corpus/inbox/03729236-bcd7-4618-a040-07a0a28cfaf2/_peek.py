from pathlib import Path
s = Path("_gen3.py").read_text(encoding="utf-8")
i = s.index("NEG = []")
j = s.index("for _scen, _topic, _text in NEG")
print(s[i:j][:1500])
