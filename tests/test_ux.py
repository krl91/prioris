"""Tests UX : légende des quadrants cohérente, image de la matrice présente."""
from pathlib import Path

from prioris.llm.facade import LLMFacade

from prioris.core.axes import PRIORITE_LABELS, QUADRANT_INFO, Priorite
from prioris.core.scoring import explain, score
from tests.test_scoring import axes

from prioris.core.axes import Estimation


def test_quadrant_info_complet():
    assert set(QUADRANT_INFO) == {"Q1", "Q2", "Q3", "Q4"}
    assert {i["p"] for i in QUADRANT_INFO.values()} == {"P1", "P2", "P3", "P4"}
    assert all(i["nom"] and i["action"] for i in QUADRANT_INFO.values())


def test_labels_boutons_pour_chaque_priorite():
    for p in Priorite:
        assert p.value in PRIORITE_LABELS[p]


def test_explain_rappelle_le_quadrant():
    r = score(axes(blk=0, cdr=1, hor=3, imp=1, ina=1, irr=0, aln=0),
              estimation=Estimation.H1_2)
    texte = explain(r)
    assert "Ni urgent ni important" in texte
    assert "reporter ou abandonner" in texte


def test_image_matrice_presente():
    png = Path(__file__).parent.parent / "prioris" / "bot" / "assets" / "eisenhower.png"
    assert png.exists() and png.stat().st_size > 10_000
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_pas_de_questions_llm_non_interactives():
    root = Path(__file__).parent.parent
    assert not hasattr(LLMFacade, "quadrant_questions")
    for rel in ("prioris/gui/app.py", "prioris/bot/handlers.py"):
        source = (root / rel).read_text(encoding="utf-8")
        assert "quadrant_questions" not in source
        assert "Questions pour situer le quadrant" not in source


def test_challenges_places_apres_entretien_factuel():
    root = Path(__file__).parent.parent
    gui = (root / "prioris/gui/app.py").read_text(encoding="utf-8")
    bot = (root / "prioris/bot/handlers.py").read_text(encoding="utf-8")

    gui_flow = gui[gui.index("    def _show_next(self)"):
                   gui.index("    def _start_subjective_challenge")]
    assert gui_flow.index("itv.next_question") < gui_flow.index(
        "self._show_challenge_question")

    bot_flow = bot[bot.index("async def _ask_next"):
                   bot.index("async def _finish_interview")]
    assert bot_flow.index("itv.next_question") < bot_flow.index(
        "_ask_challenge_question")
