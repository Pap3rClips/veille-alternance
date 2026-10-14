# Veille alternance

Collecte les offres d'alternance IT en Île-de-France sur plusieurs sites, garde celles qui collent au profil, envoie une notification sur le téléphone pour chaque nouvelle offre et alimente un tableau de bord.

## Sources

| Site | Accès | État |
|---|---|---|
| Welcome to the Jungle | index de recherche public | actif |
| HelloWork | page de résultats | actif |
| France Travail (inclut les offres APEC et partenaires) | page de résultats | actif |
| La Bonne Alternance | API officielle, clé gratuite | actif dès que `LBA_API_KEY` existe |
| LinkedIn | pages publiques sans compte | désactivé, voir `config.toml` |

## Lancer en local

```bash
pip install -r requirements.txt
python -m veille --dry-run   # affiche ce qui sortirait
python -m veille             # écrit docs/data/offers.json et notifie si NTFY_TOPIC existe
python -m http.server 5180 --directory docs   # tableau de bord sur http://localhost:5180
```

## Mise en service sur GitHub

1. Installe l'application **ntfy** sur le téléphone et abonne-toi à un sujet au nom impossible à deviner (exemple : `alt-hadrien-` suivi de 12 caractères aléatoires). Quiconque connaît ce nom lit les notifications.
2. Pousse ce dossier dans un dépôt GitHub **public** (les minutes Actions y sont gratuites).
3. Dans *Settings → Secrets and variables → Actions*, crée le secret `NTFY_TOPIC` avec le nom du sujet. Ajoute `LBA_API_KEY` si tu as la clé La Bonne Alternance.
4. Dans *Settings → Pages*, publie la branche `main`, dossier `/docs`.
5. Dans l'onglet *Actions*, lance « Veille alternance » une première fois. Ensuite le passage se répète toutes les dix minutes.

## Régler le filtre

Tout se passe dans `config.toml` : recherches, mots exclus, écoles à écarter, profils et CV associé. Le premier profil dont un mot-clé figure dans le titre l'emporte.

## Limites

- GitHub retarde souvent les tâches planifiées de 5 à 15 minutes.
- Le tableau de bord enregistre les statuts (postulée, ignorée) dans le navigateur : le téléphone et le PC tiennent chacun leur liste.
- Un site qui change sa page casse sa source. Le tableau de bord affiche alors « 1 site en erreur ».
