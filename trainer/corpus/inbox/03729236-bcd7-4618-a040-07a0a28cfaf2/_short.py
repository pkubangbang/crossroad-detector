from pathlib import Path
DIR=Path(r"C:\Proj\mycc\tools\crossroad-trainer\corpus\inbox\03729236-bcd7-4618-a040-07a0a28cfaf2")
for i,line in enumerate((DIR/"_bank2.tsv").read_text(encoding="utf-8").splitlines(),1):
    if not line.strip(): continue
    parts=line.split("\t")
    text=parts[4].replace("<<T>>","")
    if len(text)<256:
        print(i, len(text), parts[1], parts[2])
