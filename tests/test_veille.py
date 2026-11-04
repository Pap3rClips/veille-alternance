"""Tests de la détection des republications et des réglages du filtre.

    python -m unittest discover -s tests
"""
import json
import sys
import tempfile
import tomllib
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from veille import __main__ as veille_main  # noqa: E402
from veille.common import Offer  # noqa: E402

CFG = tomllib.loads((ROOT / "config.toml").read_text(encoding="utf-8"))


def offer(source_id, published, source="Welcome to the Jungle", title="Alternance - Technicien Support Informatique H/F", company="Acme"):
    return Offer(source=source, source_id=source_id, title=title, company=company,
                 location="Paris", url=f"https://exemple.fr/{source_id}", published=published)


class Republication(unittest.TestCase):
    def run_passes(self, *passes):
        """Joue plusieurs passages successifs de la veille ; renvoie l'état final et les notifications."""
        pushed = []
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "offers.json"
            batches = iter(passes)
            with mock.patch.object(veille_main, "DATA", data), \
                 mock.patch.object(veille_main, "today", lambda: date(2026, 11, 4)), \
                 mock.patch.object(veille_main, "collect", lambda cfg: (next(batches), [])), \
                 mock.patch.object(veille_main, "push", lambda topic, title, message, **kw: pushed.append(title)), \
                 mock.patch.object(sys, "argv", ["veille"]):
                for _ in passes:
                    veille_main.main()
                state = json.loads(data.read_text(encoding="utf-8"))
        return state, pushed

    def test_meme_site_nouvel_identifiant_dix_jours_apres(self):
        state, pushed = self.run_passes(
            [offer("a1", "2026-10-22")],
            [offer("a1", "2026-10-22"), offer("a2", "2026-11-03")],
        )
        self.assertEqual(len(state["offers"]), 1)
        e = state["offers"][0]
        self.assertEqual(e["published"], "2026-11-03")
        self.assertEqual(e["reopen_count"], 1)
        self.assertIn("reopened_at", e)
        self.assertEqual(e["links"][0]["id"], "Welcome to the Jungle:a2", "le lien vivant doit passer en premier")
        self.assertEqual(len(e["links"]), 2)
        self.assertTrue(any(t.startswith("Republiée") for t in pushed), pushed)

    def test_copie_sur_un_autre_site_nest_pas_une_republication(self):
        state, pushed = self.run_passes(
            [offer("a1", "2026-10-22")],
            [offer("h9", "2026-11-03", source="HelloWork")],
        )
        e = state["offers"][0]
        self.assertNotIn("reopened_at", e)
        self.assertEqual(len(e["links"]), 2)
        self.assertFalse(any(t.startswith("Republiée") for t in pushed))

    def test_ecart_trop_court(self):
        state, pushed = self.run_passes(
            [offer("a1", "2026-10-30")],
            [offer("a2", "2026-11-03")],
        )
        self.assertNotIn("reopened_at", state["offers"][0])
        self.assertFalse(any(t.startswith("Republiée") for t in pushed))

    def test_sans_date_on_ne_conclut_pas(self):
        state, pushed = self.run_passes(
            [offer("a1", "2026-10-25")],
            [offer("a2", "")],
        )
        self.assertNotIn("reopened_at", state["offers"][0])

    def test_une_seule_notification_par_offre_et_par_passage(self):
        state, pushed = self.run_passes(
            [offer("a1", "2026-10-22")],
            [offer("a2", "2026-11-03"), offer("a3", "2026-11-04")],
        )
        self.assertEqual(sum(t.startswith("Republiée") for t in pushed), 1)

    def test_offre_nouvelle_toujours_notifiee(self):
        state, pushed = self.run_passes(
            [offer("a1", "2026-10-22")],
            [offer("b1", "2026-11-03", title="Alternance Administrateur systèmes et réseaux H/F", company="Autre")],
        )
        self.assertEqual(len(state["offers"]), 2)
        self.assertTrue(any("Administrateur" in t for t in pushed))


class Filtre(unittest.TestCase):
    def profile(self, title):
        p = veille_main.classify(title, CFG)
        return p["name"] if p else None

    def test_maintenance_informatique_reste_visible(self):
        self.assertEqual(self.profile("Technicien de maintenance informatique en apprentissage"), "Support")

    def test_maintenance_hors_it_reste_ecartee(self):
        self.assertIsNone(self.profile("Technicien de maintenance industrielle - alternance"))
        self.assertIsNone(self.profile("Alternant maintenance électrique et systèmes"))

    def test_sante_securite_environnement_ecarte(self):
        self.assertIsNone(self.profile("Apprenti·e Santé Sécurité Environnement H/F"))

    def test_cyber_toujours_classee(self):
        self.assertEqual(self.profile("Alternance Security Officer H/F"), "Cyber")

    def test_ecoles_ecartees(self):
        for company in ("aivancity", "MyDigitalSchool Saint Quentin en Yvelines"):
            o = offer("x", "2026-11-03", title="Assistant Cybersécurité - Alternance H/F", company=company)
            self.assertIsNone(veille_main.keep(o, CFG), company)
        ok = offer("y", "2026-11-03", title="Assistant Cybersécurité - Alternance H/F", company="Capgemini")
        self.assertIsNotNone(veille_main.keep(ok, CFG))


if __name__ == "__main__":
    unittest.main()
