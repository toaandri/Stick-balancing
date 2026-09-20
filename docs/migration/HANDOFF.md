# Passation — suite de `correction.txt`

Ce fichier est destiné à la prochaine IA ou personne qui reprend le dépôt. Il décrit l'état réel après les corrections appliquées. Les anciens résultats MuJoCo ne font plus partie du workspace de travail : le produit cible est Unity + ML-Agents PPO.

## Nettoyage de `builds/`

Les caches et doublons volumineux ont été supprimés pour réduire l'espace disque :
installateurs téléchargés, staging `distribution-preview`, installation smoke-test,
captures, logs et ancien Python d'installation. Sont conservés `builds/tools/Unity`,
`trainer/runtime`, `builds/windows`, `builds/experiments` et `builds/packages`.
Le staging et les captures peuvent être régénérés avec les scripts de packaging.

## Corrections de bugs appliquées

- **`trainer/lock_hashes.py`** : variable `header` non définie à la ligne 111 → remplacée par `lines`.
- **`trainer/desktop.py`** : crash `IndexError` si `events.jsonl` est vide après entraînement → lecture défensive avec vérification. Mauvais mapping du statut : l'event brut était affecté directement au lieu de mapper `paused`/`completed`.
- **`trainer/session.py`** : `trainer.get_step` appelé comme propriété au lieu de méthode → corrigé en `trainer.get_step()`.
- **`trainer/evaluate.py`** : `import yaml` placé au milieu du fichier après une définition de fonction → déplacé en haut du module.
- **`trainer/desktop.py`** : les imports `from .session import main as train`, `from .launch import training_command` et `import yaml` déplacés au niveau module pour permettre le monkeypatching en tests.

## Fonctionnalités ajoutées

### N=2 et N=3 (phases 5 et 6)
- **`SwingUpAgent.cs`** : restriction `segments != 1` levée. Support de 1, 2 ou 3 segments. `BehaviorParameters.VectorObservationSize` mis à jour dynamiquement selon `task.observation_size`. Stats par segment (`Segment1/ErrorDeg`, etc.) ajoutées. Champ `segments` ajouté au journal d'épisodes.
- **`BuildPrototype.cs`** : méthodes `CreateSceneN2`, `CreateSceneN3`, menus `Stick Balancing/Create scene N=2` et `N=3`, méthodes batch `WindowsN2` et `WindowsN3`, helper interne `BuildWorker(int segments)`.
- **`desktop.py`** : argument `--segments` (1/2/3), `TaskConfig` créé avec le bon nombre de segments, nom de behavior dynamique (`StickBalancingN{N}`), migration automatique du nom dans les configs existantes. Champ `segments` retourné dans les réponses `list`, `create` et `train`. Chemin de reprise du checkpoint rendu dynamique.
- **`launch.py`** : recherche de checkpoint à la reprise élargie à tout `checkpoints/**/*.pt` au lieu d'un sous-dossier fixe.

### Interface GUI (DesktopApp.cs)
- Machine à états complète : `Ready / Starting / Training / Paused / Stopping / Evaluating / Testing / Error`.
- Indicateur coloré en header (cyan = entraînement, orange = pause, rouge = erreur, vert = prêt).
- Sélecteur de segments (1 / 2 / 3) à la création.
- Affichage du N de l'expérience sélectionnée.
- Deuxième graphique : taux de réussite des évaluations figées, avec ligne cible à 90 % (18/20).
- Boutons désactivés selon l'état actuel ; libellé du bouton pause adapté (entraînement vs test).
- `WorkerPath(segments)` : résolution du bon exécutable worker selon N.
- Retour du `DesktopApp.cs` au naming cohérent : `StopOwned`, `SetState`, suppression de l'ancien champ `mode`.

## Tests Python

31 tests passent dans `tests/migration/`. Nouveaux tests dans `tests/migration/test_desktop.py` :
- `test_list_returns_empty_for_missing_data_root`
- `test_list_skips_malformed_experiment_json`
- `test_list_returns_valid_experiment`
- `test_train_status_is_paused_when_last_event_is_paused`
- `test_train_status_is_completed_when_last_event_is_completed`
- `test_train_status_is_error_when_events_jsonl_is_empty`
- `test_train_status_is_error_when_events_jsonl_absent`

## Décisions déjà appliquées

- La scène finale est Unity 6000.0.60f1, en 3D, avec ArticulationBody et une action unique de force horizontale sur le chariot.
- Le trainer local utilise ML-Agents 1.1.0, PyTorch 2.1.1 CPU, Python privé 3.10.11 et des checkpoints PPO réels.
- Le démarrage en bas, la récompense d'élévation/stabilisation, la course du rail, le reset physique sans modification des poids et l'évaluation figée sont codés.
- Les checkpoints `initial`, `latest` et `best`, l'optimiseur, les compteurs, le verrou d'expérience et le canal JSONL de supervision existent.
- Un Player desktop, un worker sans rendu et un installateur Inno Setup ont été construits. Le Setup de prévisualisation se trouve sous `packaging/windows/output/`.
- Les captures visibles et le GIF de prototype sont dans `docs/assets/`. Le GIF documente honnêtement un modèle qui n'a pas encore réussi le swing-up.

## Preuves disponibles

- Python : 31 tests passent dans `tests/migration/`.
- Unity : `docs/migration/unity-tests.xml` contient 13 tests réussis lors du dernier lancement licencié.
- PPO : `training-proof.json` prouve la modification de 7 tenseurs ; `pause-proof.json` et `reset-proof.json` prouvent les commandes coopératives.
- Évaluation : `evaluation-proof.json` contient 20 essais figés et 0 succès. Ce résultat est un échec expérimental réel, pas une preuve de convergence.

## Manques prioritaires avant de déclarer la réception

1. **Licence batch Unity** : dans Unity Hub, rester connecté avec le compte Personal, puis lancer `Unity.exe -batchmode -quit -projectPath ... -runTests ...` depuis PowerShell. Si le code 198 revient, corriger l'activation pour le même compte Windows avant toute nouvelle preuve.
2. **Rejouer les tests Unity** après réactivation et confirmer 13/13 dans `docs/migration/unity-tests.xml`. Les nouvelles scènes N=2 et N=3 ont besoin de tests physiques séparés.
3. **Convergence PPO N=1** : lancer une vraie campagne contrôlée (plusieurs seeds, durée explicitement choisie), conserver les journaux. Seuil de réception : au moins 18/20 sur une évaluation séparée, avec maintien de 5 s.
4. **Évaluation multi-seeds** : comparer initial, politique nulle et dernier checkpoint sur les mêmes seeds ; séparer les seeds de sélection du meilleur et celles du bilan final.
5. **N=2 puis N=3** : valider physique, observations, récompense et difficulté séparément. Ne pas transférer les performances de N=1. Les Workers N=2/N=3 doivent être construits et testés.
6. **Interface** : tester réellement redimensionnement, DPI, clavier, états incompatibles, fermeture, deuxième instance, crash du worker et récupération du verrou.
7. **Distribution propre** : installer le Setup sur une machine Windows vierge ou une VM sans Python/Unity, hors ligne, puis créer une expérience, entraîner, fermer, reprendre, tester et reset.
8. **Verrouillage dépendances** : compléter les empreintes de toutes les wheels et les notices de redistribution. Le champ `dependency_lock_complete` reste `false`.
9. **Mesures** : relever étapes/s, RAM, FPS et taille disque sur une machine de référence pour N=1/2/3.

## Commandes de reprise

```powershell
# Tests Python
python -m pytest -q --tb=short

# Vérification du runtime embarqué
python -m trainer.launch --check

# Refaire les tests Unity (après licence batch valide)
.\packaging\windows\test-unity.ps1

# Construire les Players N=1, N=2, N=3 puis le desktop
.\packaging\windows\build-worker.ps1 -UnityEditor .\builds\tools\Unity\Editor\Unity.exe
# Pour N=2 et N=3, utiliser la méthode batch WindowsN2/WindowsN3 dans BuildPrototype.cs

# Construire l'application desktop puis l'installateur
.\packaging\windows\build-desktop.ps1
.\trainer\runtime\python.exe -I .\packaging\windows\stage.py --output .\builds\distribution-preview
.\packaging\windows\build-installer.ps1
```

## Règles de reprise

- Lire `correction.txt` en entier avant modification.
- Ne pas réintroduire MuJoCo, SB3, SAC ou un contrôleur caché dans le produit final.
- Ne pas annoncer « terminé » tant que l'évaluation PPO ne montre pas une compétence mesurée et que l'essai hors ligne sur machine propre n'est pas réalisé.
- Ne pas pousser ni créer de release sans instruction explicite du propriétaire.
- Conserver les preuves JSON/XML, les seeds et les échecs ; un compteur d'étapes seul ne prouve pas l'apprentissage.
- Utiliser `python -m trainer.launch` depuis la racine, pas `python -I trainer/launch.py`.
