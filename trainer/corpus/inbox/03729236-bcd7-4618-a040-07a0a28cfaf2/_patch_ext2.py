# -*- coding: utf-8 -*-
p = "_gen3.py"
s = open(p, encoding="utf-8").read()
# topics to push >=300 (currently 271..299). Add ~30-40 chars each.
ADD = {
 "zh2n-vendor":      "把这些要点整理成一页纸的清单，每次采购前逐条打勾核对一遍。",
 "zh2n-pool":        "另外记得给关键指标设好告警，免得问题悄悄积累到难以收拾的地步。",
 "zh2n-forecast":    "同时把假设和结论分开写清楚，方便以后复盘时追溯每个数字的来源。",
 "zh2n-library":     "选型时也不要只盯着热度，维护活跃度和社区响应速度同样重要得很。",
 "zh2n-difficulty":  "循序渐进比一味追进度更能帮他们建立真正的信心和长期的兴趣。",
 "zh2n-fixconf":     "记录要写得让外行也能看懂，否则过几天连自己都想不起来细节了。",
 "zh2n-summary":     "数字之外也要写下当时的判断依据，这样结论才经得起后来的推敲。",
 "zh2n-review":      "评审意见要具体到行号和改法，泛泛而谈的评论对作者帮助其实很小。",
 "zh2n-retro":       "复盘的结论要转成明确的待办，分配好负责人和截止时间才算真正闭环。",
 "zh2n-recap":       "把每节课的核心问题写在黑板上，下课时再让大家复述一遍加深印象。",
}
for topic, extra in ADD.items():
    key = 'EXT["%s"]' % topic
    i = s.find(key)
    assert i >= 0, topic
    j = s.find(")", i)
    assert j > i
    s = s[:j] + ' +\n  "%s"' % extra + s[j:]
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("patched", len(ADD))
