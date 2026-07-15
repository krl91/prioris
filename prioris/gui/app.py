"""PRIORIS graphical interface, local mode without Telegram.

Main window, interview dialog, daily plan and goals. Everything is synchronous
with no asyncio; tkinter is the only UI dependency and ships with Python 3.11+.
"""
from __future__ import annotations

import datetime as dt
import json
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk

from ..core import biases, planner, scoring
from ..core import interview as itv
from ..core.axes import (AXIS_QUESTIONS, AXIS_MEDIAN, ESTIMATION_MIN,
                          Axis, Effort, Estimation,
                          Incertitude, Metadata, Priorite)
from ..core.interview import Q
from ..i18n import (axis_labels, normalize_language, options as i18n_options,
                    question_text, t)
from ..llm import ChatClient, LLMConfig, LLMFacade, resolve
from ..llm import health as llm_health
from ..store import db
from .. import task_impact
from .. import task_revision
from ..vault import export
from ..vault import info_sync
from ..vault import scan

# ──────────────────────────────────────────────── shared constants

CATEGORIES = [
    "travail", "carriere", "sante", "finances", "ia",
    "formation", "famille", "loisirs", "perso",
]


def _category_label(cat: str) -> str:
    return "IA" if cat == "ia" else cat.capitalize()


def _parse_task_ids(raw: str | None) -> list[int] | None:
    """Parse comma-separated ids. None means create a new task."""
    if raw is None:
        return []
    raw = raw.strip()
    if not raw:
        return None
    ids: list[int] = []
    for part in raw.replace(" ", "").split(","):
        if part:
            ids.append(int(part))
    return ids


QUESTION_TEXT: dict[Q, str] = {
    Q.SUBJECTIVE:      "Instinctivement, tu la classes comment ?",
    Q.INACTION:        AXIS_QUESTIONS[Axis.INA],
    Q.BLOCAGE:         AXIS_QUESTIONS[Axis.BLK],
    Q.CDR:             AXIS_QUESTIONS[Axis.CDR],
    Q.OBJECTIF:        AXIS_QUESTIONS[Axis.ALN],
    Q.ESTIMATION:      "Temps nécessaire, réalistement ?",
    Q.IMPACT:          AXIS_QUESTIONS[Axis.IMP],
    Q.HORIZON:         AXIS_QUESTIONS[Axis.HOR],
    Q.IRREVERSIBILITE: AXIS_QUESTIONS[Axis.IRR],
    Q.EFFORT:          "Quel effort cognitif demande-t-elle ?",
    Q.DEMANDEUR:       "Qui demande cette tâche ?",
    Q.VISIBILITE:      "À quel point est-elle visible (réunions, mails, relances) ?",
    Q.PRESSION:        "Quelle pression ressens-tu dessus ?",
}


def _options(q: Q) -> list[tuple[str, str]]:
    """Return encoded (label, value) options for a question, matching handlers.py."""
    return i18n_options(q, "fr")


def _why_text(conn, task_id: int) -> str:
    """Full rationale text, matching handlers._why_text."""
    row = db.last_evaluation(conn, task_id)
    if not row:
        return "Pas d'évaluation pour cette tâche."
    task = conn.execute("SELECT titre FROM tasks WHERE id=?",
                        (task_id,)).fetchone()
    j = json.loads(row["justification_json"])
    axes_txt = "\n".join(
        f"  {a}: {d['valeur']}" + (" (défaut)" if d["defaut"] else "")
        for a, d in j["axes"].items())
    return (
        f"📋 #{task_id} {task['titre'] if task else ''}\n"
        f"{j['priorite']} — {j['quadrant']} — G={j['calculs']['G']['total']}\n"
        f"U={j['calculs']['U']['total']} · I={j['calculs']['I']['total']}\n"
        f"Axes :\n{axes_txt}\n"
        f"Ajustements : {[a['regle'] for a in j['ajustements']] or 'aucun'}\n"
        f"Mode : {j['mode']} · algo v{j['version_algo']}"
    )


# ─────────────────────────────────────────── category picker dialog

def _pick_category(parent: tk.BaseWidget) -> str | None:
    """Modal category picker. Returns None when cancelled."""
    dlg = tk.Toplevel(parent)
    dlg.title("Catégorie")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.transient(parent)

    result: list[str | None] = [None]

    ttk.Label(dlg, text="Choisir une catégorie :",
              font=("", 10)).pack(pady=(10, 6), padx=10)

    frame = ttk.Frame(dlg, padding=4)
    frame.pack()

    for i, cat in enumerate(CATEGORIES):
        def _click(c: str = cat) -> None:
            result[0] = c
            dlg.destroy()

        ttk.Button(frame, text=_category_label(cat), width=10,
                   command=_click).grid(row=i // 3, column=i % 3,
                                        padx=3, pady=3)

    ttk.Button(dlg, text="Annuler",
               command=dlg.destroy).pack(pady=(4, 8))

    dlg.update_idletasks()
    _center_on(dlg, parent)
    dlg.wait_window()
    return result[0]


def _center_on(win: tk.Toplevel, parent: tk.BaseWidget) -> None:
    """Center `win` over `parent`."""
    win.update_idletasks()
    px = parent.winfo_rootx()
    py = parent.winfo_rooty()
    pw = parent.winfo_width()
    ph = parent.winfo_height()
    ww = win.winfo_width()
    wh = win.winfo_height()
    win.geometry(f"+{px + (pw - ww) // 2}+{py + (ph - wh) // 2}")


# ──────────────────────────────────────────────── interview dialog

class InterviewDialog(tk.Toplevel):
    """Modal window that runs a task evaluation interview.

    Synchronous counterpart of the Telegram flow in handlers.py.
    """

    def __init__(
        self,
        parent: tk.BaseWidget,
        conn,
        titre: str,
        category_code: str,
        goals: list | None = None,
        deadline_days: int | None = None,
        deadline: str | None = None,
        source: str = "local",
        obsidian_path: str | None = None,
        vault_path: str | None = None,
        prioris_dir: str = "PRIORIS",
        llm: LLMFacade | None = None,
        obsidian_task: scan.VaultTask | None = None,
        language: str = "fr",
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.task_title = titre
        self.goals: list = goals or []
        self.vault_path = vault_path
        self.prioris_dir = prioris_dir
        self.llm = llm
        self.language = normalize_language(language)
        self.obsidian_task = obsidian_task
        self.result_text: str | None = None  # filled by _finish()

        # Create the task and interview rows.
        self.task_id = db.create_task(
            conn, titre, category_code,
            deadline=deadline, source=source, obsidian_path=obsidian_path,
        )
        session = itv.Session(seed=self.task_id, deadline_days=deadline_days)
        self.interview_id = db.create_interview(conn, self.task_id, session.mode)
        self.session = session
        self._goal_id: int | None = None
        self._quadrant_helpers_shown = False

        self.title(f"Entretien — {titre[:55]}")
        self.geometry("520x460")
        self.resizable(True, True)
        self.grab_set()
        self.transient(parent)

        self._build_ui()
        self._show_next()

        self.update_idletasks()
        _center_on(self, parent)

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Status bar: mode and progress.
        self._status_var = tk.StringVar(value="Mode : express")
        ttk.Label(self, textvariable=self._status_var,
                  foreground="gray", font=("", 9)).pack(
            anchor="w", padx=10, pady=(6, 0))

        # Question text.
        self._q_var = tk.StringVar()
        ttk.Label(self, textvariable=self._q_var, font=("", 11),
                  wraplength=490, justify="left").pack(
            fill="x", padx=10, pady=8)

        ttk.Separator(self).pack(fill="x", padx=8)

        # Scrollable button area, also used for goal lists.
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True, padx=8, pady=6)

        self._canvas = tk.Canvas(outer, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical",
                            command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._btn_frame = ttk.Frame(self._canvas)
        self._btn_win = self._canvas.create_window(
            (0, 0), window=self._btn_frame, anchor="nw")

        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._btn_frame.bind("<Configure>", self._on_frame_resize)

    def _on_canvas_resize(self, event: tk.Event) -> None:
        self._canvas.itemconfig(self._btn_win, width=event.width)

    def _on_frame_resize(self, event: tk.Event) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    # ── question navigation ──────────────────────────────────────────

    def _clear_buttons(self) -> None:
        for w in self._btn_frame.winfo_children():
            w.destroy()

    def _show_next(self) -> None:
        q, self.session = itv.next_question(self.session)
        self._clear_buttons()
        self._status_var.set(f"Mode : {self.session.mode}")

        if q is None:
            self._finish()
            return

        if q == Q.CLARIFICATION:
            self._show_clarification()
            return

        if q == Q.MIROIR:
            self._show_miroir()
            return

        if q == Q.OBJECTIF:
            self._show_objectif()
            return

        # Standard question: text and buttons.
        if q == Q.SUBJECTIVE:
            self._show_quadrant_helpers()
        self._q_var.set(question_text(q, self.language))
        if self.llm and self.llm.available and q in itv.Q_TO_AXIS:
            self._show_text_answer(q)
        for lbl, val in i18n_options(q, self.language):
            ttk.Button(
                self._btn_frame, text=lbl,
                command=lambda v=val, qq=q: self._on_answer(qq, v),
            ).pack(fill="x", pady=2, padx=4)

    def _show_quadrant_helpers(self) -> None:
        """Display LLM-generated quadrant helper questions once."""
        if self._quadrant_helpers_shown or not self.llm or not self.llm.available:
            return
        self._quadrant_helpers_shown = True
        self.config(cursor="watch")
        self.update_idletasks()
        questions = self.llm.quadrant_questions(self.task_title, self.language)
        self.config(cursor="")
        if not questions:
            return
        box = ttk.LabelFrame(self._btn_frame,
                             text=t("quadrant_helper_title", self.language))
        box.pack(fill="x", pady=(2, 8), padx=4)
        for i, question in enumerate(questions, start=1):
            ttk.Label(box, text=f"{i}. {question}", wraplength=470,
                      justify="left").pack(fill="x", padx=6, pady=2)

    def _show_text_answer(self, q: Q) -> None:
        """Free-text LLM answer, always confirmed before recording."""
        box = ttk.LabelFrame(self._btn_frame, text="Réponse libre (LLM)")
        box.pack(fill="x", pady=(2, 8), padx=4)
        var = tk.StringVar()
        ttk.Entry(box, textvariable=var).pack(side="left", fill="x",
                                              expand=True, padx=4, pady=4)
        ttk.Button(
            box, text="Interpréter",
            command=lambda qq=q, vv=var: self._interpret_free_text(qq, vv.get()),
        ).pack(side="right", padx=4, pady=4)

    def _interpret_free_text(self, q: Q, text: str) -> None:
        text = text.strip()
        if not text:
            return
        axis = itv.Q_TO_AXIS[q]
        self.config(cursor="watch")
        self.update_idletasks()
        parsed = self.llm.interpret_answer(
            axis, question_text(q, self.language), text) if self.llm else None
        self.config(cursor="")
        if parsed is None:
            reason = getattr(self.llm, "last_error", None) if self.llm else "LLM absent"
            messagebox.showwarning(
                "Interprétation impossible",
                "Je n'ai pas pu interpréter cette réponse.\n"
                "Utilise les boutons.\n\n"
                f"Détail : {reason}",
                parent=self,
            )
            return
        label = axis_labels(axis, self.language)[parsed.valeur]
        doute = {0: "", 1: " (hésitation)", 2: " (grande incertitude)"}[
            parsed.incertitude]
        ok = messagebox.askyesno(
            "Confirmer l'interprétation",
            f"{parsed.reformulation}\n\n"
            f"{axis.value} : « {label} »{doute}\n\n"
            "C'est bien ça ?",
            parent=self,
        )
        if not ok:
            return
        db.record_answer(self.conn, self.interview_id, parsed.axis.value,
                         parsed.valeur, text, parsed.incertitude)
        self.session = itv.answer(
            self.session, q, (parsed.valeur, Incertitude(parsed.incertitude)))
        self._show_next()

    # ── answer handling ──────────────────────────────────────────────

    def _on_answer(self, q: Q, raw: str | int) -> None:
        """Record an answer with the same logic as handlers.py 'ans' callbacks."""
        if raw == "?":
            axis = itv.Q_TO_AXIS[q]
            value: object = (AXIS_MEDIAN[axis], Incertitude.NE_SAIT_PAS)
            db.record_answer(self.conn, self.interview_id,
                             axis.value, None, "je ne sais pas", 2)
        else:
            value = (
                raw if q in (Q.SUBJECTIVE, Q.DEMANDEUR)
                else Estimation[str(raw)] if q == Q.ESTIMATION
                else int(raw)
            )
            axe = (itv.Q_TO_AXIS[q].value if q in itv.Q_TO_AXIS
                   else q.value)
            db.record_answer(
                self.conn, self.interview_id, axe,
                value if isinstance(value, int) else None, str(raw),
            )
        self.session = itv.answer(self.session, q, value)
        self._show_next()

    # ── goal question ────────────────────────────────────────────────

    def _show_objectif(self) -> None:
        self._q_var.set(question_text(Q.OBJECTIF, self.language))
        suggestion = None
        if self.llm and self.llm.available:
            self.config(cursor="watch")
            self.update_idletasks()
            suggestion = self.llm.suggest_goal(
                self.task_title,
                [(g["id"], g["titre"]) for g in self.goals],
            )
            self.config(cursor="")
            if suggestion:
                self._q_var.set(question_text(Q.OBJECTIF, self.language) +
                                "\n(⭐ = suggestion, à confirmer)")
        ttk.Button(
            self._btn_frame, text="Aucun objectif",
            command=lambda: self._on_answer(Q.OBJECTIF, 0),
        ).pack(fill="x", pady=2, padx=4)
        ttk.Button(
            self._btn_frame, text="➕ Créer un nouvel objectif",
            command=self._create_goal_from_interview,
        ).pack(fill="x", pady=2, padx=4)
        goals = sorted(self.goals[:8], key=lambda g: g["id"] != suggestion)
        for g in goals:
            ttk.Button(
                self._btn_frame,
                text=f"{'⭐ ' if g['id'] == suggestion else ''}🎯 {g['titre'][:45]}",
                command=lambda gid=g["id"]: self._on_goal_selected(gid),
            ).pack(fill="x", pady=2, padx=4)

    def _create_goal_from_interview(self) -> None:
        titre = simpledialog.askstring(
            "Nouvel objectif",
            "Titre de l'objectif :",
            parent=self,
        )
        if titre is None:
            return
        titre = titre.strip()
        if not titre:
            messagebox.showwarning(
                "Objectif vide",
                "Indique un titre pour créer l'objectif.",
                parent=self,
            )
            return
        cat = _pick_category(self)
        if cat is None:
            return
        goal_id = db.create_goal(self.conn, titre, cat)
        self.goals = db.active_goals(self.conn)
        self._on_goal_selected(goal_id)

    def _on_goal_selected(self, goal_id: int) -> None:
        self._goal_id = goal_id
        self._clear_buttons()
        self._q_var.set("À quel point y contribue-t-elle ?")
        for lbl, v in [
            ("Contribution indirecte", 1),
            ("Contribution directe", 2),
            ("Contribution majeure", 3),
        ]:
            ttk.Button(
                self._btn_frame, text=lbl,
                command=lambda val=v: self._on_objlvl(val),
            ).pack(fill="x", pady=2, padx=4)

    def _on_objlvl(self, valeur: int) -> None:
        if self._goal_id:
            db.set_task_goal(self.conn, self.task_id, self._goal_id)
        db.record_answer(self.conn, self.interview_id, "ALN",
                         valeur, f"goal:{self._goal_id}")
        self.session = itv.answer(self.session, Q.OBJECTIF, valeur)
        self._goal_id = None
        self._show_next()

    # ── clarifications for contradictions ────────────────────────────

    def _show_clarification(self) -> None:
        c = self.session.pending
        self._q_var.set(f"⚠️ {c.message}\n\n{c.question}")
        for lbl, axe, val in c.options:
            incertain = lbl.lower().startswith("je ne sais pas")
            ttk.Button(
                self._btn_frame, text=lbl,
                command=lambda a=axe, v=val, i=incertain:
                    self._on_clarify(a, v, i),
            ).pack(fill="x", pady=2, padx=4)

    def _on_clarify(self, axis_code: str, val: str, incertain: bool) -> None:
        if axis_code == "DATE":
            date_str = simpledialog.askstring(
                "Date butoir",
                "Quelle est la date butoir ?\n(format AAAA-MM-JJ, ex. 2026-07-20)\n"
                "Tape « aucune » s'il n'y en a pas.",
                parent=self,
            )
            if date_str is None:
                return  # cancelled
            if date_str.lower() in ("aucune", "aucun", "non", ""):
                self.session = itv.promise_deadline(self.session)
            else:
                try:
                    due = dt.date.fromisoformat(date_str.strip())
                    days = (due - dt.date.today()).days
                    self.session = itv.promise_deadline(self.session)
                    self.session = itv.set_deadline(self.session, days)
                    self.conn.execute(
                        "UPDATE tasks SET deadline_reelle=?,"
                        " updated_at=datetime('now') WHERE id=?",
                        (due.isoformat(), self.task_id),
                    )
                    self.conn.commit()
                except ValueError:
                    messagebox.showwarning(
                        "Format invalide",
                        "Utilise le format AAAA-MM-JJ (ex. 2026-07-20).",
                        parent=self,
                    )
                    return
        else:
            self.session = itv.clarify(
                self.session, axis_code, int(val), incertain)
        self._show_next()

    # ── mirror question ──────────────────────────────────────────────

    def _show_miroir(self) -> None:
        mq = itv.mirror_for(self.session)
        if mq is None:
            self._finish()
            return
        self._q_var.set(f"🪞 Dernière vérification : {mq.question}")
        for i, opt in enumerate(mq.options):
            ttk.Button(
                self._btn_frame, text=opt.label,
                command=lambda idx=i: self._on_miroir(idx),
            ).pack(fill="x", pady=2, padx=4)

    def _on_miroir(self, option_index: int) -> None:
        mq = itv.mirror_for(self.session)
        if mq is None:
            return
        opt = mq.options[option_index]
        db.record_answer(
            self.conn, self.interview_id,
            f"MIROIR_{mq.code}",
            opt.valeur if opt.axe else None, opt.label,
            2 if opt.incertain else 0,
        )
        self.session = itv.mirror_answer(self.session, option_index)
        self._show_next()

    # ── finalization ─────────────────────────────────────────────────

    def _finish(self) -> None:
        """Compute the score, persist it and display the result."""
        s = self.session
        axes, par_defaut = itv.final_axes(s)
        result = scoring.score(
            axes,
            estimation=s.estimation or Estimation.INCONNUE,
            deadline_days=s.deadline_days,
            incertitudes=s.incertitudes,
            mode=s.mode,
            axes_par_defaut=par_defaut,
            subjective=s.subjective,
        )
        meta = Metadata(
            demandeur=s.demandeur, visibilite=s.visibilite,
            pression=s.pression, subjective=s.subjective,
        )
        flags = biases.detect(axes, result.importance, result.priorite, meta)

        db.finish_interview(self.conn, self.interview_id, s.mode)
        est = s.estimation or Estimation.INCONNUE
        db.update_task_planning_attrs(
            self.conn, self.task_id, est.value,
            ESTIMATION_MIN[est], s.effort.value,
        )
        eval_id = db.save_evaluation(
            self.conn, self.task_id, self.interview_id,
            result, s.subjective.value if s.subjective else None,
        )
        db.save_bias_flags(self.conn, eval_id, flags)

        text = scoring.explain(result)
        if flags:
            text += "\n\nBiais détectés :\n" + "\n".join(
                f"• {f.type_biais} ({f.gravite}) : {f.message}"
                for f in flags
            )
        text += f"\n\nTâche #{self.task_id} · détail : bouton « Pourquoi ? »"

        if self.obsidian_task is not None and self.vault_path:
            annotated, detail_rel = scan.apply_result(
                self.vault_path, self.prioris_dir, self.obsidian_task,
                self.task_id, result.justification, flags,
                dt.date.today().isoformat(),
            )
            if annotated:
                text += (f"\n📝 Note annotée ({self.obsidian_task.rel_path}) "
                         f"+ détail : {detail_rel}")
            else:
                text += (f"\n⚠️ Ligne introuvable dans "
                         f"{self.obsidian_task.rel_path} — détail créé : "
                         f"{detail_rel}")
        self.result_text = text

        # Display the result in-place; do not auto-close the dialog.
        self._status_var.set("Entretien terminé")
        self._q_var.set("✅ Évaluation enregistrée !")
        self._clear_buttons()

        st = scrolledtext.ScrolledText(
            self._btn_frame, height=12, wrap="word",
            state="normal", font=("", 9),
        )
        st.insert("1.0", text)
        st.config(state="disabled")
        st.pack(fill="both", expand=True, pady=4)

        ttk.Button(
            self._btn_frame, text="Fermer",
            command=self.destroy,
        ).pack(pady=4)


# ──────────────────────────────────────────────── daily plan dialog

class TodayDialog(tk.Toplevel):
    """Energy and capacity input, then greedy daily-plan generation."""

    def __init__(
        self, parent: tk.BaseWidget, conn,
        vault_path: str | None = None, prioris_dir: str = "PRIORIS",
    ) -> None:
        super().__init__(parent)
        self.conn = conn
        self.vault_path = vault_path
        self.prioris_dir = prioris_dir
        self.result_text: str | None = None

        self.title("Plan du jour")
        self.geometry("460x280")
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)

        self._energie = tk.IntVar(value=3)
        self._capacite = tk.IntVar(value=240)

        self._build_ui()
        self.update_idletasks()
        _center_on(self, parent)

    def _build_ui(self) -> None:
        ttk.Label(self, text="Ton énergie aujourd'hui ?",
                  font=("", 11)).pack(pady=(14, 4))
        e_frame = ttk.Frame(self)
        e_frame.pack()
        for n, lbl in enumerate(
                ["Très faible", "Faible", "Normale", "Bonne", "Excellente"], 1):
            ttk.Radiobutton(e_frame, text=lbl, variable=self._energie,
                            value=n).pack(side="left", padx=5)

        ttk.Label(self, text="Heures disponibles aujourd'hui ?",
                  font=("", 11)).pack(pady=(16, 4))
        c_frame = ttk.Frame(self)
        c_frame.pack()
        for h in (2, 4, 6, 8):
            ttk.Radiobutton(c_frame, text=f"{h} h", variable=self._capacite,
                            value=h * 60).pack(side="left", padx=10)

        ttk.Button(
            self, text="📋 Générer le plan",
            command=self._generate, padding="10 6",
        ).pack(pady=18)

    def _generate(self) -> None:
        energie = self._energie.get()
        capacite = self._capacite.get()

        def deadline_days(value: str | None) -> int | None:
            if not value:
                return None
            try:
                return (dt.date.fromisoformat(value) - dt.date.today()).days
            except ValueError:
                return None

        tasks = [
            planner.PlanTask(
                r["id"], r["titre"],
                Priorite(r["priorite"]),
                r["score_global"],
                None if r["estimation"] == Estimation.INCONNUE.value
                else r["estimation_min"],
                Effort(r["effort"]),
                r["cat_code"] or "?",
                bool(r["pepite"]),
                deadline_days(r["deadline_reelle"]),
                r["deadline_reelle"],
            )
            for r in db.current_tasks(self.conn)
        ]

        plan = planner.build_day_plan(tasks, capacite, energie)
        date_str = dt.date.today().isoformat()
        db.save_plan(self.conn, date_str, capacite, energie, plan)

        if self.vault_path:
            content = export.render_plan_md(plan, date_str, energie)
            export.write_note(
                self.vault_path,
                f"{self.prioris_dir}/Plan du jour.md",
                content,
            )

        lines = [f"📋 Plan du jour ({plan.capacite_utile_min} min utiles) :"]
        lines += [
            f"{i}. {'entamer : ' if it.entamer else ''}"
            f"{it.task.titre} "
            f"({it.duree_min} min · {it.task.priorite.value})"
            f"{' 💎' if it.task.pepite else ''}"
            for i, it in enumerate(plan.items, 1)
        ]
        if plan.avertissements:
            lines += ["", *[f"⚠️ {a}" for a in plan.avertissements]]
        if plan.sacrifiees:
            lines += [
                "",
                "Non retenu : "
                + ", ".join(t.titre for t in plan.sacrifiees),
            ]
        if self.vault_path:
            lines.append("\n📝 Exporté dans Obsidian.")

        self.result_text = "\n".join(lines) or "Plan vide — plan honnête."
        self.destroy()


# ──────────────────────────────────────────────── goals dialog

class GoalsDialog(tk.Toplevel):
    """Life-goal management."""

    def __init__(self, parent: tk.BaseWidget, conn) -> None:
        super().__init__(parent)
        self.conn = conn

        self.title("Objectifs de vie")
        self.geometry("500x400")
        self.resizable(True, True)
        self.grab_set()
        self.transient(parent)

        self._build_ui()
        self._refresh()
        self.update_idletasks()
        _center_on(self, parent)

    def _build_ui(self) -> None:
        # Add form.
        add_frame = ttk.Frame(self, padding=(8, 6))
        add_frame.pack(fill="x")
        ttk.Label(add_frame, text="Nouvel objectif :").pack(side="left")
        self._entry_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self._entry_var,
                  width=32).pack(side="left", padx=6)
        ttk.Button(add_frame, text="Ajouter",
                   command=self._add_goal).pack(side="left")

        ttk.Separator(self).pack(fill="x", padx=8)

        # Scrollable list.
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True, padx=8, pady=6)
        self._canvas = tk.Canvas(outer, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical",
                            command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._list_frame = ttk.Frame(self._canvas)
        self._list_win = self._canvas.create_window(
            (0, 0), window=self._list_frame, anchor="nw")
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(
                              self._list_win, width=e.width))
        self._list_frame.bind("<Configure>",
                              lambda e: self._canvas.configure(
                                  scrollregion=self._canvas.bbox("all")))

        ttk.Button(self, text="Fermer",
                   command=self.destroy).pack(pady=6)

    def _refresh(self) -> None:
        for w in self._list_frame.winfo_children():
            w.destroy()
        goals = db.active_goals(self.conn)
        if not goals:
            ttk.Label(
                self._list_frame,
                text="Aucun objectif actif.\nAjoute-en un ci-dessus.",
                justify="center",
            ).pack(pady=20)
            return
        for g in goals:
            row = ttk.Frame(self._list_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(
                row,
                text=f"🎯 {g['titre'][:42]}",
                anchor="w", width=36,
            ).pack(side="left")
            ttk.Label(
                row,
                text=f"{g['nb_faites']}/{g['nb_taches']} tâches",
                foreground="gray", width=12,
            ).pack(side="left")
            ttk.Button(
                row, text="🏆 Atteint",
                command=lambda gid=g["id"]: self._mark_achieved(gid),
            ).pack(side="right", padx=2)

    def _add_goal(self) -> None:
        titre = self._entry_var.get().strip()
        if not titre:
            return
        cat = _pick_category(self)
        if cat is None:
            return
        db.create_goal(self.conn, titre, cat)
        self._entry_var.set("")
        self._refresh()

    def _mark_achieved(self, goal_id: int) -> None:
        if messagebox.askyesno(
            "Confirmation", "Marquer cet objectif comme atteint ?",
            parent=self,
        ):
            db.set_goal_status(self.conn, goal_id, "atteint")
            self._refresh()


class SyncPreviewDialog(tk.Toplevel):
    """Obsidian before/after preview with confirmation in the same window."""

    def __init__(self, parent: tk.BaseWidget, title: str, preview: str) -> None:
        super().__init__(parent)
        self.result = False
        self.title(title)
        self.geometry("780x560")
        self.minsize(560, 380)
        self.transient(parent)
        self.grab_set()

        ttk.Label(
            self,
            text="Vérifie l'aperçu avant/après avant d'appliquer au vault.",
            padding="8 8 8 4",
        ).pack(fill="x")

        text = scrolledtext.ScrolledText(
            self, wrap="word", font=("Menlo", 9), state="normal",
        )
        text.insert("1.0", preview)
        text.config(state="disabled")
        text.pack(fill="both", expand=True, padx=8, pady=4)

        buttons = ttk.Frame(self, padding="8")
        buttons.pack(fill="x")
        ttk.Button(
            buttons, text="Refuser", command=self._reject,
        ).pack(side="right", padx=4)
        ttk.Button(
            buttons, text="Appliquer au vault", command=self._accept,
        ).pack(side="right", padx=4)

        self.update_idletasks()
        _center_on(self, parent)

    def _accept(self) -> None:
        self.result = True
        self.destroy()

    def _reject(self) -> None:
        self.result = False
        self.destroy()


# ──────────────────────────────────────────────── main window

class MainWindow(tk.Tk):
    """Main PRIORIS window in local mode."""

    def __init__(self, cfg: dict, llm: LLMFacade | None = None) -> None:
        super().__init__()
        self.cfg = cfg
        self.language = normalize_language(cfg.get("ui", {}).get("language"))
        db_path = cfg.get("database", {}).get("path", "prioris.db")
        self.conn = db.connect(db_path)
        self.vault_path: str | None = cfg.get("obsidian", {}).get("vault_path") or None
        self.prioris_dir: str = cfg.get("obsidian", {}).get("prioris_dir", "PRIORIS")
        self.llm = llm or self._build_llm_facade()
        self._tasks: list = []
        self._base_status = ""
        self._llm_status_msg = "LLM : non testé"
        self._llm_ok = False

        self.title("PRIORIS — Mode local")
        self.geometry("740x540")
        self.minsize(520, 400)

        self._build_ui(db_path)
        self._refresh_tasks()
        self._start_warmup()

    def _build_llm_facade(self) -> LLMFacade:
        llm_cfg = LLMConfig.from_dict(self.cfg.get("llm", {}))
        client = None
        if llm_cfg.enabled:
            try:
                resolve(llm_cfg)
                client = ChatClient(llm_cfg)
            except ValueError as e:
                print(f"LLM désactivé — config invalide : {e}")
        return LLMFacade(
            client,
            log_fn=lambda t, m, ms, ok: db.log_llm_call(
                self.conn, t, m, ms, ok),
        )

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self, db_path: str) -> None:
        # Toolbar.
        toolbar = ttk.Frame(self, padding="6 4 6 0")
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="➕ Ajouter une tâche",
                   command=self.cmd_add).pack(side="left", padx=2)
        ttk.Button(toolbar, text="📅 Plan du jour",
                   command=self.cmd_today).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🎯 Objectifs",
                   command=self.cmd_goals).pack(side="left", padx=2)
        ttk.Button(toolbar, text="📥 Scan",
                   command=self.cmd_scan).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🔁 Sync Obsidian",
                   command=self.cmd_sync_obsidian).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🤖 LLM",
                   command=self.cmd_llm).pack(side="left", padx=2)
        ttk.Button(toolbar, text="📋 Liste",
                   command=self.cmd_list).pack(side="left", padx=2)
        ttk.Button(toolbar, text="🔄 Rafraîchir",
                   command=self._refresh_tasks).pack(side="right", padx=2)

        ttk.Separator(self).pack(fill="x")

        # Central area: task list on the left, output on the right.
        pane = ttk.PanedWindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=6, pady=6)

        # Left pane: task list.
        left = ttk.LabelFrame(pane, text="Tâches évaluées / planifiées")
        self._listbox = tk.Listbox(
            left, selectmode="single",
            font=("Menlo", 9), activestyle="dotbox",
        )
        sb_left = ttk.Scrollbar(left, orient="vertical",
                                  command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb_left.set)
        sb_left.pack(side="right", fill="y")
        self._listbox.pack(fill="both", expand=True)

        btn_row = ttk.Frame(left, padding="2 2")
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="✅ Marquer faite",
                   command=self.cmd_done).pack(side="left", padx=2)
        ttk.Button(btn_row, text="🔍 Pourquoi ?",
                   command=self.cmd_why).pack(side="left", padx=2)
        ttk.Button(btn_row, text="💬 Info / question",
                   command=self.cmd_task_info).pack(side="left", padx=2)

        pane.add(left, weight=1)

        # Right pane: output console.
        right = ttk.LabelFrame(pane, text="Résultat")
        self._output = scrolledtext.ScrolledText(
            right, state="disabled", wrap="word", font=("Menlo", 9),
        )
        self._output.pack(fill="both", expand=True)
        pane.add(right, weight=2)

        # Status bar.
        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", side="bottom")
        self._llm_icon_var = tk.StringVar(value="●")
        self._llm_text_var = tk.StringVar(value="LLM : non testé")
        self._llm_icon = ttk.Label(status_frame, textvariable=self._llm_icon_var,
                                   foreground="red", padding="4 2")
        self._llm_icon.pack(side="left")
        ttk.Label(status_frame, textvariable=self._llm_text_var,
                  padding="0 2").pack(side="left")
        self._status_var = tk.StringVar()
        ttk.Label(self, textvariable=self._status_var,
                  relief="sunken", anchor="w",
                  padding="4 2").pack(fill="x", side="bottom")
        self._set_status(f"Mode local · base : {db_path}")

    # ── helpers ──────────────────────────────────────────────────────

    def _set_status(self, msg: str) -> None:
        self._base_status = msg
        self._status_var.set(f"  {msg}")

    def _set_llm_status(self, ok: bool, msg: str) -> None:
        self._llm_ok = ok
        self._llm_status_msg = msg
        self._llm_icon.configure(foreground="green" if ok else "red")
        self._llm_text_var.set(msg)

    def _ensure_llm_ready(self) -> bool:
        if not self.llm or not self.llm.available:
            self._set_llm_status(False, "LLM : désactivé/offline")
            return False
        if self._llm_ok:
            return True
        self._set_status("LLM configuré mais pas prêt — tentative de démarrage...")
        self.config(cursor="watch")
        self.update_idletasks()
        ok, msg, path = llm_health.warm_up_with_retries(self.llm, attempts=3)
        self.config(cursor="")
        self._set_llm_status(ok, "LLM : prêt" if ok else f"LLM : KO/offline (voir {path})")
        self._set_status(msg if ok else f"{msg} · log : {path}")
        if not ok:
            messagebox.showwarning(
                "LLM KO/offline",
                f"{msg}\n\nLog LLM : {path}\n"
                "Les fonctions sans LLM restent disponibles.",
                parent=self,
            )
        return ok

    def _print(self, text: str) -> None:
        self._output.config(state="normal")
        self._output.insert("end", text + "\n\n" + ("─" * 40) + "\n\n")
        self._output.see("end")
        self._output.config(state="disabled")

    def _clear_output(self) -> None:
        self._output.config(state="normal")
        self._output.delete("1.0", "end")
        self._output.config(state="disabled")

    def _refresh_tasks(self) -> None:
        self._listbox.delete(0, "end")
        self._tasks = list(db.current_tasks(self.conn))
        for r in self._tasks:
            gem = "💎 " if r["pepite"] else ""
            line = (f"#{r['id']:>3} {r['priorite']} "
                    f"({r['score_global']:>4.0f})  {gem}{r['titre']}")
            self._listbox.insert("end", line)
        self._set_status(
            f"{len(self._tasks)} tâche(s) active(s) · "
            f"base : {self.cfg.get('database', {}).get('path', 'prioris.db')}"
        )

    def _start_warmup(self) -> None:
        llm_cfg = self.cfg.get("llm", {})
        if not self.llm or not self.llm.available:
            self._set_llm_status(False, "LLM : désactivé/offline")
            return
        if not llm_cfg.get("keep_warm", True):
            self._set_llm_status(True, "LLM : configuré (préchauffage désactivé)")
            return
        interval_s = float(llm_cfg.get("keep_warm_interval_min", 4)) * 60

        def loop() -> None:
            ok, msg, path = llm_health.warm_up_with_retries(self.llm, attempts=3)
            self.after(0, lambda: self._set_llm_status(
                ok, "LLM : prêt" if ok else f"LLM : KO/offline (voir {path})",
            ))
            self.after(0, lambda: self._set_status(msg if ok else f"{msg} · log : {path}"))
            while True:
                threading.Event().wait(interval_s)
                ok = self.llm.warm_up()
                if not ok:
                    err = getattr(self.llm, "last_error", "") or "échec sans détail"
                    path = llm_health.append_log(f"keep-warm KO : {err}")
                    self.after(0, lambda p=path: self._set_llm_status(
                        False, f"LLM : KO/offline (voir {p})"))
                else:
                    self.after(0, lambda: self._set_llm_status(True, "LLM : prêt"))

        threading.Thread(target=loop, daemon=True).start()

    def _selected_task_id(self) -> int | None:
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showinfo(
                "Sélection requise",
                "Sélectionne d'abord une tâche dans la liste.",
                parent=self,
            )
            return None
        return int(self._tasks[sel[0]]["id"])

    # ── commands ─────────────────────────────────────────────────────

    def cmd_add(self) -> None:
        """Add a task, then choose category and run the interview."""
        titre = simpledialog.askstring(
            "Nouvelle tâche", "Titre de la tâche :", parent=self)
        if not titre or not titre.strip():
            return
        titre = titre.strip()

        cat = _pick_category(self)
        if cat is None:
            return

        deadline_info = self._ask_deadline()
        if deadline_info is False:
            return
        deadline, deadline_days = deadline_info

        self._run_interview_for_new_task(titre, cat, deadline, deadline_days)

    def _ask_deadline(self, suggested: str | None = None) -> tuple[str | None, int | None] | bool:
        deadline = None
        deadline_days = None
        prompt = "Cette tâche a-t-elle une date limite de résolution ?"
        if suggested:
            prompt += f"\n\nDate détectée par le LLM : {suggested}\nTu peux confirmer ou modifier."
        if messagebox.askyesno(
            "Date limite",
            prompt,
            parent=self,
        ):
            date_str = simpledialog.askstring(
                "Date limite",
                "Quelle est la date limite ?\n(format AAAA-MM-JJ, ex. 2026-07-20)",
                initialvalue=suggested or "",
                parent=self,
            )
            if not date_str:
                return
            try:
                due = dt.date.fromisoformat(date_str.strip())
            except ValueError:
                messagebox.showwarning(
                    "Format invalide",
                    "Utilise le format AAAA-MM-JJ (ex. 2026-07-20).",
                    parent=self,
                )
                return
            deadline = due.isoformat()
            deadline_days = (due - dt.date.today()).days

        return deadline, deadline_days

    def _run_interview_for_new_task(
        self,
        titre: str,
        cat: str,
        deadline: str | None = None,
        deadline_days: int | None = None,
    ) -> None:
        goals = db.active_goals(self.conn)
        dlg = InterviewDialog(
            self, self.conn, titre, cat, goals=goals,
            deadline_days=deadline_days, deadline=deadline,
            vault_path=self.vault_path, prioris_dir=self.prioris_dir,
            llm=self.llm, language=self.language,
        )
        self.wait_window(dlg)

        if dlg.result_text:
            self._clear_output()
            self._print(dlg.result_text)
        self._refresh_tasks()

    def cmd_done(self) -> None:
        """Mark the selected task as done."""
        task_id = self._selected_task_id()
        if task_id is None:
            return
        task = self.conn.execute(
            "SELECT titre FROM tasks WHERE id=?", (task_id,)).fetchone()
        titre = task["titre"] if task else f"#{task_id}"
        if not messagebox.askyesno(
            "Confirmation",
            f"Marquer comme faite ?\n\n« {titre} »",
            parent=self,
        ):
            return
        db.set_task_status(self.conn, task_id, "faite")
        row = self.conn.execute(
            "SELECT estimation_min FROM tasks WHERE id=?", (task_id,)).fetchone()
        db.log_time(
            self.conn, task_id,
            (row["estimation_min"] if row else None) or 30,
            dt.date.today().isoformat(),
        )
        self._print(f"✅ Tâche #{task_id} « {titre} » marquée faite.")
        self._refresh_tasks()

    def cmd_why(self) -> None:
        """Show the full rationale for the selected task."""
        task_id = self._selected_task_id()
        if task_id is None:
            return
        self._clear_output()
        self._print(_why_text(self.conn, task_id))

    def cmd_task_info(self) -> None:
        """Add information/question and propose a confirmed revision."""
        note = simpledialog.askstring(
            "Information ou contrainte",
            "Ajoute une information, une contrainte ou une question sur cette tâche :",
            parent=self,
        )
        if not note or not note.strip():
            return
        task_id = self._selected_task_id_silent()
        if not self.llm or not self.llm.available:
            if task_id is None:
                messagebox.showinfo(
                    "Mode manuel",
                    "LLM indisponible : sélectionne une tâche puis saisis une correction.\n\n"
                    "Format : AXE=valeur raison\n"
                    "Exemple : BLK=4 Le client est maintenant bloqué\n"
                    "Axes : BLK CDR HOR IMP INA IRR ALN",
                    parent=self,
                )
                return
            self._handle_manual_task_info(task_id, note.strip())
            return
        if not self._ensure_llm_ready():
            return
        if task_id is None:
            self._handle_global_info(note.strip())
            return
        self._handle_task_info(task_id, note.strip())

    def _parse_manual_revision(self, text: str) -> tuple[str, int] | None:
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

    def _handle_manual_task_info(self, task_id: int, note: str) -> None:
        parsed = self._parse_manual_revision(note)
        if parsed is None:
            messagebox.showinfo(
                "Mode manuel",
                "LLM indisponible : indique explicitement l'axe à modifier.\n\n"
                "Format : AXE=valeur raison\n"
                "Exemple : BLK=4 Le client est maintenant bloqué\n"
                "Axes : BLK CDR HOR IMP INA IRR ALN",
                parent=self,
            )
            return
        try:
            proposal = task_revision.make_manual_proposal(
                self.conn, task_id, note, parsed[0], parsed[1])
        except ValueError as e:
            messagebox.showwarning("Correction invalide", str(e), parent=self)
            return
        if proposal is None:
            messagebox.showwarning(
                "Analyse impossible",
                f"{getattr(self.llm, 'last_error', '') or 'Tâche introuvable/non évaluée'}\n"
                "Teste le LLM avec le bouton LLM.",
                parent=self,
            )
            return
        text = task_revision.render_proposal(proposal)
        self._clear_output()
        self._print(text)
        if not proposal.has_changes:
            impact = task_impact.make_proposal(self.conn, note, self.llm)
            if impact is not None and not any(i.id == task_id for i in impact.impacted):
                self._print(
                    "Cette information ne modifie pas la tâche ciblée. "
                    "Je regarde si elle doit créer ou impacter autre chose."
                )
                self._show_impact_proposal(impact)
            return
        if messagebox.askyesno(
            "Confirmer la révision",
            text + "\n\nAppliquer cette nouvelle évaluation ?",
            parent=self,
        ):
            task_revision.apply_proposal(self.conn, proposal)
            self._print("\n✅ Révision appliquée. La priorité affichée est recalculée.")
            self._offer_obsidian_info_sync(proposal.task_id)
            self._refresh_tasks()

    def _selected_task_id_silent(self) -> int | None:
        sel = self._listbox.curselection()
        return int(self._tasks[sel[0]]["id"]) if sel else None

    def _handle_global_info(self, note: str) -> None:
        self._set_status("Recherche des tâches impactées...")
        self.config(cursor="watch")
        self.update_idletasks()
        proposal = task_impact.make_proposal(self.conn, note, self.llm)
        self.config(cursor="")
        self._set_status("Analyse terminée")
        if proposal is None:
            messagebox.showwarning(
                "Analyse impossible",
                f"{getattr(self.llm, 'last_error', '')}\nTeste le LLM avec le bouton LLM.",
                parent=self,
            )
            return
        self._show_impact_proposal(proposal)

    def _show_impact_proposal(self, proposal) -> None:
        text = task_impact.render_proposal(proposal)
        self._clear_output()
        self._print(text)
        if not proposal.has_impacted:
            if messagebox.askyesno(
                "Créer une tâche",
                f"Aucune tâche existante ne semble impactée.\n\n"
                f"Créer : « {proposal.new_task_title} » ?",
                parent=self,
            ):
                self._create_task_from_title(
                    proposal.new_task_title, proposal.suggested_deadline)
            return
        raw = simpledialog.askstring(
            "Tâches à analyser",
            "Ids à analyser, séparés par des virgules.\n"
            "Laisse vide pour créer une nouvelle tâche :",
            initialvalue=", ".join(str(i.id) for i in proposal.impacted),
            parent=self,
        )
        try:
            ids = _parse_task_ids(raw)
        except ValueError:
            messagebox.showwarning(
                "Ids invalides",
                "Utilise des ids numériques séparés par des virgules.\n"
                "Laisse vide pour créer une nouvelle tâche.",
                parent=self,
            )
            return
        if ids is None:
            if messagebox.askyesno(
                "Créer une tâche",
                f"Créer une nouvelle tâche : « {proposal.new_task_title} » ?",
                parent=self,
            ):
                self._create_task_from_title(
                    proposal.new_task_title, proposal.suggested_deadline)
            return
        for task_id in ids:
            self._handle_task_info(task_id, proposal.note)

    def _create_task_from_title(self, titre: str, suggested_deadline: str | None = None) -> None:
        if not titre.strip():
            return
        cat = _pick_category(self)
        if cat is None:
            return
        deadline_info = self._ask_deadline(suggested_deadline)
        if deadline_info is False:
            return
        deadline, deadline_days = deadline_info
        self._run_interview_for_new_task(
            titre.strip(), cat, deadline, deadline_days)

    def _handle_task_info(self, task_id: int, note: str) -> None:
        self._set_status("Analyse LLM de la tâche...")
        self.config(cursor="watch")
        self.update_idletasks()
        proposal = task_revision.make_proposal(
            self.conn, task_id, note, self.llm)
        self.config(cursor="")
        self._set_status("Analyse terminée")
        if proposal is None:
            messagebox.showwarning(
                "Tâche non évaluée",
                "Cette tâche est introuvable ou n'a pas encore d'évaluation.",
                parent=self,
            )
            return
        text = task_revision.render_proposal(proposal)
        self._clear_output()
        self._print(text)
        if not proposal.has_changes:
            impact = task_impact.make_proposal(self.conn, note, self.llm)
            if impact is not None and not any(i.id == task_id for i in impact.impacted):
                self._print(
                    "Cette information ne modifie pas la tâche ciblée. "
                    "Je regarde si elle doit créer ou impacter autre chose."
                )
                self._show_impact_proposal(impact)
            return
        if not messagebox.askyesno(
            "Confirmer la révision",
            text + "\n\nAppliquer cette nouvelle évaluation ?",
            parent=self,
        ):
            return
        task_revision.apply_proposal(self.conn, proposal)
        self._print("\n✅ Révision appliquée. La priorité affichée est recalculée.")
        self._offer_obsidian_info_sync(proposal.task_id)
        self._refresh_tasks()

    def _offer_obsidian_info_sync(self, task_id: int) -> None:
        if not self.vault_path:
            return
        proposal = info_sync.build_sync_proposal(
            self.conn, self.vault_path, self.prioris_dir, task_id)
        if proposal is None:
            return
        preview = info_sync.render_sync_preview(proposal)
        dlg = SyncPreviewDialog(self, "Synchroniser Obsidian ?", preview)
        self.wait_window(dlg)
        if not dlg.result:
            self._print("\nSynchronisation Obsidian refusée.")
            return
        info_sync.apply_sync_proposal(self.vault_path, proposal)
        self._print("\n✅ Synchronisation Obsidian appliquée.")

    def cmd_today(self) -> None:
        """Launch daily-plan generation."""
        dlg = TodayDialog(
            self, self.conn,
            vault_path=self.vault_path, prioris_dir=self.prioris_dir,
        )
        self.wait_window(dlg)
        if dlg.result_text:
            self._clear_output()
            self._print(dlg.result_text)
        self._refresh_tasks()

    def cmd_goals(self) -> None:
        """Manage life goals."""
        dlg = GoalsDialog(self, self.conn)
        self.wait_window(dlg)
        self._refresh_tasks()

    def cmd_list(self) -> None:
        """Show the current list, equivalent to /list."""
        rows = db.current_tasks(self.conn)
        if not rows:
            self._clear_output()
            self._print("Aucune tâche évaluée. Ajoute une tâche pour commencer.")
            return
        lines = [f"#{r['id']} {r['priorite']} ({r['score_global']:.0f}) "
                 f"{'💎 ' if r['pepite'] else ''}{r['titre']}"
                 for r in rows]
        self._clear_output()
        self._print("\n".join(lines))

    def cmd_llm(self) -> None:
        """Run local LLM diagnostics, equivalent to /llm."""
        if not self.llm:
            self._clear_output()
            self._print("❌ Façade LLM absente. Rappel : le LLM est optionnel.")
            return
        self._set_status("Test LLM en cours...")
        self.config(cursor="watch")
        self.update_idletasks()
        ready, ready_msg, log_path = llm_health.warm_up_with_retries(self.llm, attempts=3)
        ok, msg = self.llm.self_test() if ready else (False, f"{ready_msg} · log : {log_path}")
        self.config(cursor="")
        self._set_llm_status(ok, "LLM : prêt" if ok else "LLM : KO/offline")
        lines = [("✅ " if ok else "❌ ") + msg]
        stats = self.conn.execute(
            "SELECT type, COUNT(*) n, SUM(valide) ok, CAST(AVG(latence_ms) AS INT) avg_ms "
            "FROM llm_calls GROUP BY type ORDER BY MAX(created_at) DESC").fetchall()
        if stats:
            lines.append("Historique LLM :")
            for row in stats:
                lines.append(f"- {row['type']} : {row['ok'] or 0}/{row['n']} réussis · "
                             f"{row['avg_ms'] or 0} ms moyen")
        last_fail = self.conn.execute(
            "SELECT type, modele, latence_ms, created_at FROM llm_calls "
            "WHERE valide=0 ORDER BY created_at DESC, id DESC LIMIT 1").fetchone()
        if last_fail:
            lines.append(
                f"Dernier échec journalisé : {last_fail['type']} · "
                f"{last_fail['modele']} · {last_fail['latence_ms']} ms · "
                f"{last_fail['created_at']}")
        lines.append("Rappel : en cas de panne LLM, tout fonctionne en boutons.")
        self._clear_output()
        self._print("\n".join(lines))
        self._set_status("Diagnostic LLM terminé")

    def cmd_scan(self) -> None:
        """Scan the Obsidian vault and prioritize new tasks."""
        if not self.vault_path:
            messagebox.showinfo(
                "Vault non configuré",
                "Renseigne [obsidian] vault_path dans config.toml.",
                parent=self,
            )
            return
        self._set_status("Scan du vault en cours...")
        try:
            found = scan.find_unprioritized(self.vault_path, self.prioris_dir)
            marked = scan.find_marked(self.vault_path, self.prioris_dir)
        except OSError as e:
            messagebox.showerror("Vault inaccessible", str(e), parent=self)
            return

        sync = db.sync_from_vault_marks(
            self.conn, marked, dt.date.today().isoformat())
        lines: list[str] = [
            "Scan Obsidian terminé :",
            f"- {len(found)} ligne(s) de tâche non marquée(s) trouvée(s)",
            f"- {len(marked)} tâche(s) déjà marquée(s) PRIORIS trouvée(s)",
        ]
        if sync["done"] or sync["missing"]:
            lines.append("")
            lines.append("Synchronisation Obsidian -> PRIORIS :")
            lines += [f"✅ #{i} « {t[:50]} » cochée dans le vault -> faite"
                      for i, t in sync["done"]]
            lines += [f"❓ #{i} « {t[:50]} » introuvable dans le vault"
                      for i, t in sync["missing"]]

        fresh = [t for t in found
                 if not db.obsidian_task_known(self.conn, t.rel_path, t.titre)]
        deja = len(found) - len(fresh)
        if not fresh:
            lines.append("")
            lines.append(
                f"Aucune nouvelle tâche à prioriser ({deja} déjà connue(s)).")
            lines.append(
                "Rappel : /scan ignore les lignes déjà marquées 🎯P... et le dossier PRIORIS/.")
            lines.append(
                "Pour pousser les évaluations existantes vers Obsidian, utilise 🔁 Sync Obsidian.")
            self._clear_output()
            self._print("\n".join(lines))
            self._refresh_tasks()
            self._set_status("Scan terminé · aucune nouvelle tâche")
            return

        preview = "\n".join(f"• {t.titre[:60]} ({t.rel_path})" for t in fresh[:8])
        if len(fresh) > 8:
            preview += f"\n... et {len(fresh) - 8} autres"
        self._clear_output()
        self._print("\n".join(lines) + "\n\nNouvelles tâches à prioriser :\n" + preview)
        if not messagebox.askyesno(
            "Scan Obsidian",
            f"{len(fresh)} tâche(s) non priorisée(s) trouvée(s)"
            + (f" ({deja} déjà connues ignorées)" if deja else "")
            + " :\n\n"
            + preview
            + "\n\nLes prioriser une par une maintenant ?",
            parent=self,
        ):
            return

        processed = 0
        for vt in fresh:
            cat = _pick_category(self)
            if cat is None:
                break
            deadline_days = None
            if vt.due:
                try:
                    deadline_days = (
                        dt.date.fromisoformat(vt.due) - dt.date.today()).days
                except ValueError:
                    pass
            goals = db.active_goals(self.conn)
            dlg = InterviewDialog(
                self, self.conn, vt.titre, cat, goals=goals,
                deadline_days=deadline_days, deadline=vt.due,
                source="obsidian", obsidian_path=vt.rel_path,
                vault_path=self.vault_path, prioris_dir=self.prioris_dir,
                llm=self.llm, obsidian_task=vt, language=self.language,
            )
            self.wait_window(dlg)
            if dlg.result_text:
                processed += 1
                self._clear_output()
                self._print(dlg.result_text)
            else:
                break
        self._refresh_tasks()
        self._set_status(f"Scan terminé · {processed} tâche(s) traitée(s)")

    def cmd_sync_obsidian(self) -> None:
        """Propose a full PRIORIS-to-Obsidian synchronization."""
        if not self.vault_path:
            messagebox.showinfo(
                "Vault non configuré",
                "Renseigne [obsidian] vault_path dans config.toml.",
                parent=self,
            )
            return
        proposal = info_sync.build_full_sync_proposal(
            self.conn, self.vault_path, self.prioris_dir)
        if proposal is None:
            messagebox.showinfo(
                "Synchronisation Obsidian",
                "Aucune modification Obsidian à proposer.",
                parent=self,
            )
            return
        preview = info_sync.render_sync_preview(proposal, max_chars=12000)
        self._clear_output()
        self._print(preview)
        dlg = SyncPreviewDialog(self, "Synchronisation Obsidian complète", preview)
        self.wait_window(dlg)
        if not dlg.result:
            self._print("\nSynchronisation Obsidian refusée.")
            return
        info_sync.apply_sync_proposal(self.vault_path, proposal)
        self._print("\n✅ Synchronisation Obsidian complète appliquée.")
        self._set_status("Synchronisation Obsidian terminée")
