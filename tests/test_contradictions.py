"""Tests des règles C1–C6 (§7.1) : cas déclenchant + cas limite non déclenchant."""
from prioris.core.axes import Axis, Priorite
from prioris.core.contradictions import detect


def rules(axes, subjective=None, deadline=None):
    return [c.regle for c in detect(axes, subjective, deadline)]


def test_c1():
    assert "C1" in rules({Axis.INA: 1, Axis.CDR: 3})
    assert "C1" not in rules({Axis.INA: 2, Axis.CDR: 3})


def test_c2():
    assert "C2" in rules({Axis.BLK: 4, Axis.INA: 1})
    assert "C2" not in rules({Axis.BLK: 3, Axis.INA: 1})


def test_c3():
    assert "C3" in rules({Axis.HOR: 3, Axis.INA: 0})
    assert "C3" not in rules({Axis.HOR: 3, Axis.INA: 1})


def test_c4():
    assert "C4" in rules({Axis.IMP: 3, Axis.INA: 0})
    assert "C4" not in rules({Axis.IMP: 2, Axis.INA: 0})


def test_c5_falaise_sans_date():
    assert "C5" in rules({Axis.CDR: 4}, deadline=None)
    assert "C5" not in rules({Axis.CDR: 4}, deadline=10)


def test_c6_p1_sans_fondement():
    a = {Axis.BLK: 0, Axis.CDR: 1, Axis.INA: 1}
    assert "C6" in rules(a, subjective=Priorite.P1)
    assert "C6" not in rules(a, subjective=Priorite.P2)
    assert "C6" not in rules({**a, Axis.BLK: 1}, subjective=Priorite.P1)


def test_axes_partiels_tolere():
    """En cours d'entretien : ne lève pas sur des axes non encore répondus."""
    assert rules({Axis.INA: 1}) == []


def test_options_corrigent_un_axe_de_la_regle():
    """Audit v0.3.5 : toutes les options de toutes les règles sont actionnables
    (axe réel de la règle, ou pseudo-axe DATE pour la saisie de deadline)."""
    scenarios = [
        ({Axis.INA: 1, Axis.CDR: 3}, None, None),
        ({Axis.BLK: 4, Axis.INA: 1}, None, None),
        ({Axis.HOR: 3, Axis.INA: 0}, None, None),
        ({Axis.IMP: 3, Axis.INA: 0}, None, None),
        ({Axis.CDR: 4}, None, None),
        ({Axis.BLK: 0, Axis.CDR: 1, Axis.INA: 1}, Priorite.P1, None),
    ]
    valides = {a.value for a in Axis} | {"DATE"}
    for axes_v, subj, dl in scenarios:
        found = detect(axes_v, subj, dl)
        assert found, axes_v
        for c in found:
            assert len(c.options) == 3
            assert c.question.endswith("?")
            for label, axe, val in c.options:
                assert label and axe in valides
                assert isinstance(val, int)
                # une option corrigeant un axe cible un axe DE la règle
                if axe != "DATE":
                    assert axe in c.axes, (c.regle, label)


def test_option_je_ne_sais_pas_partout_identifiable():
    """Le bot repère « je ne sais pas » par le libellé → incertitude."""
    for axes_v, subj in [({Axis.INA: 1, Axis.CDR: 3}, None),
                         ({Axis.BLK: 4, Axis.INA: 1}, None),
                         ({Axis.CDR: 4}, None)]:
        for c in detect(axes_v, subj, None):
            assert any(lbl.lower().startswith("je ne sais pas")
                       for lbl, _, _ in c.options)
