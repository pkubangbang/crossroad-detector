from pathlib import Path
DIR=Path(r"C:\Proj\mycc\tools\crossroad-trainer\corpus\inbox\03729236-bcd7-4618-a040-07a0a28cfaf2")
head=[l for l in (DIR/"_head.tsv").read_text(encoding="utf-8").splitlines() if l.strip()]
pos17=head[0:17]
(DIR/"_pos17.tsv").write_text("\n".join(pos17),encoding="utf-8",newline="\n")
print("pos17:",len(pos17))
