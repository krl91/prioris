## PRIORIS Python Intel __VERSION__

## Version Python pour Mac Intel

- Ajoute une archive Python complète construite et testée sur un runner macOS
  Intel `x86_64`.
- Compile `llama-simple` nativement depuis llama.cpp b10012 avec Apple
  Accelerate, sans Ollama, LM Studio, serveur ni port local.
- Inclut Ministral 3B GGUF, les dépendances Python hors ligne, les tests et
  `ObsidianVault`.
- Vérifie l'installation hors ligne, la GUI Python, la signature du runtime et
  une inférence GGUF réelle avant publication.

## Télécharger

- Application Python macOS Intel : `prioris-python-intel-__VERSION__-macos-x64.zip`
- Moteur LLM Intel seul : `runtime-macos-x64.zip`
- Vérification : `SHA256SUMS.txt`

Après extraction, ouvre Terminal dans le dossier, puis exécute :

```sh
./scripts/install_unix.sh
./scripts/run_unix.sh
```

Python 3.11 ou plus récent doit déjà être installé. L'installation de PRIORIS
et de ses dépendances s'effectue ensuite sans connexion. L'archive nécessite
macOS 13 ou une version plus récente.

Consultez le [README](https://github.com/__REPOSITORY__/blob/__TAG__/README.md)
et le [guide complet](https://github.com/__REPOSITORY__/blob/__TAG__/GUIDE.md).
