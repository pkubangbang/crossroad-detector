# -*- coding: utf-8 -*-
import json, re
SID = "b8867fde-8a8a-4a49-b3fd-7a23c16cd307"
D = "C:/Proj/mycc/machine-learning/crossroad-trainer/corpus/inbox/b8867fde-8a8a-4a49-b3fd-7a23c16cd307/"
DATA = D + "_round3_data.txt"
OUT = D + "batch_round3.jsonl"
CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
def cwc(text):
    no_ws = re.sub(r"\s", "", text)
    c = len(CJK.findall(no_ws))
    if c / max(len(no_ws), 1) >= 0.5: return len(no_ws), "zh"
    return len([t for t in re.split(r"\s+", text) if t]), "en"
lines_out = []
seen = set()
seq = 1
nl = 0
stats = {"pos": [], "neg": []}
for raw in open(DATA, encoding="utf-8"):
    raw = raw.rstrip("\n")
    if not raw.strip(): continue
    kind, sc, tt, tid, cj, text = raw.split("|", 5)
    if cj == "-": cj = None
    if kind == "pos":
        fpos = text.index("@@")
        text = text.replace("@@", "")
    else:
        text = text.replace("@@", "")
        fpos = -1
    wc, lang = cwc(text)
    assert lang == "zh", (lang, text[:20])
    assert len(text) >= 256, (len(text), text[:20])
    assert text not in seen, "dup " + text[:30]
    seen.add(text)
    if kind == "pos":
        has, ine, fv = True, False, fpos
        assert 0 <= fv < len(text)
        frac = fv / len(text)
        assert 0.40 <= frac <= 0.70, ("turn not in 40-70%", tid, round(frac, 3))
    else:
        has, ine, fv = False, True, -1
        nl += 1
    rid = f"zh-{SID[:8]}-{seq:04d}"; seq += 1
    rec = {"id": rid, "text": text, "has_turn": has, "first_turn_pos": fv,
           "scenario": sc, "turn_type": tt, "is_negative": ine, "lang": lang,
           "word_count": wc, "topic_id": tid,
           "source_model": "deepseek-v4-flash:cloud", "peer_session": SID,
           "provenance": "generated", "conjunction": cj,
           "verified_by": [], "verdict": "pending"}
    lines_out.append(json.dumps(rec, ensure_ascii=False))
    stats[kind].append(len(text))
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines_out) + "\n")
for k in ("pos", "neg"):
    v = stats[k]
    print(f"{k}: n={len(v)} avgChars={sum(v)/len(v):.1f} min={min(v)}")
print("total:", len(lines_out))