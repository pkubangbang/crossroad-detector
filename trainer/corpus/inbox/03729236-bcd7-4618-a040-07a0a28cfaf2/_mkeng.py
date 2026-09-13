from pathlib import Path
DIR=Path(r"C:\Proj\mycc\tools\crossroad-trainer\corpus\inbox\03729236-bcd7-4618-a040-07a0a28cfaf2")
head=[l for l in (DIR/"_head.tsv").read_text(encoding="utf-8").splitlines() if l.strip()]
eng=head[17:23]
(DIR/"_eng.tsv").write_text("\n".join(eng),encoding="utf-8",newline="\n")
print("eng:",len(eng))
