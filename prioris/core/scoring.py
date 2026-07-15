"""Deterministic scoring engine. Pure function: same inputs, same output.

The LLM has no role here: this module imports neither llm/, bot/, store/ nor
any network client. Enforced by tests/test_architecture.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .axes import (AXIS_MAX, AXIS_MEDIAN, ESTIMATION_MIN, QUADRANT_INFO,
                   Axis, Estimation, Incertitude, Priorite)

VERSION_ALGO = 1

# Weights, on a 100-point basis.
W_U = {Axis.BLK: 30, Axis.CDR: 40, Axis.HOR: 30}
W_I = {Axis.IMP: 35, Axis.INA: 25, Axis.IRR: 20, Axis.ALN: 20}
SEUIL_URGENT = 55
SEUIL_IMPORTANT = 50
POIDS_I, POIDS_U = 0.6, 0.4

# High-leverage small task threshold.
PEPITE_I_MIN = 45
PEPITE_EST_MAX_MIN = 60


@dataclass(frozen=True)
class ScoreResult:
    urgence: float
    importance: float
    global_: float
    quadrant: str            # Q1..Q4
    priorite: Priorite
    provisoire: bool
    pepite: bool
    levier: float            # importance per estimated hour
    justification: dict = field(compare=False)

    def as_tuple(self) -> tuple:
        return (round(self.urgence, 1), round(self.importance, 1),
                round(self.global_, 1), self.quadrant, self.priorite.value)


def _apply_uncertainty(axes: dict[Axis, int],
                       incertitudes: dict[Axis, Incertitude]) -> tuple[dict[Axis, int], list[Axis]]:
    """Uncertainty dampener: NE_SAIT_PAS falls back to axis median."""
    adjusted = dict(axes)
    replaced: list[Axis] = []
    for axis, inc in incertitudes.items():
        if inc == Incertitude.NE_SAIT_PAS and axis in adjusted:
            adjusted[axis] = AXIS_MEDIAN[axis]
            replaced.append(axis)
    return adjusted, replaced


def score(axes: dict[Axis, int],
          estimation: Estimation = Estimation.INCONNUE,
          deadline_days: int | None = None,
          incertitudes: dict[Axis, Incertitude] | None = None,
          mode: str = "complet",
          axes_par_defaut: set[Axis] | None = None,
          subjective: Priorite | None = None) -> ScoreResult:
    """Compute U, I, G, quadrant and P1-P4 with self-contained rationale."""
    for axis, value in axes.items():
        if not 0 <= value <= AXIS_MAX[axis]:
            raise ValueError(f"{axis.value}={value} hors échelle 0..{AXIS_MAX[axis]}")
    missing = set(Axis) - set(axes)
    if missing:
        raise ValueError(f"Axes manquants : {sorted(a.value for a in missing)}")

    incertitudes = incertitudes or {}
    axes_par_defaut = axes_par_defaut or set()
    values, replaced = _apply_uncertainty(axes, incertitudes)
    provisoire = bool(replaced) or estimation == Estimation.INCONNUE

    termes_u = {a: w * values[a] / AXIS_MAX[a] for a, w in W_U.items()}
    termes_i = {a: w * values[a] / AXIS_MAX[a] for a, w in W_I.items()}
    urgence = sum(termes_u.values())
    importance = sum(termes_i.values())

    # Deterministic adjustments, in this order.
    ajustements: list[dict] = []
    if deadline_days is not None and deadline_days <= 7 and values[Axis.CDR] == 4:
        if urgence < 70:
            ajustements.append({"regle": "plancher_deadline", "avant": urgence, "apres": 70.0})
        urgence = max(urgence, 70.0)
    if values[Axis.IRR] == 3 and values[Axis.INA] >= 3:
        if importance < 70:
            ajustements.append({"regle": "plancher_irreversibilite", "avant": importance, "apres": 70.0})
        importance = max(importance, 70.0)
    if values[Axis.ALN] == 3:
        if importance < 55:
            ajustements.append({"regle": "plancher_objectifs", "avant": importance, "apres": 55.0})
        importance = max(importance, 55.0)

    global_ = POIDS_I * importance + POIDS_U * urgence

    urgent = urgence >= SEUIL_URGENT
    important = importance >= SEUIL_IMPORTANT
    quadrant = "Q1" if urgent and important else \
               "Q2" if important else \
               "Q3" if urgent else "Q4"
    priorite = {"Q1": Priorite.P1, "Q2": Priorite.P2,
                "Q3": Priorite.P3, "Q4": Priorite.P4}[quadrant]

    est_min = ESTIMATION_MIN[estimation]
    pepite = (importance >= PEPITE_I_MIN and est_min <= PEPITE_EST_MAX_MIN
              and estimation != Estimation.INCONNUE)
    levier = importance / max(est_min / 60.0, 0.25)

    justification = {
        "version_algo": VERSION_ALGO,
        "mode": mode,
        "axes": {a.value: {"valeur": values[a],
                           "brut": axes[a],
                           "defaut": a in axes_par_defaut,
                           "incertitude_amortie": a in replaced}
                 for a in Axis},
        "ponderations": {"U": {a.value: w for a, w in W_U.items()},
                         "I": {a.value: w for a, w in W_I.items()}},
        "calculs": {
            "U": {"termes": {a.value: round(t, 2) for a, t in termes_u.items()},
                  "total": round(urgence, 2)},
            "I": {"termes": {a.value: round(t, 2) for a, t in termes_i.items()},
                  "total": round(importance, 2)},
            "G": {"formule": f"{POIDS_I}*I + {POIDS_U}*U", "total": round(global_, 2)},
        },
        "ajustements": ajustements,
        "seuils": {"urgent": SEUIL_URGENT, "important": SEUIL_IMPORTANT},
        "quadrant": quadrant,
        "priorite": priorite.value,
        "subjective": subjective.value if subjective else None,
        "ecart_subjectif": (priorite.niveau - subjective.niveau) if subjective else None,
        "pepite": pepite,
        "levier_par_h": round(levier, 1),
        "provisoire": provisoire,
    }
    return ScoreResult(urgence, importance, global_, quadrant, priorite,
                       provisoire, pepite, levier, justification)


def explain(result: ScoreResult) -> str:
    """Text rendering for /why, without any LLM."""
    j = result.justification
    q = QUADRANT_INFO[j["quadrant"]]
    lines = [f"Priorité {j['priorite']} {q['emoji']} — {q['nom']} → {q['action']}",
             f"Score {j['calculs']['G']['total']}/100",
             f"Urgence {j['calculs']['U']['total']} (seuil {j['seuils']['urgent']}) · "
             f"Importance {j['calculs']['I']['total']} (seuil {j['seuils']['important']})"]
    for bloc in ("U", "I"):
        termes = ", ".join(f"{k}→{v}" for k, v in j["calculs"][bloc]["termes"].items())
        lines.append(f"  {bloc} = {termes}")
    for adj in j["ajustements"]:
        lines.append(f"  ajustement {adj['regle']} : {adj['avant']:.1f} → {adj['apres']:.1f}")
    if j["ecart_subjectif"] is not None and j["subjective"]:
        lines.append(f"Ton instinct : {j['subjective']} (écart {j['ecart_subjectif']:+d})")
    if j["pepite"]:
        lines.append(f"💎 Pépite — levier {j['levier_par_h']} pts d'importance/heure")
    if j["provisoire"]:
        lines.append("⚠️ Évaluation provisoire (incertitude ou estimation inconnue)")
    return "\n".join(lines)
