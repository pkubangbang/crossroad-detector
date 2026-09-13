from pathlib import Path
from collections import Counter
DIR=Path(r"C:\Proj\mycc\tools\crossroad-trainer\corpus\inbox\03729236-bcd7-4618-a040-07a0a28cfaf2")
for name in ["_bank2.tsv","_head.tsv","_neg.tsv"]:
    p=DIR/name
    if not p.exists(): print(name,"MISSING"); continue
    rows=[l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    tt=Counter(r.split("\t")[2] for r in rows if len(r.split("\t"))==5)
    print(name,"rows=",len(rows),"turn_types=",dict(tt))
