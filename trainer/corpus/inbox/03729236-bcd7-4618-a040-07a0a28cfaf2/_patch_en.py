# -*- coding: utf-8 -*-
p = "_gen3.py"
s = open(p, encoding="utf-8").read()
old = '''for _scen, _topic, _turn, _conj, _text in EN:
    ROWS.append((_scen, _topic, _turn, _conj, _text))
EN.append(("coding","en2-lock-order-neg","none","wait for",'''
new = '''EN_NEG = []
EN_NEG.append(("coding","en2-lock-order-neg","none","wait for",'''
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
# rename remaining EN.append( for negatives to EN_NEG.append(
import re
# after the first replacement, the remaining negative appends start with EN.append(("planning","en2-vendor-neg" ...
for topic in ["en2-vendor-neg","en2-pool-neg","en2-summary-neg","en2-recap-neg","en2-review-neg"]:
    marker = 'EN.append(("%s"' % ""  # placeholder
# simpler: replace the specific remaining EN.append for the 5 negatives
for k in ['"planning","en2-vendor-neg"','"debugging","en2-pool-neg"','"analysis","en2-summary-neg"','"teaching","en2-recap-neg"','"coding","en2-review-neg"']:
    s = s.replace('EN.append((%s' % k, 'EN_NEG.append((%s' % k)
# fix the final loop: iterate first 5 positives (EN) then EN_NEG
old2 = '''for _scen, _topic, _turn, _conj, _text in EN:
    ROWS.append((_scen, _topic, _turn, _conj, _text))
OUT = []'''
new2 = '''for _scen, _topic, _turn, _conj, _text in EN_NEG:
    ROWS.append((_scen, _topic, _turn, _conj, _text))
OUT = []'''
assert s.count(old2) == 1, ("loop2", s.count(old2))
s = s.replace(old2, new2)
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok")
