"""Keep the documented decision model aligned with executable constants."""
from pathlib import Path

from prioris.core.axes import AXIS_MAX, AXIS_QUESTIONS, Axis
from prioris.core.planner import (BONUS_PEPITE, DEADLINE_BONUS, MAX_MAJEURES,
                                  SEUIL_ENTAMER_G, SEUIL_MAJEURE_MIN,
                                  TRANCHE_ENTAMER_MIN)
from prioris.core.scoring import (SEUIL_IMPORTANT, SEUIL_URGENT, W_I, W_U)


ROOT = Path(__file__).parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_exact_normalized_formula_is_in_all_documentation_levels():
    """Every public document must show normalized, reconstructible formulas."""
    urgency = (
        f"U = {W_U[Axis.BLK]}×BLK/{AXIS_MAX[Axis.BLK]} + "
        f"{W_U[Axis.CDR]}×CDR/{AXIS_MAX[Axis.CDR]} + "
        f"{W_U[Axis.HOR]}×HOR/{AXIS_MAX[Axis.HOR]}"
    )
    importance = (
        f"I = {W_I[Axis.IMP]}×IMP/{AXIS_MAX[Axis.IMP]} + "
        f"{W_I[Axis.INA]}×INA/{AXIS_MAX[Axis.INA]} + "
        f"{W_I[Axis.IRR]}×IRR/{AXIS_MAX[Axis.IRR]} + "
        f"{W_I[Axis.ALN]}×ALN/{AXIS_MAX[Axis.ALN]}"
    )
    for document in ("README.md", "README.en.md", "GUIDE.md", "GUIDE.en.md",
                     "rust/README.md"):
        text = _read(document).replace(" ", "")
        assert urgency.replace(" ", "") in text, document
        assert importance.replace(" ", "") in text, document


def test_french_guide_covers_every_axis_question_scale_and_threshold():
    """The canonical guide must map every axis to its executable contract."""
    guide = _read("GUIDE.md")
    for axis in Axis:
        assert f"`{axis.value}`" in guide
        assert f"`0..{AXIS_MAX[axis]}`" in guide
        assert AXIS_QUESTIONS[axis] in guide
    assert f"`U >= {SEUIL_URGENT}`" in guide
    assert f"`I >= {SEUIL_IMPORTANT}`" in guide


def test_french_guide_covers_all_planner_constants():
    """Planner bonuses and guardrails must not silently drift from the guide."""
    guide = _read("GUIDE.md")
    bonuses = "| Bonus | " + " | ".join(f"+{bonus}" for _, bonus in DEADLINE_BONUS) + " | 0 |"
    assert bonuses in guide
    assert f"bonus pépite vaut `+{BONUS_PEPITE}`" in guide
    assert f"au maximum {MAX_MAJEURES}" in guide
    assert f"d'au moins {SEUIL_MAJEURE_MIN} minutes" in guide
    assert f"`G >= {SEUIL_ENTAMER_G}`" in guide
    assert f"au moins {TRANCHE_ENTAMER_MIN} minutes" in guide
