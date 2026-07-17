"""Tests du moteur de scoring (§12.1) — cas dorés du §6.4 + propriétés."""
import itertools

import pytest

from prioris.core.axes import AXIS_MAX, Axis, Estimation, Incertitude, Priorite
from prioris.core.scoring import score


def axes(blk=0, cdr=0, hor=0, imp=0, ina=0, irr=0, aln=0):
    return {Axis.BLK: blk, Axis.CDR: cdr, Axis.HOR: hor, Axis.IMP: imp,
            Axis.INA: ina, Axis.IRR: irr, Axis.ALN: aln}


# ------------------------------------------------------------- cas dorés
def test_golden_kallipr():
    """« Préparer l'atelier Kallipr » après correction du blocage (§6.4)."""
    r = score(axes(blk=0, cdr=1, hor=3, imp=1, ina=1, irr=0, aln=0),
              estimation=Estimation.H1_2, subjective=Priorite.P1)
    assert r.as_tuple() == (32.5, 15.0, 22.0, "Q4", "P4")
    assert r.justification["ecart_subjectif"] == 3


def test_golden_sport():
    """« Faire 45 min de sport » (§6.4) : l'invisible monte en P2."""
    r = score(axes(blk=1, cdr=3, hor=1, imp=3, ina=2, irr=1, aln=3),
              estimation=Estimation.M30_60)
    urgence, importance, global_score, quadrant, priorite = r.as_tuple()
    assert urgence == 43.5
    assert importance == 65.4
    assert global_score == pytest.approx(56.6, abs=0.1)
    assert quadrant == "Q2"
    assert priorite == "P2"


# ------------------------------------------------------------ ajustements
def test_plancher_deadline():
    r = score(axes(cdr=4, ina=1), estimation=Estimation.LT15, deadline_days=3)
    assert r.urgence == 70.0
    assert any(a["regle"] == "plancher_deadline" for a in r.justification["ajustements"])


def test_plancher_deadline_inactif_sans_falaise():
    r = score(axes(cdr=3, ina=1), estimation=Estimation.LT15, deadline_days=3)
    assert r.urgence < 70.0


def test_plancher_irreversibilite():
    r = score(axes(irr=3, ina=3), estimation=Estimation.LT15)
    assert r.importance >= 70.0


def test_plancher_objectifs():
    r = score(axes(aln=3), estimation=Estimation.LT15)
    assert r.importance >= 55.0
    assert r.priorite in (Priorite.P1, Priorite.P2)  # jamais P3/P4 (§6.2)


def test_plancher_objectifs_sans_effet_si_deja_haut():
    r = score(axes(blk=1, cdr=3, hor=1, imp=3, ina=2, irr=1, aln=3),
              estimation=Estimation.M30_60)
    assert not any(a["regle"] == "plancher_objectifs"
                   for a in r.justification["ajustements"])


# ------------------------------------------------------------- propriétés
def test_determinisme():
    a = axes(blk=2, cdr=2, hor=2, imp=2, ina=2, irr=1, aln=1)
    assert score(a, Estimation.H1_2).as_tuple() == score(a, Estimation.H1_2).as_tuple()


def test_bornes_0_100():
    for combo in itertools.product([0, None], repeat=7):
        vals = {a: (AXIS_MAX[a] if c is None else 0)
                for c, a in zip(combo, Axis)}
        r = score(vals, Estimation.LT15)
        assert 0 <= r.urgence <= 100 and 0 <= r.importance <= 100
        assert 0 <= r.global_ <= 100


def test_monotonie():
    """Augmenter un axe ne baisse jamais le score global (§12.1)."""
    base = axes(blk=2, cdr=2, hor=2, imp=2, ina=2, irr=1, aln=1)
    g0 = score(base, Estimation.H1_2).global_
    for axis in Axis:
        for delta in range(1, AXIS_MAX[axis] - base[axis] + 1):
            higher = dict(base)
            higher[axis] = base[axis] + delta
            assert score(higher, Estimation.H1_2).global_ >= g0 - 1e-9, axis


def test_amortisseur_incertitude():
    r = score(axes(blk=5, ina=2), estimation=Estimation.LT15,
              incertitudes={Axis.BLK: Incertitude.NE_SAIT_PAS})
    assert r.provisoire
    assert r.justification["axes"]["BLK"]["valeur"] == 2  # médiane conservatrice


def test_estimation_inconnue_provisoire():
    assert score(axes(), estimation=Estimation.INCONNUE).provisoire


def test_pepite():
    r = score(axes(imp=3, ina=2, aln=2), estimation=Estimation.M30_60)
    assert r.importance >= 45 and r.pepite
    assert not score(axes(imp=3, ina=2, aln=2), estimation=Estimation.H2_4).pepite


def test_hors_echelle():
    with pytest.raises(ValueError):
        score(axes(blk=6), Estimation.LT15)
    with pytest.raises(ValueError):
        score({Axis.BLK: 1}, Estimation.LT15)  # axes manquants


def test_justification_autosuffisante():
    """§6.5 : le score doit être reconstructible depuis le JSON seul."""
    r = score(axes(blk=0, cdr=1, hor=3, imp=1, ina=1, irr=0, aln=0),
              estimation=Estimation.H1_2)
    j = r.justification
    u = sum(j["calculs"]["U"]["termes"].values())
    i = sum(j["calculs"]["I"]["termes"].values())
    assert u == pytest.approx(j["calculs"]["U"]["total"], abs=0.01)
    assert i == pytest.approx(j["calculs"]["I"]["total"], abs=0.01)
    assert 0.6 * i + 0.4 * u == pytest.approx(j["calculs"]["G"]["total"], abs=0.01)
