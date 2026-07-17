# PRIORIS

PRIORIS est un assistant personnel pour décider quoi faire maintenant, quoi
planifier, quoi déléguer et quoi laisser de côté. Il transforme une liste de
tâches en priorités expliquées, en plan du jour réaliste et en notes Obsidian
synchronisées.

Le principe important : le coeur de décision reste déterministe et explicable.
Un LLM peut aider à comprendre une phrase, poser de meilleures questions ou
proposer une modification, mais il ne modifie rien sans confirmation.

## À quoi ça sert

PRIORIS aide quand une simple todo-list ne suffit plus :

- choisir les tâches vraiment importantes au lieu de suivre seulement l'urgence ;
- comparer des tâches personnelles, professionnelles, santé, finances ou famille ;
- éviter les décisions impulsives grâce à un entretien guidé ;
- produire un plan du jour compatible avec ton énergie, ta capacité et les dates
  limites ;
- garder une trace claire des raisons d'une priorité ;
- synchroniser les tâches et les décisions avec un vault Obsidian.

## Ce que tu peux faire

- Ajouter une tâche, choisir une catégorie, une date limite éventuelle et répondre
  à un entretien express ou complet.
- Obtenir un score P1-P4 avec explication détaillée, contradictions détectées et
  signaux de biais.
- Générer un plan du jour qui met en concurrence score, urgence réelle, dates de
  réalisation, énergie disponible et temps estimé.
- Ajouter une information ou poser une question avec `/info` : PRIORIS propose
  les tâches impactées, explique l'impact, suggère une révision ou une nouvelle
  tâche, puis demande confirmation.
- Gérer des objectifs de vie et relier les tâches à ces objectifs.
- Scanner un vault Obsidian, importer les tâches `- [ ]`, écrire les notes
  `PRIORIS/<id>.md`, cocher les tâches terminées et synchroniser avec aperçu
  avant/après.

## Interfaces

| Interface | Usage | Points forts |
|---|---|---|
| GUI locale | Fenêtre simple sur la machine | Aucun compte, aucun serveur, aucun port local |
| Telegram | Utilisation mobile et notifications | Pratique pour capturer et traiter les tâches partout |
| Obsidian | Vault Markdown personnel | Notes lisibles, liens courts, historique durable |
| LLM optionnel | Interprétation et aide à la décision | Questions plus pertinentes, analyse `/info`, reformulations |

La GUI locale est le mode par défaut des releases. Telegram reste optionnel :
il suffit de laisser le token vide pour ne pas l'utiliser.

## Modes LLM

PRIORIS fonctionne avec ou sans LLM :

- **Sans LLM** : entretien à boutons, scoring local et plan du jour déterministe.
- **LLM local autonome** : modèle GGUF embarqué, runtime `llama-simple`, sans
  Ollama, sans LM Studio, sans serveur et sans port local.
- **Ollama / LM Studio** : possible si tu préfères gérer tes modèles avec ces
  outils.
- **LLM externe** : OpenAI, Anthropic/Claude, endpoint compatible, GitHub
  Copilot ou autre provider configuré.

Dans la release standard, le modèle local 3B est déjà inclus et configuré.

## Potentiel de la solution

PRIORIS peut devenir un cockpit personnel de décision : priorités quotidiennes,
suivi des objectifs, mémoire des arbitrages, audit des biais récurrents,
rapports périodiques, synchronisation Markdown et assistance LLM contrôlée. La
base actuelle privilégie la fiabilité : données locales, confirmations avant
modification, logs, tests et séparation nette entre calcul déterministe et aide
LLM.

## Architecture

```text
prioris/
├── core/          Fonctions pures, zéro I/O
├── store/         SQLite append-only
├── vault/         Scan/synchro/export Obsidian
├── gui/           Interface graphique locale tkinter
├── bot/           Adaptateur Telegram
└── llm/           Façade LLM optionnelle, providers et diagnostics
tests/             191 tests automatisés
```

Contrainte vérifiée par `tests/test_architecture.py` : `core/` n'importe ni
store, ni bot, ni vault, ni SQLite, ni Telegram, ni client réseau.

## Installation depuis la release

Le chemin standard est de télécharger la dernière archive prête à l'emploi :
<https://github.com/krl91/prioris/releases/latest>

Télécharge **un seul fichier compressé**, celui de ton système. Ne télécharge
pas les assets `runtime-*` seuls : ils ne contiennent pas toute l'application.

| Système | Fichier à télécharger | Commandes après extraction |
|---|---|---|
| macOS Apple Silicon | `prioris-macos-arm64.zip` | `cd prioris-macos-arm64` puis `./scripts/install_unix.sh` puis `./scripts/run_unix.sh` |
| Windows x64 | `prioris-windows-x64.zip` | `cd prioris-windows-x64` puis `.\scripts\install_windows.ps1` puis `.\scripts\run_windows.ps1` |
| Linux x64 | `prioris-linux-x64.tar.gz` | `cd prioris-linux-x64` puis `./scripts/install_unix.sh` puis `./scripts/run_unix.sh` |

Chaque archive contient l'application, la documentation, `config.example.toml`,
un vault Obsidian exemple, un `wheelhouse/` pour installer les dépendances Python
hors ligne, le runtime local `llama-simple` sans serveur pour la plateforme, le
modèle `Ministral-3-3B-Instruct-2512-Q4_K_M.gguf`, et un `config.toml` déjà
réglé pour démarrer en GUI locale avec ce modèle. Les nouvelles archives
incluent aussi `tests/` pour vérifier l'installation après extraction.

macOS Apple Silicon :

```bash
cd prioris-macos-arm64
./scripts/install_unix.sh
./scripts/run_unix.sh
```

Sur macOS, lance bien `install_unix.sh` avant le premier démarrage. Le runtime
`llama-simple` est signé ad-hoc, et les scripts retirent la quarantaine macOS
sur tout le dossier extrait. Le fournisseur LLM local refait aussi ce nettoyage
juste avant d'appeler le binaire. Ce n'est pas une notarisation Apple Developer
complète, mais cela évite le blocage Gatekeeper courant sur l'archive
téléchargée.

Linux x64 :

```bash
cd prioris-linux-x64
./scripts/install_unix.sh
./scripts/run_unix.sh
```

Windows PowerShell :

```powershell
cd prioris-windows-x64
.\scripts\install_windows.ps1
.\scripts\run_windows.ps1
```

Pour le mode `local_gguf`, place le modèle GGUF dans `models/`, par exemple
`models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf`, puis vérifie `config.toml`.
Dans les releases récentes, le modèle 3B est déjà inclus dans le bundle OS. Le
8B reste optionnel et se télécharge séparément.

## Installation développeur depuis le dépôt source

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Résultat attendu dans un clone complet du dépôt source : `191 passed`.

Les nouvelles archives release prêtes à l'emploi incluent aussi `tests/`. Pour
vérifier une release après extraction :

```bash
python -m pytest
```

Si tu utilises une ancienne archive et obtiens `collected 0 items`, elle
n'embarquait pas encore les tests. Dans ce cas, vérifie au minimum :

```bash
python -c "import prioris; print('PRIORIS import ok')"
python -m prioris.bot.main
```

Installation offline : fournir les roues Python dans `wheelhouse/`, puis :

```bash
pip install --no-index --find-links wheelhouse -e ".[dev]"
```

PRIORIS ne télécharge aucun modèle au démarrage. Pour `local_gguf`, la release
doit déjà embarquer le binaire d'inférence CLI/stdout et le fichier `.gguf`.
Le runtime autonome est volontairement limité à `llama-simple` et à ses
dépendances : pas de `llama-server`, pas de `ggml-rpc-server`, pas de
`llama-cli`, et aucun port local ouvert.

Téléchargement manuel des modèles GGUF recommandés :

- 3B Q4_K_M, recommandé par défaut :
  https://huggingface.co/unsloth/Ministral-3-3B-Instruct-2512-GGUF/resolve/main/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf
- 8B Q4_K_M, plus lourd :
  https://huggingface.co/unsloth/Ministral-3-8B-Instruct-2512-GGUF/resolve/main/Ministral-3-8B-Instruct-2512-Q4_K_M.gguf

Place le fichier choisi dans `models/`, puis renseigne `model` dans
`config.toml`.

Chemins Windows dans `config.toml` : privilégier les `/`, par exemple
`vault_path = "C:/Users/Example/Documents/Vault"`. Les chemins Windows avec `\`
sont acceptés si tu utilises des quotes simples TOML :
`vault_path = 'C:\Users\Example\Documents\Vault'`.

## Lancement

### GUI locale

Laisser le token Telegram vide :

```toml
[telegram]
token = ""
```

Puis :

```bash
python -m prioris.bot.main
```

La GUI expose : ajout de tâche, plan du jour, objectifs, liste, scan Obsidian,
synchro Obsidian, diagnostic LLM, marquer faite, justification et
Info/question.

### Langue

Le français reste la langue par défaut. Pour utiliser les questions/options
d'entretien en anglais :

```toml
[ui]
language = "en"
```

Les calculs, scores et confirmations restent identiques. Quand un LLM est
actif, PRIORIS affiche aussi 3 questions adaptées au titre de la tâche pour
aider à situer le quadrant urgent/important avant la question instinctive.

### Telegram

1. Créer un bot via **@BotFather**.
2. Copier `config.example.toml` vers `config.toml`.
3. Renseigner `[telegram] token`.
4. Lancer :

```bash
python -m prioris.bot.main
```

## Commandes

| Commande | Effet |
|---|---|
| `/add <titre>` | nouvelle tâche, catégorie, date limite éventuelle, entretien |
| `/today` | énergie, capacité, plan du jour, export Obsidian |
| `/list` | tâches évaluées triées par priorité et score |
| `/why <id>` | justification complète du score |
| `/done <id>` | marquer faite, log temps, case Obsidian cochée si liée |
| `/scan` | importer/synchroniser les tâches Obsidian |
| `/goals` | gérer les objectifs |
| `/llm` | diagnostic LLM, préchauffage, derniers échecs |
| `/info ...` | information/question, impact, révision ou nouvelle tâche |

## Obsidian

`/scan` et le bouton **Scan** lisent les tâches `- [ ]` non marquées du vault.
Après priorisation, PRIORIS ajoute un marqueur court :

```md
- [ ] Mettre à jour le CV 🎯P2 [[PRIORIS/12]]
```

La note `PRIORIS/12.md` contient un titre clair, le résultat, les axes, les
infos ajoutées via `/info` et le lien retour vers la note source. Les anciens
liens longs `[[PRIORIS/details/12 - titre|détail]]` restent lus et sont migrés
au prochain **Sync Obsidian**.

## État

191 tests passent localement. Les améliorations restantes envisagées sont :
scénarios comparés avancés, alertes d'équilibre de vie, rapport mensuel de
biais, mémoire de décision plus riche, et création contrôlée de lignes Obsidian
pour les tâches locales sans `obsidian_path`.
