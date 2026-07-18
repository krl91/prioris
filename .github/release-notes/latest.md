# PRIORIS v0.5.2

## Correctif depuis v0.5.1

- Le budget de sortie pour interpréter une réponse libre passe de 96 à 160
  tokens. Cela évite qu'une reformulation un peu détaillée tronque l'accolade
  finale du JSON.
- Un test unitaire verrouille ce budget. Le plafond utilisateur `max_tokens`
  reste prioritaire lorsqu'il est inférieur.
- La même correction est appliquée au port Rust 0.2.1, avec une longueur de
  reformulation bornée par son schéma JSON.

## Télécharger

- macOS Apple Silicon : `prioris-macos-arm64.zip`
- Windows x64 : `prioris-windows-x64.zip`
- Linux x64 : `prioris-linux-x64.tar.gz`
- Vault exemple seul : `ObsidianVault.zip`

Chaque archive OS contient l'application Python, les tests, `ObsidianVault`, le
runtime `llama-simple` sans serveur, le modèle Ministral 3B GGUF et une
configuration prête à démarrer.

Documentation : [README](https://github.com/krl91/prioris/blob/v0.5.2/README.md)
et [guide complet](https://github.com/krl91/prioris/blob/v0.5.2/GUIDE.md).
