# Revue UX — espace de travail scientifique

Date : 29 septembre 2026.

## Références consultées

- [MATLAB — organisation du bureau](https://www.mathworks.com/help/matlab/matlab_env/overview-of-new-desktop-layout.html) : panneaux latéraux, zone de figures, accès aux outils, clavier.
- [AutoCAD — espaces de travail](https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-DidYouKnow/files/GUID-1D87D5C3-21BC-499E-A560-79592348D47E.htm) : commandes groupées par tâche, palettes autour de la zone de travail.
- [Nielsen Norman Group — visibilité de l'état du système](https://www.nngroup.com/articles/visibility-system-status/) : retour d'action, sélection perceptible, état explicite.

## Changements appliqués

- Explorateur à gauche, aperçu physique central, contrôle à droite. Création de projet repliable pour réduire la charge visuelle.
- Sélection signalée par fond et bordure ; titre du projet au-dessus de l'aperçu.
- Action de calcul mise en avant, commandes secondaires neutres, focus clavier et survol visibles.
- Champs sur deux lignes avec unités, aide au survol et validation avant lancement ; budget conforme aux limites du moteur (256 à 10 000 000).
- Actions de session désactivées tant qu'aucun projet n'est sélectionné ; formulaire verrouillé pendant une session.
- Aperçu provenant des articulations physiques, et non d'angles dessinés arbitrairement. Force nulle et indépendance des essais explicitement indiquées.
- Zoom, cadrage, grille métrique (maille 0,5 m) et réinitialisation propres à l'aperçu.
- Mesures du chariot et du premier angle en temps réel ; graphiques vidés lors du changement de projet.
- Arrêt d'évaluation corrigé : conservation du type d'opération avant changement d'état.
- F1 pour l'aide, F5 pour actualiser lorsque le système est disponible.

## Limites explicites

L'aperçu est une simulation indépendante ; il ne montre pas l'entraînement ni la sauvegarde évaluée. Les essais interactifs restent dans une fenêtre 3D séparée. Les panneaux ne sont pas encore déplaçables. Aucun audit de lecteur d'écran ou test utilisateur formel n'a été effectué : ces changements ne constituent pas une certification d'accessibilité ni la garantie d'une UX parfaite.
