## PRIORIS Rust __VERSION__

## Correctifs depuis Rust 0.2.2

- L'archive macOS contient maintenant `PRIORIS.app`, lançable par double-clic,
  au lieu d'exposer un binaire nu à Finder.
- Le bundle et son Mach-O sont signés avec un certificat Developer ID
  Application, Hardened Runtime et horodatage Apple ; la signature ad hoc a été
  supprimée.
- Le workflow soumet l'application à `notarytool`, agrafe et valide le ticket,
  puis exige une évaluation Gatekeeper `spctl` réussie avant publication.
- L'application ouverte depuis Finder retrouve automatiquement `config.toml`,
  le modèle GGUF et `ObsidianVault` dans le dossier extrait.
- Une release Rust est désormais refusée si les identifiants Apple manquent ou
  si la signature, la notarisation ou un contrôle de lancement échoue.

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
