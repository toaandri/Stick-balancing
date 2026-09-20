# Prototype Unity — sources non compilées

Ce dossier prépare la phase 0 de la migration. L’application finale et son interface ne sont pas encore livrées. Voir [l’état de réception](../docs/migration/phase-0.md).

## Outils développeur à installer

Unity Hub puis **Unity Editor 6000.0.60f1**, avec support Windows. La version est candidate et doit être testée avec ML-Agents 3.0.0. Python 3.14 du laboratoire historique ne convient pas au trainer 1.1.0 ; son futur runtime privé cible CPython 3.10.11 x64. Aucun outil n’a été installé automatiquement.

1. Ajouter `unity/` comme projet dans Hub et ouvrir avec l’éditeur choisi.
2. Attendre la résolution des packages. Conserver `Packages/packages-lock.json` généré ; ne pas le fabriquer manuellement.
3. Corriger toute erreur de compilation avant d’aller plus loin. Aucun résultat de compilation n’est encore disponible.
4. Menu **Stick Balancing → Create phase-0 scene**. Cette commande crée/remplace uniquement la scène générée `Assets/Scenes/Prototype.unity`.
5. Ouvrir **Window → General → Test Runner**, exécuter les tests EditMode. Puis ajouter/exécuter les validations physiques décrites dans l’audit ; les tests de contrat seuls ne suffisent pas.

Dans la scène sans trainer, la commande est nulle. Cela ne représente ni un agent entraîné ni une interface produit.

## Construction développeur

Depuis la racine du dépôt :

```powershell
./packaging/windows/build-worker.ps1 -UnityEditor 'C:/Program Files/Unity/Hub/Editor/6000.0.60f1/Editor/Unity.exe'
```

Sortie prévue : `builds/windows/worker/StickBalancingWorker.exe` avec ses données Unity adjacentes. Ne pas distribuer l’exécutable seul. Le script est préparé, **non exécuté**, faute d’éditeur.

Après assemblage et validation du runtime privé :

```powershell
python -m trainer.launch --check
python -m trainer.launch --train --data-root "$env:LOCALAPPDATA/StickBalancing/PrototypeExperiments"
```

Le Python système ci-dessus exécute uniquement l’outil développeur. Le processus d’apprentissage utilise le chemin absolu du **runtime privé**. Le futur produit ne doit plus exiger cette commande ni Python système. Le lanceur refuse les outils absents ou incompatibles et ne télécharge rien. Un entraînement de 2048 pas ne démontre pas la maîtrise de la tâche.

Les sources `.meta` sont fournies pour les assets actuels. Après génération de la scène dans Unity, conserver également ses nouveaux `.meta` et les réglages générés à vérifier. Le rendu est volontairement minimal avant validation technique ; URP/UI Toolkit viendront dans la phase interface.
