## PRIORIS Rust __VERSION__

## Correctifs depuis Rust 0.2.3

- Corrige l'analyse Clippy Linux en conditionnant l'import macOS de `Path`.
- Empêche le workflow Python de traiter les tags et releases `rust-v*`.
- Permet une release macOS gratuite avec signature ad hoc lorsque les secrets
  Apple sont absents ; l'utilisateur autorise une fois `PRIORIS.app` dans les
  réglages de sécurité macOS.
- Inclut `OUVRIR-MACOS.md` avec la procédure bilingue et ne retire jamais la
  quarantaine automatiquement dans la distribution Rust.
- Conserve le chemin Developer ID et notarisation lorsque les six secrets Apple
  sont configurés, et refuse une configuration partielle.
- Remplace la release `rust-v0.2.3`, invalide car elle contenait des artefacts
  Python après le déclenchement incorrect du workflow principal.

## Télécharger

- macOS Apple Silicon : `prioris-__TAG__-macos-arm64.zip`
- Windows x64 : `prioris-__TAG__-windows-x64.zip`
- Linux x64 : `prioris-__TAG__-linux-x64.tar.gz`
- Vérification : `SHA256SUMS.txt`

Chaque archive contient l'application native, `config.toml`, les scripts de
lancement, `ObsidianVault` et le modèle Ministral 3B GGUF. Sur macOS, conserve
ces éléments dans le même dossier et ouvre `PRIORIS.app`.

Cette version Rust reste publiée en préversion et séparée des releases Python.
Consultez le [README Rust](https://github.com/__REPOSITORY__/blob/__TAG__/rust/README.md),
le [README principal](https://github.com/__REPOSITORY__/blob/__TAG__/README.md)
et le [guide](https://github.com/__REPOSITORY__/blob/__TAG__/GUIDE.md).
