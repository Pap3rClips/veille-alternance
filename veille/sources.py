"""Une fonction par site. Chacune prend (query, cfg) et renvoie une liste d'Offer."""
import os
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from .common import Offer, fetch, relative_date

# Clé publique de recherche, lue dans le site welcometothejungle.com.
WTTJ_APP = os.environ.get("WTTJ_ALGOLIA_APP", "CSEKHVMS53")
WTTJ_KEY = os.environ.get("WTTJ_ALGOLIA_KEY", "4bd8f6215d0cc52b26430765769e65a0")

# Code région France Travail et centre de recherche La Bonne Alternance par région.
REGIONS = {
    "Île-de-France": {"ft": "11R", "wttj": "Ile-de-France", "lat": 48.8566, "lon": 2.3522, "radius": 60},
}


def welcometothejungle(query, cfg):
    region = REGIONS[cfg["region"]]["wttj"]
    r = fetch(
        "POST",
        f"https://{WTTJ_APP.lower()}-dsn.algolia.net/1/indexes/wttj_jobs_production_fr_published_at_desc/query",
        headers={
            "X-Algolia-Application-Id": WTTJ_APP,
            "X-Algolia-API-Key": WTTJ_KEY,
            "Referer": "https://www.welcometothejungle.com/",
            "Origin": "https://www.welcometothejungle.com",
        },
        json={
            "query": query,
            "hitsPerPage": 30,
            "filters": f'contract_type:apprenticeship AND offices.state:"{region}"',
        },
    )
    offers = []
    for h in r.json().get("hits", []):
        org = h.get("organization") or {}
        cities = ", ".join(dict.fromkeys(o.get("city") or "" for o in h.get("offices", []))).strip(", ")
        offers.append(
            Offer(
                source="Welcome to the Jungle",
                source_id=h["objectID"],
                title=h.get("name", ""),
                company=org.get("name", ""),
                location=cities,
                url=f"https://www.welcometothejungle.com/fr/companies/{org.get('slug', '')}/jobs/{h.get('slug', '')}",
                published=(h.get("published_at") or "")[:10],
            )
        )
    return offers


def hellowork(query, cfg):
    r = fetch(
        "GET",
        "https://www.hellowork.com/fr-fr/emploi/recherche.html",
        params={"k": query, "l": cfg["region"], "c": "Alternance", "st": "date"},
    )
    soup = BeautifulSoup(r.text, "html.parser")
    offers = []
    for li in soup.select("li[data-id-storage-item-id]"):
        oid = li["data-id-storage-item-id"]
        title = li.select_one('input[name="title"]')
        company = li.select_one('input[name="company"]')
        loc = li.select_one('[data-cy="localisationCard"]')
        if not title:
            continue
        offers.append(
            Offer(
                source="HelloWork",
                source_id=oid,
                title=title.get("value", ""),
                company=company.get("value", "") if company else "",
                location=loc.get_text(strip=True) if loc else "",
                url=f"https://www.hellowork.com/fr-fr/emplois/{oid}.html",
                published=relative_date(li.get_text(" ", strip=True)[-40:]),
            )
        )
    return offers


def francetravail(query, cfg):
    r = fetch(
        "GET",
        "https://candidat.francetravail.fr/offres/recherche",
        params={
            "motsCles": query,
            "natureOffre": "E2",  # contrats d'apprentissage et de professionnalisation
            "lieux": REGIONS[cfg["region"]]["ft"],
            "tri": "1",  # par date
            "offresPartenaires": "true",
        },
    )
    soup = BeautifulSoup(r.content, "html.parser")
    offers = []
    for li in soup.select("li[data-id-offre]"):
        oid = li["data-id-offre"]
        title = li.select_one(".media-heading-title")
        sub = li.select_one("p.subtext")
        date = li.select_one("p.date")
        if not title:
            continue
        span = sub.select_one("span") if sub else None
        location = span.get_text(" ", strip=True) if span else ""
        if span:
            span.extract()
        company = " ".join(sub.get_text(" ", strip=True).split()).rstrip("- ") if sub else ""
        offers.append(
            Offer(
                source="France Travail",
                source_id=oid,
                title=title.get_text(strip=True),
                company=company.strip(),
                location=location.strip(),
                url=f"https://candidat.francetravail.fr/offres/recherche/detail/{oid}",
                published=relative_date(date.get_text(strip=True) if date else ""),
            )
        )
    return offers


def linkedin(query, cfg):
    r = fetch(
        "GET",
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
        params={
            "keywords": f"alternance {query}",
            "location": cfg["region"],
            "f_TPR": "r86400",  # dernières 24 h
            "sortBy": "DD",
            "start": "0",
        },
    )
    soup = BeautifulSoup(r.content, "html.parser")
    offers = []
    for card in soup.select("[data-entity-urn]"):
        oid = card["data-entity-urn"].rsplit(":", 1)[-1]
        title = card.select_one(".base-search-card__title")
        company = card.select_one(".base-search-card__subtitle")
        loc = card.select_one(".job-search-card__location")
        date = card.select_one("time")
        if not title:
            continue
        offers.append(
            Offer(
                source="LinkedIn",
                source_id=oid,
                title=title.get_text(strip=True),
                company=company.get_text(strip=True) if company else "",
                location=loc.get_text(strip=True) if loc else "",
                url=f"https://www.linkedin.com/jobs/view/{oid}",
                published=date.get("datetime", "") if date else "",
                alternance_sure=False,
            )
        )
    return offers


def labonnealternance(query, cfg):
    """API officielle. Cherche par mots du titre : l'API filtre par zone, le tri se fait chez nous."""
    key = os.environ.get("LBA_API_KEY")
    if not key:
        return []
    reg = REGIONS[cfg["region"]]
    r = fetch(
        "GET",
        "https://api.apprentissage.beta.gouv.fr/api/job/v1/search",
        headers={"Authorization": f"Bearer {key}"},
        params={"latitude": reg["lat"], "longitude": reg["lon"], "radius": reg["radius"], "romes": LBA_ROMES},
    )
    offers = []
    for j in r.json().get("jobs", []):
        ident = j.get("identifier") or {}
        offer = j.get("offer") or {}
        work = j.get("workplace") or {}
        addr = ((work.get("location") or {}).get("address")) or ""
        oid = ident.get("id") or ident.get("partner_job_id")
        if not oid or not offer.get("title"):
            continue
        cp = re.search(r"\b\d{5}\b.*", addr)
        offers.append(
            Offer(
                source="La Bonne Alternance",
                source_id=str(oid),
                title=offer["title"],
                company=work.get("name") or work.get("legal_name") or "",
                location=cp.group(0) if cp else addr,
                url=(j.get("apply") or {}).get("url")
                or f"https://labonnealternance.apprentissage.beta.gouv.fr/recherche?q={quote(offer['title'])}",
                published=((offer.get("publication") or {}).get("creation") or "")[:10],
            )
        )
    return offers


# Métiers ROME : systèmes et réseaux, support, sécurité, études et développement, télécoms, data.
LBA_ROMES = "M1801,M1810,I1401,M1802,M1805,M1804,M1806,M1811,M1844"
# La Bonne Alternance ignore le mot-clé : un seul appel par passage suffit.
SINGLE_CALL = {"labonnealternance"}

ALL = {
    "welcometothejungle": welcometothejungle,
    "hellowork": hellowork,
    "francetravail": francetravail,
    "linkedin": linkedin,
    "labonnealternance": labonnealternance,
}
