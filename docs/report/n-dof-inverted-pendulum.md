# Rapport de validation — pendule inversé à N segments

Validation locale : Windows, Python 3.14.2, MuJoCo 3.11.0, NumPy 2.4.1. Les valeurs ci-dessous proviennent des commandes exécutées sur ce dépôt. Elles caractérisent ces scénarios, pas toutes les configurations possibles.

## Référence physique

La chaîne est un ensemble de capsules articulées sur un chariot horizontal. Les angles MuJoCo sont relatifs ; les orientations des segments sont leurs sommes cumulées. La source de vérité est `mj_step`. Le modèle récursif est comparé aux matrices de masse et aux biais MuJoCo ; le modèle symbolique fournit une validation indépendante pour N≤3.

Les essais de référence utilisent `joint_frictionloss=0`, conformément aux articulations sans frottement du cahier des charges. Le frottement est réintroduit explicitement dans les essais de robustesse.

## Résultats mesurés

### Pendule simple, inclinaison de 5°, PID, 10 s

```powershell
python scripts/run_pid_n1.py --N 1 --theta-deg 5 --time 10
```

| Indicateur | Valeur |
| --- | --- |
| Angle final | 0,016° |
| Course maximale | 0,426 m |
| Force maximale | 6,98 N |

Les données, paramètres et courbes sont enregistrés dans `results/pid_n1/`.

### Deux segments, première articulation à 2°, 10 s

```powershell
python scripts/run_dashboard.py --N 2 --theta-deg 2 --time 10
```

| Contrôleur | Réussite finale | Établissement observé | Course maximale | Force maximale | Coût J |
| --- | --- | --- | --- | --- | --- |
| PID | Non | Aucun | ≈1 410 m | 100 N | ≈3,87×10⁷ |
| LQR | Oui | 1,45 s | 0,198 m | 4,81 N | 1,18 |
| Horizon fini | Oui | 1,57 s | 0,213 m | 3,33 N | 1,20 |

Le déplacement extrême du PID provient d’un rail sans butées et d’une commande incapable de stabiliser ce scénario. Il constitue un échec mesuré et explicitement conservé. Ce PID n’est pas une solution générale au système sous-actionné multi-segment.

### Robustesse et limite locale

```powershell
python scripts/run_experiments.py
```

Pour PID N=1, angle initial de 2°, durée 8 s, les essais sans frottement sec et avec `joint_frictionloss=0.01` réussissent au critère final. Les valeurs 0,05 et 0,1 échouent. Avec les autres paramètres par défaut, les délais 0, 1 et 5 pas réussissent dans ce scénario, avec des efforts de contrôle différents. Cela ne garantit pas la réussite pour un délai plus grand ou un autre N.

La recherche locale LQR N=3, durée 8 s, intervalle [0,5° ; 25°], tolérance 0,1°, donne environ **17,822°** après 8 itérations. Ce nombre utilise le critère final de réussite. Il ne constitue ni une preuve de monotonie ni une limite globale du bassin d’attraction ; examiner aussi le balayage des angles et prolonger les essais avant toute conclusion générale.

Le script de scalabilité mesure une durée globale, construction du modèle et du contrôleur incluse. Ses valeurs temporelles dépendent de la machine et de sa charge.

### Démonstrations animées

Les [GIF](../assets/) proviennent de simulations MuJoCo de 6 s : N=1 à 5° pour aucune commande/PID/LQR, puis N=3 à 1° pour LQR/horizon fini. Le [manifeste](../assets/manifest.json) conserve les paramètres et métriques exacts. Les images représentent géométriquement les états simulés et ne sont pas des captures de la fenêtre native.

```powershell
python scripts/generate_readme_media.py
```

## Corrections issues de l’audit

| Défaut trouvé | Correction | Protection contre la régression |
| --- | --- | --- |
| Délai configuré mais ignoré | File de forces réellement appliquée | Séquence exacte avec 2 pas de retard et remise à zéro |
| Graine d’expérience écrasée au reset | Copie des paramètres avec la graine effective | Identité à graine égale et différence à graine distincte |
| Conditions initiales configurées remplacées par zéro | Respect du mode/du vecteur explicite | Essai aléatoire effectivement perturbé |
| Mesures bruitées enregistrées comme vérité physique | Journalisation des états MuJoCo | Équilibre sans commande conservé malgré un bruit de mesure |
| Compensation artificielle des angles dans la réussite | Vérification de chaque orientation absolue | Angles opposés et angles cumulés rejetés |
| Interface modifiant directement les positions | Commande par force via le simulateur partagé | Équivalence temps réel/headless avec fenêtre substituée |
| Mauvais ordre d’état et temps nul dans l’interface | État entrelacé et horloge MuJoCo | Contrôleur espion et comparaison des trajectoires |
| Inertie du modèle de conception approximative | Inertie de capsule et prise en compte armature/amortissement | Comparaison avec MuJoCo sans surcharge manuelle d’inertie |
| Coûts ignorant Q explicite ou comptant un intervalle final fictif | Pondérations cohérentes et intervalles réels | Tests du coût et scénarios comparatifs |
| Résultats sans paramètres conservés | NPZ avec métadonnées et fichier params.json | Aller-retour complet |
| Riccati à horizon fixe recalculé à chaque commande | Gain précalculé une fois | Tests linéaires et non linéaires de l’horizon fini |
| YAML d’expériences sans exécuteur | Script batch et compte rendu d’erreurs | Lot valide/invalide avec fichiers produits |
| Tables omettant le paramètre balayé | Colonnes supplémentaires affichées | Inspection des sorties du rapport |

## Critères de réception et limites

La suite vérifie le modèle jusqu’à N=20 à l’équilibre et la récupération de scénarios perturbés avec PID/LQR/horizon fini. Les tests de réception imposent une orientation de chaque segment inférieure à 1° pendant toute la dernière seconde, une course inférieure à 5 m et une force dans les limites.

La réussite finale exposée par l’API reste un indicateur ponctuel plus faible : elle ne remplace pas cette vérification temporelle. Les grands N, les saturations longues, les perturbations fortes et le frottement nécessitent des études spécifiques. La commande à horizon fini n’est pas un MPC avec contraintes optimisées. L’affichage natif OpenGL/Tkinter reste à vérifier visuellement ; son moteur est testé sans fenêtre. La CI est ajoutée mais son exécution distante n’est pas attestée ici.

```powershell
python -m pytest tests -q --junitxml=results/tests.xml
python -m pytest tests/test_acceptance.py -v
python scripts/run_batch.py
```

Le [README](../../README.md) contient la correspondance complète entre exigences, commandes, paramètres et tests.
