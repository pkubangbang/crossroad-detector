from pathlib import Path
DIR=Path(r"C:\Proj\mycc\tools\crossroad-trainer\corpus\inbox\03729236-bcd7-4618-a040-07a0a28cfaf2")
rows=[l for l in (DIR/"_bank2.tsv").read_text(encoding="utf-8").splitlines() if l.strip()]
pos=rows[0:17]      # 17 positive rows
eng=rows[45:51]     # 6 english rows (indices 45..50)
# write positives+english as the fixed head
(DIR/"_head.tsv").write_text("\n".join(pos+eng),encoding="utf-8",newline="\n")
print("head rows:",len(pos+eng))
