# Recherche GUI — références et décisions

Mise à jour : 20 septembre 2026.

La recherche a été faite avant de formaliser la suite GUI dans `correction.txt`.

## Références consultées

- [Unity UI Toolkit](https://docs.unity3d.com/Manual/UIElements.html) : Unity recommande UI Toolkit pour les nouvelles interfaces et sépare structure UXML, styles USS et logique runtime.
- [Guide UI Toolkit avancé pour Unity 6](https://docs.unity3d.com/Manual/best-practice-guides/ui-toolkit-for-advanced-unity-developers/bpg-uiad-index.html) : architecture réutilisable, performances et workflow de production.
- [Microsoft Fluent 2](https://fluent2.microsoft.design/) : hiérarchie, navigation et états accessibles pour les logiciels de bureau.
- [Material Design 3](https://m3.material.io/) : navigation, feedback, focus et accessibilité comme références complémentaires.

## Décisions appliquées au projet

- Garder une interface de laboratoire sombre avec une hiérarchie stable : expérience à gauche, vue 3D au centre, état et commandes à droite, métriques en bas.
- Utiliser des libellés français explicites, les unités physiques, le checkpoint sélectionné et l’origine du modèle.
- Réserver cyan à l’activité, vert à la réussite et orange aux alertes, toujours avec texte ou icône.
- Prévoir des états visibles pour démarrage, entraînement, pause, évaluation, erreur et arrêt.
- Conserver UI Toolkit et déplacer progressivement la structure/style vers des assets UXML/USS réutilisables au lieu de multiplier les contrôles construits en C#.

## Vérifications restantes

Tester 1280x720, 1920x1080 et facteur Windows 150 %, navigation clavier, focus visible,
états disabled/loading/error, seconde instance, crash worker et récupération du verrou.
Capturer chaque état dans le README et mesurer le coût de mise à jour UI pendant le PPO.
