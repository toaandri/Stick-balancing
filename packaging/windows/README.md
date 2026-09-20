# Distribution Windows

Un bundle de prévisualisation local et son installateur Inno Setup peuvent être construits. Ils regroupent l’interface Unity, le worker, le runtime Python privé, le trainer, la configuration et les notices disponibles. L’installateur place l’application sous le profil de l’utilisateur ; les expériences restent dans `persistentDataPath` et ne sont jamais supprimées à la désinstallation.

Ce n’est pas une release : le prototype ne démontre pas encore un swing-up réussi, N=2/N=3 ne sont pas validés, et l’installation sur une machine Windows vierge hors ligne reste à contrôler.

Depuis la racine du dépôt :

```powershell
# Construit les deux Players après activation de la licence Unity.
.\packaging\windows\build-desktop.ps1
.\packaging\windows\build-worker.ps1 -UnityEditor .\builds\tools\Unity\Editor\Unity.exe

# Assemble les fichiers puis crée le Setup.exe.
.\trainer\runtime\python.exe -I .\packaging\windows\stage.py --output .\builds\distribution-preview
.\packaging\windows\build-installer.ps1
```

Le résultat est `packaging/windows/output/StickBalancing-Prototype-Setup.exe`. `bundle-manifest.json` contient les tailles et SHA-256 de chaque fichier livré. `notices/` contient les notices de licences collectées par le script ; celles qui ne peuvent pas être déterminées automatiquement doivent être revues avant une diffusion publique.

Le bundle ne télécharge pas de dépendance, ne modifie pas `PATH` et ne lance pas `pip`. Une mise à jour du code existant peut être recopiée dans un staging déjà vérifié avec :

```powershell
.\trainer\runtime\python.exe -I .\packaging\windows\stage.py --output .\builds\distribution-preview --refresh-code
```

La licence Unity est requise pour reconstruire les Players, pas pour exécuter l’application déjà construite. L’éditeur doit être réactivé si les builds ou les tests Unity échouent avec « No valid Unity Editor license found ».
