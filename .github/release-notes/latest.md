# PRIORIS v0.4.12

PRIORIS est un assistant personnel d'aide à la décision pour transformer une liste de tâches en priorités expliquées, en plan du jour réaliste et en notes Obsidian synchronisées.

Cette release est pensée pour une installation simple : téléchargez l'archive correspondant à votre système, décompressez-la, puis lancez le script fourni. Le modèle local 3B, le runtime d'inférence sans serveur, la configuration et le vault Obsidian exemple sont inclus dans les bundles complets.

## Nouveautés principales

- **Réponses libres LLM sur tout l'entretien** : en GUI et Telegram, quand le
  LLM est disponible, l'utilisateur peut répondre en texte libre à toutes les
  questions à choix. PRIORIS interprète, propose l'option comprise, puis demande
  confirmation avant toute écriture ou recalcul.
- **Fallback boutons si le LLM est KO/offline** : aucun blocage utilisateur,
  l'interface explique l'échec et conserve le mode boutons.
- **Challenge anti-biais après l'instinct** : la réponse à « Instinctivement,
  tu la classes comment ? » ne force pas le score. Elle sert à générer 3
  questions ciblées pour vérifier vraie urgence, pression sociale, manque
  d'information ou importance sous-estimée.
- **Clarifications et question miroir en texte libre** : le LLM peut aussi
  interpréter ces réponses dynamiques, toujours avec confirmation.
- **Fix dylib Team ID macOS (Hardened Runtime)** : avec `--options runtime`, macOS vérifie que les dylibs chargées ont le même Team ID que le binaire. Les deux étant signés en ad-hoc indépendamment, macOS les rejetait avec `different Team IDs`. Fix : entitlement `com.apple.security.cs.disable-library-validation` ajouté à la signature de `llama-simple`.
- **Fix dylib rpath macOS** : `@executable_path` ajouté via `install_name_tool` pour que `dyld` trouve `libllama.0.dylib` dans le même répertoire que le binaire.
- **Test unitaire** `tests/test_runtime_macos.py` : vérifie le rpath et l’entitlement sur macOS — ces deux régressions seront désormais détectées automatiquement dans le CI.
- **Fix macOS Gatekeeper** : signature Hardened Runtime pour le bypass via Réglages Système.
- **Script `allow-macos.sh`** inclus dans le zip runtime.

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
