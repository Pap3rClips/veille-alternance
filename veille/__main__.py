"""Collecte les offres, garde les nouvelles, notifie, met à jour docs/data/offers.json.

    python -m veille            passage normal
    python -m veille --dry-run  affiche sans notifier ni écrire
"""
import json
import os
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import sources
from .common import fetch, has_term, norm, today

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data" / "offers.json"
KEEP_DAYS = 90
HEARTBEAT_HOUR = 8  # heure de Paris du résumé quotidien
ERROR_ALERT_AFTER = 3  # passages en échec d'affilée avant alerte
ALTERNANCE_TERMS = ["alternance", "alternant", "alternante", "apprenti", "apprentie", "apprentissage", "contrat pro"]


def classify(title, cfg):
    """Renvoie le profil (dict) correspondant au titre, ou None si l'offre est hors cible."""
    t = norm(title)
    if any(has_term(t, x) for x in cfg["exclude_title"]):
        return None
    for p in cfg["profiles"]:
        if any(has_term(t, k) for k in p["keywords"]):
            return p
    return None


def keep(offer, cfg):
    if not offer.alternance_sure and not any(has_term(norm(offer.title), x) for x in ALTERNANCE_TERMS):
        return None
    company = norm(offer.company)
    if any(has_term(company, x) for x in cfg["exclude_company"]):
        return None
    if offer.published and offer.published < (today() - timedelta(days=cfg["max_age_days"])).isoformat():
        return None
    return classify(offer.title, cfg)


def collect(cfg):
    found, errors = {}, []
    for name, func in sources.ALL.items():
        if not cfg["sources"].get(name):
            continue
        queries = cfg["queries"][:1] if name in sources.SINGLE_CALL else cfg["queries"]
        for q in queries:
            try:
                for o in func(q, cfg):
                    found.setdefault(o.id, o)
            except Exception as e:  # un site en panne ne doit pas bloquer les autres
                errors.append(f"{name} ({q}) : {e}")
                break
    return list(found.values()), errors


def push(topic, title, message, url=None, tags=None, priority=3):
    if not topic:
        return
    body = {"topic": topic, "title": title, "message": message, "tags": tags or [], "priority": priority}
    if url:
        body["click"] = url
        body["actions"] = [{"action": "view", "label": "Postuler", "url": url}]
    fetch("POST", os.environ.get("NTFY_SERVER", "https://ntfy.sh"), json=body)


def main():
    dry = "--dry-run" in sys.argv
    cfg = tomllib.loads((ROOT / "config.toml").read_text(encoding="utf-8"))
    topic = os.environ.get("NTFY_TOPIC", "")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    state = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {"offers": []}
    known = state["offers"]
    first_run = not known
    by_id = {link["id"]: o for o in known for link in o["links"]}
    by_key = {o["key"]: o for o in known}

    # Un changement de profils dans config.toml s'applique aussi aux offres déjà connues.
    for o in known:
        p = classify(o["title"], cfg)
        if p:
            o["profile"], o["cv"] = p["name"], p["cv"]

    raw, errors = collect(cfg)
    fresh = []
    for o in raw:
        if o.id in by_id:
            continue
        profile = keep(o, cfg)
        if not profile:
            continue
        link = {"id": o.id, "source": o.source, "url": o.url}
        key = f"{norm(o.title)}|{norm(o.company)}"
        if key in by_key:  # même offre vue sur un autre site : on ajoute le lien, sans notifier
            by_key[key]["links"].append(link)
            by_id[o.id] = by_key[key]
            continue
        entry = {
            "key": key,
            "title": o.title,
            "company": o.company,
            "location": o.location,
            "profile": profile["name"],
            "cv": profile["cv"],
            "published": o.published,
            "first_seen": now,
            "links": [link],
        }
        known.append(entry)
        by_key[key] = by_id[o.id] = entry
        fresh.append(entry)

    print(f"{len(raw)} offres lues, {len(fresh)} nouvelles, {len(errors)} erreurs")
    for e in errors:
        print("  ERREUR", e)
    for e in fresh:
        print(f"  [{e['profile']}] {e['title']} | {e['company']} | {e['location']} | {e['links'][0]['source']}")
    if dry:
        return

    if first_run:
        push(topic, "Veille alternance activée", f"{len(fresh)} offres déjà en ligne, visibles dans le tableau de bord.", tags=["white_check_mark"])
    else:
        limit = cfg["max_push_per_run"]
        for e in fresh[:limit]:
            push(
                topic,
                f"[{e['profile']}] {e['title']}",
                f"{e['company']} · {e['location']}\n{e['links'][0]['source']} · CV : {e['cv']}",
                url=e["links"][0]["url"],
                tags=["briefcase"],
                priority=4,
            )
        if len(fresh) > limit:
            push(topic, f"{len(fresh) - limit} autres nouvelles offres", "Ouvre le tableau de bord pour les voir.", url=os.environ.get("DASHBOARD_URL"))

    # Résumé du matin : prouve que la veille tourne, même sans nouvelle offre.
    paris = datetime.now(ZoneInfo("Europe/Paris"))
    if paris.hour >= HEARTBEAT_HOUR and state.get("heartbeat") != paris.date().isoformat():
        since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        last_day = sum(1 for o in known if o["first_seen"] >= since)
        push(topic, "Veille active", f"{last_day} nouvelles offres en 24 h, {len(known)} au total.", url=os.environ.get("DASHBOARD_URL"), tags=["sunrise"], priority=2)
        state["heartbeat"] = paris.date().isoformat()

    # Un site en panne plusieurs passages d'affilée déclenche une alerte, une seule fois.
    streak = state.get("error_streak", 0) + 1 if errors else 0
    if streak == ERROR_ALERT_AFTER:
        push(topic, "Veille : site en panne", "\n".join(errors)[:500], tags=["warning"], priority=4)
    state["error_streak"] = streak

    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).isoformat()
    state["offers"] = sorted((o for o in known if o["first_seen"] >= cutoff), key=lambda o: o["first_seen"], reverse=True)
    state["updated"] = now
    state["errors"] = errors
    state["profiles"] = [p["name"] for p in cfg["profiles"]]
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
