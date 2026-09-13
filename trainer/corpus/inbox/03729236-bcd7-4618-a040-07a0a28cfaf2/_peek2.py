import runpy, sys, re
sys.argv=["_gen3.py"]
# import the module up to the ROWS build by exec
src = open("_gen3.py", encoding="utf-8").read()
# cut before emitter
cut = src.index("OUT = []")
head = src[:cut]
ns = {}
exec(compile(head, "_gen3_head.py", "exec"), ns)
ROWS = ns["ROWS"]
NEG = ns["NEG"]
print("NEG count", len(NEG))
for scen, topic, text in NEG:
    print(topic, len(text))
