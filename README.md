# Actus Ville pour Home Assistant

Intégration Home Assistant qui lit le flux RSS d'une page Facebook de mairie (ou tout flux RSS / Atom)
et expose les publications comme un fil de messages, avec un événement « info importante » pour les
coupures d'eau, d'électricité, alertes…

```
Page Facebook ──► rss.app (flux RSS) ──► actus_ville ──► sensor : liste des posts ──► carte Markdown
                                                     └─► event  : nouveau post / info importante ──► notification
```

Aucune dépendance Python à installer : l'intégration n'utilise que la bibliothèque standard et
`aiohttp` déjà fourni par Home Assistant.

## 1. Créer le flux RSS de la page Facebook

Facebook ne fournit pas d'accès aux pages qu'on n'administre pas. Un service tiers s'en charge :

1. Sur [rss.app](https://rss.app), créer un flux à partir de l'adresse de la page Facebook de la ville
   (`https://www.facebook.com/<page-de-la-ville>`).
2. Copier l'URL du flux (`https://rss.app/feeds/xxxxxxxx.xml`).
3. L'ouvrir dans un navigateur : on doit voir du XML avec les publications.

Vérifier les limites de l'offre gratuite (nombre de flux, fréquence de rafraîchissement).
FetchRSS fonctionne aussi : l'intégration accepte n'importe quel flux RSS 2.0 ou Atom.

## 2. Installer dans Home Assistant

Par HACS :

1. HACS > ⋮ > **Dépôts personnalisés**
2. Dépôt : `https://github.com/ThePowerVoid/ha-actus-ville`, type : **Intégration**, puis Ajouter.
3. Ouvrir **Actus Ville** dans HACS > **Télécharger**.
4. Redémarrer Home Assistant.

Les nouvelles versions (releases GitHub) apparaissent ensuite comme mises à jour dans HACS.

Sans HACS, copier `custom_components/actus_ville` dans le dossier `custom_components` du volume
monté sur `/config`, puis redémarrer le conteneur.

## 3. Ajouter l'intégration

Paramètres > Appareils et services > Ajouter une intégration > **Actus Ville**

- **Nom** : `Lyon` (donne le nom des entités)
- **URL du flux RSS** : l'URL rss.app

Le bouton **Configurer** de l'intégration permet ensuite de régler :

| Option | Défaut |
|---|---|
| Intervalle de mise à jour | 30 min |
| Nombre de publications gardées | 10 |
| Mots-clés « info importante » | coupure, interruption, panne, enedis, électricité, eau potable, fuite, gaz, alerte, vigilance, inondation, crue, canicule, restriction |

Un mot-clé est cherché comme mot entier, sans tenir compte des majuscules ni des accents, avec le
pluriel en s ou x : « coupure » trouve « COUPURES », « panne » ne trouve pas « panneau ».

## Entités

Avec Home Assistant en français et le nom « Lyon » :

| Entité | Rôle |
|---|---|
| `sensor.lyon_derniere_publication` | État : date du dernier post. Attribut `posts` : la liste des posts. |
| `event.lyon_nouvelle_publication` | Un événement par nouveau post : `nouveau_post` ou `info_importante`. |

Les identifiants réels sont visibles dans Outils de développement > États.

Chaque post (dans l'attribut `posts` et dans les attributs de l'événement) contient :

| Clé | Contenu |
|---|---|
| `date` | date ISO 8601 (UTC) ou `null` |
| `text` | texte brut, tronqué à 1000 caractères |
| `link` | lien vers la publication |
| `image` | URL de la première image ou `null` |
| `important` | `true` si un mot-clé est présent |
| `keywords` | mots-clés trouvés |
| `id` | identifiant stable du post |

L'attribut `posts` n'est pas enregistré dans l'historique (recorder) pour ne pas alourdir la base.

## 4. Afficher les posts

Coller [`exemples/carte_markdown.yaml`](exemples/carte_markdown.yaml) dans une carte manuelle.
Les infos importantes ont un bandeau orange.

## 5. Notification pour les infos importantes

Importer [`exemples/automatisation_info_importante.yaml`](exemples/automatisation_info_importante.yaml)
et remplacer `notify.mobile_app_mon_telephone` par le service de son téléphone.

## Comportement à connaître

- Au tout premier ajout, les posts déjà présents sont marqués comme lus : pas de rafale de
  notifications. Les posts déjà vus sont mémorisés et survivent aux redémarrages.
- Un nouveau post publié il y a plus de 3 jours ne déclenche pas d'événement.
- Les posts arrivés pendant que Home Assistant était arrêté sont annoncés à la mise à jour suivante.
- Délai total = rafraîchissement de rss.app + intervalle de l'intégration.
- Les URL d'images Facebook expirent : les images des vieux posts peuvent ne plus s'afficher.
- Si le flux est injoignable, le capteur passe « indisponible » et l'intégration réessaie.

## Tests

Les tests du parseur n'ont besoin que de Python :

```bash
python3 -m unittest discover -s tests -v
```
