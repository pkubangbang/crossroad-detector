from pathlib import Path
DIR=Path(r"C:\Proj\mycc\tools\crossroad-trainer\corpus\inbox\03729236-bcd7-4618-a040-07a0a28cfaf2")
rows=[l for l in (DIR/"_bank2.tsv").read_text(encoding="utf-8").splitlines() if l.strip()]
print("total rows:",len(rows))
from collections import Counter
tts=Counter(r.split("\t")[2] for r in rows if len(r.split("\t"))==5)
print("turn_types:",dict(tts))
bad=[(i+1,len(r.split("\t"))) for i,r in enumerate(rows) if len(r.split("\t"))!=5]
print("malformed rows:",bad[:10])
for i,r in enumerate(rows,1):
    p=r.split("\t")
    if len(p)==5 and "hedged" in p[2]:
        print(i,"HEDGED",p[1],len(p[4].replace("<<T>>","")))
