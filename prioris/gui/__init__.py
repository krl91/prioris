"""Interface graphique locale (mode sans Telegram).

Lancée automatiquement quand [telegram] token est vide ou absent dans config.toml.
Utilise uniquement tkinter (stdlib Python ≥ 3.11) — zéro installation supplémentaire.

Limites par rapport au mode Telegram :
- accès local uniquement (même machine, même session utilisateur)
- pas d'interface mobile
- pas de notifications push
- le scan Obsidian n'est pas exposé dans l'interface (accessible via config)
- le préchauffage LLM (keep_warm) n'est pas actif
"""
