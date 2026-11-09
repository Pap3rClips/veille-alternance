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

## Offres republiées

Quand une entreprise remet en ligne, sur le même site, une offre déjà vue (même titre, même entreprise, publiée au moins 7 jours après la précédente), la veille envoie une notification « Republiée » et la carte porte un badge pendant 14 jours. Le besoin est redevenu actif : poste resté vacant ou embauche tombée à l'eau, la veille ne peut pas savoir lequel. Une copie qui apparaît sur un autre site n'est pas comptée, et un site qui rafraîchit la date sans changer l'identifiant de l'offre n'est pas détecté.

## Offres clôturées

À chaque passage, la veille vérifie sur leur site quelques offres déjà connues (25 au plus, chacune au plus deux fois par jour) : page en 404 ou 410 sur France Travail et HelloWork, page HelloWork marquée « expirée », offre retirée de l'index de Welcome to the Jungle. Une offre dont tous les liens sont retirés sort de l'onglet « À postuler » ; dans les autres onglets, elle porte un badge « Clôturée ». Une offre encore présente dans les résultats de recherche, ou republiée, redevient ouverte. Les offres La Bonne Alternance ne sont pas vérifiées.

## Relances

L'onglet « À relancer » liste les candidatures marquées « Postulée » sans suite depuis 7 jours. « Relancée » repousse la suivante de 7 jours, deux relances au maximum. Une relance ne compte pas dans l'objectif du jour.

## Tests

```bash
python -m unittest discover -s tests
```

## Limites

- Les offres republiées ne couvrent qu'une partie des postes qui se libèrent : beaucoup d'entreprises redemandent un profil à leur école ou à leur réseau sans republier d'annonce.
- GitHub retarde souvent les tâches planifiées de 5 à 15 minutes.
- Le tableau de bord enregistre les statuts (postulée, ignorée) dans le navigateur : le téléphone et le PC tiennent chacun leur liste.
- Un site qui change sa page casse sa source. Le tableau de bord affiche alors « 1 site en erreur ».
