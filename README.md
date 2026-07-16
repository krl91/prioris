# PRIORIS

Assistant personnel d'aide à la décision : tâches, priorités, plan du jour et
synchronisation Obsidian. Le coeur reste déterministe : le LLM est optionnel et
ne décide jamais seul.

## Fonctionnalités

- Entretien express/complet à boutons, avec contradictions C1-C6.
- Scoring déterministe P1-P4, `/why`, biais 1-4/7/9 et justification complète.
- Plan du jour avec énergie, capacité, estimations et dates de réalisation.
- Mode Telegram ou GUI locale tkinter sans serveur.
- `/info` : ajout d'informations, questions, impact sur les tâches, création de
  nouvelle tâche, échéance détectée, révision confirmée, repli manuel sans LLM.
- Objectifs de vie, question miroir et vérification de cohérence LLM optionnelle.
- Obsidian : scan du vault, import des tâches, cases cochées, notes
  `PRIORIS/<id>.md`, liens courts `[[PRIORIS/<id>]]`, synchro complète avec
  aperçu avant/après.
- LLM optionnel : aucun LLM, moteur local intégré `prioris/rules-v1`, GGUF local
  autonome sans port, Ollama/LM Studio, OpenAI, Anthropic/Claude, custom,
  GitHub Copilot.

## Architecture

```text
prioris/
├── core/          Fonctions pures, zéro I/O
├── store/         SQLite append-only
├── vault/         Scan/synchro/export Obsidian
├── gui/           Interface graphique locale tkinter
├── bot/           Adaptateur Telegram
└── llm/           Façade LLM optionnelle, providers et diagnostics
tests/             190 tests automatisés
```

Contrainte vérifiée par `tests/test_architecture.py` : `core/` n'importe ni
store, ni bot, ni vault, ni SQLite, ni Telegram, ni client réseau.

## Installation depuis la release

Le chemin standard est de télécharger la dernière archive prête à l'emploi :
<https://github.com/krl91/prioris/releases/latest>

Télécharge l'archive correspondant à ton système depuis la dernière release :

- `prioris-macos-arm64.zip`
- `prioris-windows-x64.zip`
- `prioris-linux-x64.tar.gz`

Chaque archive contient l'application, la documentation, `config.example.toml`,
un vault Obsidian exemple, un `wheelhouse/` pour installer les dépendances Python
hors ligne, le runtime local `llama-simple` sans serveur pour la plateforme, le
modèle `Ministral-3-3B-Instruct-2512-Q4_K_M.gguf`, et un `config.toml` déjà
réglé pour démarrer en GUI locale avec ce modèle.

Installation :

```bash
cd prioris-*
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

## Installation développeur

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Résultat attendu : `190 passed`.

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

190 tests passent localement. Les améliorations restantes envisagées sont :
scénarios comparés avancés, alertes d'équilibre de vie, rapport mensuel de
biais, mémoire de décision plus riche, et création contrôlée de lignes Obsidian
pour les tâches locales sans `obsidian_path`.
