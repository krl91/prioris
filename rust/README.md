# PRIORIS Rust

Port natif autonome de PRIORIS pour Windows, Linux et macOS. Le code de
l'application est en Rust et le binaire n'a besoin ni de Python, ni d'Ollama,
ni de LM Studio. Le mode GGUF embarqué charge Ministral directement dans le
processus avec `mistral.rs`; il ne démarre aucun serveur et n'ouvre aucun port.

## Installer une release Rust

Les releases Rust sont séparées des releases Python et utilisent des tags
`rust-v*`. Ouvre la [liste des releases](https://github.com/krl91/prioris/releases),
puis télécharge uniquement l'archive correspondant à ton système :

| Système | Archive Rust 0.2.0 |
|---|---|
| macOS Apple Silicon | `prioris-rust-v0.2.0-macos-arm64.zip` |
| Windows x64 | `prioris-rust-v0.2.0-windows-x64.zip` |
| Linux x64 | `prioris-rust-v0.2.0-linux-x64.tar.gz` |

Décompresse l'archive puis lance `scripts/run.sh` sous macOS/Linux ou
`scripts/run.ps1` sous Windows. Le modèle Ministral 3B, `config.toml` et
`ObsidianVault` sont déjà inclus. `SHA256SUMS.txt`, joint à la release, permet
de vérifier l'intégrité de l'archive.

## État fonctionnel

La version Rust fournit :

- la GUI native locale ;
- Telegram optionnel en long polling, sans webhook entrant, exécuté en
  arrière-plan sans remplacer la GUI ;
- la modification et la sauvegarde de `config.toml` depuis la GUI ;
- le même schéma SQLite que la version Python ;
- le scoring déterministe P1-P4 et le plan du jour avec dates et énergie ;
- l'algorithme v2 avec `IMP` explicite en express, intervalles de robustesse,
  quadrants possibles et axe pivot ;
- un entretien qui affiche et attend une seule question à la fois ;
- les réponses libres LLM avec proposition avant validation dans la GUI ;
- trois questions anti-biais LLM posées successivement et intégrées au calcul
  uniquement après confirmation ;
- les catégories personnalisées persistantes ;
- les objectifs, `/list`, `/today`, `/done`, `/scan`, `/info` et `/llm` ;
- le scan, l'annotation et l'export Markdown Obsidian ;
- les modes sans LLM, interpréteur intégré, GGUF embarqué, Ollama, LM Studio,
  OpenAI-compatible, Anthropic et GitHub Copilot.
- la génération JSON contrainte par schéma pour le GGUF embarqué, les budgets
  de tokens par appel, l'abstention explicite et la présélection `/info`.

Limites actuelles par rapport à la version Python 0.5.0 :

- Telegram utilise des réponses numérotées et ne propose pas encore les mêmes
  boutons de confirmation que la GUI ;
- les règles détaillées de contradictions, questions miroir, drapeaux de biais
  et la révision complète des axes via `/info` restent à porter ;
- l'interface Rust est actuellement en français ; `ui.language = "en"` sera
  pris en charge dans une tranche suivante ;
- la synchronisation Obsidian complète avant/après reste plus limitée que dans
  la version Python.

Le dossier ne doit donc pas encore remplacer la version Python en production
si ces fonctions sont indispensables. Il constitue une application native
fonctionnelle et testée, mais pas encore une parité fonctionnelle à 100 %.

## Compilation

Prérequis développeur : Rust 1.92 ou plus récent.

```bash
cd rust
cargo test
cargo check --no-default-features --features embedded-llm
cargo build --release --features embedded-llm
```

Sur macOS Apple Silicon, le build distribué utilise Apple Accelerate, présent
avec macOS :

```bash
cargo build --release --features embedded-llm,accelerate
```

La feature `metal` reste disponible pour les développeurs ayant installé le
composant Metal Toolchain de Xcode. Elle n'est pas requise par la release.

Le binaire se trouve dans `target/release/prioris` ou
`target/release/prioris.exe`.

## Configuration et lancement

```bash
cp config.example.toml config.toml
./target/release/prioris --config config.toml
```

La GUI reste ouverte même lorsqu'un token Telegram est configuré. Telegram est
alors démarré en arrière-plan et partage la même instance LLM initiale afin de
ne pas charger deux fois un modèle GGUF. Pour lancer uniquement Telegram :

```bash
./target/release/prioris --config config.toml --no-gui
```

`--headless` est un alias de `--no-gui`. Ce mode refuse de démarrer si le token
Telegram est vide.

L'onglet **Configuration** permet de modifier et enregistrer directement les
sections Telegram, SQLite, interface, Obsidian et LLM. Les secrets sont masqués
par défaut. Les changements LLM et Obsidian sont appliqués à la GUI après
sauvegarde ; Telegram et le chemin SQLite nécessitent un redémarrage. Sous
Unix, le fichier sauvegardé reçoit les permissions `0600`.

Dans une archive distribuée, `scripts/run.sh` lance directement l'application.
Sur macOS, ce script retire aussi l'attribut de quarantaine de l'archive avant
de lancer le binaire signé ad hoc. Une distribution sans cet assouplissement
nécessiterait un certificat Apple Developer ID et une notarisation Apple.

Sous Windows PowerShell :

```powershell
Copy-Item config.example.toml config.toml
.\target\release\prioris.exe --config config.toml
```

Mode Telegram sans fenêtre sous Windows :

```powershell
.\target\release\prioris.exe --config config.toml --no-gui
```

Pour fonctionner sans LLM :

```toml
[llm]
enabled = false
```

Pour le modèle embarqué sans serveur :

```toml
[llm]
enabled = true
provider = "local_gguf"
model = "models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
```

La première génération charge environ 2 Go de poids et nécessite davantage de
RAM pour les activations et le cache. Le test effectué sur le modèle 3B fourni
a réussi en CPU ; le build de développement a mis environ 93 secondes pour le
premier diagnostic. Un build `--release` est requis pour l'utilisation normale.

## Calcul et planification

Le port Rust conserve le calcul déterministe de la version principale. Les axes
sont `BLK` blocage, `CDR` coût du retard, `HOR` horizon, `IMP` impact, `INA`
coût de l'inaction, `IRR` irréversibilité et `ALN` alignement objectif :

```text
U = 30 × BLK/5 + 40 × CDR/4 + 30 × HOR/4
I = 35 × IMP/4 + 25 × INA/4 + 20 × IRR/3 + 20 × ALN/3
G = 0,6 × I + 0,4 × U
```

Urgent signifie `U >= 55`, important `I >= 50`, ce qui produit Q1/P1 à
Q4/P4. Le plan trie ensuite par
`V = G + bonus échéance + bonus pépite + ajustement énergie`, avec les P1
d'abord et sans planifier les P4 ni les estimations inconnues. Les questions,
échelles, exemples, planchers et règles exactes sont détaillés dans
[`../GUIDE.md`](../GUIDE.md), sections 2.5.2 à 2.5.4.

## Vérifications intégrées

```bash
./prioris --self-test
./prioris --llm-smoke models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf
```

Le premier test vérifie le binaire, SQLite et le scoring. Le second charge
réellement le GGUF, vérifie le schéma JSON de santé, puis interprète une réponse
`IMP` structurée avec validation de l'échelle et de la confiance.

## Note sur « 100 % Rust »

Le code applicatif et le moteur LLM embarqué sont en Rust. La compatibilité avec
le fichier `prioris.db` existant est conservée au moyen de `rusqlite`, qui lie
SQLite, bibliothèque écrite en C, directement dans le binaire. Il n'y a aucune
dépendance Python ni processus serveur. Si « 100 % Rust » signifie également
interdire toute bibliothèque native non-Rust, il faudra remplacer SQLite par un
format de stockage Rust et perdre la compatibilité directe avec la base actuelle.
