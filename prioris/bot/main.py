"""PRIORIS bot entrypoint.

    python -m prioris.bot.main            (reads config.toml from repo root)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

try:
    import tomllib                      # Python ≥ 3.11
except ModuleNotFoundError:             # Python 3.10 : pip install tomli
    import tomli as tomllib

from telegram.ext import (ApplicationBuilder, CallbackQueryHandler,
                          CommandHandler, MessageHandler, filters)

from ..llm import ChatClient, LLMConfig, LLMFacade, resolve
from ..llm import health as llm_health
from ..store import db
from ..i18n import normalize_language
from . import handlers


def _needs_gui(cfg: dict) -> bool:
    """Return True when the Telegram token is missing or empty."""
    return not cfg.get("telegram", {}).get("token", "").strip()


def main() -> None:
    config_path = Path(sys.argv[1] if len(sys.argv) > 1 else "config.toml")
    if not config_path.exists():
        sys.exit(f"Config introuvable : {config_path} (copie config.example.toml)")
    try:
        cfg = tomllib.loads(config_path.read_text("utf-8"))
    except tomllib.TOMLDecodeError as e:
        sys.exit(
            f"Erreur de syntaxe dans {config_path} : {e}\n"
            "Rappel TOML : pas de \\ d'échappement dans les chemins entre "
            "guillemets — écrire \"/Users/example/Mobile Documents/Vault\" "
            "(espaces permis), pas \"Mobile\\ Documents\".")

    # Local mode without Telegram.
    if _needs_gui(cfg):
        try:
            import tkinter as _tk  # noqa: F401 - availability check
        except ImportError:
            sys.exit(
                "tkinter indisponible sur cette installation Python.\n"
                "Sur Debian/Ubuntu : sudo apt install python3-tk\n"
                "Sur macOS : python.org officiel inclut tkinter.")
        from ..gui.main import run_gui
        print("PRIORIS démarré — mode local (interface graphique).")
        run_gui(cfg)
        return

    conn = db.connect(cfg["database"]["path"])

    # Optional LLM layer: buttons still work without it.
    llm_cfg = LLMConfig.from_dict(cfg.get("llm", {}))
    mode = "boutons seuls"
    if llm_cfg.enabled:
        try:
            base_url, _ = resolve(llm_cfg)
            client = ChatClient(llm_cfg)
            mode = f"LLM {llm_cfg.provider} ({llm_cfg.model}) via {base_url}"
        except ValueError as e:
            client, mode = None, f"boutons seuls — config LLM invalide : {e}"
    else:
        client = None
    facade = LLMFacade(
        client, log_fn=lambda t, m, ms, ok: db.log_llm_call(conn, t, m, ms, ok))

    # Warm-up loads the model at startup, before interviews, then keeps it warm.
    keep_warm = bool(cfg.get("llm", {}).get("keep_warm", True))
    interval_min = float(cfg.get("llm", {}).get("keep_warm_interval_min", 4))

    async def _post_init(application) -> None:
        if not facade.available:
            return
        ok, msg, log_path = await asyncio.to_thread(
            llm_health.warm_up_with_retries, facade, 3)
        application.bot_data["llm_ready"] = ok
        application.bot_data["llm_log_path"] = str(log_path)
        if ok:
            print(f"{msg}.")
        else:
            print(f"{msg}. Voir {log_path}. Replis boutons actifs.")
        if not ok or not keep_warm:
            return

        async def warm_loop() -> None:
            while True:
                await asyncio.sleep(interval_min * 60)
                ok = await asyncio.to_thread(facade.warm_up)
                application.bot_data["llm_ready"] = ok
                if not ok:
                    err = getattr(facade, "last_error", "") or "échec sans détail"
                    path = llm_health.append_log(f"keep-warm KO : {err}")
                    application.bot_data["llm_log_path"] = str(path)

        # Plain asyncio task: Application.create_task is not available while the
        # app is not yet running in post_init. Keep a reference to avoid GC.
        application.bot_data["_warm_task"] = asyncio.get_running_loop() \
            .create_task(warm_loop())

    app = (ApplicationBuilder().token(cfg["telegram"]["token"])
           .post_init(_post_init).build())
    app.bot_data["conn"] = conn
    app.bot_data["vault_path"] = cfg.get("obsidian", {}).get("vault_path")
    app.bot_data["prioris_dir"] = cfg.get("obsidian", {}).get("prioris_dir", "PRIORIS")
    app.bot_data["language"] = normalize_language(cfg.get("ui", {}).get("language"))
    app.bot_data["llm"] = facade
    app.bot_data["llm_ready"] = False
    app.bot_data["llm_log_path"] = str(llm_health.DEFAULT_LOG_PATH)

    app.add_handler(CommandHandler("add", handlers.cmd_add))
    app.add_handler(CommandHandler("scan", handlers.cmd_scan))
    app.add_handler(CommandHandler("goals", handlers.cmd_goals))
    app.add_handler(CommandHandler("today", handlers.cmd_today))
    app.add_handler(CommandHandler("list", handlers.cmd_list))
    app.add_handler(CommandHandler("why", handlers.cmd_why))
    app.add_handler(CommandHandler("done", handlers.cmd_done))
    app.add_handler(CommandHandler("llm", handlers.cmd_llm))
    app.add_handler(CommandHandler("info", handlers.cmd_info))
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                   handlers.on_text))

    print(f"PRIORIS démarré — {mode}.")
    app.run_polling()


if __name__ == "__main__":
    main()
