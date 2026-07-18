"""Deterministic scoring engine. Pure function: same inputs, same output.

The LLM has no role here: this module imports neither llm/, bot/, store/ nor
any network client. Enforced by tests/test_architecture.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .axes import (AXIS_MAX, AXIS_MEDIAN, ESTIMATION_MIN, QUADRANT_INFO,
                   Axis, Estimation, Incertitude, Priorite)

VERSION_ALGO = 2

# Weights, on a 100-point basis.
W_U = {Axis.BLK: 30, Axis.CDR: 40, Axis.HOR: 30}
W_I = {Axis.IMP: 35, Axis.INA: 25, Axis.IRR: 20, Axis.ALN: 20}
SEUIL_URGENT = 55
SEUIL_IMPORTANT = 50
POIDS_I, POIDS_U = 0.6, 0.4

# High-leverage small task threshold.
PEPITE_I_MIN = SEUIL_IMPORTANT
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
    robuste: bool
    quadrants_possibles: tuple[str, ...]
    axe_pivot: str | None
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


def _score_pair(values: dict[Axis, int], deadline_days: int | None,
                record: bool = False) -> tuple[float, float, list[dict]]:
    """Return adjusted U/I scores for one point in the uncertainty space."""
    urgence = sum(weight * values[axis] / AXIS_MAX[axis]
                  for axis, weight in W_U.items())
    importance = sum(weight * values[axis] / AXIS_MAX[axis]
                     for axis, weight in W_I.items())
    ajustements: list[dict] = []

    def apply_floor(name: str, current: float, floor: float) -> float:
        if record and current < floor:
            ajustements.append({"regle": name, "avant": current, "apres": floor})
        return max(current, floor)

    if deadline_days is not None and deadline_days <= 7 and values[Axis.CDR] == 4:
        urgence = apply_floor("plancher_deadline", urgence, 70.0)
    if values[Axis.IRR] == 3 and values[Axis.INA] >= 3:
        importance = apply_floor("plancher_irreversibilite", importance, 70.0)
    if (values[Axis.ALN] == 3
            and (values[Axis.IMP] >= 2 or values[Axis.INA] >= 2)):
        importance = apply_floor("plancher_objectifs", importance, 55.0)
    elif record and values[Axis.ALN] == 3:
        ajustements.append({
            "regle": "garde_fou_objectifs",
            "motif": "ALN seul ne suffit pas sans impact ou coût d'inaction",
        })
    return urgence, importance, ajustements


def _uncertainty_ranges(values: dict[Axis, int],
                        incertitudes: dict[Axis, Incertitude],
                        axes_par_defaut: set[Axis]) -> dict[Axis, tuple[int, int]]:
    """Build auditable value intervals used for quadrant robustness."""
    ranges: dict[Axis, tuple[int, int]] = {}
    for axis in Axis:
        value = values[axis]
        if axis == Axis.IMP and axis in axes_par_defaut:
            ranges[axis] = (0, AXIS_MAX[axis])
        elif incertitudes.get(axis) == Incertitude.NE_SAIT_PAS:
            median = AXIS_MEDIAN[axis]
            ranges[axis] = (max(0, median - 1), min(AXIS_MAX[axis], median + 1))
        elif incertitudes.get(axis) == Incertitude.HESITANT:
            ranges[axis] = (max(0, value - 1), min(AXIS_MAX[axis], value + 1))
        else:
            ranges[axis] = (value, value)
    return ranges


def _quadrants_for_bounds(u_min: float, u_max: float,
                          i_min: float, i_max: float) -> tuple[str, ...]:
    urgent_states = ([False] if u_max < SEUIL_URGENT else
                     [True] if u_min >= SEUIL_URGENT else [False, True])
    important_states = ([False] if i_max < SEUIL_IMPORTANT else
                        [True] if i_min >= SEUIL_IMPORTANT else [False, True])
    order = ("Q1", "Q2", "Q3", "Q4")
    found = set()
    for urgent in urgent_states:
        for important in important_states:
            found.add("Q1" if urgent and important else
                      "Q2" if important else "Q3" if urgent else "Q4")
    return tuple(q for q in order if q in found)


def _pivot_axis(ranges: dict[Axis, tuple[int, int]], u_crosses: bool,
                i_crosses: bool) -> str | None:
    candidates: list[tuple[float, Axis]] = []
    if u_crosses:
        candidates.extend((W_U[axis] * (hi - lo) / AXIS_MAX[axis], axis)
                          for axis, (lo, hi) in ranges.items()
                          if axis in W_U and hi > lo)
    if i_crosses:
        candidates.extend((W_I[axis] * (hi - lo) / AXIS_MAX[axis], axis)
                          for axis, (lo, hi) in ranges.items()
                          if axis in W_I and hi > lo)
    return max(candidates, default=(0.0, None), key=lambda item: item[0])[1].value \
        if candidates else None


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
    provisoire = (bool(replaced) or estimation == Estimation.INCONNUE
                  or bool(axes_par_defaut & {Axis.IMP}))

    termes_u = {a: w * values[a] / AXIS_MAX[a] for a, w in W_U.items()}
    termes_i = {a: w * values[a] / AXIS_MAX[a] for a, w in W_I.items()}
    urgence, importance, ajustements = _score_pair(values, deadline_days, record=True)

    ranges = _uncertainty_ranges(values, incertitudes, axes_par_defaut)
    lower = {axis: bounds[0] for axis, bounds in ranges.items()}
    upper = {axis: bounds[1] for axis, bounds in ranges.items()}
    u_min, i_min, _ = _score_pair(lower, deadline_days)
    u_max, i_max, _ = _score_pair(upper, deadline_days)
    quadrants_possibles = _quadrants_for_bounds(u_min, u_max, i_min, i_max)
    robuste = len(quadrants_possibles) == 1
    u_crosses = u_min < SEUIL_URGENT <= u_max
    i_crosses = i_min < SEUIL_IMPORTANT <= i_max
    axe_pivot = _pivot_axis(ranges, u_crosses, i_crosses)
    provisoire = provisoire or not robuste

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
        "robustesse": {
            "robuste": robuste,
            "U_intervalle": [round(u_min, 2), round(u_max, 2)],
            "I_intervalle": [round(i_min, 2), round(i_max, 2)],
            "quadrants_possibles": list(quadrants_possibles),
            "axe_pivot": axe_pivot,
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
                       provisoire, pepite, levier, robuste,
                       quadrants_possibles, axe_pivot, justification)


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
        if "avant" in adj and "apres" in adj:
            lines.append(
                f"  ajustement {adj['regle']} : "
                f"{adj['avant']:.1f} → {adj['apres']:.1f}")
        else:
            lines.append(f"  {adj['regle']} : {adj.get('motif', '')}".rstrip())
    if j["ecart_subjectif"] is not None and j["subjective"]:
        lines.append(f"Ton instinct : {j['subjective']} (écart {j['ecart_subjectif']:+d})")
    if j["pepite"]:
        lines.append(f"💎 Pépite — levier {j['levier_par_h']} pts d'importance/heure")
    robustesse = j["robustesse"]
    if robustesse["robuste"]:
        lines.append(f"Quadrant robuste : {robustesse['quadrants_possibles'][0]}")
    else:
        pivot = f" · axe pivot {robustesse['axe_pivot']}" if robustesse["axe_pivot"] else ""
        lines.append("Quadrant sensible : "
                     f"{' / '.join(robustesse['quadrants_possibles'])}{pivot}")
        lines.append(f"  U ∈ {robustesse['U_intervalle']} · I ∈ {robustesse['I_intervalle']}")
    if j["provisoire"]:
        lines.append("⚠️ Évaluation provisoire (incertitude ou estimation inconnue)")
    return "\n".join(lines)
