from pathlib import Path
from collections import Counter
DIR=Path(r"C:\Proj\mycc\tools\crossroad-trainer\corpus\inbox\03729236-bcd7-4618-a040-07a0a28cfaf2")
rows=[l for l in (DIR/"_all.tsv").read_text(encoding="utf-8").splitlines() if l.strip()]
print("rows:",len(rows))
tt=Counter(r.split("\t")[2] for r in rows if len(r.split("\t"))==5)
print("turn_types:",dict(tt))
bad=[(i+1,len(r.split("\t"))) for i,r in enumerate(rows) if len(r.split("\t"))!=5]
print("malformed:",bad)
# short check
shorts=[(i+1,r.split("\t")[1],len(r.split("\t")[4].replace("<<T>>",""))) for i,r in enumerate(rows) if len(r.split("\t"))==5 and len(r.split("\t")[4].replace("<<T>>",""))<256]
print("under256:",len(shorts))
for s in shorts: print("  ",s)
