# 🍼 Physiolac Stock Alert — Lyon & France (V2)

Application indépendante de suivi du **Physiolac Bio 1er âge classique, boîte de 800 g, EAN 3518646124167** (0–6 mois). Exclut les variantes Bio AR, épaissie, 2e âge, 400 g. Prévoit un tableau de bord accessible sur ordinateur ou téléphone, une recherche de stocks planifiée, et des alertes **sans Telegram**.

**Important : le ZIP contient le programme et une configuration de déploiement, pas un service déjà mis en ligne.** Tu dois créer ton dépôt GitHub et configurer au moins un canal de notification. Nous n'avons pas validé les stocks en temps réel : les sites peuvent bloquer les robots ou modifier leurs pages.

## 1 — Mode recommandé : surveillance PC éteint + notifications Android ntfy

Pré-requis : un compte [GitHub](https://github.com/), un téléphone Android et l'appli gratuite [ntfy](https://ntfy.sh/).

1. Installe **ntfy** (Google Play ou F-Droid). Dans l'app, abonne-toi à un **topic** / canal à nom aléatoire long, par exemple `physiolac_k7Q4xN9aT2zB6pY8vM3wR`. **Choisis ton propre canal** d'au moins 20 caractères, impossible à deviner. Sur ntfy.sh sans compte, les topics ne sont pas privés : quiconque connaît le nom peut écouter ou publier. Pour une vraie confidentialité, configure un compte/serveur avec droits d'accès.
2. Sur GitHub, crée un **nouveau dépôt public**, par exemple `physiolac-stock-alert`. Le site public affichera la disponibilité des vendeurs, **mais pas** tes secrets de notification. Si tu souhaites un dépôt privé, vérifie les conditions GitHub Pages de ton abonnement.
3. Décompresse le ZIP puis téléverse **le contenu** du dossier `Physiolac-Stock-Alert` à la racine du dépôt, y compris le dossier caché `.github/workflows/`. Le moyen le plus fiable : **GitHub Desktop** ou Git. Ne téléverse **jamais** `config.json` ni tes identifiants.
4. Dans le dépôt : **Settings → Secrets and variables → Actions → Secrets → New repository secret**, crée `NTFY_TOPIC` : colle exactement le topic de l'étape 1.
5. Dans **Settings → Actions → General**, autorise l'exécution des workflows et les permissions d'écriture nécessaires au GITHUB_TOKEN si l'interface te le demande. Dans **Settings → Pages → Build and deployment → Source**, choisis **GitHub Actions** (pas "Deploy from a branch").
6. Va dans **Actions → Physiolac - surveillance et alertes → Run workflow**. Coche `send_test` pour recevoir une notification de test et déclencher le premier contrôle.
7. Dans **Settings → Pages**, ouvre l'URL générée pour consulter les stocks depuis ton téléphone. L'adresse ressemblera à `https://TONCOMPTE.github.io/physiolac-stock-alert/`.

**Cadence** : la tâche tente un contrôle vers `:08` et `:38` de chaque heure (UTC), toutes les 30 minutes, jour et nuit. GitHub Actions **ne garantit pas les horaires** : des exécutions peuvent être retardées ou supprimées. Les exécutions planifiées peuvent être désactivées dans un dépôt public inactif depuis 60 jours. Ce n'est pas un processus qui s'exécute en permanence : c'est un contrôle périodique depuis le cloud.

**Ne pas confondre** : l'icône de rechargement du site GitHub Pages recharge les données existantes. Pour déclencher un vrai contrôle immédiat, ouvre l'onglet **Actions → Run workflow** sur GitHub.

## 2 — Autres options de notification (compatibles entre elles)

Dans GitHub → **Settings → Secrets and variables → Actions**, les paramètres doivent être séparés selon les noms exacts ci-dessous.

| Canal | Paramètres Secrets | Paramètres Variables (facultatives) | Notes |
| --- | --- | --- | --- |
| **ntfy** (recommandé) | `NTFY_TOPIC`, `NTFY_ACCESS_TOKEN` (si serveur avec authentification) | `NTFY_BASE_URL` (défaut `https://ntfy.sh`) | Application Android ; topic long et imprévisible |
| **E-mail SMTP** | `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_TO`, éventuellement `EMAIL_FROM` | `SMTP_HOST`, `SMTP_PORT` (par défaut 587) | Gmail : `smtp.gmail.com`, 587, identifiants + **mot de passe d'application** si disponible sur le compte ; ne pas mettre ton mot de passe Gmail habituel |
| **Discord** | `DISCORD_WEBHOOK_URL` | — | Webhook dans un salon Discord privé ; ne jamais exposer l'URL |
| **Pushover** | `PUSHOVER_TOKEN`, `PUSHOVER_USER` | — | Application dédiée, potentiellement payante |

Les paramètres SMTP peuvent aussi être enregistrés comme *secrets* ; dans ce cas, il faut adapter le workflow pour lire `secrets.SMTP_HOST` et `secrets.SMTP_PORT` au lieu de `vars`.

Pour tester : **Actions → Run workflow**, cocher `send_test`, puis consulter les logs du job si l'alerte n'arrive pas. Le test n'achète rien.

Ne crée jamais de secret directement dans les fichiers `.py`, `.html`, `.json` ou `.yml` du dépôt. Les erreurs détaillées ne montrent pas les identifiants secrets dans le tableau de bord.

## 3 — Boutiques ajoutées

Le fichier `shops.json` contient **15 adresses** :

- **10 fiches produit ciblées pouvant être contrôlées** : Atida, Newpharma, Redcare, Pharmacie Veau, Easypara, Cocooncenter, Pharma GDD, Pharmashopdiscount, Pharmacie de la Poste, **Grande Pharmacie de la Part-Dieu (Lyon 3e)**.
- **5 catalogues ou pages vendeurs complémentaires (NON contrôlés automatiquement)** : Pharmacie de l'Ambre (Lyon 4e), Grande Pharmacie Lyonnaise (Lyon 2e), Pharmacie Gambetta (Lyon 7e), IllicoPHARMA (Oullins), E.Leclerc Parapharmacie. Leur présence dans le tableau de bord aide à accéder aux catalogues, **mais ne prouve pas que le produit exact est disponible**. Aucun de ces cinq catalogues ne déclenche d'alerte.

Pourquoi cette distinction ? Une recherche générale « Physiolac » peut afficher des produits **AR**, épaissis ou de **2e âge** ; un bouton « Ajouter au panier » sur une page de catalogue ne prouve pas la disponibilité du bon produit.

Pour étendre l'analyse automatique d'une pharmacie, obtenir son **URL de fiche produit exacte**, puis remplacer `mode: "catalog"` par `mode: "product"` dans `shops.json`. Vérifier le résultat à la première exécution ; les sites de commerce peuvent empêcher la lecture ou afficher leurs stocks uniquement via JavaScript.

## 4 — Mode local Windows (facultatif)

1. Installe [Python 3.10+](https://www.python.org/downloads/).
2. Décompresse les fichiers, puis double-clique `Demarrer-Windows.bat`.
3. Va à `http://127.0.0.1:8765` ; Paramètres → saisis le même **topic ntfy**, Enregistrer → Envoyer un test.
4. Tu peux aussi configurer l'e-mail ou Discord par variables d'environnement ou par un fichier privé `config.json` non suivi par Git.

En local seulement, la surveillance exige un **PC allumé**.

## 5 — Comportement, limites et sécurité

- Le moniteur cherche les données structurées du vendeur (JSON-LD) ou des signes explicites de disponibilité **sur la fiche produit principale**. `unknown` = site bloqué, résultat ambigu ou catalogue non vérifiable ; **pas** une rupture certaine.
- Les notifications partent à la **première disponibilité confirmée** puis lors d'un retour après **une rupture confirmée**. Une erreur temporaire ou un captcha n'entraîne pas une nouvelle alerte, et une alerte échouée est réessayée au contrôle suivant.
- Un résultat « En stock » est un **indice**, jamais une réservation. Le stock peut changer avant ton achat ; certaines boutiques affichent des disponibilités par magasin.
- Pas de contournement de captcha, pas d'achat automatique, pas de compte boutique, pas d'accès à tes données personnelles. Les requêtes sont limitées à un contrôle toutes les 30 minutes par fiche.
- Le tableau de bord GitHub Pages est **public** dans cette configuration, les **secrets restent dans GitHub Actions**. Le nom de ton topic ntfy ne doit pas être mis dans le tableau de bord.
- Le déploiement n'a pas été testé sur un dépôt GitHub réel depuis cet environnement et la lecture HTTP des vendeurs n'a pas été éprouvée depuis GitHub. Il peut être nécessaire d'adapter certains sites et canaux après le premier test.

## 6 — Vérification locale et fichiers

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python monitor.py --once
python monitor.py --test-alert
```

Fichiers : `monitor.py` (détection et basculements), `notifications.py` (ntfy, e-mail, Discord, Pushover), `shops.json` (adresses), `server.py` et `static/index.html` (interface locale), `.github/workflows/stock-check.yml` (surveillance cloud), `docs` (site statique GitHub Pages), `data/status.json` (données publiques contrôlées).
