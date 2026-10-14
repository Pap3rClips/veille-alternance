import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})


def fetch(method, url, **kwargs):
    """Requête avec délai de politesse ; lève une exception si le site refuse."""
    for attempt in range(2):  # une seconde chance si la connexion saute
        time.sleep(0.4 + 3 * attempt)
        try:
            r = session.request(method, url, timeout=25, **kwargs)
            break
        except requests.ConnectionError:
            if attempt:
                raise
    r.raise_for_status()
    return r


@dataclass
class Offer:
    source: str
    source_id: str
    title: str
    company: str
    location: str
    url: str
    published: str = ""  # date ISO (AAAA-MM-JJ) quand la source la donne
    alternance_sure: bool = True  # False si la source ne filtre pas sur le contrat
    extra: dict = field(default_factory=dict)

    @property
    def id(self):
        return f"{self.source}:{self.source_id}"


def norm(text):
    """Minuscules sans accents ni ponctuation, pour comparer des titres."""
    text = re.sub(r"\([a-zA-Zèé/·.]{1,6}\)", "", text or "")  # (e), (ne), (trice), (H/F)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9+/]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def has_term(haystack, term):
    """Vrai si `term` figure comme mot entier (ou début de mot pour les racines longues)."""
    term = norm(term)
    if len(term) <= 4:
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack) is not None
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}", haystack) is not None


def today():
    return datetime.now(timezone.utc).date()


def relative_date(text):
    """'il y a 5 jours', 'hier', 'Publié aujourd'hui' -> date ISO. Chaîne vide si illisible."""
    t = norm(text)
    if not t:
        return ""
    if "aujourd" in t or "instant" in t or "heure" in t or "minute" in t:
        return today().isoformat()
    if "hier" in t:
        return (today() - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\s*(jour|semaine|mois)", t)
    if not m:
        return ""
    days = int(m.group(1)) * {"jour": 1, "semaine": 7, "mois": 30}[m.group(2)]
    return (today() - timedelta(days=days)).isoformat()
