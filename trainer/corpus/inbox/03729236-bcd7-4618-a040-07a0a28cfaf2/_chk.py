import re
from pathlib import Path
D=Path(".")
for f in ["_pos17.tsv","_hedged.tsv"]:
    for line in (D/f).read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        p=line.split("\t")
        print(f, p[0], p[1], p[2], "MARKED" if "<<T>>" in p[4] else "NOMARK", len(p[4]))
