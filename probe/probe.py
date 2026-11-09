import collections, json, sys
sys.path.insert(0, ".")
from veille.sources import is_closed
d = json.load(open("docs/data/offers.json"))
c = collections.Counter()
for o in d["offers"]:
    for l in o["links"]:
        r = is_closed(l)
        c[(l["source"], r)] += 1
        print(l["source"], r, l["url"][-60:])
for k, v in sorted(c.items(), key=str):
    print("TOTAL", k, v)
