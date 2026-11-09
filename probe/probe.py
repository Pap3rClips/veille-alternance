import json, re, sys, time
sys.path.insert(0, ".")
from veille.common import session
from veille.sources import WTTJ_APP, WTTJ_KEY
MARK = re.compile(r"(plus disponible|n.est plus|expir|pourvue|cl[oô]tur|d[ée]sactiv|supprim|no longer|plus en ligne|archiv|introuvable|n.existe)", re.I)
d = json.load(open("docs/data/offers.json"))
for o in d["offers"]:
    for l in o["links"]:
        time.sleep(0.4)
        try:
            r = session.get(l["url"], timeout=25, allow_redirects=True)
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
            m = MARK.search(txt)
            snip = txt[max(0, m.start()-60):m.end()+60] if m else ""
            hist = ",".join(str(h.status_code) for h in r.history)
            extra = ""
            if l["source"] == "Welcome to the Jungle":
                oid = l["id"].split(":", 1)[1]
                a = session.get(f"https://{WTTJ_APP.lower()}-dsn.algolia.net/1/indexes/wttj_jobs_production_fr_published_at_desc/{oid}",
                    headers={"X-Algolia-Application-Id": WTTJ_APP, "X-Algolia-API-Key": WTTJ_KEY, "Referer": "https://www.welcometothejungle.com/", "Origin": "https://www.welcometothejungle.com"}, timeout=25)
                extra = f" algolia={a.status_code}"
            print(f"{o['first_seen'][:10]} | {l['source']} | {r.status_code} [{hist}] | {r.url[:110]} | len={len(r.text)}{extra} | {snip[:200]}")
        except Exception as e:
            print(f"{o['first_seen'][:10]} | {l['source']} | EXC {e!r}"[:300])
