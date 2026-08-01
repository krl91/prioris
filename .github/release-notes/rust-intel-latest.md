## PRIORIS Rust Intel __VERSION__

## Première version macOS Intel

- Ajoute une application native `x86_64` construite sur le runner GitHub
  `macos-15-intel`.
- Reprend la GUI, Telegram optionnel, Obsidian et le modèle Ministral 3B GGUF
  embarqué sans serveur ni port.
- Vérifie explicitement l'architecture Intel avec `uname`, `file` et `lipo`.
- Applique la même signature macOS, la même gestion d'App Translocation et les
  mêmes tests post-bundle que la version Apple Silicon.

## Télécharger

- macOS Intel x64 : `prioris-__TAG__-macos-x64.zip`
- Vérification : `SHA256SUMS.txt`

L'archive contient `PRIORIS.app`, la configuration initiale, les scripts,
`ObsidianVault` et le modèle Ministral 3B GGUF. Elle nécessite macOS 13 ou une
version plus récente.

Cette release Intel reste une préversion séparée. Consultez le
[README Rust](https://github.com/__REPOSITORY__/blob/__TAG__/rust/README.md),
le [README principal](https://github.com/__REPOSITORY__/blob/__TAG__/README.md)
et le [guide](https://github.com/__REPOSITORY__/blob/__TAG__/GUIDE.md).
