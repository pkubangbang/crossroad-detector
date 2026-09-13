# -*- coding: utf-8 -*-
import re
p = "_gen3.py"
s = open(p, encoding="utf-8").read()
# extra on-topic tail to append to the 6 short EXT entries
ADD = {
 "zh2n-fixconf": "以后遇到相似的报错就能第一时间联想到这里的处理方式。",
 "zh2n-summary": "总之结论要清楚，行动项要落到人头上，时间点也要写明白。",
 "zh2n-recap": "把每次作业里卡住的地方记下来，期末复习的时候会特别有用。",
 "zh2n-closing": "这样下次再遇到同类问题，团队里任何人都能快速对照处理。",
 "zh2n-handoff": "交接完成后最好约一个短会当面过一遍，确认对方真的接住了。",
 "zh2n-pause": "带着这个疑问继续听，后面的例子会把答案一点点揭示出来。",
}
for topic, extra in ADD.items():
    key = 'EXT["%s"]' % topic
    i = s.find(key)
    assert i >= 0, topic
    j = s.find(")", i)
    s = s[:j] + ' +\n  "%s"' % extra + s[j:]
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("patched", len(ADD))
