# -*- coding: utf-8 -*-
p = "_gen3.py"
s = open(p, encoding="utf-8").read()
anchor = 'for _scen, _topic, _turn, _conj, _text in EN_NEG:'
assert s.count(anchor) == 1, s.count(anchor)
ins = ('for _scen, _topic, _turn, _conj, _text in EN:\n'
'    ROWS.append((_scen, _topic, _turn, _conj, _text))\n')
s = s.replace(anchor, ins + anchor, 1)
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("inserted EN-pos loop before EN_NEG loop")
