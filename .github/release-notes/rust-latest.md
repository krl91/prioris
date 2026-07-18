## PRIORIS Rust __VERSION__

## Correctifs depuis Rust 0.2.1

- Les questions anti-biais ne bloquent plus l'entretien lorsqu'une réponse
  conteste leur prémisse ou lorsque le LLM s'abstient. Aucun axe n'est inventé.
- Les réponses courtes `oui`, `non`, `pas du tout` et `tout à fait` sont
  interprétées de manière déterministe avant l'inférence.
- La question miroir reconnaît les conséquences explicitement graves ou
  vitales et reste conservatrice pour les formulations ambiguës.
- Les mêmes règles sont couvertes par les tests Rust et par le test GGUF réel
  exécuté sur les archives macOS, Windows et Linux avant leur publication.

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
