# PRIORIS

PRIORIS transforme vos tâches, idées et demandes en décisions claires et assumées.

Lorsque tout semble urgent, PRIORIS vous guide pas à pas pour identifier ce qui compte réellement. Il vous aide à choisir la meilleure action : agir maintenant, planifier, déléguer ou abandonner.

Grâce à une approche inspirée de la matrice d’Eisenhower et à un questionnement intelligent, chaque recommandation est justifiée et traçable.

✔ Priorités argumentées
✔ Plan quotidien réaliste
✔ Réduction de la charge mentale
✔ Synchronisation avec Obsidian
✔ Décisions explicables et vérifiables

L’IA assiste votre réflexion, elle ne décide pas à votre place.

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
tests/             229 tests automatisés
```

Un port natif expérimental est disponible dans [`rust/`](rust/README.md). Il
produit un binaire Windows, Linux ou macOS sans Python et peut charger le GGUF
Ministral directement dans le processus, sans serveur ni port. Consulte son
README pour l'état exact de la parité fonctionnelle et les limites actuelles.
Ses releases utilisent des tags `rust-v*` et restent séparées des releases
Python `v0.x`. À partir de Rust 0.2.4, l'archive macOS contient une application
`PRIORIS.app` signée Developer ID, notarée par Apple et lançable par
double-clic ; le workflow refuse la publication si un contrôle Gatekeeper
échoue.

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

Résultat attendu dans un clone complet du dépôt source : `229 passed`.

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
  https://huggingface.co/unsloth/Ministral-3-3B-Instruct-2512-GGUF/resolve/7564922f37fa5bbb62b87f09a55c12f1f91d7a6a/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf
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
actif, tu peux répondre en texte libre à toutes les questions à choix :
PRIORIS interprète la réponse, propose l'option comprise, puis attend ta
confirmation. Si le LLM est KO/offline, l'interface repasse aux boutons. La
réponse à « Instinctivement, tu la classes comment ? » ne force pas le score :
elle prépare des questions de challenge anti-biais. Elles sont posées une par
une après les questions factuelles, juste avant le calcul. Chaque réponse peut
proposer une correction d'axe, expliquée puis confirmée avant d'entrer dans le
calcul. Une question LLM peut contenir une prémisse fausse : réponds-le
librement. PRIORIS enregistre alors la contestation et continue sans modifier
le score ; si la réponse apporte aussi un fait chiffrable, il propose la
correction correspondante. Une abstention du LLM ne bloque jamais ces
questions anti-biais. Les réponses courtes `oui` et `non` sont reconnues
directement comme réponses complètes et certaines. Une contestation explicite
sans autre fait est également reconnue avant l'appel LLM. La vérification miroir
reconnaît aussi les conséquences explicitement graves ou vitales sans convertir
les réponses ambiguës en choix arbitraires.

### Calcul et planification

- Une question affichée attend toujours une réponse. Une réponse LLM non
  confirmée n'est jamais utilisée.
- Les sept axes viennent de questions factuelles : `BLK` blocage réel
  (ex. acteur critique bloqué), `CDR` coût du retard (ex. coût qui explose à une date),
  `HOR` horizon de visibilité (ex. problème visible cette semaine), `IMP`
  différence entre fait et non fait (ex. gain structurant), `INA` conséquence
  d'un mois d'inaction (ex. crise), `IRR` irréversibilité (ex. décision non
  rattrapable) et `ALN` alignement avec un objectif (ex. contribution directe).
- Chaque valeur est normalisée par le maximum de son échelle. Ligne de calcul
  exacte : `U = 30×BLK/5 + 40×CDR/4 + 30×HOR/4` ;
  `I = 35×IMP/4 + 25×INA/4 + 20×IRR/3 + 20×ALN/3` ;
  `G = 0,6×I + 0,4×U`.
- Seuils : urgent si `U >= 55`, important si `I >= 50`. `Q1 -> P1`, `Q2 -> P2`,
  `Q3 -> P3`, `Q4 -> P4`.
- Le mode express demande désormais `IMP` séparément de `INA` : un fort impact
  stratégique n'est plus déduit, ni écrasé, par le coût d'un mois d'inaction.
  Une réponse hésitante ou inconnue produit aussi un intervalle `U/I` ; `/why`
  indique si le quadrant est robuste, les quadrants possibles et l'axe pivot.
- `G` départage et planifie les tâches ; il ne choisit pas le quadrant, qui
  dépend uniquement des seuils de `U` et `I`.
- Valeur de planification : `V = G + bonus échéance (0 à 40) + bonus pépite
  (0 ou 10) + ajustement énergie (-25 à +10, ou exclusion)`. Les P1 sont
  examinées avant les P2/P3 ; les P4 et estimations inconnues sont exclues.

Les échelles complètes, un exemple chiffré par axe, les valeurs express par
défaut, les intervalles de robustesse, les planchers, leurs limites et toutes
les règles du plan sont détaillés dans
[GUIDE.md](GUIDE.md), sections 2.5.2 à 2.5.4.

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

229 tests passent localement. Les améliorations restantes envisagées sont :
scénarios comparés avancés, alertes d'équilibre de vie, rapport mensuel de
biais, mémoire de décision plus riche, et création contrôlée de lignes Obsidian
pour les tâches locales sans `obsidian_path`.
