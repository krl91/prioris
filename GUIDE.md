# PRIORIS — Guide d'installation et d'utilisation

MVP V0.1 · pour le dossier de conception, voir `conception-assistant-decision.md`

---

## Partie 1 — Installation rapide depuis une release

### 1.1 Télécharger l'archive de ton système

Le chemin recommandé pour utiliser PRIORIS est le plus simple :

1. Ouvre la dernière release GitHub :
   <https://github.com/krl91/prioris/releases/latest>
2. Télécharge **un seul fichier**, celui de ton système. Ne prends pas les
   archives `runtime-*` seules : elles ne contiennent pas toute l'application.

| Système | Fichier compressé à télécharger | Commandes après extraction |
|---|---|---|
| macOS Apple Silicon | `prioris-macos-arm64.zip` | `cd prioris-macos-arm64` puis `./scripts/install_unix.sh` puis `./scripts/run_unix.sh` |
| Windows x64 | `prioris-windows-x64.zip` | `cd prioris-windows-x64` puis `.\scripts\install_windows.ps1` puis `.\scripts\run_windows.ps1` |
| Linux x64 | `prioris-linux-x64.tar.gz` | `cd prioris-linux-x64` puis `./scripts/install_unix.sh` puis `./scripts/run_unix.sh` |

3. Décompresse l'archive dans le dossier de ton choix.
4. Ouvre un terminal dans le dossier décompressé.
5. Vérifie que `config.toml` existe déjà à la racine du dossier. Dans une
   release normale, il est fourni et prêt à l'emploi.
6. Lance le script fourni.

macOS Apple Silicon :

```bash
cd prioris-macos-arm64
./scripts/install_unix.sh
./scripts/run_unix.sh
```

Le runtime macOS `llama-simple` est signé en mode ad-hoc avec Hardened Runtime
dans la release. Les scripts `install_unix.sh` et `run_unix.sh` retirent aussi
l'attribut de quarantaine macOS sur tout le dossier extrait, et le fournisseur
LLM local refait ce nettoyage juste avant d'appeler le binaire. Ce n'est pas une
notarisation Apple Developer complète, mais cela évite le blocage Gatekeeper
courant sur l'archive téléchargée.

> **Si macOS bloque `llama-simple` avec « Apple n'a pas pu confirmer… »**
> (dialog Gatekeeper au premier lancement) : c'est normal pour un binaire
> téléchargé sans notarisation Apple payante. Deux façons de l'autoriser :
>
> **Option A – script inclus (zip runtime uniquement)**
> ```bash
> chmod +x allow-macos.sh && ./allow-macos.sh
> ```
> Ce script retire l'attribut quarantaine sur tout le dossier.
>
> **Option B – via l'app complète (recommandé)**
> Passe par `./scripts/install_unix.sh` : le script retire automatiquement
> la quarantaine sur l'intégralité du dossier extrait.
>
> **Option C – manuellement**
> ```bash
> xattr -dr com.apple.quarantine /chemin/vers/prioris-macos-arm64
> ```

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

L'archive contient déjà tout ce qu'il faut pour démarrer :

- l'application PRIORIS ;
- la documentation ;
- `config.toml` prêt à l'emploi ;
- le vault `ObsidianVault` ;
- les dépendances Python dans `wheelhouse/` pour une installation offline ;
- le runtime local `llama-simple` sans serveur et sans port local ;
- le modèle `Ministral-3-3B-Instruct-2512-Q4_K_M.gguf`.

La configuration par défaut démarre en **GUI locale**, sans Telegram, avec le
LLM local GGUF 3B embarqué. Aucun téléchargement de modèle n'est fait au
lancement.

Si `config.toml` manque après extraction, recrée-le depuis l'exemple :

macOS / Linux :

```bash
cp config.example.toml config.toml
```

Windows PowerShell :

```powershell
Copy-Item config.example.toml config.toml
```

Puis ouvre `config.toml` et vérifie au minimum :

```toml
[telegram]
token = ""                  # vide = GUI locale, pas Telegram

[obsidian]
vault_path = "ObsidianVault"
prioris_dir = "PRIORIS"

[llm]
enabled = true
provider = "local_gguf"
runner_path = "auto"
model = "models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
```

Pour démarrer sans LLM, remplace seulement :

```toml
[llm]
enabled = false
```

### 1.2 Prérequis

| Besoin | Détail |
|---|---|
| Python ≥ 3.11 | vérifier : `python3 --version` |
| Un compte Telegram | **optionnel** — uniquement pour le mode Telegram |
| Une machine allumée | PC perso ou NAS — le bot doit tourner pour répondre (mode Telegram) |
| (Optionnel) Vault Obsidian | pour l'export du plan du jour |

Aucun compte, aucune clé API et aucun service cloud ne sont nécessaires pour le
mode release par défaut. Telegram, Ollama/LM Studio ou les LLM externes sont des
options avancées.

**PRIORIS propose deux modes d'interface, contrôlés par `config.toml` :**

| Mode | Config | Avantages | Limitations |
|---|---|---|---|
| **Telegram** | `token = "123456:..."` | Mobile, notifications push, disponible de partout | Compte Telegram + bot à créer |
| **Local (GUI)** | `token = ""` ou absent | Zéro compte requis, aucune dépendance externe | Même machine uniquement, pas de mobile |

### 1.3 Mode local — interface graphique (sans Telegram)

Si tu préfères ne pas utiliser Telegram, laisse le champ `token` vide (ou
absent) dans `config.toml`. PRIORIS démarre alors une fenêtre graphique locale
(tkinter, inclus dans Python — **aucune installation supplémentaire**).

```toml
[telegram]
token = ""          # vide → mode local automatique
```

Lancement :

```bash
python -m prioris.bot.main          # détecte le token vide, lance la GUI
# ou directement :
python -m prioris.gui.main
```

L'interface propose les principales fonctions du mode Telegram :

| Action | Équivalent Telegram |
|---|---|
| ➕ Ajouter une tâche | `/add` |
| 📅 Plan du jour | `/today` |
| 📋 Liste | `/list` |
| 🎯 Objectifs | `/goals` |
| ✅ Marquer faite | `/done` |
| 🔍 Pourquoi ? | `/why` |
| 💬 Info / question | `/info` |
| 📥 Scan du vault | `/scan` |
| 🤖 Diagnostic LLM | `/llm` |

Pendant un entretien GUI, si l'objectif attendu n'est pas dans la liste, clique
**➕ Créer un nouvel objectif**, saisis son titre, choisis sa catégorie, puis
indique son niveau de contribution. La tâche en cours sera rattachée à ce nouvel
objectif sans devoir interrompre l'entretien.

**Limites documentées du mode local :**

- Accès local uniquement (même machine, même session utilisateur)
- Pas d'interface mobile
- Pas de notifications push
- Le scan Obsidian (`/scan`) est exposé dans la GUI, mais reste interactif :
  les tâches sont évaluées une par une, comme dans Telegram.
- Le LLM est optionnel. Si `[llm] enabled = false`, la GUI fonctionne en
  boutons/scoring local. Si `[llm] enabled = true`, la GUI active le diagnostic,
  le préchauffage `keep_warm`, les suggestions d'objectif et l'interprétation
  de réponses libres avec confirmation avant scoring. Les réponses libres sont
  acceptées sur toutes les questions à choix. Si le LLM est KO/offline, la GUI
  affiche l'erreur et repasse aux boutons. La réponse instinctive P1/P2/P3/P4
  sert à formuler des questions de challenge anti-biais. PRIORIS termine d'abord
  les questions factuelles, puis pose ces challenges un par un juste avant le
  calcul. Chaque réponse peut proposer une correction d'axe, toujours confirmée
  avant d'entrer dans le calcul.

**Langue de l'interface d'entretien.** Le français est la valeur par défaut.
Pour basculer les questions/options d'entretien en anglais :

```toml
[ui]
language = "en"
```

La configuration `"fr"` ou l'absence de section `[ui]` conserve le français.
Le scoring ne change pas : seule la formulation des questions/options est
traduite.

### 1.4 Créer le bot Telegram (5 min) — mode Telegram uniquement

1. Dans Telegram, ouvrir une conversation avec **@BotFather**.
2. Envoyer `/newbot`.
3. Choisir un nom d'affichage (ex. `PRIORIS`) puis un identifiant unique
   finissant par `bot` (ex. `prioris_local_bot`).
4. BotFather répond avec un **token** de la forme
   `1234567890:AAExEmPlE-DeToKeN...` → **le copier**, c'est la seule chose à garder.
5. Recommandé : `/setcommands` auprès de BotFather, puis coller :

```
add - Nouvelle tâche (entretien)
today - Plan du jour
list - Tâches évaluées
why - Justification d'un score
done - Marquer une tâche faite
scan - Prioriser les tâches du vault
goals - Objectifs de vie
llm - Diagnostic du LLM
```

Le bot est personnel : ne partage pas le token (quiconque l'a contrôle le bot).

### 1.5 Installation développeur ou manuelle

PRIORIS doit pouvoir être installé **offline** : l'application ne télécharge
ni dépendances, ni modèle LLM au démarrage. En environnement sans réseau, il
faut donc fournir à l'avance les dépendances Python dans un dossier local
`wheelhouse/`. Le provider par défaut `prioris/rules-v1` est intégré au code :
aucun modèle séparé n'est requis. Seuls les providers externes optionnels
(Ollama, LM Studio, OpenAI-compatible) demandent une installation ou une
authentification séparée. Le mode `local_gguf` reste offline lui aussi, mais
la release doit contenir le binaire d'inférence et le fichier modèle GGUF.

1. Place-toi dans le dossier du projet :

```bash
cd prioris
```

2. Crée l'environnement virtuel :

macOS / Linux :

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Installe PRIORIS :

```bash
pip install -e ".[dev]"
```

Si tu es dans une archive offline qui contient `wheelhouse/`, utilise plutôt :

```bash
pip install --no-index --find-links wheelhouse -e ".[dev]"
```

Les scripts `scripts/install_unix.sh` et `scripts/install_windows.ps1` font déjà
cette installation avec l'extra `dev`, afin que `python -m pytest` soit
disponible dans la release.

4. Crée le fichier de configuration :

macOS / Linux :

```bash
cp config.example.toml config.toml
```

Windows PowerShell :

```powershell
Copy-Item config.example.toml config.toml
```

5. Ouvre `config.toml` et choisis le mode voulu.

GUI locale sans Telegram :

```toml
[telegram]
token = ""
```

Telegram :

```toml
[telegram]
token = "1234567890:AAExEmPlE..."
```

Vault Obsidian :

```toml
[obsidian]
vault_path = "/Users/example/Documents/ObsidianVault"
prioris_dir = "PRIORIS"
```

Sous Windows, écris de préférence les chemins avec `/` :

```toml
[obsidian]
vault_path = "C:/Users/Example/Documents/ObsidianVault"
prioris_dir = "PRIORIS"
```

6. Choisis le mode LLM.

Sans LLM :

```toml
[llm]
enabled = false
```

LLM local GGUF embarqué :

```toml
[llm]
enabled = true
provider = "local_gguf"
runner_path = "auto"
model = "models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
```

Provider intégré sans vrai modèle génératif :

```toml
[llm]
enabled = true
provider = "prioris"
model = "rules-v1"
```

7. Vérifie l'installation.

Dans les releases récentes, le dossier `tests/` est inclus. La vérification
complète est donc :

```bash
python -m pytest
```

Résultat attendu : `225 passed`.

Vérification minimale si tu veux seulement confirmer que l'application démarre :

```bash
python -c "import prioris; print('PRIORIS import ok')"
python -m prioris.bot.main
```

Si tu utilises une ancienne archive qui n'embarque pas `tests/`, `pytest` peut
afficher `collected 0 items`. Dans ce cas, ce n'est pas un échec de
l'application ; utilise la vérification minimale ci-dessus.

Dans un clone complet du dépôt source, lance aussi :

```bash
pytest
```

Résultat attendu : `225 passed`. Si un test échoue, ne pas aller plus loin —
le moteur de scoring est le produit, il doit être irréprochable.

### 1.6 Rappels pour Obsidian et Windows

Dans `config.toml`, la base SQLite est créée automatiquement au premier
lancement :

```toml
[database]
path = "prioris.db"
```

Pour désactiver Obsidian, laisse `vault_path` vide :

```toml
[obsidian]
vault_path = ""
prioris_dir = "PRIORIS"
```

Sous Windows, écris de préférence :

```toml
[obsidian]
vault_path = "C:/Users/Example/Documents/Vault"
```

Si tu veux garder les `\`, utilise des quotes simples TOML pour éviter les
échappements :

```toml
[obsidian]
vault_path = 'C:\Users\Example\Documents\Vault'
```

L'export écrit uniquement `PRIORIS/Plan du jour.md` dans le vault — jamais
ailleurs. Le dossier `PRIORIS/` est créé s'il n'existe pas.

### 1.7 Premier lancement

```bash
python -m prioris.bot.main
```

Si `[telegram] token = ""`, la fenêtre GUI locale s'ouvre. Si un token Telegram
est renseigné, ouvre ton bot dans Telegram et envoie `/add Tester PRIORIS`. Si
la question de catégorie apparaît, tout fonctionne.

### 1.8 Lancement automatique (recommandé)

Le bot doit tourner en permanence pour l'usage quotidien.

**Linux / NAS (systemd)** — `/etc/systemd/system/prioris.service` :

```ini
[Unit]
Description=PRIORIS bot
After=network-online.target

[Service]
WorkingDirectory=/home/prioris/prioris
ExecStart=/home/prioris/prioris/.venv/bin/python -m prioris.bot.main
Restart=on-failure
User=prioris

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now prioris
journalctl -u prioris -f          # logs
```

**macOS (launchd)** — `~/Library/LaunchAgents/net.prioris.bot.plist` :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>net.prioris.bot</string>
  <key>ProgramArguments</key><array>
    <string>/Users/prioris/prioris/.venv/bin/python</string>
    <string>-m</string><string>prioris.bot.main</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/prioris/prioris</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
```

```bash
launchctl load ~/Library/LaunchAgents/net.prioris.bot.plist
```

### 1.9 Conversation et LLM — 4 modes possibles

La couche conversation permet de **répondre en texte libre** pendant
l'entretien : PRIORIS propose une interprétation, que tu confirmes d'un bouton.
Sans cette couche (ou si elle échoue), tout continue à fonctionner en boutons.

Choisis un seul mode dans `[llm]`. Le scoring reste toujours déterministe :
le LLM sert uniquement à interpréter/reformuler des réponses libres, proposer
un objectif et alimenter le diagnostic `/llm`. Une sortie LLM invalide retombe
sur les boutons.

| Mode | Réseau | Dépendance | À choisir si |
|---|---:|---:|---|
| 1. Sans LLM | Non | Non | Tu veux le mode le plus simple et robuste |
| 2. LLM local autonome | Non | Non au runtime | Tu veux Ministral offline sans Ollama/LM Studio |
| 3. Ollama / LM Studio | Localhost | Oui | Tu utilises déjà un gestionnaire de modèles local |
| 4. LLM externe | Oui | Oui | Tu acceptes un service cloud/API pour une meilleure qualité |

**Mode 1 — Ne pas utiliser de LLM**

Configuration minimale :

```toml
[llm]
enabled = false
```

Comportement :
- aucun modèle chargé ;
- aucune connexion réseau ;
- aucun serveur local ;
- aucune clé API ;
- entretien, scoring, liste, scan Obsidian, plan du jour et export restent
  disponibles en boutons.

Limites :
- pas d'interprétation automatique des réponses libres ;
- pas de préchauffage LLM ;
- le bouton **LLM** ou `/llm` indique simplement que le LLM est désactivé.

Vérification :

```bash
python -m prioris.bot.main
```

Dans la GUI, utilise les boutons d'entretien. Dans Telegram, les commandes
restent utilisables, mais les réponses libres sont moins assistées.

**Alternative sans grand modèle — interpréteur PRIORIS intégré**

Ce mode n'est pas un vrai LLM génératif. Il donne seulement une NLU locale
déterministe, utile si tu veux un peu d'aide texte libre sans modèle lourd :

```toml
[llm]
enabled = true
provider = "prioris"
model = "rules-v1"
```

Propriétés :
- offline ;
- aucun serveur local ;
- aucun téléchargement ;
- latence quasi nulle ;
- comportement conservateur : en cas d'ambiguïté, PRIORIS demande confirmation
  ou revient aux boutons.

**Mode 2 — LLM local autonome sans Ollama ni LM Studio**

Configuration recommandée, 100 % locale au runtime :

```toml
[llm]
enabled = true
provider = "local_gguf"
runner_path = "auto"
model = "models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf"
max_tokens = 512
timeout_s = 120
```

Fichiers requis dans la release offline :
- un modèle GGUF local, par défaut
  `models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf` ;
- un runtime d'inférence pure sans serveur ni port local, par défaut
  `runtime/macos-arm64/llama-simple` sur macOS Apple Silicon.

Les archives de release sont volontairement limitées au binaire
`llama-simple` et à ses dépendances. Elles ne doivent pas contenir
`llama-server`, `ggml-rpc-server`, `llama-cli` ni bibliothèque serveur/RPC.

`runner_path = "auto"` cherche les chemins suivants :

| Système | Runtime autonome |
|---|---|
| macOS Apple Silicon | `runtime/macos-arm64/llama-simple` |
| macOS Intel | `runtime/macos-x64/llama-simple` à fournir |
| Windows x64 | `runtime/windows-x64/llama-simple.exe` fourni |
| Windows arm64 | `runtime/windows-arm64/llama-simple.exe` à fournir |
| Linux x64 | `runtime/linux-x64/llama-simple` |
| Linux arm64 | `runtime/linux-arm64/llama-simple` à fournir |

Important sécurité : PRIORIS refuse les binaires qui annoncent une couche
serveur localhost interne. Le mode autonome doit rester un simple process local
CLI/stdout. Il ne doit pas ouvrir de port.

Modèles locaux disponibles :

| Modèle | Chemin | Taille | Usage |
|---|---|---:|---|
| Ministral 3 3B Q4_K_M | `models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf` | ~2.0 Go | Défaut recommandé |
| Ministral 3 8B Q4_K_M | `models/Ministral-3-8B-Instruct-2512-Q4_K_M.gguf` | ~4.8 Go | Plus lourd, plus lent, potentiellement meilleur |

Pour utiliser le 8B, change uniquement la ligne `model` :

```toml
model = "models/Ministral-3-8B-Instruct-2512-Q4_K_M.gguf"
```

Vérification rapide :

```bash
python -m prioris.bot.main
```

Puis lance `/llm` dans Telegram ou clique **LLM** dans la GUI. Résultat validé
sur macOS arm64 avec le 3B : self-test OK en environ 6,7 s, sans erreur
`failed to get a free port`. Test réel : « Le client est bloqué… » →
`BLK = 4`, incertitude `0`.

Artefacts vérifiés :

| Artefact | Chemin | SHA256 |
|---|---|---|
| Ministral 3 3B Q4_K_M | `models/Ministral-3-3B-Instruct-2512-Q4_K_M.gguf` | `fd46fc371ff0509bfa8657ac956b7de8534d7d9baaa4947975c0648c3aa397f4` |
| Ministral 3 8B Q4_K_M | `models/Ministral-3-8B-Instruct-2512-Q4_K_M.gguf` | `33e7a72cf5e6e2cfc2f2847075acc013d68bba023e35310cef86b5cf8fdca761` |
| Runtime pur macOS arm64 CPU-only | `runtime/macos-arm64/llama-simple` | `d77108bcc15f8c108d69cf8e948cad1076d39b4d4a63468b95971c33c38cd3cf` |
| Runtime pur Windows x64 CPU-only | `runtime/windows-x64/llama-simple.exe` | `03f14ad4fbf1fcfff31e39816c4226694a140eb2eb231c90f8ac33463cdcb123` |
| DLL Windows x64 `libstdc++` | `runtime/windows-x64/libstdc++-6.dll` | `d3ad53ee65b5c4b04ec4fb64d2144f2a3a19f9c1148396f52585700c3dd4327c` |
| DLL Windows x64 `libgcc` | `runtime/windows-x64/libgcc_s_seh-1.dll` | `f500f79080d3ecc22c72434ff890e8b74abe9a65388fca7cb2734869b53d2afb` |
| DLL Windows x64 `libwinpthread` | `runtime/windows-x64/libwinpthread-1.dll` | `1bb16e85f19c34629364de7407b3531201e787d803df0db6e46d01d2e8a277ac` |
| Sources llama.cpp b10012 | `artifacts/downloads/llama.cpp-b10012-src.tar.gz` | `869d4418f77919f52084dbd36ae8897a30747574e6d53aab61ea2f9c3d804445` |

Compatibilité Windows :
- le GGUF 3B est portable Windows/macOS ;
- `runtime/windows-x64/llama-simple.exe` a été cross-compilé depuis macOS avec
  MinGW-w64 installé via Homebrew ;
- `llama-simple.exe` et les trois DLL ci-dessus sont vérifiés comme binaires
  PE32+ x86-64 pour Windows ;
- les DLL non-système requises par `llama-simple.exe` sont déjà embarquées dans
  `runtime/windows-x64/` : `libstdc++-6.dll`, `libgcc_s_seh-1.dll` et
  `libwinpthread-1.dll` ;
- les autres dépendances vues par `objdump` (`KERNEL32.dll`, `ADVAPI32.dll`,
  `api-ms-win-crt-*`) sont des DLL système Windows/Universal CRT ;
- l'utilisateur Windows ne doit rien télécharger pour ce runtime si le dossier
  `runtime/windows-x64/` est livré complet ;
- `llama-cli.exe`, `llama-server.exe` et `ggml-rpc-server.exe` ne sont pas
  livrés dans le runtime autonome.

Commande utilisée pour installer la toolchain sur macOS :

```bash
brew install mingw-w64
```

Compilation Windows x64 reproductible depuis les sources llama.cpp b10012 :

```powershell
cmake -S artifacts/build/llama.cpp-b10012 `
  -B artifacts/build/llama.cpp-b10012-win-x64-build `
  -DCMAKE_TOOLCHAIN_FILE="$PWD/artifacts/build/mingw-w64-x86_64-toolchain.cmake" `
  -DLLAMA_BUILD_SERVER=OFF `
  -DLLAMA_BUILD_APP=OFF `
  -DLLAMA_BUILD_TESTS=OFF `
  -DLLAMA_BUILD_TOOLS=OFF `
  -DLLAMA_BUILD_EXAMPLES=ON `
  -DGGML_METAL=OFF `
  -DGGML_BLAS=OFF `
  -DGGML_OPENMP=OFF
cmake --build artifacts/build/llama.cpp-b10012-win-x64-build --target llama-simple -j 8
```

Limite actuelle : la validation complète Windows doit être faite sur Windows.
Depuis macOS, je peux compiler et inspecter le format PE x64, mais pas exécuter
le binaire Windows avec le modèle. Test Windows à faire sur la machine cible :

```powershell
.\runtime\windows-x64\llama-simple.exe `
  -m .\models\Ministral-3-3B-Instruct-2512-Q4_K_M.gguf `
  -n 8 "Réponds exactement: OK"
python -m prioris.bot.main
```

**Mode 3 — Utiliser Ollama ou LM Studio**

Ce mode utilise un serveur local déjà lancé par un outil externe. PRIORIS ne
télécharge pas de modèle et ne lance pas Ollama/LM Studio à ta place.

Ollama :

```toml
[llm]
enabled = true
provider = "ollama"
model = "ministral-3:3b"
timeout_s = 120
```

Prérequis Ollama :

```bash
ollama list
ollama serve
```

Le modèle doit déjà être présent. Si tu veux le télécharger, fais-le toi-même
avant, par exemple :

```bash
ollama pull ministral-3:3b
```

LM Studio :

```toml
[llm]
enabled = true
provider = "lmstudio"
model = "ministral-3-3b-instruct"   # nom affiché dans LM Studio
timeout_s = 120
```

Prérequis LM Studio :
- charger le modèle dans LM Studio ;
- ouvrir l'onglet *Developer* ;
- activer le serveur local ;
- vérifier que l'endpoint OpenAI-compatible écoute sur
  `http://localhost:1234/v1`.

Limites du mode 3 :
- localhost est utilisé, donc ce n'est pas le mode “zéro port” ;
- la sécurité dépend de la configuration Ollama/LM Studio ;
- l'installation offline de PRIORIS ne suffit pas : le modèle doit déjà être
  installé dans l'outil externe.

**Mode 4 — Utiliser un LLM externe**

Ce mode sort de la machine : il nécessite une connexion réseau et une clé API.
Utilise `api_key_env` plutôt que `api_key` pour éviter d'écrire un secret dans
`config.toml`.

OpenAI :

```bash
export OPENAI_API_KEY="sk-..."
```

```toml
[llm]
enabled = true
provider = "openai"
model = "gpt-4o-mini"
api_key_env = "OPENAI_API_KEY"
timeout_s = 15
```

Claude / Anthropic :

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

```toml
[llm]
enabled = true
provider = "anthropic"
model = "claude-3-5-haiku-latest"
api_key_env = "ANTHROPIC_API_KEY"
timeout_s = 30
```

GitHub Copilot, expérimental :

```bash
export PRIORIS_COPILOT_TOKEN="..."
```

```toml
[llm]
enabled = true
provider = "copilot"
model = "gpt-4o"
api_key_env = "PRIORIS_COPILOT_TOKEN"
timeout_s = 30
```

Le token Copilot n'est pas un PAT GitHub standard. L'authentification dépend de
ton abonnement et de ton environnement GitHub/Copilot.

Endpoint externe OpenAI-compatible, par exemple Mistral API ou serveur maison :

```toml
[llm]
enabled = true
provider = "custom"
base_url = "https://api.exemple.com/v1"
model = "nom-du-modele"
api_key_env = "PRIORIS_LLM_TOKEN"
timeout_s = 30
```

Changer de provider = éditer ces 2–4 lignes et relancer le bot. Le démarrage
affiche le mode actif (`LLM prioris (rules-v1) via builtin://prioris`).
Les appels sont journalisés dans la table `llm_calls` (latence, validité).

**`/llm` dans Telegram** ou le bouton **LLM** dans la GUI teste la connexion
(aller-retour réel) et affiche la cause exacte en cas d'échec + les
statistiques d'usage par type d'appel (`nlu`, `task_impact`, `task_revision`,
`warmup`, etc.) et le dernier échec journalisé. À lancer après toute
modification de la config.

La GUI affiche aussi une pastille LLM en bas de fenêtre : verte si le LLM est
prêt, rouge s'il est désactivé, KO ou offline. En mode Telegram, si un LLM est
configuré mais pas prêt, PRIORIS tente 3 démarrages/préchauffages avant
d'abandonner temporairement et indique le fichier de diagnostic.

Journal LLM : `logs/llm.log`. Il contient les tentatives de démarrage, les
échecs de keep-warm et les causes connues (`timeout`, connexion refusée, sortie
invalide, etc.). C'est le premier fichier à lire si la pastille est rouge ou si
Telegram annonce un LLM KO/offline.

**Latence et préchauffage** : avec `provider = "prioris"`, le préchauffage est
instantané. Avec `local_gguf`, Ollama ou LM Studio, charger un modèle local peut
prendre plus d'une minute ; PRIORIS le préchauffe au démarrage du bot ou de la
GUI puis le maintient en mémoire par un ping toutes les 4 min
(`keep_warm = true`, réglable).
Pendant une interprétation longue, le bot affiche « ⏳ J'interprète… » et le
reste du bot ne se fige jamais. Timeout : 120 s local / 15 s cloud, ajustable
via `timeout_s` pour les providers externes.

**Garanties (§1.4 du dossier)** : le LLM interprète et reformule, il ne
décide jamais. Chaque interprétation est confirmée par bouton ✅/✏️ avant
d'entrer dans le calcul. Sortie invalide 2 fois → repli boutons avec diagnostic
visible (`/llm` ou bouton **LLM**). Pour `/info`, un échec LLM réel est affiché
comme une erreur d'analyse, pas comme « aucune modification proposée ».

Les appels utilisent une température nulle et un budget de sortie adapté :
environ 160 tokens pour interpréter un axe/choix, 128 pour une réponse de
challenge, 192 pour générer les trois challenges et 320 pour `/info`, toujours
bornés par `max_tokens`. Le modèle peut répondre `status="abstain"`; une
confiance inférieure à `0,55` ou une abstention déclenche le repli manuel au
lieu d'inventer une valeur. Les quelques exemples inclus dans les prompts
montrent notamment « je ne sais pas » et « aucune candidate ne correspond ».

Dans la version Rust avec GGUF embarqué, `mistral.rs` contraint directement les
tokens générés avec un schéma JSON et garde le modèle chargé dans le processus.
Dans la version Python autonome, `llama-simple` reste un binaire CLI/stdout sans
serveur : il est relancé par appel et ne fournit pas l'option de grammaire de
`llama-cli`; PRIORIS compense par prompt strict, validation, abstention et deux
tentatives. Les endpoints compatibles utilisent `response_format` lorsqu'ils
le supportent. Aucun de ces mécanismes ne donne au LLM le droit de calculer ou
d'écrire une priorité.

### 1.10 Sauvegarde

Tout l'état vit dans **un seul fichier** : `prioris.db`. Une copie datée
suffit (cron quotidien recommandé) :

```bash
cp prioris.db "backup/prioris-$(date +%F).db"
```

---

## Partie 2 — Utilisation quotidienne

### 2.1 La routine (10 min/jour)

| Moment | Action |
|---|---|
| Au fil de l'eau | une tâche arrive → `/add <titre>` → catégorie → date limite éventuelle → entretien |
| Le matin | `/today` → énergie → capacité → plan reçu (et écrit dans Obsidian) |
| Quand c'est fait | `/done` → choisir la tâche dans la liste (ou `/done <id>`) |
| Doute sur un score | `/why` → choisir la tâche dans la liste (ou `/why <id>`) |
| Info nouvelle | `/info <texte>` → tâches impactées ou nouvelle tâche → confirmation |
| Régulièrement | `/scan` → prioriser les tâches du vault Obsidian une par une |

`/why` et `/done` **sans argument** affichent la liste des tâches en boutons
(`#id · priorité · titre`) : pas besoin de retenir les identifiants.

Toute action qui **modifie** une tâche (`/done`, y compris via les boutons)
affiche d'abord une confirmation avec la fiche de la tâche (id, titre,
priorité, catégorie, note source) — impossible de se tromper de numéro.

À la question « Instinctivement, tu la classes comment ? », le bot envoie
l'**image de la matrice** en rappel, et chaque bouton porte sa légende :
P1 🔥 urgent+important · P2 🎯 important, pas urgent · P3 ⚡ urgent, pas
important · P4 🗑 ni l'un ni l'autre. Le résultat rappelle aussi le quadrant
en toutes lettres.

### 2.2 Ajouter et évaluer une tâche

```
Toi : /add Préparer l'atelier projet de jeudi
Bot : Catégorie ?                     [Travail] [Carrière] [Santé] …
Bot : Cette tâche a-t-elle une date limite de résolution ?
Bot : Instinctivement, tu la classes comment ?   [P1] [P2] [P3] [P4]
Bot : Quelle différence réelle entre « fait » et « pas fait » ?
Bot : Si personne n'y touche pendant un mois… ?  [Aucune] [Gêne] …
Bot : Qui est bloqué si ce n'est pas fait cette semaine ?
Bot : Comment le coût évolue-t-il si tu attends ?
Bot : Cette tâche contribue-t-elle à un objectif de vie ?
Bot : Temps nécessaire, réalistement ?
Bot : Priorité P4 — Q4 — score 22/100 … Biais détectés : client (fort)…
```

Points clés :

- **Réponds avec les faits, pas le ressenti** — la question « instinctivement »
  capture justement ton ressenti pour le comparer au calcul. C'est le cœur
  du système anti-biais : ne « corrige » pas ton instinct, donne-le brut.
- **« 🤷 Je ne sais pas » est une réponse légitime.** L'axe prend une valeur
  médiane et l'évaluation est marquée provisoire — mieux qu'une fausse certitude.
- **Date limite** : si la tâche a une vraie date de résolution, indique-la au
  format `AAAA-MM-JJ` au moment de la création. Elle influence l'horizon,
  peut déclencher l'entretien complet et active le plancher deadline quand le
  coût du retard est une falaise. Si la date est floue, choisis **Aucune date
  limite** plutôt que d'inventer.
- **L'entretien s'allonge tout seul quand il le faut** (P1 instinctif,
  conséquence grave, deadline < 7 j, contradiction) : 7 questions deviennent
  13. C'est voulu : une tâche à enjeu mérite ses questions.
- **Si le bot signale une contradiction** (⚠️), il pose une question de
  clarification avec 3 choix. Réponds honnêtement : la correction s'applique
  à l'axe, jamais au score directement.
- **Avec le LLM activé** : tu peux répondre en texte libre à toutes les
  questions à choix (« honnêtement pas grand-chose, ça peut glisser »,
  « plutôt P2 », « environ une heure », « c'est surtout le client »). Le bot
  reformule et propose l'option comprise → tu confirmes ✅ ou corriges ✏️.
  L'hésitation détectée (« je pense », « peut-être ») est enregistrée comme
  incertitude quand la question le permet. Si le LLM est KO/offline, PRIORIS
  explique l'échec et repasse aux boutons.
  Après confirmation de la réponse « Instinctivement », PRIORIS utilise ce
  P1/P2/P3/P4 pour préparer 3 questions de challenge. Il termine d'abord
  l'entretien factuel, puis les pose **une seule à la fois**, juste avant le
  calcul final :
  est-ce une vraie échéance ou seulement de la pression ? y a-t-il un impact
  mesurable ? manque-t-il une information ? Chaque réponse est attendue,
  interprétée par le LLM, puis peut proposer une correction d'axe (`CDR`,
  `INA`, `BLK`, `IMP`, `HOR`, `IRR`, `ALN`). La correction n'est appliquée au
  calcul que si tu confirmes. Une question sans réponse n'est jamais utilisée.
  Hors entretien, un message libre propose de créer la tâche.

### 2.3 Le plan du jour

```
Toi : /today
Bot : Ton énergie aujourd'hui ?   [Très faible] … [Excellente]
Bot : Heures maîtrisables ?       [2 h] [4 h] [6 h] [8 h]
Bot : 📋 Plan du jour (192 min utiles) :
      1. Finaliser modèle de données (90 min · P1)
      2. 45 min de sport 💎 (45 min · P2)
      Non retenu : préparer slides internes
```

Ce qu'il faut savoir pour l'interpréter :

- **« Heures maîtrisables »** = temps réellement à ta main, hors réunions et
  interruptions. Sois pessimiste : le moteur retire déjà 20 % de marge.
- **Ordre de sélection** : les P1 sont considérées en premier, triées par valeur
  décroissante. Ensuite PRIORIS remplit la capacité restante avec les P2/P3.
- **Valeur de planification** : `score_global + bonus pépite + bonus échéance
  + ajustement énergie`. Une échéance proche peut donc faire remonter une tâche
  face à une autre, sans rendre planifiable une P4.
- **Contraintes réalistes** : P4 jamais planifiée, estimation inconnue jamais
  planifiée, maximum 3 tâches majeures, effort incompatible évité si l'énergie
  du jour est faible. Une P1 trop grosse peut être seulement entamée si la
  capacité restante le permet.
- **Un plan court est un plan honnête.** 2 tâches faites > 12 planifiées.
  Jamais plus de 3 tâches « majeures » (> 1 h ou effort élevé).
- **L'énergie compte** : à « très faible », les tâches de conception sont
  exclues ; à « excellente », elles sont favorisées et les tâches mécaniques
  attendront un jour creux.
- **Les dates de réalisation comptent dans l'ordre du plan** : une tâche avec
  une échéance proche reçoit un bonus borné qui concurrence le score global
  (`G`). Une tâche moins bien notée peut donc passer devant si elle est due
  demain, mais la date ne contourne pas les garde-fous : P4 reste exclue,
  l'énergie et la capacité restent respectées, et le plan signale l'échéance
  dans la note de la ligne.
- **Les P4 ne sont jamais planifiés** — le bot les liste comme candidates à
  l'abandon. Les abandonner est une décision, pas un échec.
- Le plan est aussi écrit dans `PRIORIS/Plan du jour.md` (cases cochables
  dans Obsidian).

### 2.4 Lire une évaluation

- **P1** : urgent ET important → à faire en premier.
- **P2** : important, pas urgent → *le quadrant des objectifs* ; c'est lui
  que le système protège (sport, CV, finances y montent structurellement).
- **P3** : urgent, pas important → traiter vite et petit, ou déléguer.
- **P4** : ni l'un ni l'autre → reporter sans culpabilité, ou abandonner.
- **💎 pépite** : faible coût, forte valeur — remonte dans tous les plans.
- **Écart** entre ton instinct et le calcul : c'est la matière du coaching.
  Un écart de 2–3 niveaux répété sur les demandes client = ton biais documenté.
- Tu peux **contester** : `/why <id>` montre chaque terme du calcul. Si un
  axe est faux, refais l'entretien — on corrige les entrées, jamais la sortie.

### 2.4.1 Ajouter une information ou une contrainte

Si tu reçois une information nouvelle, utilise d'abord le mode global :

```bash
/info Le client est bloqué depuis ce matin
/info La deadline réelle est vendredi et après ce sera trop tard
```

PRIORIS effectue d'abord une présélection locale déterministe de **cinq tâches
maximum** : texte normalisé, mots significatifs communs, puis ordre stable par
pertinence et id. Le LLM ne reçoit que ces candidates et doit classer chacune
indépendamment ; tout id extérieur est rejeté. Si la présélection est vide, il
doit proposer une nouvelle tâche. Cette approche réduit le contexte et les faux
rapprochements sans embarquer un second modèle d'embeddings. Le LLM propose
ensuite une liste d'ids avec une explication tâche par tâche. Cette liste est une proposition :
tu peux choisir seulement certaines tâches, ou cibler directement une tâche avec :

```bash
/info 12 Le client est bloqué depuis ce matin
```

En GUI, clique **💬 Info / question** sans sélectionner de tâche pour lancer
l'analyse globale. Sélectionne une tâche avant de cliquer pour faire une analyse
ciblée.
Si l'analyse ciblée conclut que l'information ne modifie pas cette tâche,
PRIORIS relance automatiquement l'analyse globale : il peut alors proposer une
autre tâche impactée ou une nouvelle tâche à créer.
Dans la fenêtre **Tâches à analyser**, tu peux modifier la liste d'ids proposée ;
si tu laisses le champ vide, cela signifie **créer une nouvelle tâche**.
Cette création suit le même flux qu'une tâche normale : catégorie, date limite
éventuelle, puis entretien de priorisation.
Si le LLM identifie une échéance dans l'information (`ce soir`, `demain`,
`d'ici une heure`, ou une date `AAAA-MM-JJ`), PRIORIS affiche
**Date limite détectée**. Cette date n'est jamais appliquée automatiquement :
en GUI, le champ de date est prérempli et tu peux confirmer ou modifier ; dans
Telegram, tu peux utiliser la date proposée, la modifier, ou choisir aucune date.

Si ton `/info` est formulé comme une question, PRIORIS affiche aussi une
**réponse directe courte** avant l'analyse d'impact. Cette phrase est seulement
informative : les modifications éventuelles restent soumises à confirmation.

Pour chaque tâche retenue, le LLM lit l'évaluation actuelle et l'information
nouvelle. Il ne recalcule pas la priorité lui-même : il propose seulement des
changements d'axes factuels (`BLK`, `CDR`, `HOR`, `IMP`, `INA`, `IRR`, `ALN`) avec
une explication. PRIORIS affiche alors l'ancien score, le nouveau score calculé
par le moteur déterministe et la liste des axes modifiés. Rien n'est écrit tant
que tu ne confirmes pas.

Si tu confirmes, PRIORIS crée une **nouvelle évaluation append-only** et garde
l'information dans `task_notes`. L'ancienne évaluation reste consultable en base.
Si la tâche vient d'Obsidian (`/scan`) et que le vault est configuré, PRIORIS
propose ensuite une **synchronisation Obsidian** : il affiche un aperçu
**avant / après** des fichiers qui seraient modifiés (note de détail PRIORIS et,
si besoin, marqueur de priorité sur la ligne source). Tu peux accepter ou refuser ;
rien n'est écrit dans le vault sans confirmation. La note `PRIORIS/<id>.md`
contient aussi une section **Informations ajoutées** avec les notes saisies via
`/info`.
Si aucune tâche existante ne semble clairement impactée, le LLM propose une
nouvelle tâche à créer, que tu peux accepter ou ignorer.

Sans LLM, l'analyse globale automatique n'est pas possible. PRIORIS propose alors
un repli manuel : tu sélectionnes explicitement la tâche et l'axe à modifier.

```bash
/info 12 BLK=4 Le client est maintenant bloqué
/info 18 CDR=4 Tout se joue à la deadline de vendredi
```

En GUI sans LLM, sélectionne la tâche puis clique **💬 Info / question** et saisis
le même format, par exemple `BLK=4 Le client est maintenant bloqué`. PRIORIS
affiche quand même l'ancien score, le nouveau score et demande confirmation avant
d'écrire une nouvelle évaluation.

### 2.5 /goals et la question miroir (V0.4)

**Objectifs de vie.** Déclare-les une fois : `/goals Développer une activité
drone`, `/goals Améliorer ma condition physique`… `/goals` seul liste les
objectifs actifs (avec leur avancement en tâches) et permet de les marquer
atteints 🏆 ou suspendus ⏸. Dès qu'un objectif existe, la question
« objectifs » de l'entretien propose TES objectifs en boutons : tu choisis
lequel et le niveau de contribution (indirecte / directe / majeure). La tâche
est liée à l'objectif, et une contribution majeure est protégée par le
scoring (plancher d'importance §6.2 : jamais P3/P4).

Dans la GUI, cette même question affiche aussi **➕ Créer un nouvel objectif** :
utile si l'objectif existe dans ta tête mais pas encore dans PRIORIS. Il est créé,
puis sélectionné immédiatement pour la tâche en cours. Si tu ne veux rattacher la
tâche à aucun objectif, choisis simplement **Aucun objectif**.

La fiche d'un objectif (touche-le dans /goals) permet aussi de **changer sa
catégorie** 📁 et de lancer une **vérification de cohérence** 🔍 : le LLM
signale les tâches rattachées qui ne semblent pas contribuer à l'objectif,
avec un bouton « Détacher » par tâche — il signale, tu décides. À l'entretien,
si le LLM est actif, l'objectif le plus probable est marqué ⭐ (simple
suggestion, c'est toujours toi qui choisis).

**Question miroir 🪞.** En fin d'entretien, une (et une seule) question de
vérification peut apparaître, choisie selon tes réponses : « Serais-tu
surpris qu'on te demande des comptes dans 15 jours ? » (si tu as dit que
l'inaction ne coûte rien), « Quelqu'un reprendrait-il cette tâche si tu
partais demain ? » (si impact majeur), « La personne bloquée t'a-t-elle
relancé ? » (si blocage fort), « Et si tu la faisais la semaine prochaine ? »
(si P1 instinctif). Une réponse qui contredit tes dires corrige l'axe
concerné — comme toujours, on corrige les entrées, jamais le score.

### 2.5.1 Comment les réponses LLM influencent le quadrant

PRIORIS respecte une règle stricte : **une question affichée = une réponse
attendue**. Les textes générés par le LLM ne servent au calcul que s'ils passent
par ce flux :

1. PRIORIS termine les questions factuelles, puis pose un seul challenge.
2. Tu réponds.
3. Le LLM interprète la réponse comme une proposition d'axe et de valeur :
   `CDR` coût du retard, `INA` conséquence de ne rien faire, `BLK` blocage,
   `IMP` impact, `HOR` horizon, `IRR` irréversibilité, `ALN` objectif.
4. PRIORIS explique la correction proposée.
5. Tu confirmes ou refuses.
6. Seulement si tu confirmes, l'axe est modifié dans la session d'entretien.

Le calcul final est ensuite déterministe et n'appelle plus le LLM :

- urgence `U = 30×BLK/5 + 40×CDR/4 + 30×HOR/4`
- importance `I = 35×IMP/4 + 25×INA/4 + 20×IRR/3 + 20×ALN/3`
- score global `G = 0,6×I + 0,4×U`
- seuil urgent : `U >= 55`
- seuil important : `I >= 50`
- quadrant : `Q1` si urgent et important, `Q2` si important seul, `Q3` si
  urgent seul, `Q4` sinon
- priorité : `Q1 -> P1`, `Q2 -> P2`, `Q3 -> P3`, `Q4 -> P4`

Les planchers protègent certains cas : deadline réelle très proche, forte
irréversibilité, contribution majeure à un objectif. Les biais sont détectés
après ce calcul en comparant les axes, le résultat calculé et ton classement
instinctif.

### 2.5.2 Référence exhaustive des paramètres

Les sept axes sont les **seules entrées pondérées du score**. Une réponse de
bouton, une réponse libre interprétée puis confirmée, une clarification ou une
question miroir aboutissent toutes au même résultat : une valeur entière sur
l'échelle de l'axe concerné. La date confirmée peut seulement activer le
plancher déterministe décrit plus bas. Le LLM ne fournit jamais directement
`U`, `I`, `G`, le quadrant ou la priorité.

| Axe | Rattaché à | Question factuelle et échelle complète | Exemple chiffré |
|---|---|---|---|
| `BLK` blocage réel, `0..5` | Urgence, poids 30 | « Qui est bloqué si ce n'est pas fait cette semaine ? » `0` personne ; `1` moi seul ; `2` une autre personne ; `3` une équipe ou plusieurs personnes ; `4` un acteur critique ; `5` plusieurs équipes ou une chaîne critique. | Un acteur critique réellement empêché d'avancer donne `BLK=4`, donc `30×4/5 = 24` points d'urgence. L'échelle combine étendue et criticité : une personne seulement en attente n'est pas forcément bloquée. |
| `CDR` coût du retard, `0..4` | Urgence, poids 40 | « Comment le coût évolue-t-il si tu attends ? » `0` rien ; `1` accumulation douce ; `2` nette ; `3` aggravation croissante ; `4` falaise à une date. | Un dépôt impossible après vendredi donne `CDR=4`, soit `40×4/4 = 40` points d'urgence. |
| `HOR` horizon, `0..4` | Urgence, poids 30 | « Quand le problème deviendra-t-il visible ? » `0` jamais ; `1` dans plus d'un mois ; `2` dans 2 à 4 semaines ; `3` cette semaine ; `4` déjà visible. | Une conséquence visible cette semaine donne `HOR=3`, soit `30×3/4 = 22,5` points d'urgence. |
| `IMP` impact, `0..4` | Importance, poids 35 | `Quelle différence réelle entre « fait » et « pas fait » ?` `0` négligeable ; `1` confort ; `2` notable ; `3` majeure ; `4` structurante. | Une certification qui change réellement l'accès à un poste peut donner `IMP=3`, soit `35×3/4 = 26,25` points d'importance. |
| `INA` coût d'un mois d'inaction, `0..4` | Importance, poids 25 | « Si personne n'y touche pendant un mois, que se passe-t-il concrètement ? » `0` rien ; `1` gêne ; `2` vrai problème ; `3` crise ; `4` dégâts irrécupérables. | Un mois sans agir crée un vrai problème mais pas une crise : `INA=2`, soit `25×2/4 = 12,5` points d'importance. |
| `IRR` irréversibilité, `0..3` | Importance, poids 20 | « Peut-on revenir en arrière ou rattraper plus tard ? » `0` réversible ; `1` rattrapable avec effort ; `2` rattrapable jusqu'à une date ; `3` irréversible. | Une option récupérable seulement avant signature donne `IRR=2`, soit `20×2/3 = 13,33` points d'importance. |
| `ALN` alignement objectif, `0..3` | Importance, poids 20 | « Cette tâche contribue-t-elle à un de tes objectifs de vie ? » `0` aucun ; `1` indirecte ; `2` directe ; `3` majeure. | Préparer l'examen décisif d'un objectif actif peut donner `ALN=3`, soit 20 points et le plancher d'importance décrit plus bas. |

**Entretien express et valeurs dérivées.** Le flux express demande le
classement instinctif, puis `IMP`, `INA`, `BLK`, `CDR`, `ALN` et l'estimation,
une question et une réponse à la fois. `IMP` est toujours explicite : l'impact
positif d'une action et le dommage d'un mois d'inaction sont deux critères
indépendants. S'il ne bascule pas en mode complet, seuls `IRR = 1` et `HOR`
sont dérivés. `HOR` vient de la date limite :
`4` si elle est échue ou aujourd'hui, `3` à 1-7 jours, `2` à 8-30 jours,
`1` au-delà de 30 jours, ou la médiane `2` sans date. Ces valeurs sont marquées
« par défaut » dans la justification. Le mode complet demande explicitement
`HOR` et `IRR`, puis l'effort et les métadonnées de biais.

**Incertitude et robustesse.** « Je ne sais pas » ne vaut pas zéro. Le score
central utilise la médiane conservatrice : `BLK=2`, `CDR=2`, `HOR=2`, `IMP=2`,
`INA=2`, `IRR=1`, `ALN=1`. En parallèle, l'algorithme v2 calcule un intervalle :

- réponse certaine `v` : `[v, v]` ;
- réponse hésitante `v` : `[max(0,v-1), min(max_axe,v+1)]` ;
- réponse inconnue : `[médiane-1, médiane+1]`, borné par l'échelle ;
- ancien dossier où `IMP` avait été dérivé : intervalle strict `[0,4]`.

Les coins bas et haut sont recalculés avec les mêmes poids et planchers. Si
l'intervalle de `U` traverse 55 ou celui de `I` traverse 50, le quadrant est
**sensible** et l'évaluation provisoire. PRIORIS liste tous les quadrants
possibles et nomme comme **axe pivot** l'axe incertain dont l'amplitude pondérée
`poids × (haut-bas) / maximum` est la plus forte sur le seuil traversé.
Exemple : `IMP=2` hésitant donne `[1,3]`, soit une amplitude de
`35×2/4=17,5` points d'importance. Si `I` varie alors de 42 à 59, Q4 et Q2
sont possibles et `IMP` est l'axe à clarifier en premier. Si aucun seuil n'est
traversé, le quadrant est robuste même si une réponse était hésitante.

**Questions anti-biais et prémisse fausse.** Les trois questions formulées par
le LLM sont des hypothèses de vérification, pas des faits. Elles sont posées une
par une après les questions factuelles. Pour chaque réponse, l'interpréteur
produit exactement l'un de ces résultats :

1. `correction` : un fait permet de proposer au plus un axe et une valeur ; la
   GUI ou Telegram explique la proposition et attend la confirmation avant de
   modifier le calcul ;
2. `premise_false` : la réponse rejette une hypothèse contenue dans la question ;
   elle est conservée dans l'historique. Sans autre fait exploitable, aucun axe
   n'est modifié et l'entretien passe à la question suivante ;
3. `no_change` : le LLM s'abstient ou sa confiance est inférieure à `0,55` ; la
   réponse est conservée avec une incertitude forte, aucun chiffre n'est
   inventé et l'entretien continue.

Cas particulier déterministe : une réponse réduite à `oui`, `non` ou une
variante non ambiguë (`pas du tout`, `tout à fait`) est complète pour une
question fermée. PRIORIS la reconnaît avant l'appel au LLM, l'enregistre avec
une incertitude nulle et continue avec `no_change`, car confirmer ou rejeter une
hypothèse ne fournit pas à lui seul une valeur numérique pour un axe. Exemple :
à « Y a-t-il une pression sociale qui influence P1 ? », `non` signifie que ce
biais proposé est rejeté ; ce n'est ni une panne ni une raison de modifier
`CDR`, `IMP` ou un autre axe.

Une contestation explicite sans fait supplémentaire, par exemple « la question
comporte une information fausse », suit le même chemin déterministe : aucun
appel LLM n'est nécessaire, l'incertitude d'interprétation vaut zéro, aucun axe
n'est modifié et l'entretien continue. Si la même réponse contient aussi un
fait exploitable, par exemple une échéance ou une action immédiate, le LLM reste
appelé afin de proposer au plus une correction confirmable.

La dernière question miroir dispose du même garde-fou conservateur. Lorsque ses
options sont exactement « Un vrai problème », « Rien de grave, en fait » et
« Je ne sais pas », une conséquence explicitement mortelle, vitale ou grave est
classée dans la première option avec une incertitude nulle. Par exemple « je
meurs car j'ai besoin de manger pour vivre » soutient « Un vrai problème ».
« Il ne se passerait rien de grave » soutient la seconde option. Sans marqueur
fort, le repli ne choisit rien et laisse le LLM ou les boutons traiter la
réponse. L'interprétation reste affichée et soumise à confirmation avant toute
correction issue de la question miroir.

Exemple : « Pourquoi cette tâche est-elle urgente alors qu'elle ne nécessite
pas d'action immédiate ? » contient une hypothèse. « Cette information est
fausse : je dois agir maintenant » produit au minimum `premise_false`. Si la
suite précise « avant 12 h, sinon je perds le créneau », le LLM peut en plus
proposer une correction de `CDR`, que l'utilisateur doit confirmer. « La
prémisse est fausse » seule ne suffit jamais à choisir arbitrairement une
valeur. Ainsi, toute réponse est utilisée soit comme fait confirmé dans les
axes, soit comme trace d'audit ; seules les valeurs confirmées entrent dans les
formules `U`, `I` et `G`.

**Paramètres qui ne rentrent pas directement dans le score.**

| Paramètre | Question ou origine | Utilisation réelle | Exemple |
|---|---|---|---|
| Priorité instinctive `P1..P4` | « Instinctivement, tu la classes comment ? » | Déclenche éventuellement le mode complet, choisit les challenges et mesure l'écart/biais ; ne force jamais le quadrant. | Dire P1 puis obtenir P4 produit un écart de 3 niveaux à expliquer, pas une remontée artificielle du score. |
| Date limite | Saisie à la création ou proposée par `/info` puis confirmée | Dérive `HOR` en express, déclenche le mode complet si elle est à moins de 7 jours, peut activer le plancher deadline et fournit le bonus du plan. | Une date à J+3 donne `HOR=3`; avec `CDR=4`, `U` est ensuite au minimum 70. |
| Estimation | `<15`, `15-30`, `30-60`, `1-2 h`, `2-4 h`, `>4 h`, inconnue | Convertie respectivement en `10, 22, 45, 90, 180, 300` minutes ; sert à la pépite, au levier et à la capacité du plan. Une estimation inconnue rend l'évaluation provisoire et exclut la tâche du plan. | `30-60 min` vaut 45 minutes pour la planification. |
| Effort | Faible, moyen, élevé | Ajuste la valeur selon l'énergie ; un effort élevé fait aussi de la tâche une tâche majeure. | À énergie 1, une P2 d'effort élevé est exclue ; une vraie P1 reste proposée avec avertissement. |
| Demandeur | Moi, collègue, manager, client | Détection de biais uniquement, jamais le score. | Une demande client sans blocage ni coût du retard peut signaler un biais client. |
| Visibilité `0..3` | Niveau d'exposition de la tâche | Détection des biais de visibilité et de bruit uniquement. | Une tâche très discutée avec `IMP<=1` et `INA<=1` est signalée comme bruit. |
| Pression `0..3` | Pression ressentie | Détection du biais de culpabilité uniquement. | Pression forte avec `BLK<=1` et `INA<=1` déclenche un signal, sans ajouter de points. |

### 2.5.3 Calcul exact du score et exemple complet

Chaque axe est normalisé par son maximum avant application de son poids. Les
trois scores restent donc compris entre 0 et 100 :

```text
U = 30 × BLK/5 + 40 × CDR/4 + 30 × HOR/4
I = 35 × IMP/4 + 25 × INA/4 + 20 × IRR/3 + 20 × ALN/3
G = 0,6 × I + 0,4 × U
```

Avant de calculer `G`, trois planchers déterministes sont appliqués dans cet
ordre :

1. date limite à 7 jours ou moins **et** `CDR=4` : `U = max(U, 70)` ;
2. `IRR=3` **et** `INA>=3` : `I = max(I, 70)` ;
3. `ALN=3` **et** (`IMP>=2` ou `INA>=2`) : `I = max(I, 55)`.

Le troisième garde-fou empêche un simple alignement déclaré de forcer P2 sans
impact ni conséquence d'inaction mesurable. Ces planchers ne rajoutent pas 70 points : ils remontent seulement un total
inférieur au seuil indiqué. Le JSON de justification conserve les termes avant
plancher et chaque ajustement avant/après.

Le quadrant utilise ensuite `U >= 55` et `I >= 50` :

| Urgent | Important | Quadrant | Priorité | Lecture |
|---|---|---|---|---|
| oui | oui | Q1 | P1 | faire en premier |
| non | oui | Q2 | P2 | planifier et protéger |
| oui | non | Q3 | P3 | déléguer ou traiter vite et petit |
| non | non | Q4 | P4 | reporter ou abandonner |

**Exemple complet : 45 minutes d'activité physique liée à un objectif.**
Supposons `BLK=1`, `CDR=3`, `HOR=1`, `IMP=3`, `INA=2`, `IRR=1`, `ALN=3` :

```text
U = 30×1/5 + 40×3/4 + 30×1/4 = 6 + 30 + 7,5 = 43,5
I = 35×3/4 + 25×2/4 + 20×1/3 + 20×3/3
  = 26,25 + 12,5 + 6,67 + 20 = 65,42
G = 0,6×65,42 + 0,4×43,5 = 56,65
```

`U < 55` et `I >= 50` donnent Q2/P2. Aucun plancher ne change ici le résultat,
car `I` dépasse déjà 55. Avec une estimation connue de 45 minutes, cette tâche
est aussi une **pépite** : `I >= 50` et durée `<= 60 min`. Son levier affiché
est `I / max(durée_en_heures, 0,25)`, ici environ `87,2` points d'importance par
heure. Le levier est informatif ; seul le bonus pépite de 10 intervient dans le
plan du jour.

### 2.5.4 Calcul exhaustif du plan du jour

1. **Capacité utile.** PRIORIS prend `entier(capacité déclarée × 0,8)`. Quatre
   heures maîtrisables donnent donc 192 minutes planifiables.
2. **Éligibilité.** Une P4 ou une estimation inconnue est exclue avant le tri.
3. **Valeur de tri.** Pour chaque candidate :

```text
V = G + bonus_pépite + bonus_échéance + ajustement_énergie
```

Le bonus pépite vaut `+10` si `I >= 50`, estimation connue et durée `<= 60 min`.
Le bonus d'échéance est borné et dépend du nombre de jours restants :

| Échéance | J<=0 | J<=1 | J<=3 | J<=7 | J<=14 | J<=30 | >30 ou aucune |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bonus | +40 | +35 | +28 | +20 | +12 | +6 | 0 |

L'ajustement d'énergie dépend de l'effort :

| Énergie | Effort faible | Effort moyen | Effort élevé |
|---|---:|---:|---:|
| 1, très faible | 0 | -25 | exclu, sauf P1 |
| 2, faible | 0 | 0 | -25 |
| 3, moyenne | 0 | 0 | 0 |
| 4 ou 5, forte/excellente | -10 | 0 | +10 |

4. **Ordre.** Toutes les P1 éligibles sont triées par `V` décroissante et
   examinées avant toute P2/P3. La capacité restante est ensuite remplie avec
   les P2/P3, elles aussi par `V` décroissante. Une égalité est départagée par
   l'identifiant de tâche, ce qui rend le plan reproductible.
5. **Garde-fous.** Une tâche majeure est une tâche d'au moins 60 minutes ou
   d'effort élevé ; le plan en contient au maximum 3. Une P1 exigeante à
   énergie très faible reste considérée, mais reçoit un avertissement. Une P2
   ou P3 incompatible est exclue.
6. **Capacité insuffisante.** La tâche est prise entière si elle tient. Sinon,
   si `G >= 60` et qu'il reste au moins 60 minutes, PRIORIS propose une tranche
   « entamer 60 min ». Sinon elle est exclue pour capacité insuffisante.

**Exemple de concurrence date/score, sans bonus pépite.** Une P2 à `G=72`,
échéance J+30, effort moyen vaut `72+6=78`. Une P2 à `G=55`, échéance demain,
vaut `55+35=90` : elle passe devant. En revanche, une P4 due aujourd'hui reste
exclue malgré son bonus théorique, car l'éligibilité est vérifiée avant le
calcul de `V`.

### 2.5.5 Modèles, sensibilité, limites et sources

PRIORIS emploie deux modèles successifs qu'il ne faut pas confondre :

1. **classification** : les seuils de `U` et `I` choisissent Q1-Q4/P1-P4 ;
2. **ordonnancement** : `G`, puis `V`, départagent les tâches déjà classées et
   remplissent la capacité du jour.

Ainsi, deux P2 peuvent avoir des `G` différents, mais un grand `G` ne transforme
jamais une P4 en P2. L'intervalle de robustesse teste la stabilité de la
classification ; il ne constitue pas une probabilité. Les poids actuels sont
conservés pour assurer la continuité. Une future calibration doit partir de
cas réellement observés et d'une **swing weighting** : comparer la valeur d'un
passage du minimum au maximum de chaque critère, puis tester la sensibilité des
résultats, comme recommandé par le guide MCDA du gouvernement britannique
([MCDA, GOV.UK](https://www.gov.uk/government/publications/green-book-supplementary-guidance-multi-criteria-decision-analysis/use-of-multi-criteria-decision-analysis-in-options-appraisal-of-economic-cases)).

Limites à auditer sur les données d'usage :

- `CDR` et `HOR` peuvent décrire une partie du même phénomène temporel. Il faut
  mesurer leur corrélation avant de réduire un poids ; l'intervalle et l'axe
  pivot rendent déjà les cas fragiles visibles.
- `BLK` est ordinal et mélange nombre de personnes et criticité. Les libellés
  v2 clarifient ce compromis, mais `BLK=4` n'est pas mathématiquement « deux
  fois » `BLK=2`.
- le bonus d'échéance du plan, borné à `+40`, est une heuristique distincte du
  score ; il évite qu'une date proche soit ignorée mais doit être réévalué sur
  l'historique des plans.
- les dépendances entre tâches ne sont pas encore modélisées ; `BLK` exprime
  seulement le blocage courant.
- la présélection `/info` est lexicale. Des embeddings amélioreraient les
  synonymes, mais ajouteraient un modèle, du poids disque et une nouvelle
  chaîne d'inférence offline ; ce choix est donc reporté et explicite.

Références utilisées : le modèle additif pondéré et l'analyse de sensibilité
s'appuient sur le guide MCDA précité et sur l'étude du JRC consacrée à la
robustesse des classements sous incertitude
([JRC, 2013](https://publications.jrc.ec.europa.eu/repository/handle/JRC87397)).
Le principe « coût du retard divisé par durée » est une référence de comparaison,
pas la formule de PRIORIS
([WSJF, Scaled Agile](https://framework.scaledagile.com/wsjf/)). Pour les sorties
LLM structurées, voir la documentation officielle des grammaires GBNF de
[llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md),
les sorties contraintes de
[mistral.rs](https://github.com/EricLBuehler/mistral.rs) et l'évaluation
[JSONSchemaBench](https://arxiv.org/abs/2501.10868). Ces sources justifient la
méthode ; les poids et seuils restent des choix produit versionnés, à calibrer
sur l'usage de PRIORIS.

### 2.6 /scan — prioriser les tâches de ton vault (V0.3)

`/scan` parcourt tout le vault et trouve les tâches `- [ ]` **non priorisées**
(les lignes déjà marquées 🎯, les tâches cochées, le dossier PRIORIS/ et les
notes avec `prioris: ignore` en frontmatter sont ignorés). Il propose ensuite
de les évaluer **une par une** : catégorie → entretien habituel → résultat.

Après chaque évaluation, PRIORIS écrit dans le vault :

1. **La ligne de la tâche est annotée** dans sa note d'origine :
   `- [ ] Mettre à jour le CV 🎯P2 [[PRIORIS/12]]`
   Seule cette ligne est modifiée, rien d'autre. Si la note a changé entre le
   scan et l'évaluation, PRIORIS **n'écrit pas** et te le dit.
2. **Une note de détail** est créée dans `PRIORIS/<id>.md` avec un titre clair
   `# PRIORIS #<id> — <titre>` : score, axes, ajustements, biais détectés, lien
   retour vers la note source.

**Synchronisation automatique** : avant de chercher les nouvelles tâches,
`/scan` récupère tes modifications manuelles dans le vault. Une tâche marquée
🎯 que tu as **cochée** dans Obsidian (`- [x]`) est marquée faite dans PRIORIS
(temps loggé) — fiable même si tu as modifié le texte de la ligne, car l'id
est porté par le lien `[[PRIORIS/12]]`. Les anciens liens longs
`[[PRIORIS/details/12 - titre|détail]]` restent lus et sont migrés vers le format
court lors d'une synchronisation. Une tâche marquée 🎯 qui a
**disparu** du vault est signalée mais son statut est conservé : à toi de
décider (/done ou ignorer).

La symétrie existe aussi : `/done` dans Telegram **coche la case** `- [x]`
de la ligne 🎯 correspondante dans ta note Obsidian (retrouvée par son id,
donc fiable même si tu as réécrit la ligne).

En GUI, le bouton **🔁 Sync Obsidian** propose une synchronisation complète
PRIORIS → Obsidian pour toutes les tâches déjà liées au vault. PRIORIS affiche
un aperçu **avant / après** de chaque fichier concerné dans une fenêtre dédiée,
avec les boutons **Appliquer au vault** et **Refuser** dans cette même fenêtre.
Cette synchronisation régénère les notes `PRIORIS/<id>.md` et ajuste les
marqueurs de priorité `🎯P...` sur les lignes source quand ils ont changé. Elle
ne crée pas arbitrairement de nouvelles lignes dans le vault pour les tâches
locales sans `obsidian_path`.

Le tag `#sujet/x` et la date `📅 YYYY-MM-DD` de la ligne sont récupérés
(la date devient la deadline réelle de l'évaluation). Tu peux t'arrêter à
tout moment (⏹ Stop) : les tâches restantes seront retrouvées au prochain
`/scan`. Le dossier PRIORIS est renommable via `[obsidian] prioris_dir`.

### 2.7 Les 3 premières semaines (critère du §0)

Le MVP est en période d'essai contre son critère de succès :
utilisation ≥ 5 j/7, et ≥ 1 décision réellement changée par semaine
(une « urgence » dépriorisée, une tâche personnelle faite).

Conseils pour cette période : évalue **tout** ce qui arrive (même le trivial,
l'entretien express coûte 30 s) ; fais confiance au P4 même quand il pique ;
note les scores qui te semblent faux — si un axe est systématiquement mal
posé, c'est l'algorithme qu'on ajustera (nouvelle `version_algo`), pas les
scores à la main.

### 2.8 Dépannage

| Symptôme | Cause probable | Remède |
|---|---|---|
| Le bot ne répond pas | processus arrêté | relancer ; vérifier `systemctl status prioris` / logs |
| `Config introuvable` | lancé hors du dossier | lancer depuis `prioris/` ou passer le chemin : `python -m prioris.bot.main /chemin/config.toml` |
| `Unauthorized` au démarrage | token invalide | re-copier le token depuis BotFather |
| `TOMLDecodeError: Unescaped '\\'` | chemin collé avec échappement shell | dans `config.toml`, retirer les `\` : `"Mobile Documents"`, pas `"Mobile\ Documents"` |
| Pas d'export Obsidian | `vault_path` vide ou faux | chemin absolu du vault dans `config.toml` |
| Plan vide | tâches en P4, estimations « inconnue », ou énergie très faible | `/list` pour voir l'état ; estimer les tâches ; c'est peut-être un plan honnête |
| Entretien bloqué | session mémoire perdue (redémarrage) | relancer `/add` — rien n'est corrompu, SQLite est la source de vérité |
| Une question anti-biais contient une prémisse fausse | question générée trop affirmative | répondre librement « la prémisse est fausse » et préciser le fait correct si possible ; la contestation est enregistrée et l'entretien continue sans inventer de score |
| « Je n'ai pas pu interpréter » systématique | Ollama pas lancé, nom de modèle inexact, ou 1er appel (chargement du modèle) | `/llm` dans Telegram : test aller-retour + cause exacte ; `ollama list` pour le nom ; réessayer après le 1er chargement |

---

## Partie 3 — État du projet et suite

**Fait** : entretien express/complet à boutons, contradictions C1–C6, scoring
déterministe avec `/why`, plan du jour réaliste avec énergie/capacité,
objectifs de vie, question miroir, biais 1–4/7/9, schéma SQLite append-only,
mode Telegram et mode GUI local sans serveur.

**LLM optionnel livré** : mode sans LLM, moteur local déterministe `prioris`,
LLM local GGUF autonome sans port, compatibilité Ollama/LM Studio, endpoints
externes OpenAI/Anthropic/GitHub Copilot/custom, préchauffage, diagnostic
`/llm`/bouton LLM, logs `logs/llm.log`, interprétation de réponses libres et
suggestion d'objectif toujours confirmées par l'utilisateur.

**/info livré** : analyse globale ou ciblée, réponse directe aux questions,
proposition de tâches impactées ou de nouvelle tâche, échéance détectée à
confirmer/modifier, révision d'axes confirmée, repli manuel sans LLM, et
synchronisation Obsidian proposée avec aperçu avant/après.

**Obsidian livré** : `/scan`/bouton Scan pour importer les tâches du vault,
synchro cases cochées Obsidian → PRIORIS, `/done` → case cochée dans Obsidian,
notes `PRIORIS/<id>.md` avec titre clair, format de lien court
`[[PRIORIS/<id>]]`, migration des anciens liens longs, bouton GUI
**🔁 Sync Obsidian** avec confirmation dans une fenêtre d'aperçu.

**État tests** : 225 tests automatisés passent localement dans le dépôt source
complet. Les nouvelles archives release embarquent aussi `tests/` pour permettre
une vérification après extraction.

**Reste à décider / améliorer** : scénarios comparés avancés, alertes
d'équilibre de vie, rapport mensuel de biais, mémoire de décision plus riche,
et éventuelle création de lignes Obsidian pour les tâches locales qui ne viennent
pas du vault. Ces points doivent rester guidés par l'usage réel plutôt que par
une roadmap figée.
