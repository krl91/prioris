"""Tests du mode GUI local.

Ces tests couvrent :
- la détection du mode (token vide → GUI, token renseigné → Telegram)
- les fonctions utilitaires de l'interface (options, texte justification)
- le flux d'entretien complet en mode local (sans ouvrir de fenêtre)

Aucun test n'instancie de widget tkinter : seules les fonctions pures et la
logique de routage sont testées, ce qui garantit l'exécution en environnement
sans affichage (CI/CD).
"""
import json
import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("tkinter")

from prioris.bot.main import _needs_gui
from prioris.core.axes import (AXIS_LABELS, ESTIMATION_MIN, Axis, Effort,
                                 Estimation, Incertitude, Priorite)
from prioris.core.interview import Q, Session, answer, final_axes, next_question
from prioris.core import scoring
from prioris.gui.app import (CATEGORIES, QUESTION_TEXT, SyncPreviewDialog, _category_choices,
                             _category_label,
                             _options, _parse_task_ids, _why_text)
from prioris.i18n import normalize_language, options as i18n_options, question_text
from prioris.store import db


# ─────────────────────────────────── détection du mode (routage)

class TestNeedsGui:
    def test_token_vide_active_gui(self):
        assert _needs_gui({"telegram": {"token": ""}}) is True

    def test_token_absent_active_gui(self):
        assert _needs_gui({}) is True

    def test_section_telegram_absente_active_gui(self):
        assert _needs_gui({"database": {"path": "prioris.db"}}) is True

    def test_token_espaces_active_gui(self):
        assert _needs_gui({"telegram": {"token": "   "}}) is True

    def test_token_renseigne_desactive_gui(self):
        assert _needs_gui({"telegram": {"token": "123456:ABC"}}) is False

    def test_token_realiste_desactive_gui(self):
        token = "1234567890:AAExEmPlEtOkEnAABBCCDDEEFF"
        assert _needs_gui({"telegram": {"token": token}}) is False


# ─────────────────────────────────── _options : cohérence avec handlers.py

class TestOptions:
    def test_subjective_quatre_priorites(self):
        opts = _options(Q.SUBJECTIVE)
        assert len(opts) == 4
        vals = [v for _, v in opts]
        assert set(vals) == {"P1", "P2", "P3", "P4"}

    def test_estimation_sept_valeurs(self):
        opts = _options(Q.ESTIMATION)
        assert len(opts) == 7
        names = [v for _, v in opts]
        assert "INCONNUE" in names
        assert "LT15" in names

    def test_effort_trois_valeurs(self):
        opts = _options(Q.EFFORT)
        assert len(opts) == 3
        vals = [v for _, v in opts]
        assert vals == ["1", "2", "3"]

    def test_demandeur_quatre_valeurs(self):
        opts = _options(Q.DEMANDEUR)
        assert len(opts) == 4
        vals = [v for _, v in opts]
        assert "moi" in vals and "manager" in vals

    def test_visibilite_pression_zero_a_trois(self):
        for q in (Q.VISIBILITE, Q.PRESSION):
            opts = _options(q)
            assert len(opts) == 4
            vals = [v for _, v in opts]
            assert vals == ["0", "1", "2", "3"]

    def test_axes_incluent_je_ne_sais_pas(self):
        """Toutes les questions d'axe doivent avoir l'option « Je ne sais pas »."""
        axis_questions = [
            Q.INACTION, Q.BLOCAGE, Q.CDR, Q.OBJECTIF,
            Q.IMPACT, Q.HORIZON, Q.IRREVERSIBILITE,
        ]
        for q in axis_questions:
            opts = _options(q)
            vals = [v for _, v in opts]
            assert "?" in vals, f"{q} devrait avoir « Je ne sais pas »"

    def test_axes_labels_correspondent_a_axes_py(self):
        """Les labels de l'UI doivent correspondre à AXIS_LABELS du core."""
        q = Q.INACTION
        opts = _options(q)
        expected_labels = AXIS_LABELS[Axis.INA]
        for i, (lbl, val) in enumerate(opts[:-1]):  # sauf "Je ne sais pas"
            assert lbl == expected_labels[i]
            assert val == str(i)


# ─────────────────────────────────── QUESTION_TEXT : couverture complète

class TestQuestionText:
    def test_toutes_les_questions_standard_ont_un_texte(self):
        standard_qs = [
            Q.SUBJECTIVE, Q.INACTION, Q.BLOCAGE, Q.CDR, Q.OBJECTIF,
            Q.ESTIMATION, Q.IMPACT, Q.HORIZON, Q.IRREVERSIBILITE,
            Q.EFFORT, Q.DEMANDEUR, Q.VISIBILITE, Q.PRESSION,
        ]
        for q in standard_qs:
            assert q in QUESTION_TEXT, f"Question {q} absente de QUESTION_TEXT"
            assert QUESTION_TEXT[q], f"Texte vide pour {q}"

    def test_textes_non_vides(self):
        for q, txt in QUESTION_TEXT.items():
            assert len(txt) > 5, f"Texte trop court pour {q}: {txt!r}"


class TestI18n:
    def test_francais_par_defaut(self):
        assert normalize_language(None) == "fr"
        assert normalize_language("unknown") == "fr"
        assert "Instinctivement" in question_text(Q.SUBJECTIVE)

    def test_questions_et_options_anglaises(self):
        assert question_text(Q.SUBJECTIVE, "en").startswith("Instinctively")
        opts = i18n_options(Q.DEMANDEUR, "en")
        assert ("Me", "moi") in opts
        assert ("Client", "client") in opts
        axis_opts = i18n_options(Q.INACTION, "en")
        assert axis_opts[0] == ("Nothing at all", "0")
        assert axis_opts[-1] == ("🤷 I don't know", "?")


# ─────────────────────────────────── CATEGORIES

def test_categories_non_vide():
    assert len(CATEGORIES) >= 5


def test_categories_contiennent_travail_et_perso():
    assert "travail" in CATEGORIES
    assert "perso" in CATEGORIES


def test_categorie_ia_affichee_en_majuscules():
    assert _category_label("ia") == "IA"
    assert _category_label("travail") == "Travail"


def test_categories_gui_lit_les_categories_personnalisees(tmp_path):
    conn = db.connect(tmp_path / "prioris.db")
    code = db.create_category(conn, "Maison")
    assert (code, "Maison") in _category_choices(conn)


def test_dialogue_sync_preview_existe():
    assert SyncPreviewDialog.__name__ == "SyncPreviewDialog"


def test_parse_task_ids_vide_signifie_nouvelle_tache():
    assert _parse_task_ids("") is None
    assert _parse_task_ids("   ") is None


def test_parse_task_ids_annulation_ne_cree_rien():
    assert _parse_task_ids(None) == []


def test_parse_task_ids_liste():
    assert _parse_task_ids("12, 15,18") == [12, 15, 18]


# ─────────────────────────────────── flux d'entretien (sans GUI, sans DB)

class TestInterviewFluxLocal:
    """Vérifie que le flux d'entretien express complet peut être parcouru
    en mode local en utilisant core/ directement (comme app.py le fait)."""

    def _run_express(self) -> scoring.ScoreResult:
        """Simule un entretien express minimal : toutes les réponses à la médiane."""
        s = Session(seed=42)
        answers = {
            Q.SUBJECTIVE:  Priorite.P2.value,
            Q.IMPACT:      2,
            Q.INACTION:    2,
            Q.BLOCAGE:     2,
            Q.CDR:         2,
            Q.OBJECTIF:    0,
            Q.ESTIMATION:  Estimation.H1_2.name,
        }
        q, s = next_question(s)
        while q is not None and q not in (Q.CLARIFICATION, Q.MIROIR):
            raw = answers.get(q)
            if raw is None:
                break
            value = (
                raw if q in (Q.SUBJECTIVE,)
                else Estimation[raw] if q == Q.ESTIMATION
                else int(raw)
            )
            s = answer(s, q, value)
            q, s = next_question(s)

        axes, par_defaut = final_axes(s)
        return scoring.score(
            axes,
            estimation=s.estimation or Estimation.INCONNUE,
            deadline_days=s.deadline_days,
            incertitudes=s.incertitudes,
            mode=s.mode,
            axes_par_defaut=par_defaut,
            subjective=s.subjective,
        )

    def test_flux_express_produit_un_score(self):
        result = self._run_express()
        assert 0 <= result.global_ <= 100

    def test_flux_express_produit_une_priorite_valide(self):
        result = self._run_express()
        assert result.priorite in (Priorite.P1, Priorite.P2,
                                    Priorite.P3, Priorite.P4)

    def test_flux_express_produit_justification(self):
        result = self._run_express()
        j = result.justification
        assert "version_algo" in j
        assert "axes" in j
        assert "priorite" in j


# ─────────────────────────────────── _why_text avec base réelle

@pytest.fixture()
def tmp_conn(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    yield conn
    conn.close()


def test_why_text_sans_evaluation(tmp_conn):
    task_id = db.create_task(tmp_conn, "Tâche sans éval", "travail")
    texte = _why_text(tmp_conn, task_id)
    assert "évaluation" in texte.lower()


def test_why_text_avec_evaluation(tmp_conn):
    from prioris.core.axes import Axis, Effort, Estimation, Priorite
    from prioris.core import interview as itv
    from prioris.core.interview import Q

    titre = "Tâche test why"
    task_id = db.create_task(tmp_conn, titre, "travail")

    # Entretien minimal
    s = Session(seed=task_id)
    for q, raw in [
        (Q.SUBJECTIVE, Priorite.P2.value),
        (Q.IMPACT, 1),
        (Q.INACTION, 1),
        (Q.BLOCAGE, 1),
        (Q.CDR, 1),
        (Q.OBJECTIF, 0),
        (Q.ESTIMATION, Estimation.M30_60.name),
    ]:
        value = (raw if q == Q.SUBJECTIVE
                 else Estimation[raw] if q == Q.ESTIMATION
                 else int(raw))
        s = itv.answer(s, q, value)

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
    interview_id = db.create_interview(tmp_conn, task_id, s.mode)
    db.finish_interview(tmp_conn, interview_id, s.mode)
    db.update_task_planning_attrs(
        tmp_conn, task_id,
        (s.estimation or Estimation.INCONNUE).value,
        ESTIMATION_MIN[s.estimation or Estimation.INCONNUE],
        s.effort.value,
    )
    db.save_evaluation(tmp_conn, task_id, interview_id, result,
                        s.subjective.value if s.subjective else None)

    texte = _why_text(tmp_conn, task_id)
    assert titre in texte
    assert "P" in texte          # priorite
    assert "Score" in texte or "G=" in texte


# ─────────────────────────────────── architecture : gui/ n'importe pas bot/

def test_gui_ninterporte_pas_bot():
    """Le module GUI ne doit pas dépendre du module bot/ ni de telegram."""
    import re
    gui_dir = Path(__file__).parent.parent / "prioris" / "gui"
    for py in gui_dir.glob("*.py"):
        source = py.read_text(encoding="utf-8")
        # Vérifie uniquement les lignes d'import réelles (pas les docstrings/commentaires)
        import_lines = [
            line for line in source.splitlines()
            if re.match(r"\s*(import|from)\s", line)
        ]
        for line in import_lines:
            assert not re.search(r"prioris\.bot", line), \
                f"{py.name} importe prioris.bot — interdit : {line.strip()}"
            assert not re.search(r"\btelegram\b", line), \
                f"{py.name} importe telegram — interdit : {line.strip()}"


def test_gui_ninterporte_pas_core_directement():
    """gui/ peut importer core/ et store/ mais pas bot/."""
    # Ce test vérifie surtout l'absence de dépendances circulaires.
    import prioris.gui.app  # noqa: F401  — doit s'importer sans erreur
