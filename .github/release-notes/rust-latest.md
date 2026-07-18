## PRIORIS Rust __VERSION__

## Correctifs depuis Rust 0.2.3

- Corrige l'analyse Clippy Linux en conditionnant l'import macOS de `Path`.
- Empêche le workflow Python de traiter les tags et releases `rust-v*`.
- Exige les six secrets Apple avant toute construction de release macOS Rust.
- Supprime la signature ad hoc et le script de retrait de quarantaine des
  archives officielles ; la signature Developer ID, la notarisation, l'agrafage
  du ticket et l'évaluation Gatekeeper doivent tous réussir.
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
