# Validation locale â€” 20 septembre 2026

Le prototype fonctionne sur le poste de dÃ©veloppement Windows. Cette validation ne constitue pas une rÃ©ception complÃ¨te de `correction.txt`, ni un essai sur une machine vierge.

## Outils installÃ©s

- Unity Hub 3.21.3 et Unity Editor **6000.0.60f1**. La capture fournie confirme une licence **Personal** activÃ©e le 19/09/2026 dans Unity Hub. Un lancement batch ultÃ©rieur a toutefois renvoyÃ© le code 198 Â« No valid Unity Editor license found Â» : lâ€™activation de Hub doit donc Ãªtre revalidÃ©e pour le compte Windows qui lance les scripts.
- Inno Setup **6.7.3**, installÃ© par utilisateur.
- CPython **3.10.11** privÃ©, ML-Agents/ML-Agents Envs **1.1.0**, PyTorch **2.1.1+cpu**, NumPy **1.23.5**.
- ML-Agents Unity **3.0.0**, Sentis **2.1.0**. Lâ€™archive officielle Sentis est utilisÃ©e explicitement, car le registre de cette version dâ€™Unity substitue une API incompatible.
- Setuptools **70.3.0** : ML-Agents 1.1 utilise `pkg_resources`, absent des versions rÃ©centes initialement rÃ©solues.

Sentis : SHA256 `8764419fdcdec48735d06b6f4c556a44aa3c19440dbcdf5987aa80de35a02155`. La commande `prepare-unity.ps1` contrÃ´le aussi le SHA1 publiÃ© par le registre Unity avant usage.

## RÃ©sultats observÃ©s

| VÃ©rification | Preuve |
|---|---|
| Compilation Unity et construction Windows | Journaux locaux `builds/unity-build.log` et `builds/unity-desktop-build.log` |
| Physique Unity | **13 tests rÃ©ussis**, [rapport XML](unity-tests.xml) |
| RÃ©gression Python aprÃ¨s dÃ©placement du laboratoire | **185 tests rÃ©ussis** : contrats, protocole et tests historiques |
| Optimisation PPO rÃ©elle | **7 tenseurs de politique modifiÃ©s**, variation maximale absolue 0,0385038 |
| Reprise complÃ¨te | Sessions dÃ©marrÃ©es Ã  **0 puis 2 112 Ã©tapes**, checkpoint final **4 196 Ã©tapes** |
| Optimiseur sauvegardÃ© | 13 Ã©tats de paramÃ¨tres, compteur Adam maximum 177 |
| Pause coopÃ©rative | ArrÃªt Ã  **260 Ã©tapes**, checkpoint prÃ©sent et verrou libÃ©rÃ© |
| Ã‰valuation figÃ©e | **20 essais, 0 rÃ©ussite**, poids mÃ©moire et fichier inchangÃ©s |
| Remise en bas pendant le test | **2 resets**, poids inchangÃ©s, arrÃªt coopÃ©ratif rÃ©ussi |
| Service de lâ€™interface | CrÃ©ation rÃ©elle puis session courte terminÃ©e Ã  **537 Ã©tapes** |
| Bundle Windows | Installation silencieuse réussie avant le nettoyage dans `builds/install-smoke` (sortie 0, exécutable et runtime PyTorch privé présents) ; le dossier de test a ensuite été supprimé.

Les preuves lisibles par machine sont [training-proof.json](training-proof.json), [pause-proof.json](pause-proof.json), [evaluation-proof.json](evaluation-proof.json) et [reset-proof.json](reset-proof.json). Un compteur peut dÃ©passer lÃ©gÃ¨rement le budget demandÃ© parce que ML-Agents traite une trajectoire complÃ¨te Ã  la fois.

Le modÃ¨le court **ne maÃ®trise pas le swing-up**. Les 20 essais sont des dÃ©parts perturbÃ©s par une sÃ©quence reproductible de graine 42 ; ils ne constituent pas une campagne indÃ©pendante sur 20 graines dâ€™entraÃ®nement. Les checkpoints initiaux, derniers et meilleurs restent identifiables. Â« Meilleur Â» signifie meilleur parmi les Ã©valuations disponibles, mÃªme si le taux de rÃ©ussite reste nul.

## Physique contrÃ´lÃ©e

MÃ©canique dans le plan Unity x-y, gravitÃ© suivant -y, axes des articulations suivant z. Le chariot porte une barre de longueur 1 m et masse 0,5 kg ; masse du chariot 2 kg. Pas physique 0,002 s, dÃ©cision tous les cinq pas. Les contacts sont dÃ©sactivÃ©s, les charniÃ¨res sont passives, lâ€™action agit uniquement sur le chariot.

Les tests contrÃ´lent repos en bas, chute sans commande, signe de force, saturation, reset, absence de drives, comparaison avec un pas divisÃ© par deux, pÃ©riode des petites oscillations du systÃ¨me chariot/barre libre et dÃ©rive Ã©nergÃ©tique infÃ©rieure Ã  3 % sur quatre secondes sans effort ni dissipation.

## DÃ©fauts trouvÃ©s pendant lâ€™intÃ©gration

- IncompatibilitÃ© Sentis : corrigÃ©e par lâ€™archive officielle verrouillÃ©e, sans modifier le code tiers.
- CrÃ©ation de matÃ©riaux en EditMode : remplacÃ©e par des propriÃ©tÃ©s par rendu et un matÃ©riau partagÃ© conservÃ© dans le Player.
- Lecture bloquante de stdin : elle bloquait la crÃ©ation des workers Windows. Les commandes JSONL sont maintenant lues sans blocage, entre deux avancÃ©es du trainer.
- Canal de statistiques absent dans lâ€™Ã©valuation : ajoutÃ© et vidÃ© aprÃ¨s chaque dÃ©cision.
- Capture dâ€™une fenÃªtre masquÃ©e : image noire ; les contrÃ´les visuels utilisent un rendu rÃ©el de lâ€™application visible.

## Limites et rÃ©ception restante

Lâ€™interface est un premier prototype : son rendu a Ã©tÃ© inspectÃ© et les services quâ€™elle appelle ont Ã©tÃ© exercÃ©s. Cela ne remplace pas un test interactif complet de chaque bouton, du clavier, du DPI et des diffÃ©rentes rÃ©solutions. Lâ€™automatisation native du bureau Ã©tait indisponible pendant cette session.

Restent notamment : apprentissage convergent et bilan multi-seeds, N=2/N=3, camÃ©ra interactive et paramÃ¨tres graphiques, import/export contrÃ´lÃ©, sÃ©lection pÃ©riodique automatique du meilleur modÃ¨le, gestion complÃ¨te des verrous aprÃ¨s crash, installation/mise Ã  jour/dÃ©sinstallation sur une machine propre et vÃ©rification hors ligne sans outils de dÃ©veloppement. Les empreintes des fichiers du bundle ne remplacent pas encore un verrou de tÃ©lÃ©chargement de toutes les wheels.

Lâ€™audit initial est conservÃ© dans [phase-0.md](phase-0.md). Le laboratoire MuJoCo a Ã©tÃ© retirÃ© du workspace Ã  la demande du propriÃ©taire ; lâ€™historique Git garde les fichiers supprimÃ©s jusquâ€™Ã  validation dâ€™un commit. Aucun push ni release de cette migration nâ€™a Ã©tÃ© effectuÃ©.
