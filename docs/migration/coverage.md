# Couverture de `correction.txt`

Audit des sources et preuves réalisé le 20 septembre 2026. `Partiel` signifie que
le code existe mais que la preuve de réception demandée par le cahier des charges
manque encore.

| Section | Sujet | État réel |
|---:|---|---|
| 0 | Audit, migration progressive, pas de release implicite | Partiel : audit documenté, aucune release ; migrations Git non commitées |
| 1 | Objectif scientifique, départ bas, agent local | Partiel : contrat et trainer présents, compétence PPO non démontrée |
| 2 | Stack Unity/ML-Agents/PPO verrouillée | Partiel : versions choisies ; empreintes et notices complètes manquantes |
| 3 | Player + trainer autonome sans éditeur | Partiel : Player/runtime construits ; validation hors ligne machine propre manquante |
| 4 | Physique Unity et contrôles | Partiel : 13 tests historiques réussis ; batch Unity à rejouer après licence |
| 5 | Observations, actions, reset, épisodes | Implémenté pour N=1 ; N=2/N=3 non réceptionnés |
| 6 | Critères, évaluation figée, preuves de progrès | Partiel : 20 essais figés à 0/20, multi-seeds et seuil 18/20 manquants |
| 7 | GUI 3D et accessibilité | Partiel : prototype visible ; UXML/USS, clavier, DPI, états et écrans manquants |
| 8 | Boutons et machine à états | Partiel : train/pause/reset/test présents ; import/export, aide, paramètres et crash recovery manquants |
| 9 | Sauvegarde/reprise et données utilisateur | Partiel : checkpoints/optimiseur/verrou présents ; compatibilité et reprise après crash à tester |
| 10 | Performance et processus | Partiel : supervision locale présente ; mesures RAM/FPS/étapes/s et tests multi-instance manquants |
| 11 | Setup.exe autonome Windows | Partiel : Setup construit et smoke-testé ; machine propre hors ligne et notices complètes manquantes |
| 12 | Migration et phases N=1/2/3 | N=1 prototype ; N=2/N=3 non validés ; ancien `legacy/` supprimé sur instruction du propriétaire |
| 13 | Critères de réception | Non atteint : plusieurs preuves listées ci-dessus manquent encore |
| 14 | Sources techniques | Références présentes ; compatibilité batch et distribution restent à revalider |
| 15 | Recherche GUI web et application | Références et règles écrites ; implémentation UXML/USS et tests ergonomiques restent à faire |

La suite Python actuelle passe à 24/24. Ce résultat ne remplace aucune des validations
Unity, PPO, GUI ou Windows indiquées comme partielles.
