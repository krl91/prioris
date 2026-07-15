"""Tests des signatures de biais (§7.3) — règles MVP 1–4, 7, 9."""
from prioris.core.axes import Axis, Demandeur, Metadata, Priorite
from prioris.core.biases import detect


def axes(blk=0, cdr=0, hor=0, imp=0, ina=0, irr=0, aln=0):
    return {Axis.BLK: blk, Axis.CDR: cdr, Axis.HOR: hor, Axis.IMP: imp,
            Axis.INA: ina, Axis.IRR: irr, Axis.ALN: aln}


def types(flags):
    return {f.type_biais for f in flags}


def test_biais_client_fort():
    """Cas Kallipr : subjectif P1, calculé P4, demande client sans blocage."""
    meta = Metadata(demandeur=Demandeur.CLIENT, visibilite=2, subjective=Priorite.P1)
    flags = detect(axes(cdr=1, hor=3, ina=1), importance=15.0,
                   calculee=Priorite.P4, meta=meta)
    client = next(f for f in flags if f.type_biais == "client")
    assert client.gravite == "fort"
    assert client.preuve["ecart"] == 3
    assert "visibilite" in types(flags)


def test_pas_de_biais_sans_ecart():
    meta = Metadata(demandeur=Demandeur.CLIENT, subjective=Priorite.P4)
    flags = detect(axes(cdr=1, ina=1), importance=15.0,
                   calculee=Priorite.P4, meta=meta)
    assert "client" not in types(flags)
    assert "urgence" not in types(flags)


def test_biais_urgence():
    meta = Metadata(subjective=Priorite.P2)
    flags = detect(axes(cdr=1, hor=2, ina=1), importance=20.0,
                   calculee=Priorite.P4, meta=meta)
    assert "urgence" in types(flags)


def test_biais_hierarchique():
    meta = Metadata(demandeur=Demandeur.MANAGER, subjective=Priorite.P1)
    flags = detect(axes(blk=2, cdr=3, ina=2), importance=30.0,
                   calculee=Priorite.P3, meta=meta)
    assert "hierarchique" in types(flags)


def test_biais_culpabilite_sans_subjectif():
    """La culpabilité ne dépend pas de l'écart : pression sur tâche mineure."""
    meta = Metadata(pression=3)
    flags = detect(axes(blk=1, ina=1), importance=10.0,
                   calculee=Priorite.P4, meta=meta)
    assert "culpabilite" in types(flags)


def test_biais_bruit():
    meta = Metadata(visibilite=3)
    flags = detect(axes(ina=1, imp=1), importance=12.0,
                   calculee=Priorite.P4, meta=meta)
    assert "bruit" in types(flags)


def test_preuves_presentes():
    """Chaque flag cite les valeurs qui l'ont déclenché (§7.3)."""
    meta = Metadata(demandeur=Demandeur.CLIENT, visibilite=2, pression=2,
                    subjective=Priorite.P1)
    for f in detect(axes(cdr=1, hor=1, ina=1, imp=1), importance=10.0,
                    calculee=Priorite.P4, meta=meta):
        assert f.preuve and f.message
