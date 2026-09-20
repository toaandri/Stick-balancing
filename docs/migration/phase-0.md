> Audit initial conservÃ© pour traÃ§abilitÃ©. Les mentions Â« non installÃ©/non compilÃ© Â» ci-dessous dÃ©crivent le dÃ©but de la migration. Ã‰tat actuel et preuves : [validation.md](validation.md). Le laboratoire historique a Ã©tÃ© retirÃ© du workspace Ã  la demande du propriÃ©taire.

# Migration Unity â€” audit et Ã©tat de la phase 0

RÃ©fÃ©rence propriÃ©taire : `correction.txt`, rÃ©vision 3, 19 septembre 2026. Cette dÃ©cision remplace les choix de moteur et dâ€™interface du document de conception historique. Aucun push ni release de cette migration nâ€™est effectuÃ©.

## Ã‰tat rÃ©el

**Phase 0 commencÃ©e, rÃ©ception non atteinte.** Sources et contrats prÃ©parÃ©s ; aucune compilation C#, physique Unity, optimisation PPO ou installation hors ligne nâ€™est attestÃ©e. Le propriÃ©taire confirme que Unity/Hub et Inno Setup ne sont pas installÃ©s.

| Ã‰lÃ©ment | Ã‰tat observÃ© |
| --- | --- |
| DÃ©pÃ´t de dÃ©part | Branche main, HEAD `00e997a`, corrections historiques dÃ©jÃ  poussÃ©es |
| Commit demandÃ© pour comparaison | `c2dd6c9077b7260410dca9662497ee5f84cca5d7`, ancÃªtre local |
| DiffÃ©rence c2dd6c9 â†’ HEAD avant migration | 40 fichiers, +1387/-361 lignes et deux GIF |
| Modifications utilisateur initiales | `correction.txt`, `MUJOCO_LOG.TXT`, `screenshot.png` non suivis ; conservÃ©s |
| AGENTS.md | Aucun trouvÃ© dans lâ€™inventaire du dÃ©pÃ´t |
| Python dÃ©tectÃ© | 3.14 ; incompatible avec le trainer ML-Agents choisi |
| Unity Editor/Hub, Inno Setup | Non installÃ©s, confirmÃ© par le propriÃ©taire |
| .NET | HÃ´te `dotnet` prÃ©sent ; aucun SDK listÃ© |
| Player / runtime privÃ© / Setup.exe | Absents |

### Confrontation aux constats de lâ€™annexe

Lâ€™annexe associe des fichiers de rÃ©ception/GIF et 162 tests au commit c2dd6c9. Localement, ces ajouts appartiennent Ã  `00e997a`, aprÃ¨s ce commit. Les numÃ©ros de lignes et le rÃ©sultat Linux de lâ€™annexe ne doivent donc pas Ãªtre prÃ©sentÃ©s comme une nouvelle vÃ©rification locale de c2dd6c9.

| Constat | Ã‰tat local vÃ©rifiÃ© |
| --- | --- |
| Pas de RL | `controllers/factory.py` fournit none/PID/LQR/horizon fini. Aucun optimiseur de politique dans lâ€™ancien laboratoire |
| DÃ©part prÃ¨s du haut | `simulation/perturbations.py`, `config/default.yaml`, `scripts/run_gui.py` |
| GIF enregistrÃ©s, non apprentissage | `scripts/generate_readme_media.py`, `docs/assets/manifest.json` |
| Rail non bornÃ© physiquement | `simulation/mujoco_model.py`, `analysis/metrics.py` ; conservÃ© comme limitation historique |
| RÃ©ussite finale non pÃ©riodique | `analysis/metrics.py` : critÃ¨re local prÃ¨s de zÃ©ro ; inadaptÃ© au swing-up gÃ©nÃ©ral |
| Sauvegardes de trajectoires | `experiments/runner.py` : NPZ/JSON, aucun checkpoint neuronal |
| DÃ©lai, graine, ordre dâ€™Ã©tat GUI | DÃ©jÃ  corrigÃ©s en `00e997a` ; ne pas rÃ©appliquer les anciennes corrections |
| Installateur absent | Ancienne CI Python uniquement ; aucun binaire autonome |

Les anciennes sources ne sont plus prÃ©sentes dans le workspace. Les nouvelles dÃ©pendances sont isolÃ©es sous `trainer/` et `unity/`.

## Combinaison candidate, pas encore validÃ©e

| Composant | Version candidate | Justification |
| --- | --- | --- |
| Unity Editor Windows x64 | 6000.0.60f1, famille Unity 6.0 LTS | [Fiche officielle de la version](https://unity.com/releases/editor/whats-new/6000.0.60f1) ; validation rÃ©elle encore requise |
| ML-Agents Unity | 3.0.0 / release_22 | [Manifeste de la release](https://github.com/Unity-Technologies/ml-agents/blob/release_22/com.unity.ml-agents/package.json), minimum dÃ©clarÃ© Unity 2023.2 |
| mlagents / mlagents-envs | 1.1.0 | [Version du trainer release_22](https://github.com/Unity-Technologies/ml-agents/blob/release_22/ml-agents/mlagents/trainers/__init__.py) |
| CPython privÃ© | 3.10.11 Windows x64 | Dans lâ€™intervalle 3.10.1â€“3.10.12 imposÃ© par [setup.py](https://github.com/Unity-Technologies/ml-agents/blob/release_22/ml-agents/setup.py) ; ne pas utiliser le Python 3.14 historique |
| PyTorch | 2.1.1+cpu | Variante CPU candidate, respectant la borne du trainer ; disponibilitÃ©/rÃ©solution Windows Ã  confirmer |
| NumPy | 1.23.5 | Intervalle du trainer >=1.23.5,<1.24 |

Les versions directes sont inscrites dans `configs/toolchain.json`, `unity/Packages/manifest.json`, `trainer/requirements.in`. **Ce ne sont pas des verrous de dÃ©pendances transitives rÃ©solus.** Le `packages-lock.json` Unity doit provenir du vÃ©ritable resolve de lâ€™Ã©diteur. Le verrou Python avec hashes et le wheelhouse doivent Ãªtre produits avec le runtime Windows choisi. Aucune fausse matrice Â« validÃ©e Â» nâ€™est fournie.

Le prototype utilise le rendu intÃ©grÃ©, suffisant pour vÃ©rifier la mÃ©canique. URP et UI Toolkit restent la cible dâ€™interface aprÃ¨s validation du cycle Player/trainer ; aucune interface finale nâ€™est prÃ©sentÃ©e comme terminÃ©e.

## Sources prÃ©parÃ©es

- `CartChain.cs` : racine dâ€™articulation immobile, chariot prismatique, articulations revolute passives, une force suivant x. UnitÃ©s SI ; plan x-y Unity, gravitÃ© suivant -y, axes des charniÃ¨res suivant z. Le rail est Ã©levÃ©. Les volumes visibles sont des barres Ã  inertie de pavÃ©, **pas** les capsules MuJoCo : nouvelle validation nÃ©cessaire. Tous les contacts sont explicitement dÃ©sactivÃ©s pour ce prototype.
- `SwingUpAgent.cs` : Agent ML-Agents N=1 ; cinq observations numÃ©riques (x, vitesse, sin/cos de lâ€™orientation, vitesse angulaire), une action continue bornÃ©e, force maintenue entre dÃ©cisions. DÃ©part `[pi, 0, ...]` perturbÃ©, pas `.002 s`, dÃ©cision tous les cinq pas. RÃ©compense dâ€™Ã©lÃ©vation, bonus de maintien et petites pÃ©nalitÃ©s dâ€™effort/course.
- `TaskContract.cs` : angles pÃ©riodiques et vitesses absolues cumulÃ©es ; maintien consÃ©cutif cinq secondes, tolÃ©rance 10Â°, vitesse <0,5 rad/s, horizon 30 s, sortie de rail Ã  Â±2,5 m. Limite de temps â†’ `EpisodeInterrupted`, rÃ©ussite/sortie de rail â†’ `EndEpisode`. Les valeurs sont candidates.
- `BuildPrototype.cs` : crÃ©ation explicite dâ€™une scÃ¨ne de travail et build Windows du worker. Lâ€™environnement partagÃ© peut tourner avec ou sans rendu. Sans trainer, la commande heuristique vaut zÃ©ro ; aucun modÃ¨le prÃ©entraÃ®nÃ© ni LQR cachÃ©.
- `trainer/storage.py` : identitÃ© dâ€™expÃ©rience, empreinte de compatibilitÃ©, Ã©criture atomique des mÃ©tadonnÃ©es avec copie prÃ©cÃ©dente, exclusion mutuelle des trainers. **Cela nâ€™implÃ©mente pas encore les sauvegardes atomiques des checkpoints du trainer.**
- `trainer/launch.py` : vÃ©rification du runtime privÃ© et Player, arguments structurÃ©s sans shell, lancement volontaire dâ€™un essai PPO court, logs distincts de stdout JSON. Le trainer lance le worker. Aucun entraÃ®nement au simple `--check`.
- `configs/ppo-smoke.yaml` : plafond 2048 pas, petit rÃ©seau CPU, un worker. Câ€™est un essai de communication/optimisation, aucune promesse de swing-up.

Le paramÃ©trage des contrats autorise N=1/2/3 pour prÃ©parer les schÃ©mas ; le Player refuse N>1 tant que la physique et lâ€™apprentissage Ã  un segment ne sont pas validÃ©s.

## VÃ©rifications effectuables sans Unity

```powershell
python -m pytest tests/migration -q
python -m trainer.launch --check
```

Le diagnostic retourne actuellement `ready: false`, Â« Unity worker Player is not built Â» et Â« private Python runtime is missing Â». Ce refus est intentionnel ; il ne simule pas un succÃ¨s.

Les tests Python vÃ©rifient la pÃ©riodicitÃ©, le maintien consÃ©cutif, la vitesse, les raisons de fin, la compatibilitÃ©, les Ã©critures de mÃ©tadonnÃ©es et lâ€™exclusion mutuelle. Les tests C# EditMode sont Ã©crits mais **non exÃ©cutÃ©s**. Ils ne prouvent pas la physique. Le test Python utilisant un fichier tÃ©moin de checkpoint ne doit jamais Ãªtre prÃ©sentÃ© comme une preuve de conservation des poids dâ€™une vraie politique.

## Verrous de rÃ©ception Ã  lever dans lâ€™ordre

1. Installer Unity Editor sÃ©lectionnÃ© avec support Windows, rÃ©soudre les packages et compiler ; conserver le verrou gÃ©nÃ©rÃ© et les logs. Ne pas supposer le projet compilable avant cela.
2. Tests physiques PlayMode : chute, force nulle, signe de force, oscillations en bas, inerties, absence de drives, Ã©nergie sans dissipation, reset des coordonnÃ©es rÃ©duites, comparaison dt/2 et solveur. VÃ©rifier la gÃ©omÃ©trie et les axes dans la scÃ¨ne.
3. Assembler CPython privÃ© et toutes les roues natives avec hashes ; rÃ©soudre ML-Agents/PyTorch sans toucher le Python systÃ¨me. RÃ©viser la combinaison si nÃ©cessaire, conserver notices et provenance.
4. EntraÃ®nement court dans un Player construit, sauvegarde dâ€™un **checkpoint initial rÃ©el** avant la premiÃ¨re optimisation et dâ€™un dernier checkpoint complet. Comparer les tenseurs de politique, pas seulement le compteur ou le hash global dâ€™un fichier contenant les compteurs.
5. Reprise dâ€™un checkpoint complet : optimiseur et compteur, budget supÃ©rieur au compteur existant, absence dâ€™Ã©crasement. Le simple flag `--resume` prÃ©parÃ© par le lanceur ne valide pas ce fonctionnement.
6. Ã‰valuation sÃ©parÃ©e par service local, politique dÃ©terministe et normalisation figÃ©es ; 20 seeds fixes, tÃ©moins zÃ©ro/alÃ©atoire/initial, puis seeds de bilan distinctes. **Service non implÃ©mentÃ© Ã  ce stade.**
7. Supervision coopÃ©rative et protocole JSONL : dÃ©marrage/connexion/timeout, arrÃªt/sauvegarde/pause, processus enfants seulement. Le lanceur de dÃ©veloppement attend un essai court terminÃ© naturellement ; il ne fournit pas encore Pause/ArrÃªter fiables.
8. UI Toolkit complÃ¨te et belle scÃ¨ne, donnÃ©es sous persistentDataPath, paramÃ¨tres graphiques et tests DPI/clavier. Ne pas exposer ce lanceur comme application grand public.
9. Setup.exe autonome, notices, checksums, essais sur Windows propre hors ligne. Aucun installateur nâ€™est construit avant la preuve du prototype empaquetÃ©.

Les mÃ©triques initial/meilleur/dernier, la rÃ©tention de checkpoints, lâ€™export/import, lâ€™aperÃ§u par checkpoint et les essais propres sans Python/Unity restent Ã  rÃ©aliser. Aucune campagne longue nâ€™a Ã©tÃ© lancÃ©e, aucun poids nâ€™a Ã©tÃ© entraÃ®nÃ© et rien nâ€™a Ã©tÃ© poussÃ© pour cette migration.

