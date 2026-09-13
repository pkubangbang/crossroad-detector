src = open("_gen3.py", encoding="utf-8").read()
cut = src.index("OUT = []")
ns = {}
exec(compile(src[:cut], "h", "exec"), ns)
for scen, topic, text in ns["NEG"]:
    need = 300 - len(text)
    print("%-22s len=%3d need>=%3d" % (topic, len(text), need))
