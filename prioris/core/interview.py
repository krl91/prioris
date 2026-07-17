"""Pure channel-agnostic interview state machine.

One question at a time. Express mode by default; escalates to full mode when
the stakes justify it. Clarifications are inserted for contradictions and are
capped at two. Telegram and GUI are adapters over this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from . import contradictions as contra
from .axes import (Axis, Demandeur, Effort, Estimation, Incertitude,
                   Priorite, express_defaults)
from .mirror import MirrorQuestion, select_mirror

MAX_CLARIFICATIONS = 2


class Q(str, Enum):
    SUBJECTIVE = "SUBJECTIVE"
    INACTION = "INACTION"        # INA
    BLOCAGE = "BLOCAGE"          # BLK
    CDR = "CDR"
    OBJECTIF = "OBJECTIF"        # ALN
    ESTIMATION = "ESTIMATION"
    # full-mode extras
    IMPACT = "IMPACT"            # IMP
    HORIZON = "HORIZON"          # HOR
    IRREVERSIBILITE = "IRREVERSIBILITE"  # IRR
    EFFORT = "EFFORT"
    DEMANDEUR = "DEMANDEUR"
    VISIBILITE = "VISIBILITE"
    PRESSION = "PRESSION"
    CLARIFICATION = "CLARIFICATION"
    MIROIR = "MIROIR"


EXPRESS_FLOW = [Q.SUBJECTIVE, Q.INACTION, Q.BLOCAGE, Q.CDR, Q.OBJECTIF, Q.ESTIMATION]
FULL_EXTRA = [Q.IMPACT, Q.HORIZON, Q.IRREVERSIBILITE, Q.EFFORT,
              Q.DEMANDEUR, Q.VISIBILITE, Q.PRESSION]

Q_TO_AXIS = {Q.INACTION: Axis.INA, Q.BLOCAGE: Axis.BLK, Q.CDR: Axis.CDR,
             Q.OBJECTIF: Axis.ALN, Q.IMPACT: Axis.IMP, Q.HORIZON: Axis.HOR,
             Q.IRREVERSIBILITE: Axis.IRR}


@dataclass(frozen=True)
class Session:
    """Immutable interview state: every answer produces a new session."""
    deadline_days: int | None = None
    mode: str = "express"                       # express | complet
    asked: tuple[Q, ...] = ()
    axes: dict = field(default_factory=dict)     # Axis -> int
    incertitudes: dict = field(default_factory=dict)
    subjective: Priorite | None = None
    estimation: Estimation | None = None
    effort: Effort = Effort.MOYEN
    demandeur: Demandeur = Demandeur.MOI
    visibilite: int = 0
    pression: int = 0
    clarifications: int = 0
    pending: contra.Contradiction | None = None
    resolved_rules: tuple[str, ...] = ()
    seed: int = 0                # task id, used for deterministic mirror choice
    mirror_done: bool = False


def _flow(s: Session) -> list[Q]:
    return EXPRESS_FLOW + (FULL_EXTRA if s.mode == "complet" else [])


def _should_escalate(s: Session) -> bool:
    """Escalate express to full mode for high-stakes signals."""
    if s.subjective == Priorite.P1:
        return True
    if s.axes.get(Axis.INA, 0) >= 3:
        return True
    if s.deadline_days is not None and s.deadline_days < 7:
        return True
    return False


def next_question(s: Session) -> tuple[Q | None, Session]:
    """Return the next question and session. None means interview complete."""
    if s.pending is not None:
        return Q.CLARIFICATION, s
    if s.mode == "express" and _should_escalate(s):
        s = replace(s, mode="complet")
    for q in _flow(s):
        if q not in s.asked:
            return q, s
    # Mirror question: one end-of-interview probe, when applicable.
    if not s.mirror_done and mirror_for(s) is not None:
        return Q.MIROIR, s
    return None, s


def mirror_for(s: Session) -> MirrorQuestion | None:
    """Return this interview's deterministic mirror probe."""
    return select_mirror(s.axes, s.subjective, s.seed)


def mirror_answer(s: Session, option_index: int) -> Session:
    """Apply the mirror answer: adjust the target axis, if any, then re-test."""
    mq = mirror_for(s)
    if mq is None:
        raise ValueError("aucune question miroir applicable")
    opt = mq.options[option_index]
    axes = dict(s.axes)
    kw: dict = {"mirror_done": True}
    if opt.axe:
        axis = Axis(opt.axe)
        axes[axis] = opt.valeur
        if opt.incertain:
            incs = dict(s.incertitudes)
            incs[axis] = Incertitude.NE_SAIT_PAS
            kw["incertitudes"] = incs
    s = replace(s, axes=axes, **kw)
    return _check_contradictions(s)


def answer(s: Session, q: Q, value) -> Session:
    """Record an answer and run contradiction detection.

    `value` is an int for axes/visibility/pressure, or a Priorite, Estimation,
    Effort or Demandeur depending on the question. Axis answers also accept
    `(value, Incertitude)`.
    """
    inc = Incertitude.SUR
    if isinstance(value, tuple):
        value, inc = value

    axes = dict(s.axes)
    kw: dict = {}
    if q == Q.SUBJECTIVE:
        kw["subjective"] = Priorite(value)
    elif q == Q.ESTIMATION:
        kw["estimation"] = Estimation(value)
    elif q == Q.EFFORT:
        kw["effort"] = Effort(value)
    elif q == Q.DEMANDEUR:
        kw["demandeur"] = Demandeur(value)
    elif q == Q.VISIBILITE:
        kw["visibilite"] = int(value)
    elif q == Q.PRESSION:
        kw["pression"] = int(value)
    elif q in Q_TO_AXIS:
        axis = Q_TO_AXIS[q]
        axes[axis] = int(value)
        incs = dict(s.incertitudes)
        incs[axis] = inc
        kw["incertitudes"] = incs
    else:
        raise ValueError(f"réponse inattendue pour {q}")

    s = replace(s, asked=s.asked + (q,), axes=axes, **kw)
    return _check_contradictions(s)


def clarify(s: Session, axis_code: str, corrected_value: int,
            incertain: bool = False) -> Session:
    """Answer a clarification: adjust an axis, resolve the rule and re-test.

    `incertain` means the user answered "I don't know": the median value is set
    and uncertainty is recorded, making the evaluation provisional.
    """
    if s.pending is None:
        raise ValueError("aucune clarification en attente")
    axis = Axis(axis_code)
    axes = dict(s.axes)
    axes[axis] = corrected_value
    kw: dict = {}
    if incertain:
        incs = dict(s.incertitudes)
        incs[axis] = Incertitude.NE_SAIT_PAS
        kw["incertitudes"] = incs
    s = replace(s, axes=axes,
                resolved_rules=s.resolved_rules + (s.pending.regle,),
                pending=None, clarifications=s.clarifications + 1, **kw)
    return _check_contradictions(s)


def promise_deadline(s: Session) -> Session:
    """C5 "I will provide the date" option; the date arrives via set_deadline."""
    if s.pending is None:
        raise ValueError("aucune clarification en attente")
    s = replace(s, resolved_rules=s.resolved_rules + (s.pending.regle,),
                pending=None, clarifications=s.clarifications + 1)
    return s


def set_deadline(s: Session, deadline_days: int) -> Session:
    """Set the real deadline as remaining days and re-test rules."""
    s = replace(s, deadline_days=deadline_days)
    return _check_contradictions(s)


def set_axis_probe(s: Session, axis_code: str, value: int,
                   incertain: bool = False) -> Session:
    """Apply an LLM-interpreted probe answer as an axis update."""
    axis = Axis(axis_code)
    axes = dict(s.axes)
    axes[axis] = int(value)
    kw: dict = {"axes": axes}
    if incertain:
        incs = dict(s.incertitudes)
        incs[axis] = Incertitude.NE_SAIT_PAS
        kw["incertitudes"] = incs
    return _check_contradictions(replace(s, **kw))


def _check_contradictions(s: Session) -> Session:
    if s.clarifications >= MAX_CLARIFICATIONS:
        return s  # cap reached: evaluation remains provisional
    found = [c for c in contra.detect(s.axes, s.subjective, s.deadline_days)
             if c.regle not in s.resolved_rules]
    if found and s.pending is None:
        s = replace(s, pending=found[0])
        if s.mode == "express":
            s = replace(s, mode="complet")   # contradiction implies higher stakes
    return s


def final_axes(s: Session) -> tuple[dict, set]:
    """Complete axes for scoring: explicit answers plus express defaults.

    Returns `(axes, defaulted_axes)`.
    """
    axes = dict(s.axes)
    defaults = express_defaults(axes.get(Axis.INA, 0), s.deadline_days)
    par_defaut = set()
    for axis, val in defaults.items():
        if axis not in axes:
            axes[axis] = val
            par_defaut.add(axis)
    if Axis.ALN not in axes:
        axes[Axis.ALN] = 0
        par_defaut.add(Axis.ALN)
    return axes, par_defaut


def is_provisoire(s: Session) -> bool:
    unresolved = [c for c in contra.detect(s.axes, s.subjective, s.deadline_days)
                  if c.regle not in s.resolved_rules]
    return bool(unresolved) and s.clarifications >= MAX_CLARIFICATIONS
