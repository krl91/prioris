# PRIORIS v0.5.0

## Nouveautés depuis v0.4.14

### Scoring v2

- Le mode express demande désormais `IMP` séparément de `INA`. Une tâche à fort
  impact stratégique n'est plus déclassée parce que son coût d'inaction à un
  mois est faible.
- Les réponses certaines, hésitantes et inconnues produisent un intervalle de
  scores. PRIORIS indique si le quadrant est robuste, les quadrants possibles
  et l'axe pivot à clarifier.
- Le plancher `ALN=3` exige maintenant un impact ou un coût d'inaction mesurable.
  Le seuil « pépite » est aligné sur le seuil d'importance à 50.
- Les libellés `BLK` distinguent mieux étendue du blocage et criticité.

### LLM et `/info`

- `/info` présélectionne localement jusqu'à cinq tâches avant l'analyse LLM et
  rejette tout identifiant extérieur à cette liste.
- Les appels utilisent une température nulle et un budget de sortie adapté à
  chaque opération. Une abstention ou une confiance inférieure à 0,55 déclenche
  le repli manuel.
- Les prompts structurés incluent des exemples courts et une validation plus
  stricte, sans donner au LLM le contrôle du score ou des écritures.

### Documentation et qualité

- README français/anglais mis à jour pour démarrer rapidement.
- Guides français/anglais complétés avec formules, intervalles, exemples,
  limites connues, distinction classification/planification et sources.
- 214 tests Python passent ; les tests de release restent obligatoires avant et
  après construction des archives.

## Télécharger

- macOS Apple Silicon : `prioris-macos-arm64.zip`
- Windows x64 : `prioris-windows-x64.zip`
- Linux x64 : `prioris-linux-x64.tar.gz`
- Vault exemple seul : `ObsidianVault.zip`

Chaque archive OS contient l'application Python, les tests, `ObsidianVault`, le
runtime `llama-simple` sans serveur, le modèle Ministral 3B GGUF et une
configuration prête à démarrer.

Documentation : [README](https://github.com/krl91/prioris/blob/v0.5.0/README.md)
et [guide complet](https://github.com/krl91/prioris/blob/v0.5.0/GUIDE.md).
