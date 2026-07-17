# PRIORIS v0.4.9

PRIORIS est un assistant personnel d'aide à la décision pour transformer une liste de tâches en priorités expliquées, en plan du jour réaliste et en notes Obsidian synchronisées.

Cette release est pensée pour une installation simple : téléchargez l'archive correspondant à votre système, décompressez-la, puis lancez le script fourni. Le modèle local 3B, le runtime d'inférence sans serveur, la configuration et le vault Obsidian exemple sont inclus dans les bundles complets.

## Nouveautés principales

- **Fix macOS Gatekeeper** : le runtime `llama-simple` est désormais signé avec Hardened Runtime (`--options runtime`), ce qui le place dans la catégorie « développeur non identifié » (bypassable) plutôt que « malware potentiel » sur macOS 14+ Sonoma et 15+ Sequoia.
- **Script `allow-macos.sh`** inclus dans le zip runtime : une seule commande (`chmod +x allow-macos.sh && ./allow-macos.sh`) retire l'attribut quarantaine sans passer par les Réglages Système.
- Les scripts `install_unix.sh` et `run_unix.sh` continuent de retirer automatiquement la quarantaine sur l'intégralité du dossier extrait.

## Quel fichier télécharger ?

Téléchargez un seul fichier dans la section **Assets**, selon votre système :

| Système | Fichier à télécharger | Lancement après extraction |
|---|---|---|
| macOS Apple Silicon | `prioris-macos-arm64.zip` | `./scripts/install_unix.sh` puis `./scripts/run_unix.sh` |
| Windows x64 | `prioris-windows-x64.zip` | `.\scripts\install_windows.ps1` puis `.\scripts\run_windows.ps1` |
| Linux x64 | `prioris-linux-x64.tar.gz` | `./scripts/install_unix.sh` puis `./scripts/run_unix.sh` |

Ne téléchargez pas les assets `runtime-*` seuls pour installer PRIORIS : ils ne contiennent que le runtime d'inférence, pas l'application complète.

## Contenu des bundles complets

Chaque archive `prioris-*` contient :

- l'application PRIORIS ;
- `config.toml` déjà configuré pour la GUI locale et le modèle local ;
- `config.example.toml` pour personnaliser la configuration ;
- le dossier `ObsidianVault` ;
- le modèle local 3B dans `models/` ;
- le runtime `llama-simple` dans `runtime/` ;
- les scripts `scripts/install_*` et `scripts/run_*` ;
- le dossier `wheelhouse/` pour installer les dépendances Python offline ;
- le dossier `tests/` pour vérifier l'archive extraite ;
- la documentation française et anglaise.

## Documentation

- README : https://github.com/krl91/prioris#readme
- Guide d'installation et d'utilisation : https://github.com/krl91/prioris/blob/main/GUIDE.md
- English guide: https://github.com/krl91/prioris/blob/main/GUIDE.en.md

## Vérifications

Cette version a été construite par GitHub Actions. Le workflow exécute les tests avant le build, puis vérifie les archives produites : présence de `config.toml`, `ObsidianVault`, modèle GGUF, runtime `llama-simple`, dossier `tests/`, installation offline, exécution de `python -m pytest` depuis l'archive extraite et absence de binaires serveur/RPC.
