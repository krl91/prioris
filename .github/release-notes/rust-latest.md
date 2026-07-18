## PRIORIS Rust __VERSION__

## Correctifs depuis Rust 0.2.4

- Corrige la fermeture immédiate de `PRIORIS.app` lors d'un lancement depuis
  Finder avec App Translocation.
- Place le modèle, la configuration initiale et le vault initial dans
  `Contents/Resources`, à l'intérieur du bundle signé.
- Initialise les données modifiables dans
  `~/Library/Application Support/PRIORIS` sans écraser les changements de
  l'utilisateur lors des lancements suivants.
- Affiche une alerte en cas d'échec au démarrage et écrit le diagnostic dans
  `~/Library/Logs/PRIORIS/prioris.log`.
- Ajoute des tests macOS dédiés au runtime du bundle avant sa publication.

## Télécharger

- macOS Apple Silicon : `prioris-__TAG__-macos-arm64.zip`
- Windows x64 : `prioris-__TAG__-windows-x64.zip`
- Linux x64 : `prioris-__TAG__-linux-x64.tar.gz`
- Vérification : `SHA256SUMS.txt`

Chaque archive contient l'application native, `config.toml`, les scripts de
lancement, `ObsidianVault` et le modèle Ministral 3B GGUF. Sur macOS, ouvre
`PRIORIS.app` : elle initialise automatiquement son espace de travail local.

Cette version Rust reste publiée en préversion et séparée des releases Python.
Consultez le [README Rust](https://github.com/__REPOSITORY__/blob/__TAG__/rust/README.md),
le [README principal](https://github.com/__REPOSITORY__/blob/__TAG__/README.md)
et le [guide](https://github.com/__REPOSITORY__/blob/__TAG__/GUIDE.md).
