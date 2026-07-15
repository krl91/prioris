"""Local GUI entrypoint, without Telegram.

    python -m prioris.bot.main       (auto-opens GUI when Telegram token is empty)
    python -m prioris.gui.main       (forces local mode)
    python -m prioris.gui.main config.toml
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from .app import MainWindow


def run_gui(cfg: dict) -> None:
    """Launch the main PRIORIS window in local mode.

    `cfg` is the already-parsed config.toml dictionary.
    Blocks until the window is closed.
    """
    app = MainWindow(cfg)
    app.mainloop()


def main() -> None:
    """Direct launch: ``python -m prioris.gui.main [config.toml]``."""
    config_path = Path(sys.argv[1] if len(sys.argv) > 1 else "config.toml")
    if not config_path.exists():
        sys.exit(
            f"Config introuvable : {config_path}\n"
            "(copie config.example.toml → config.toml et laisse token vide)"
        )
    try:
        cfg = tomllib.loads(config_path.read_text("utf-8"))
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"Erreur de syntaxe dans {config_path} : {e}")

    print("PRIORIS démarré — mode local (interface graphique).")
    run_gui(cfg)


if __name__ == "__main__":
    main()
