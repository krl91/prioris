"""Telegram adapter (python-telegram-bot >= 21) over core/.

No decision logic lives here: this module translates questions to buttons and
persists through store/. Always one question per message.
"""
from __future__ import annotations

import datetime as dt
import json

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import asyncio
from importlib import resources

from ..core import interview as itv
from ..core import biases, planner, scoring
from ..core.axes import (AXIS_MEDIAN, ESTIMATION_MIN, Effort, Estimation, Incertitude,
                         Metadata, Priorite)
from ..core.interview import Q
from ..i18n import options as i18n_options, question_text, t
from ..store import db
from .. import task_impact
from .. import task_revision
from ..llm import health as llm_health
from ..vault import export, info_sync, scan

# In-memory interview sessions: chat_id -> state.
SESSIONS: dict[int, dict] = {}

CATEGORIES = ["travail", "carriere", "sante", "finances", "ia",
              "formation", "famille", "loisirs", "perso"]


def _category_label(cat: str) -> str:
    return "IA" if cat == "ia" else cat.capitalize()


def _deadline_days(deadline: str | None) -> int | None:
    if not deadline:
        return None
    try:
        return (dt.date.fromisoformat(deadline) - dt.date.today()).days
    except ValueError:
        return None


async def _start_new_task_interview(message, chat_id: int, context,
                                    titre: str, cat: str,
                                    deadline: str | None = None) -> None:
    conn = context.bot_data["conn"]
    task_id = db.create_task(conn, titre, cat, deadline=deadline)
    session = itv.Session(seed=task_id, deadline_days=_deadline_days(deadline))
    interview_id = db.create_interview(conn, task_id, session.mode)
    SESSIONS[chat_id] = {"conn": conn, "task_id": task_id,
                         "interview_id": interview_id, "session": session}
    await _ask_next(message, chat_id, context)


QUESTION_TEXT = {q: question_text(q, "fr") for q in Q if q not in (Q.CLARIFICATION, Q.MIROIR)}


def _language(context) -> str:
    return context.bot_data.get("language", "fr")


async def _ensure_llm_ready(message, context) -> bool:
    llm = context.bot_data.get("llm")
    if not llm or not llm.available:
        await message.reply_text(
            "LLM indisponible : non configuré ou disabled. "
            "Utilise le mode manuel si disponible.")
        return False
    if context.bot_data.get("llm_ready"):
        return True
    await message.reply_text("LLM configuré mais pas prêt — tentative de démarrage (3 essais)…")
    ok, msg, path = await asyncio.to_thread(
        llm_health.warm_up_with_retries, llm, 3)
    context.bot_data["llm_ready"] = ok
    context.bot_data["llm_log_path"] = str(path)
    if not ok:
        await message.reply_text(
            f"{msg}\nLog LLM : {path}\n"
            "Je continue en mode boutons/manuel quand c'est possible.")
        return False
    await message.reply_text(f"{msg}.")
    return True


def _options(q: Q, language: str = "fr") -> list[tuple[str, str]]:
    """Return encoded (label, value) options for a question."""
    return i18n_options(q, language)


def _keyboard(q: Q, language: str = "fr") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(lbl, callback_data=f"ans|{q.value}|{val}")]
            for lbl, val in _options(q, language)]
    return InlineKeyboardMarkup(rows)


async def _send_quadrant_helpers(message, context, state: dict) -> None:
    """Show LLM-generated quadrant helper questions once per interview."""
    if state.get("quadrant_helpers_shown"):
        return
    llm = context.bot_data.get("llm")
    if not llm or not llm.available:
        return
    if not await _ensure_llm_ready(message, context):
        return
    task = state["conn"].execute(
        "SELECT titre FROM tasks WHERE id=?", (state["task_id"],)).fetchone()
    questions = await asyncio.to_thread(
        llm.quadrant_questions,
        task["titre"] if task else "",
        _language(context),
    )
    state["quadrant_helpers_shown"] = True
    if not questions:
        return
    lines = [t("quadrant_helper_title", _language(context))]
    lines += [f"{i}. {question}" for i, question in enumerate(questions, start=1)]
    await message.reply_text("\n".join(lines))


async def _send_subjective_challenge(message, context, state: dict,
                                     subjective: str) -> None:
    """Ask LLM challenge questions after the instinctive classification."""
    if state.get("subjective_challenge_shown"):
        return
    llm = context.bot_data.get("llm")
    if not llm or not llm.available:
        return
    if not await _ensure_llm_ready(message, context):
        return
    task = state["conn"].execute(
        "SELECT titre FROM tasks WHERE id=?", (state["task_id"],)).fetchone()
    questions = await asyncio.to_thread(
        llm.subjective_challenge_questions,
        task["titre"] if task else "",
        subjective,
        _language(context),
    )
    state["subjective_challenge_shown"] = True
    if not questions:
        return
    lines = ["Questions pour challenger ton instinct :"]
    lines += [f"{i}. {question}" for i, question in enumerate(questions, start=1)]
    await message.reply_text("\n".join(lines))


def _typed_answer_value(q: Q, raw: str):
    """Convert a button/free-text option value to the type expected by core."""
    if raw == "?":
        axis = itv.Q_TO_AXIS[q]
        return (AXIS_MEDIAN[axis], Incertitude.NE_SAIT_PAS)
    if q in (Q.SUBJECTIVE, Q.DEMANDEUR):
        return raw
    if q == Q.ESTIMATION:
        return Estimation[raw]
    return int(raw)


def _answer_axis_code(q: Q) -> str:
    return itv.Q_TO_AXIS[q].value if q in itv.Q_TO_AXIS else q.value


def _current_question_options(state: dict, q: Q, lang: str) -> list[tuple[str, str]]:
    if q == Q.CLARIFICATION:
        c = state["session"].pending
        return [(lbl, str(i)) for i, (lbl, _axe, _val) in enumerate(c.options)]
    if q == Q.MIROIR:
        mq = itv.mirror_for(state["session"])
        return [(opt.label, str(i)) for i, opt in enumerate(mq.options)]
    return i18n_options(q, lang)


def _current_question_text(state: dict, q: Q, lang: str) -> str:
    if q == Q.CLARIFICATION:
        c = state["session"].pending
        return c.question
    if q == Q.MIROIR:
        mq = itv.mirror_for(state["session"])
        return mq.question if mq else ""
    return question_text(q, lang)


async def _apply_dynamic_answer(message, context, state: dict, q: Q,
                                option_index: int) -> bool:
    if q == Q.CLARIFICATION:
        c = state["session"].pending
        label, axis_code, raw_value = c.options[option_index]
        if axis_code == "DATE":
            state["session"] = itv.promise_deadline(state["session"])
            state["awaiting_date"] = True
            await message.reply_text(
                "Quelle est la date butoir ? (format AAAA-MM-JJ, ex. 2026-07-20)")
            return True
        incertain = label.lower().startswith("je ne sais pas")
        db.record_answer(state["conn"], state["interview_id"],
                         axis_code, int(raw_value), label,
                         2 if incertain else 0)
        state["session"] = itv.clarify(
            state["session"], axis_code, int(raw_value), incertain)
        await message.reply_text("Noté, axe corrigé. Suite…")
        await _ask_next(message, message.chat_id, context)
        return True
    if q == Q.MIROIR:
        mq = itv.mirror_for(state["session"])
        opt = mq.options[option_index]
        db.record_answer(state["conn"], state["interview_id"],
                         f"MIROIR_{mq.code}",
                         opt.valeur if opt.axe else None, opt.label,
                         2 if opt.incertain else 0)
        state["session"] = itv.mirror_answer(state["session"], option_index)
        await _ask_next(message, message.chat_id, context)
        return True
    return False


async def _ask_next(message, chat_id: int, context) -> None:
    state = SESSIONS[chat_id]
    q, session = itv.next_question(state["session"])
    state["session"] = session
    state["current_q"] = q          # pour router les réponses libres (NLU)
    if q is None:
        await _finish_interview(message, chat_id, context)
        return
    if q == Q.CLARIFICATION:
        c = session.pending
        rows = [[InlineKeyboardButton(
            lbl, callback_data=f"clar|{axe}|{val}"
            f"|{1 if lbl.lower().startswith('je ne sais pas') else 0}")]
            for lbl, axe, val in c.options]
        await message.reply_text(f"⚠️ {c.message}\n\n{c.question}",
                                 reply_markup=InlineKeyboardMarkup(rows))
        return
    if q == Q.MIROIR:
        # Question miroir (§7.2) : sonde unique de fin d'entretien.
        mq = itv.mirror_for(session)
        rows = [[InlineKeyboardButton(o.label, callback_data=f"mir|{i}")]
                for i, o in enumerate(mq.options)]
        await message.reply_text(f"🪞 Dernière vérification : {mq.question}",
                                 reply_markup=InlineKeyboardMarkup(rows))
        return
    if q == Q.OBJECTIF:
        # Declared goals are offered as buttons; otherwise use the 0-3 scale.
        goals = db.active_goals(state["conn"])
        if goals:
            # LLM suggestion is only a star on a button, never auto-applied.
            sugg = None
            llm = context.bot_data.get("llm")
            if llm and llm.available:
                task = state["conn"].execute(
                    "SELECT titre FROM tasks WHERE id=?",
                    (state["task_id"],)).fetchone()
                sugg = await asyncio.to_thread(
                    llm.suggest_goal, task["titre"] if task else "",
                    [(g["id"], g["titre"]) for g in goals])
            ordered = sorted(goals[:8], key=lambda g: g["id"] != sugg)
            rows = [[InlineKeyboardButton(
                "Aucun objectif", callback_data=f"ans|{Q.OBJECTIF.value}|0")]]
            rows += [[InlineKeyboardButton(
                f"{'⭐ ' if g['id'] == sugg else ''}🎯 {g['titre'][:40]}",
                callback_data=f"obj|{g['id']}")] for g in ordered]
            texte = question_text(q, _language(context)) + \
                ("\n(⭐ = suggestion, à confirmer)" if sugg else "")
            await message.reply_text(texte,
                                     reply_markup=InlineKeyboardMarkup(rows))
            return
    if q == Q.SUBJECTIVE:
        # Visual reminder of quadrants when asking for instinctive priority.
        await _send_quadrant_helpers(message, context, state)
        lang = _language(context)
        try:
            png = resources.files("prioris.bot").joinpath(
                "assets/eisenhower.png").read_bytes()
            await message.reply_photo(png, caption=question_text(q, lang),
                                      reply_markup=_keyboard(q, lang))
            return
        except (FileNotFoundError, OSError):
            pass  # graceful degradation: text only
    lang = _language(context)
    await message.reply_text(question_text(q, lang), reply_markup=_keyboard(q, lang))


async def _finish_interview(message, chat_id: int, context) -> None:
    state = SESSIONS.pop(chat_id)
    conn, s = state["conn"], state["session"]
    axes, par_defaut = itv.final_axes(s)
    result = scoring.score(
        axes, estimation=s.estimation or Estimation.INCONNUE,
        deadline_days=s.deadline_days, incertitudes=s.incertitudes,
        mode=s.mode, axes_par_defaut=par_defaut, subjective=s.subjective)
    meta = Metadata(demandeur=s.demandeur, visibilite=s.visibilite,
                    pression=s.pression, subjective=s.subjective)
    flags = biases.detect(axes, result.importance, result.priorite, meta)

    db.finish_interview(conn, state["interview_id"], s.mode)
    est = s.estimation or Estimation.INCONNUE
    db.update_task_planning_attrs(conn, state["task_id"], est.value,
                                  ESTIMATION_MIN[est], s.effort.value)
    eval_id = db.save_evaluation(conn, state["task_id"], state["interview_id"],
                                 result, s.subjective.value if s.subjective else None)
    db.save_bias_flags(conn, eval_id, flags)

    text = scoring.explain(result)
    if flags:
        text += "\n\nBiais détectés :\n" + "\n".join(
            f"• {f.type_biais} ({f.gravite}) : {f.message}" for f in flags)
    text += f"\n\nDétail : /why {state['task_id']}"

    # Write back to Obsidian for tasks imported through /scan.
    vt = state.get("obsidian")
    vault = context.bot_data.get("vault_path")
    if vt is not None and vault:
        prioris_dir = context.bot_data.get("prioris_dir", "PRIORIS")
        annotated, detail_rel = await asyncio.to_thread(
            scan.apply_result, vault, prioris_dir, vt, state["task_id"],
            result.justification, flags, dt.date.today().isoformat())
        if annotated:
            text += f"\n📝 Note annotée ({vt.rel_path}) + détail : {detail_rel}"
        else:
            text += (f"\n⚠️ Ligne introuvable dans {vt.rel_path} (note modifiée "
                     f"entre-temps ?) — détail créé : {detail_rel}")

    # Continue scan flow by offering the next queued task.
    queue = context.chat_data.get("scan_queue") or []
    markup = None
    if queue:
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"▶️ Tâche suivante ({len(queue)} restantes)",
                                 callback_data="scannext"),
            InlineKeyboardButton("⏹ Stop", callback_data="scanstop")]])
    await message.reply_text(text, reply_markup=markup)


# ---------------------------------------------------------------- commandes
async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    titre = " ".join(context.args) if context.args else None
    if not titre:
        await update.message.reply_text("Usage : /add <titre de la tâche>")
        return
    context.chat_data["pending_title"] = titre
    rows = [[InlineKeyboardButton(_category_label(c), callback_data=f"cat|{c}")]
            for c in CATEGORIES]
    await update.message.reply_text(f"Nouvelle tâche : « {titre} ». Catégorie ?",
                                    reply_markup=InlineKeyboardMarkup(rows))


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = [[InlineKeyboardButton(lbl, callback_data=f"nrg|{n}")]
            for n, lbl in enumerate(
                ["Très faible", "Faible", "Normale", "Bonne", "Excellente"], 1)]
    await update.message.reply_text("Ton énergie aujourd'hui ?",
                                    reply_markup=InlineKeyboardMarkup(rows))


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = context.bot_data["conn"]
    rows = db.current_tasks(conn)
    if not rows:
        await update.message.reply_text("Aucune tâche évaluée. /add pour commencer.")
        return
    lines = [f"#{r['id']} {r['priorite']} ({r['score_global']:.0f}) "
             f"{'💎 ' if r['pepite'] else ''}{r['titre']}" for r in rows]
    await update.message.reply_text("\n".join(lines))


def _why_text(conn, task_id: int) -> str:
    row = db.last_evaluation(conn, task_id)
    if not row:
        return "Pas d'évaluation pour cette tâche."
    task = conn.execute("SELECT titre FROM tasks WHERE id=?", (task_id,)).fetchone()
    j = json.loads(row["justification_json"])
    axes_txt = "\n".join(
        f"  {a}: {d['valeur']}" + (" (défaut)" if d["defaut"] else "")
        for a, d in j["axes"].items())
    return (f"📋 #{task_id} {task['titre'] if task else ''}\n"
            f"{j['priorite']} — {j['quadrant']} — G={j['calculs']['G']['total']}\n"
            f"U={j['calculs']['U']['total']} · I={j['calculs']['I']['total']}\n"
            f"Axes :\n{axes_txt}\n"
            f"Ajustements : {[a['regle'] for a in j['ajustements']] or 'aucun'}\n"
            f"Mode : {j['mode']} · algo v{j['version_algo']}")


async def _pick_task(update, conn, action: str, prompt: str,
                     statuts=("evaluee", "planifiee")) -> None:
    """Liste les tâches en boutons « #id titre » → callback `<action>|<id>`."""
    marks = ",".join("?" * len(statuts))
    rows = conn.execute(
        f"SELECT * FROM v_task_current WHERE statut IN ({marks}) "
        "ORDER BY priorite, score_global DESC LIMIT 25", statuts).fetchall()
    if not rows:
        await update.message.reply_text("Aucune tâche évaluée. /add pour commencer.")
        return
    buttons = [[InlineKeyboardButton(
        f"#{r['id']} {r['priorite']} · {r['titre'][:40]}",
        callback_data=f"{action}|{r['id']}")] for r in rows]
    await update.message.reply_text(prompt, reply_markup=InlineKeyboardMarkup(buttons))


async def cmd_why(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = context.bot_data["conn"]
    if context.args:
        await update.message.reply_text(_why_text(conn, int(context.args[0])))
    else:
        await _pick_task(update, conn, "why", "Justification de quelle tâche ?")


def _task_card(conn, task_id: int) -> str | None:
    """Short task card for confirmations, to avoid wrong-id mistakes."""
    row = conn.execute(
        "SELECT t.id, t.titre, t.statut, t.obsidian_path, c.label AS categorie,"
        " (SELECT priorite FROM evaluations WHERE task_id = t.id"
        "  ORDER BY created_at DESC, id DESC LIMIT 1) AS priorite"
        " FROM tasks t LEFT JOIN categories c ON c.id = t.category_id"
        " WHERE t.id = ?", (task_id,)).fetchone()
    if not row:
        return None
    lignes = [f"#{row['id']} « {row['titre']} »",
              f"{row['priorite'] or 'non évaluée'} · {row['categorie'] or '?'}"
              f" · statut : {row['statut']}"]
    if row["obsidian_path"]:
        lignes.append(f"📄 {row['obsidian_path']}")
    return "\n".join(lignes)


async def _confirm(message, conn, task_id: int, action_label: str,
                   confirm_cb: str) -> None:
    """Require confirmation before every task-mutating action."""
    card = _task_card(conn, task_id)
    if card is None:
        await message.reply_text(f"Tâche #{task_id} introuvable.")
        return
    rows = [[InlineKeyboardButton(f"✅ Oui, {action_label}",
                                  callback_data=f"{confirm_cb}|{task_id}"),
             InlineKeyboardButton("❌ Annuler", callback_data="cancel")]]
    await message.reply_text(f"{action_label.capitalize()} cette tâche ?\n\n{card}",
                             reply_markup=InlineKeyboardMarkup(rows))


def _mark_done(conn, task_id: int, vault: str | None = None,
               prioris_dir: str = "PRIORIS") -> str:
    db.set_task_status(conn, task_id, "faite")
    row = conn.execute("SELECT titre, estimation_min, source FROM tasks WHERE id=?",
                       (task_id,)).fetchone()
    db.log_time(conn, task_id, (row["estimation_min"] if row else None) or 30,
                dt.date.today().isoformat())
    msg = (f"✅ Fait : {row['titre'] if row else f'#{task_id}'}\n"
           "(Temps loggé sur l'estimation.)")
    # PRIORIS-to-vault symmetry: check the box in the source note.
    if row and row["source"] == "obsidian" and vault:
        ok, rel = scan.check_task_line(vault, task_id, prioris_dir)
        msg += (f"\n☑️ Case cochée dans Obsidian ({rel})" if ok else
                "\n⚠️ Ligne 🎯 introuvable dans le vault — case non cochée")
    return msg


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = context.bot_data["conn"]
    if context.args:
        await _confirm(update.message, conn, int(context.args[0]),
                       "marquer comme faite", "cdone")
    else:
        await _pick_task(update, conn, "done", "Quelle tâche est faite ?")


async def cmd_goals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Declare and track life goals."""
    conn = context.bot_data["conn"]
    if context.args:
        context.chat_data["pending_goal"] = " ".join(context.args)
        rows = [[InlineKeyboardButton(_category_label(c), callback_data=f"gcat|{c}")]
                for c in CATEGORIES]
        await update.message.reply_text(
            f"Nouvel objectif : « {context.chat_data['pending_goal']} ». Catégorie ?",
            reply_markup=InlineKeyboardMarkup(rows))
        return
    goals = db.active_goals(conn)
    if not goals:
        await update.message.reply_text(
            "Aucun objectif déclaré.\nDéclare-les avec /goals <titre>, "
            "ex. :\n/goals Développer une activité drone\n"
            "/goals Améliorer ma condition physique\n"
            "Ils seront proposés à chaque entretien (question objectifs) "
            "et protégés par le scoring (plancher §6.2).")
        return
    rows = [[InlineKeyboardButton(
        f"🎯 {g['titre'][:35]} · {g['nb_faites']}/{g['nb_taches']} tâches",
        callback_data=f"goal|{g['id']}")] for g in goals]
    await update.message.reply_text(
        f"{len(goals)} objectif(s) actif(s) — touche pour gérer, "
        "/goals <titre> pour ajouter :",
        reply_markup=InlineKeyboardMarkup(rows))


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Find unprioritized vault tasks and offer to evaluate them one by one."""
    vault = context.bot_data.get("vault_path")
    if not vault:
        await update.message.reply_text(
            "Aucun vault configuré ([obsidian] vault_path dans config.toml).")
        return
    conn = context.bot_data["conn"]
    prioris_dir = context.bot_data.get("prioris_dir", "PRIORIS")
    await update.message.reply_text("🔍 Scan du vault en cours…")
    try:
        found = await asyncio.to_thread(scan.find_unprioritized, vault, prioris_dir)
        marked = await asyncio.to_thread(scan.find_marked, vault, prioris_dir)
    except OSError as e:
        await update.message.reply_text(f"Vault inaccessible : {e}")
        return

    # Vault-to-SQLite sync: pick up manual vault changes.
    sync = db.sync_from_vault_marks(conn, marked, dt.date.today().isoformat())
    if sync["done"] or sync["missing"]:
        lines = ["🔄 Synchronisation Obsidian → PRIORIS :"]
        lines += [f"✅ #{i} « {t[:50]} » cochée dans le vault → faite"
                  for i, t in sync["done"]]
        lines += [f"❓ #{i} « {t[:50]} » introuvable dans le vault "
                  f"(ligne supprimée ?) — statut conservé, /done ou ignore"
                  for i, t in sync["missing"]]
        await update.message.reply_text("\n".join(lines))
    fresh = [t for t in found
             if not db.obsidian_task_known(conn, t.rel_path, t.titre)]
    deja = len(found) - len(fresh)
    if not fresh:
        await update.message.reply_text(
            f"Aucune nouvelle tâche à prioriser ({deja} déjà connues, "
            f"les lignes marquées 🎯 sont ignorées).")
        return
    context.chat_data["scan_queue"] = fresh
    apercu = "\n".join(f"• {t.titre[:60]}  ({t.rel_path})" for t in fresh[:8])
    if len(fresh) > 8:
        apercu += f"\n… et {len(fresh) - 8} autres"
    await update.message.reply_text(
        f"📥 {len(fresh)} tâche(s) non priorisée(s) trouvée(s)"
        + (f" ({deja} déjà connues ignorées)" if deja else "") + " :\n"
        + apercu,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("▶️ Prioriser une par une", callback_data="scannext"),
            InlineKeyboardButton("Annuler", callback_data="scanstop")]]))


async def _scan_next(message, context) -> None:
    """Present the next queued task: category, then interview."""
    queue = context.chat_data.get("scan_queue") or []
    if not queue:
        await message.reply_text("File vide — scan terminé ✅")
        return
    vt = queue.pop(0)
    context.chat_data["scan_queue"] = queue
    context.chat_data["scan_current"] = vt
    rows = [[InlineKeyboardButton(_category_label(c), callback_data=f"scat|{c}")]
            for c in CATEGORIES]
    extra = f"\n📅 échéance : {vt.due}" if vt.due else ""
    await message.reply_text(
        f"📄 « {vt.titre} »\nNote : {vt.rel_path}{extra}\n"
        f"(reste {len(queue)} après celle-ci)\n\nCatégorie ?",
        reply_markup=InlineKeyboardMarkup(rows))


async def cmd_llm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Diagnostic de la couche LLM : test aller-retour + statistiques."""
    llm = context.bot_data.get("llm")
    conn = context.bot_data["conn"]
    if llm and llm.available:
        await update.message.reply_text(
            "Démarrage/test du LLM en cours… (3 essais, jusqu'à 2 min par essai)")
        ready, ready_msg, log_path = await asyncio.to_thread(
            llm_health.warm_up_with_retries, llm, 3)
        context.bot_data["llm_ready"] = ready
        context.bot_data["llm_log_path"] = str(log_path)
        ok, message = (await asyncio.to_thread(llm.self_test)) if ready \
            else (False, f"{ready_msg} · log : {log_path}")
    else:
        ok, message = False, "façade absente ou LLM désactivé"
    lines = [("✅ " if ok else "❌ ") + message]
    stats = conn.execute(
        "SELECT type, COUNT(*) n, SUM(valide) ok, CAST(AVG(latence_ms) AS INT) avg_ms "
        "FROM llm_calls GROUP BY type ORDER BY MAX(created_at) DESC").fetchall()
    if stats:
        lines.append("Historique LLM :")
        for row in stats:
            lines.append(f"- {row['type']} : {row['ok'] or 0}/{row['n']} réussis · "
                         f"{row['avg_ms'] or 0} ms moyen")
    last_fail = conn.execute(
        "SELECT type, modele, latence_ms, created_at FROM llm_calls "
        "WHERE valide=0 ORDER BY created_at DESC, id DESC LIMIT 1").fetchone()
    if last_fail:
        lines.append(
            f"Dernier échec journalisé : {last_fail['type']} · "
            f"{last_fail['modele']} · {last_fail['latence_ms']} ms · "
            f"{last_fail['created_at']}")
    lines.append("Rappel : en cas de panne LLM, tout fonctionne en boutons.")
    await update.message.reply_text("\n".join(lines))


async def cmd_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add information or a question to a task, then confirm the revision."""
    if not context.args:
        await update.message.reply_text(
            "Usage :\n"
            "/info <information ou contrainte>\n"
            "/info <id> <information ou contrainte>\n"
            "Exemple : /info Le client est bloqué depuis ce matin")
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        await _info_global(update, context, " ".join(context.args).strip())
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Ajoute l'information après l'id.\n"
            "Exemple : /info 12 Le client est bloqué depuis ce matin")
        return
    note = " ".join(context.args[1:]).strip()
    llm = context.bot_data.get("llm")
    if not llm or not llm.available:
        manual = _parse_manual_revision(note)
        if manual is None:
            await update.message.reply_text(
                "LLM indisponible : utilise le mode manuel.\n"
                "Format : /info <id> <AXE>=<valeur> <raison>\n"
                "Exemple : /info 12 BLK=4 Le client est maintenant bloqué\n"
                "Axes : BLK CDR HOR IMP INA IRR ALN")
            return
        axis_code, value = manual
        await _manual_info_for_task(update, context, task_id, note, axis_code, value)
        return
    await _info_for_task(update, context, task_id, note)


def _parse_manual_revision(text: str) -> tuple[str, int] | None:
    for part in text.split():
        if "=" not in part:
            continue
        axis, raw = part.split("=", 1)
        axis = axis.strip().upper()
        if axis not in {"BLK", "CDR", "HOR", "IMP", "INA", "IRR", "ALN"}:
            continue
        try:
            return axis, int(raw)
        except ValueError:
            return None
    return None


async def _manual_info_for_task(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                task_id: int, note: str,
                                axis_code: str, value: int) -> None:
    try:
        proposal = task_revision.make_manual_proposal(
            context.bot_data["conn"], task_id, note, axis_code, value)
    except ValueError as e:
        await update.message.reply_text(str(e))
        return
    if proposal is None:
        await update.message.reply_text(
            f"Analyse impossible pour #{task_id} "
            "(tâche introuvable/non évaluée).")
        return
    text = task_revision.render_proposal(proposal)
    if not proposal.has_changes:
        await update.message.reply_text(text)
        return
    context.chat_data[f"revision:{task_id}"] = proposal
    rows = [[InlineKeyboardButton("✅ Appliquer", callback_data=f"revapply|{task_id}"),
             InlineKeyboardButton("Annuler", callback_data="cancel")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))


async def _info_global(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       note: str) -> None:
    llm = context.bot_data.get("llm")
    if not await _ensure_llm_ready(update.message, context):
        return
    wait_msg = await update.message.reply_text("⏳ Je cherche les tâches impactées…")
    proposal = await asyncio.to_thread(
        task_impact.make_proposal, context.bot_data["conn"], note, llm)
    try:
        await wait_msg.delete()
    except Exception:
        pass
    if proposal is None:
        await update.message.reply_text(
            f"Analyse impossible ({getattr(llm, 'last_error', '')} — /llm).")
        return
    await _send_impact_proposal(update.message, context, proposal)


async def _send_impact_proposal(message, context, proposal) -> None:
    text = task_impact.render_proposal(proposal)
    context.chat_data["impact_note"] = proposal.note
    context.chat_data["impact_new_task_title"] = proposal.new_task_title
    context.chat_data["impact_deadline_suggestion"] = proposal.suggested_deadline
    if proposal.has_impacted:
        rows = [[InlineKeyboardButton(f"Analyser #{item.id}",
                                      callback_data=f"impactrev|{item.id}")]
                for item in proposal.impacted]
        rows.append([InlineKeyboardButton("Créer une nouvelle tâche",
                                          callback_data="impactnew")])
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))
    else:
        context.chat_data["pending_title"] = proposal.new_task_title
        context.chat_data["pending_deadline_suggestion"] = proposal.suggested_deadline
        rows = [[InlineKeyboardButton("➕ Créer cette tâche", callback_data="newtask"),
                 InlineKeyboardButton("Ignorer", callback_data="ignore")]]
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))


async def _info_for_task(update: Update, context: ContextTypes.DEFAULT_TYPE,
                         task_id: int, note: str) -> None:
    llm = context.bot_data.get("llm")
    if not await _ensure_llm_ready(update.message, context):
        return
    wait_msg = await update.message.reply_text("⏳ J'analyse cette information…")
    proposal = await asyncio.to_thread(
        task_revision.make_proposal, context.bot_data["conn"], task_id, note, llm)
    try:
        await wait_msg.delete()
    except Exception:
        pass
    if proposal is None:
        await update.message.reply_text(
            f"Tâche #{task_id} introuvable ou pas encore évaluée.")
        return
    text = task_revision.render_proposal(proposal)
    if not proposal.has_changes:
        await update.message.reply_text(text)
        impact = await asyncio.to_thread(
            task_impact.make_proposal, context.bot_data["conn"], note, llm)
        if impact is not None and not any(i.id == task_id for i in impact.impacted):
            await update.message.reply_text(
                "Cette information ne modifie pas la tâche ciblée. "
                "Je regarde si elle doit créer ou impacter autre chose.")
            await _send_impact_proposal(update.message, context, impact)
        return
    context.chat_data[f"revision:{task_id}"] = proposal
    rows = [[InlineKeyboardButton("✅ Appliquer", callback_data=f"revapply|{task_id}"),
             InlineKeyboardButton("Annuler", callback_data="cancel")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))


async def _offer_obsidian_info_sync(message, context,
                                    task_id: int) -> None:
    vault = context.bot_data.get("vault_path")
    if not vault:
        return
    proposal = await asyncio.to_thread(
        info_sync.build_sync_proposal,
        context.bot_data["conn"], vault,
        context.bot_data.get("prioris_dir", "PRIORIS"),
        task_id,
    )
    if proposal is None:
        return
    context.chat_data[f"obsidian_sync:{task_id}"] = proposal
    rows = [[InlineKeyboardButton("✅ Appliquer au vault",
                                  callback_data=f"obsyncapply|{task_id}"),
             InlineKeyboardButton("Refuser",
                                  callback_data=f"obsyncskip|{task_id}")]]
    await message.reply_text(
        info_sync.render_sync_preview(proposal),
        reply_markup=InlineKeyboardMarkup(rows),
    )


# ---------------------------------------------------------- free-text answers
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free text.

    During interviews: local/LLM NLU then button confirmation. Outside
    interviews: propose creating a task.
    """
    chat_id = update.message.chat_id
    text = update.message.text.strip()

    state = SESSIONS.get(chat_id)
    pending_deadline = context.chat_data.get("pending_newtask_deadline")
    if pending_deadline:
        if text.lower() in ("aucune", "aucun", "non"):
            deadline = None
        else:
            try:
                due = dt.date.fromisoformat(text)
            except ValueError:
                await update.message.reply_text(
                    "Format invalide — envoie une date AAAA-MM-JJ "
                    "(ex. 2026-07-20), ou « aucune ».")
                return
            deadline = due.isoformat()
        context.chat_data.pop("pending_newtask_deadline", None)
        await _start_new_task_interview(
            update.message, chat_id, context,
            pending_deadline["titre"], pending_deadline["cat"], deadline)
        return

    if state is not None and state.get("awaiting_date"):
        # C5: receive the promised hard-deadline date.
        try:
            due = dt.date.fromisoformat(text)
        except ValueError:
            await update.message.reply_text(
                "Format invalide — AAAA-MM-JJ (ex. 2026-07-20), "
                "ou envoie « aucune » s'il n'y a pas de date."
                if text.lower() not in ("aucune", "aucun", "non") else
                "Compris, pas de vraie date.")
            if text.lower() in ("aucune", "aucun", "non"):
                state.pop("awaiting_date", None)
                await _ask_next(update.message, chat_id, context)
            return
        state.pop("awaiting_date", None)
        days = (due - dt.date.today()).days
        state["session"] = itv.set_deadline(state["session"], days)
        conn = context.bot_data["conn"]
        conn.execute("UPDATE tasks SET deadline_reelle=?, "
                     "updated_at=datetime('now') WHERE id=?",
                     (due.isoformat(), state["task_id"]))
        conn.commit()
        await update.message.reply_text(
            f"📅 Deadline notée : {due.isoformat()} (J{days:+d}). Suite…")
        await _ask_next(update.message, chat_id, context)
        return

    if state is not None:
        q = state.get("current_q")
        if q is None:
            await update.message.reply_text(
                "Réponds avec les boutons de la question ci-dessus 🙏")
            return
        llm = context.bot_data.get("llm")
        parsed = None
        options = _current_question_options(state, q, _language(context))
        if llm and llm.available and await _ensure_llm_ready(update.message, context):
            # Immediate feedback: interpretation can be slow on a cold model.
            wait_msg = await update.message.reply_text("⏳ J'interprète ta réponse…")
            await update.message.chat.send_action("typing")
            # asyncio.to_thread keeps HTTP calls from freezing the bot.
            parsed = await asyncio.to_thread(
                llm.interpret_question_answer,
                _current_question_text(state, q, _language(context)),
                options,
                text,
                _language(context),
            )
            try:
                await wait_msg.delete()
            except Exception:
                pass
        if parsed is None:
            raison = getattr(llm, "last_error", None) if llm else "LLM absent"
            await update.message.reply_text(
                "Je n'ai pas pu interpréter — mode boutons :"
                + (f"\n(détail : {raison} — /llm pour diagnostiquer)" if raison else ""),
                reply_markup=None if q in (Q.CLARIFICATION, Q.MIROIR)
                else _keyboard(q, _language(context)))
            return
        state["question_nlu"] = {"q": q, "texte": text, "parsed": parsed}
        doute = {0: "", 1: " (avec une part d'hésitation)",
                 2: " (grande incertitude)"}[parsed.incertitude]
        label = next(
            label for label, value in options
            if value == parsed.value
        )
        rows = [[InlineKeyboardButton("✅ Oui", callback_data="cfm"),
                 InlineKeyboardButton("✏️ Corriger", callback_data="edit")]]
        await update.message.reply_text(
            f"{parsed.reformulation}\n→ « {label} »{doute}. "
            "C'est bien ça ?", reply_markup=InlineKeyboardMarkup(rows))
        return

    # Outside interviews, a free-text message is a potential task.
    context.chat_data["pending_title"] = text
    rows = [[InlineKeyboardButton("➕ Créer la tâche", callback_data="newtask"),
             InlineKeyboardButton("Ignorer", callback_data="ignore")]]
    await update.message.reply_text(
        f"On en fait une tâche ? « {text} »", reply_markup=InlineKeyboardMarkup(rows))


# ---------------------------------------------------------------- callbacks
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    kind, *rest = query.data.split("|")
    chat_id = query.message.chat_id
    conn = context.bot_data["conn"]

    if kind == "why":
        await query.message.reply_text(_why_text(conn, int(rest[0])))

    elif kind == "done":
        # Even from button lists, confirm with the task card.
        await _confirm(query.message, conn, int(rest[0]),
                       "marquer comme faite", "cdone")

    elif kind == "cdone":
        msg = await asyncio.to_thread(
            _mark_done, conn, int(rest[0]),
            context.bot_data.get("vault_path"),
            context.bot_data.get("prioris_dir", "PRIORIS"))
        await query.message.reply_text(msg)

    elif kind == "cancel":
        await query.message.reply_text("Annulé — rien n'a été modifié.")

    elif kind == "revapply":
        key = f"revision:{int(rest[0])}"
        proposal = context.chat_data.pop(key, None)
        if proposal is None:
            await query.message.reply_text(
                "Proposition expirée ou introuvable — relance /info.")
            return
        await asyncio.to_thread(task_revision.apply_proposal, conn, proposal)
        await query.message.reply_text(
            "✅ Révision appliquée. La priorité a été recalculée.\n\n"
            + _why_text(conn, proposal.task_id))
        await _offer_obsidian_info_sync(query.message, context, proposal.task_id)

    elif kind == "obsyncapply":
        task_id = int(rest[0])
        key = f"obsidian_sync:{task_id}"
        proposal = context.chat_data.pop(key, None)
        vault = context.bot_data.get("vault_path")
        if proposal is None or not vault:
            await query.message.reply_text(
                "Proposition de synchro expirée — relance /info.")
            return
        await asyncio.to_thread(info_sync.apply_sync_proposal, vault, proposal)
        await query.message.reply_text("✅ Synchronisation Obsidian appliquée.")

    elif kind == "obsyncskip":
        task_id = int(rest[0])
        context.chat_data.pop(f"obsidian_sync:{task_id}", None)
        await query.message.reply_text("Synchronisation Obsidian refusée.")

    elif kind == "impactrev":
        note = context.chat_data.get("impact_note")
        if not note:
            await query.message.reply_text("Analyse expirée — relance /info.")
            return
        llm = context.bot_data.get("llm")
        task_id = int(rest[0])
        wait_msg = await query.message.reply_text("⏳ J'analyse cette tâche…")
        proposal = await asyncio.to_thread(
            task_revision.make_proposal, conn, task_id, note, llm)
        try:
            await wait_msg.delete()
        except Exception:
            pass
        if proposal is None:
            await query.message.reply_text(
                f"Analyse impossible pour #{task_id} "
                f"({getattr(llm, 'last_error', '') or 'tâche introuvable/non évaluée'} — /llm).")
            return
        text = task_revision.render_proposal(proposal)
        if not proposal.has_changes:
            await query.message.reply_text(text)
            return
        context.chat_data[f"revision:{task_id}"] = proposal
        rows = [[InlineKeyboardButton("✅ Appliquer", callback_data=f"revapply|{task_id}"),
                 InlineKeyboardButton("Annuler", callback_data="cancel")]]
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))

    elif kind == "impactnew":
        note = context.chat_data.get("impact_note", "Nouvelle tâche")
        title = context.chat_data.get("impact_new_task_title") or note[:90]
        context.chat_data["pending_title"] = title
        context.chat_data["pending_deadline_suggestion"] = (
            context.chat_data.get("impact_deadline_suggestion", "")
        )
        rows = [[InlineKeyboardButton(_category_label(c), callback_data=f"cat|{c}")]
                for c in CATEGORIES]
        await query.message.reply_text(
            f"Nouvelle tâche : « {context.chat_data['pending_title']} ». Catégorie ?",
            reply_markup=InlineKeyboardMarkup(rows))

    elif kind == "cfm" and chat_id in SESSIONS:
        state = SESSIONS[chat_id]
        nlu = state.pop("question_nlu", None) or state.pop("nlu", None)
        if not nlu:
            return
        q, parsed = nlu["q"], nlu["parsed"]
        if hasattr(parsed, "axis"):
            inc = Incertitude(parsed.incertitude)
            db.record_answer(state["conn"], state["interview_id"],
                             parsed.axis.value, parsed.valeur, nlu["texte"],
                             parsed.incertitude)
            state["session"] = itv.answer(state["session"], q,
                                          (parsed.valeur, inc))
        else:
            if q in (Q.CLARIFICATION, Q.MIROIR):
                if await _apply_dynamic_answer(
                        query.message, context, state, q, int(parsed.value)):
                    return
            value = _typed_answer_value(q, parsed.value)
            db.record_answer(
                state["conn"], state["interview_id"], _answer_axis_code(q),
                None if parsed.value == "?" else (
                    value if isinstance(value, int) else None),
                nlu["texte"], parsed.incertitude,
            )
            state["session"] = itv.answer(state["session"], q, value)
            if q == Q.SUBJECTIVE:
                await _send_subjective_challenge(
                    query.message, context, state, parsed.value)
        await _ask_next(query.message, chat_id, context)

    elif kind == "edit" and chat_id in SESSIONS:
        state = SESSIONS[chat_id]
        state.pop("question_nlu", None)
        state.pop("nlu", None)
        q = state.get("current_q")
        if q and q not in (Q.CLARIFICATION, Q.MIROIR):
            await query.message.reply_text(
                question_text(q, _language(context)),
                reply_markup=_keyboard(q, _language(context)))

    elif kind == "newtask":
        titre = context.chat_data.get("pending_title", "Sans titre")
        rows = [[InlineKeyboardButton(_category_label(c), callback_data=f"cat|{c}")]
                for c in CATEGORIES]
        await query.message.reply_text(f"Nouvelle tâche : « {titre} ». Catégorie ?",
                                       reply_markup=InlineKeyboardMarkup(rows))

    elif kind == "ignore":
        context.chat_data.pop("pending_title", None)
        await query.message.reply_text("Ignoré.")

    elif kind == "cat":
        titre = context.chat_data.get("pending_title", "Sans titre")
        suggestion = context.chat_data.get("pending_deadline_suggestion", "")
        context.chat_data["pending_task_meta"] = {
            "titre": titre,
            "cat": rest[0],
            "suggested_deadline": suggestion,
        }
        if suggestion:
            rows = [[InlineKeyboardButton(f"Utiliser {suggestion}",
                                          callback_data="ddl|suggest"),
                     InlineKeyboardButton("Modifier", callback_data="ddl|ask")],
                    [InlineKeyboardButton("Aucune date limite",
                                          callback_data="ddl|none")]]
            prompt = (
                "Cette tâche a-t-elle une date limite de résolution ?\n"
                f"Date détectée par le LLM : {suggestion}. "
                "Confirme, modifie ou ignore cette date."
            )
        else:
            rows = [[InlineKeyboardButton("Aucune date limite", callback_data="ddl|none"),
                     InlineKeyboardButton("Saisir une date", callback_data="ddl|ask")]]
            prompt = "Cette tâche a-t-elle une date limite de résolution ?"
        await query.message.reply_text(prompt, reply_markup=InlineKeyboardMarkup(rows))

    elif kind == "ddl":
        meta = context.chat_data.pop("pending_task_meta", None)
        if meta is None:
            await query.message.reply_text("Création expirée — relance /add.")
            return
        context.chat_data.pop("pending_title", None)
        context.chat_data.pop("pending_deadline_suggestion", None)
        if rest[0] == "none":
            await _start_new_task_interview(
                query.message, chat_id, context, meta["titre"], meta["cat"], None)
        elif rest[0] == "suggest":
            await _start_new_task_interview(
                query.message, chat_id, context,
                meta["titre"], meta["cat"], meta.get("suggested_deadline") or None)
        else:
            context.chat_data["pending_newtask_deadline"] = meta
            suffix = ""
            if meta.get("suggested_deadline"):
                suffix = f"\nDate détectée : {meta['suggested_deadline']}."
            await query.message.reply_text(
                "Quelle est la date limite ? "
                "(format AAAA-MM-JJ, ex. 2026-07-20, ou « aucune »)"
                + suffix)

    elif kind == "scat":
        vt = context.chat_data.pop("scan_current", None)
        if vt is None:
            return
        task_id = db.create_task(conn, vt.titre, rest[0], deadline=vt.due,
                                 source="obsidian", obsidian_path=vt.rel_path,
                                 sujet_tag=vt.sujet_tag)
        deadline_days = None
        if vt.due:
            try:
                deadline_days = (dt.date.fromisoformat(vt.due)
                                 - dt.date.today()).days
            except ValueError:
                pass
        session = itv.Session(deadline_days=deadline_days, seed=task_id)
        interview_id = db.create_interview(conn, task_id, session.mode)
        SESSIONS[chat_id] = {"conn": conn, "task_id": task_id,
                             "interview_id": interview_id, "session": session,
                             "obsidian": vt}
        await _ask_next(query.message, chat_id, context)

    elif kind == "scannext":
        if chat_id in SESSIONS:
            await query.message.reply_text("Termine d'abord l'entretien en cours.")
        else:
            await _scan_next(query.message, context)

    elif kind == "scanstop":
        n = len(context.chat_data.pop("scan_queue", []) or [])
        context.chat_data.pop("scan_current", None)
        await query.message.reply_text(
            f"Scan interrompu ({n} tâche(s) non traitée(s) — relance /scan "
            "quand tu veux, elles seront retrouvées).")

    elif kind == "ans" and chat_id in SESSIONS:
        state = SESSIONS[chat_id]
        q = Q(rest[0])
        raw = rest[1]
        if raw == "?":   # je ne sais pas → médiane + incertitude (§6.2)
            axis = itv.Q_TO_AXIS[q]
            value = (AXIS_MEDIAN[axis], Incertitude.NE_SAIT_PAS)
            db.record_answer(state["conn"], state["interview_id"], axis.value,
                             None, "je ne sais pas", 2)
        else:
            value = _typed_answer_value(q, raw)
            axe = _answer_axis_code(q)
            db.record_answer(state["conn"], state["interview_id"], axe,
                             value if isinstance(value, int) else None, str(raw))
        state["session"] = itv.answer(state["session"], q, value)
        if q == Q.SUBJECTIVE:
            await _send_subjective_challenge(query.message, context, state, str(raw))
        await _ask_next(query.message, chat_id, context)

    elif kind == "mir" and chat_id in SESSIONS:
        state = SESSIONS[chat_id]
        mq = itv.mirror_for(state["session"])
        if mq is None:
            return
        opt = mq.options[int(rest[0])]
        db.record_answer(state["conn"], state["interview_id"],
                         f"MIROIR_{mq.code}",
                         opt.valeur if opt.axe else None, opt.label,
                         2 if opt.incertain else 0)
        state["session"] = itv.mirror_answer(state["session"], int(rest[0]))
        if opt.axe:
            await query.message.reply_text(
                f"Noté — {opt.axe} corrigé en conséquence.")
        await _ask_next(query.message, chat_id, context)

    elif kind == "obj" and chat_id in SESSIONS:
        SESSIONS[chat_id]["goal_id"] = int(rest[0])
        rows = [[InlineKeyboardButton(lbl, callback_data=f"objlvl|{v}")]
                for lbl, v in [("Contribution indirecte", 1),
                               ("Contribution directe", 2),
                               ("Contribution majeure", 3)]]
        await query.message.reply_text("À quel point y contribue-t-elle ?",
                                       reply_markup=InlineKeyboardMarkup(rows))

    elif kind == "objlvl" and chat_id in SESSIONS:
        state = SESSIONS[chat_id]
        goal_id = state.pop("goal_id", None)
        valeur = int(rest[0])
        if goal_id:
            db.set_task_goal(conn, state["task_id"], goal_id)
        db.record_answer(state["conn"], state["interview_id"], "ALN",
                         valeur, f"goal:{goal_id}")
        state["session"] = itv.answer(state["session"], Q.OBJECTIF, valeur)
        await _ask_next(query.message, chat_id, context)

    elif kind == "gcat":
        titre = context.chat_data.pop("pending_goal", None)
        if titre:
            db.create_goal(conn, titre, rest[0])
            await query.message.reply_text(
                f"🎯 Objectif créé : « {titre} » ({rest[0]}).\n"
                "Il sera proposé à chaque entretien.")

    elif kind == "goal":
        g = conn.execute("SELECT * FROM goals WHERE id=?", (int(rest[0]),)).fetchone()
        if g:
            rows = [[InlineKeyboardButton("🏆 Atteint", callback_data=f"gset|{g['id']}|atteint"),
                     InlineKeyboardButton("⏸ Suspendre", callback_data=f"gset|{g['id']}|suspendu")],
                    [InlineKeyboardButton("📁 Changer de catégorie", callback_data=f"gmvcat|{g['id']}"),
                     InlineKeyboardButton("🔍 Cohérence (LLM)", callback_data=f"gaudit|{g['id']}")],
                    [InlineKeyboardButton("Annuler", callback_data="cancel")]]
            await query.message.reply_text(f"🎯 « {g['titre']} » — que faire ?",
                                           reply_markup=InlineKeyboardMarkup(rows))

    elif kind == "gset":
        db.set_goal_status(conn, int(rest[0]), rest[1])
        await query.message.reply_text(
            "🏆 Objectif marqué atteint — bravo." if rest[1] == "atteint"
            else "⏸ Objectif suspendu (réactivable en base).")

    elif kind == "gmvcat":
        rows = [[InlineKeyboardButton(_category_label(c),
                                      callback_data=f"gmv|{rest[0]}|{c}")]
                for c in CATEGORIES]
        await query.message.reply_text("Nouvelle catégorie ?",
                                       reply_markup=InlineKeyboardMarkup(rows))

    elif kind == "gmv":
        db.set_goal_category(conn, int(rest[0]), rest[1])
        await query.message.reply_text(f"📁 Catégorie changée : {rest[1]}.")

    elif kind == "gaudit":
        gid = int(rest[0])
        llm = context.bot_data.get("llm")
        g = conn.execute("SELECT titre FROM goals WHERE id=?", (gid,)).fetchone()
        tasks = db.goal_tasks(conn, gid, actives_seulement=False)
        if not tasks:
            await query.message.reply_text("Aucune tâche liée à cet objectif.")
        elif not await _ensure_llm_ready(query.message, context):
            return
        else:
            await query.message.reply_text(
                f"🔍 Analyse de {len(tasks)} tâche(s)…")
            douteuses = await asyncio.to_thread(
                llm.audit_goal, g["titre"],
                [(t["id"], t["titre"]) for t in tasks])
            if douteuses is None:
                await query.message.reply_text(
                    f"Analyse impossible ({getattr(llm, 'last_error', '')} — /llm).")
            elif not douteuses:
                await query.message.reply_text(
                    f"✅ Les {len(tasks)} tâches semblent cohérentes avec l'objectif.")
            else:
                await query.message.reply_text(
                    f"⚠️ {len(douteuses)} tâche(s) au lien douteux — à toi de décider :")
                for d in douteuses:
                    titre = next((t["titre"] for t in tasks if t["id"] == d["id"]), "?")
                    rows = [[InlineKeyboardButton("🔗 Détacher de l'objectif",
                                                  callback_data=f"gdet|{d['id']}"),
                             InlineKeyboardButton("Garder", callback_data="cancel")]]
                    await query.message.reply_text(
                        f"#{d['id']} « {titre} »\n💬 {d['raison']}",
                        reply_markup=InlineKeyboardMarkup(rows))

    elif kind == "gdet":
        db.set_task_goal(conn, int(rest[0]), None)
        await query.message.reply_text("🔗 Tâche détachée de l'objectif "
                                       "(son score reste inchangé jusqu'à réévaluation).")

    elif kind == "clar" and chat_id in SESSIONS:
        state = SESSIONS[chat_id]
        if rest[0] == "DATE":       # C5 : l'utilisateur va donner la date
            state["session"] = itv.promise_deadline(state["session"])
            state["awaiting_date"] = True
            await query.message.reply_text(
                "Quelle est la date butoir ? (format AAAA-MM-JJ, ex. 2026-07-20)")
            return
        incertain = len(rest) > 2 and rest[2] == "1"
        state["session"] = itv.clarify(state["session"], rest[0],
                                       int(rest[1]), incertain)
        await query.message.reply_text("Noté, axe corrigé. Suite…")
        await _ask_next(query.message, chat_id, context)

    elif kind == "nrg":
        context.chat_data["energie"] = int(rest[0])
        rows = [[InlineKeyboardButton(f"{h} h", callback_data=f"cap|{h * 60}")]
                for h in (2, 4, 6, 8)]
        await query.message.reply_text("Heures maîtrisables aujourd'hui ?",
                                       reply_markup=InlineKeyboardMarkup(rows))

    elif kind == "cap":
        energie = context.chat_data.get("energie", 3)
        capacite = int(rest[0])
        def deadline_days(value: str | None) -> int | None:
            if not value:
                return None
            try:
                return (dt.date.fromisoformat(value) - dt.date.today()).days
            except ValueError:
                return None

        tasks = [planner.PlanTask(
            r["id"], r["titre"], Priorite(r["priorite"]), r["score_global"],
            None if r["estimation"] == Estimation.INCONNUE.value else r["estimation_min"],
            Effort(r["effort"]), r["cat_code"] or "?", bool(r["pepite"]),
            deadline_days(r["deadline_reelle"]), r["deadline_reelle"])
            for r in db.current_tasks(conn)]
        plan = planner.build_day_plan(tasks, capacite, energie)
        date_str = dt.date.today().isoformat()
        db.save_plan(conn, date_str, capacite, energie, plan)

        vault = context.bot_data.get("vault_path")
        if vault:
            prioris_dir = context.bot_data.get("prioris_dir", "PRIORIS")
            content = export.render_plan_md(plan, date_str, energie)
            export.write_note(vault, f"{prioris_dir}/Plan du jour.md", content)

        lines = [f"📋 Plan du jour ({plan.capacite_utile_min} min utiles) :"]
        lines += [f"{i}. {'entamer : ' if it.entamer else ''}{it.task.titre} "
                  f"({it.duree_min} min · {it.task.priorite.value})"
                  f"{' 💎' if it.task.pepite else ''}"
                  for i, it in enumerate(plan.items, 1)]
        if plan.avertissements:
            lines += ["", *[f"⚠️ {a}" for a in plan.avertissements]]
        if plan.sacrifiees:
            lines += ["", "Non retenu : " + ", ".join(t.titre for t in plan.sacrifiees)]
        lines.append("" if not vault else "\n📝 Exporté dans Obsidian.")
        await query.message.reply_text("\n".join(filter(None, lines))
                                       or "Plan vide — plan honnête.")
