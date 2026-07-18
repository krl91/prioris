## PRIORIS Rust __VERSION__

## Nouveautés depuis Rust 0.1.1

- Algorithme v2 commun avec Python : `IMP` explicite en mode express,
  intervalles de robustesse, quadrants possibles et axe pivot.
- Garde-fou sur l'alignement objectif, seuil pépite aligné à 50 et libellés de
  blocage clarifiés.
- Génération GGUF embarquée contrainte par schéma JSON avec `mistral.rs`, sans
  serveur et sans port local.
- Budgets de tokens par opération, température nulle, abstention explicite et
  seuil de confiance.
- `/info` transmet au LLM une présélection déterministe de cinq tâches maximum
  et rejette les identifiants extérieurs.
- Affichage de la robustesse dans la GUI et Telegram ; tests et `clippy` propres.

## Télécharger

- macOS Apple Silicon : `prioris-__TAG__-macos-arm64.zip`
- Windows x64 : `prioris-__TAG__-windows-x64.zip`
- Linux x64 : `prioris-__TAG__-linux-x64.tar.gz`
- Vérification : `SHA256SUMS.txt`

Chaque archive contient le binaire natif, `config.toml`, les scripts de
lancement, `ObsidianVault` et le modèle Ministral 3B GGUF.

Cette version Rust reste publiée en préversion et séparée des releases Python.
Consultez le [README Rust](https://github.com/__REPOSITORY__/blob/__TAG__/rust/README.md),
le [README principal](https://github.com/__REPOSITORY__/blob/__TAG__/README.md)
et le [guide](https://github.com/__REPOSITORY__/blob/__TAG__/GUIDE.md).
