# PRIORIS v0.5.3

## Correctifs depuis v0.5.2

- Les questions anti-biais ne bloquent plus l'entretien lorsqu'une réponse
  conteste leur prémisse ou lorsque le LLM s'abstient. La contestation est
  conservée sans inventer de modification du score.
- Les réponses fermées courtes comme `oui`, `non`, `pas du tout` et
  `tout à fait` sont reconnues de manière déterministe avant tout appel LLM.
- La dernière question miroir reconnaît les conséquences explicitement graves
  ou vitales, tout en laissant les réponses ambiguës au LLM ou aux boutons.
- Une réponse qui corrige une prémisse et apporte aussi un fait exploitable peut
  toujours produire une proposition d'axe, soumise à confirmation.
- La suite compte désormais 225 tests. Les archives sont en plus vérifiées
  après construction avec le véritable modèle GGUF embarqué sur chaque OS pour
  ces trois régressions.

## Télécharger

- macOS Apple Silicon : `prioris-macos-arm64.zip`
- Windows x64 : `prioris-windows-x64.zip`
- Linux x64 : `prioris-linux-x64.tar.gz`
- Vault exemple seul : `ObsidianVault.zip`

Chaque archive OS contient l'application Python, les tests, `ObsidianVault`, le
runtime `llama-simple` sans serveur, le modèle Ministral 3B GGUF et une
configuration prête à démarrer.

Documentation : [README](https://github.com/krl91/prioris/blob/v0.5.3/README.md)
et [guide complet](https://github.com/krl91/prioris/blob/v0.5.3/GUIDE.md).
