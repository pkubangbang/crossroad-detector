import json, re
from pathlib import Path
CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
SID = "03729236-bcd7-4618-a040-07a0a28cfaf2"; SID8 = SID[:8]
DIR = Path(r"C:\Proj\mycc\tools\crossroad-trainer\corpus\inbox\03729236-bcd7-4618-a040-07a0a28cfaf2")
def compute(text):
    no_ws = re.sub(r"\s","",text)
    if not no_ws: return 0,"en"
    cjk=len(CJK.findall(no_ws))
    if cjk/len(no_ws)>=0.5: return len(no_ws),"zh"
    return len([t for t in re.split(r"\s+",text) if t]),"en"
raw=(DIR/"_bank2.tsv").read_text(encoding="utf-8")
docs=[]
for i,line in enumerate(raw.splitlines(),1):
    if not line.strip(): continue
    parts=line.split("\t")
    if len(parts)!=5: raise SystemExit("line %d: %d fields"%(i,len(parts)))
    docs.append(parts)
OUT=[]
for n,(scenario,topic_id,turn_type,conj,text) in enumerate(docs,1):
    has_turn="<<T>>" in text
    if has_turn:
        fpos=text.index("<<T>>"); ct=text.replace("<<T>>",""); tt=turn_type
    else:
        fpos=-1; ct=text; tt="none"
    wc,lang=compute(ct)
    OUT.append({"id":"%s-%s-%04d"%(lang,SID8,n),"text":ct,"has_turn":has_turn,
      "first_turn_pos":fpos,"scenario":scenario,"turn_type":tt,"is_negative":(not has_turn),
      "lang":lang,"word_count":wc,"topic_id":topic_id,"source_model":"deepseek-v4-flash:cloud",
      "peer_session":SID,"provenance":"generated","conjunction":(conj if conj else None),
      "verified_by":[],"verdict":"pending"})
lines=[json.dumps(o,ensure_ascii=False) for o in OUT]
(DIR/"batch_zh_long.jsonl").write_text("\n".join(lines)+"\n",encoding="utf-8",newline="\n")
pos=[o for o in OUT if o["has_turn"]]; neg=[o for o in OUT if not o["has_turn"]]
mism=[(o["id"],len(o["text"])) for o in OUT if len(o["text"])<256]
print("docs=%d pos=%d neg=%d zh=%d"% (len(OUT),len(pos),len(neg),sum(1 for o in OUT if o["lang"]=="zh")))
print("min_chars=",min(len(o["text"]) for o in OUT),"under256=",mism)
if pos: print("posAvg=%.0f"%(sum(len(o["text"]) for o in pos)/len(pos)))
if neg: print("negAvg=%.0f"%(sum(len(o["text"]) for o in neg)/len(neg)))
