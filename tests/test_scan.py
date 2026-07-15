"""Tests du scan Obsidian (V0.3) — vault factice dans tmp_path.

Contrat de sécurité testé : détection fiable, annotation chirurgicale de la
seule ligne concernée, jamais d'écriture si la ligne a changé.
"""
from prioris.core.axes import Estimation, Priorite
from prioris.core.scoring import score
from prioris.vault import scan
from tests.test_scoring import axes


def make_vault(tmp_path):
    (tmp_path / "Journal").mkdir()
    (tmp_path / "PRIORIS").mkdir()
    (tmp_path / "Journal" / "2026-07-12.md").write_text(
        "# Lundi\n"
        "- [ ] Préparer l'atelier Kallipr #sujet/kallipr 📅 2026-07-16\n"
        "- [x] Tâche déjà faite\n"
        "- [ ] Mettre à jour le CV\n"
        "- [ ] Ancienne tâche 🎯P3 [[PRIORIS/9]]\n"
        "du texte normal - [ ] pas une tâche\n", "utf-8")
    (tmp_path / "ignore-moi.md").write_text(
        "---\nprioris: ignore\n---\n- [ ] tâche à ignorer\n", "utf-8")
    (tmp_path / "PRIORIS" / "Plan du jour.md").write_text(
        "- [ ] toto (10 min · P3)\n", "utf-8")
    return tmp_path


def test_find_detecte_les_bonnes_taches(tmp_path):
    vault = make_vault(tmp_path)
    found = scan.find_unprioritized(vault)
    titres = [t.titre for t in found]
    assert titres == ["Préparer l'atelier Kallipr", "Mettre à jour le CV"]


def test_find_exclusions(tmp_path):
    vault = make_vault(tmp_path)
    found = scan.find_unprioritized(vault)
    raws = "\n".join(t.raw_line for t in found)
    assert "déjà faite" not in raws          # - [x]
    assert "🎯" not in raws                   # déjà priorisée
    assert "à ignorer" not in raws            # prioris: ignore
    assert "toto" not in raws                 # dossier PRIORIS/


def test_find_extrait_sujet_et_deadline(tmp_path):
    vault = make_vault(tmp_path)
    kallipr = scan.find_unprioritized(vault)[0]
    assert kallipr.sujet_tag == "kallipr"
    assert kallipr.due == "2026-07-16"
    assert kallipr.rel_path == "Journal/2026-07-12.md"


def test_rel_paths_restent_posix_pour_liens_obsidian(tmp_path):
    (tmp_path / "A" / "B").mkdir(parents=True)
    (tmp_path / "A" / "B" / "Note.md").write_text(
        "- [ ] Tâche Windows compatible\n", "utf-8")
    found = scan.find_unprioritized(tmp_path)
    assert found[0].rel_path == "A/B/Note.md"
    assert "\\" not in found[0].rel_path


def test_annotate_ligne_exacte_seulement(tmp_path):
    vault = make_vault(tmp_path)
    vt = scan.find_unprioritized(vault)[0]
    marker = scan.build_marker("P4", "PRIORIS/1.md")
    assert scan.annotate_task_line(vault, vt.rel_path, vt.raw_line, marker)
    text = (vault / "Journal" / "2026-07-12.md").read_text("utf-8")
    assert text.count("🎯P4") == 1
    assert "Kallipr #sujet/kallipr 📅 2026-07-16 🎯P4 [[PRIORIS/1]]" in text
    # les autres lignes sont intactes
    assert "- [ ] Mettre à jour le CV\n" in text
    assert "- [x] Tâche déjà faite\n" in text
    # la tâche annotée n'est plus détectée au scan suivant
    assert all(t.titre != vt.titre for t in scan.find_unprioritized(vault))


def test_annotate_ligne_modifiee_refuse(tmp_path):
    """Si la note a changé entre scan et évaluation : ne rien écrire."""
    vault = make_vault(tmp_path)
    vt = scan.find_unprioritized(vault)[0]
    note = vault / "Journal" / "2026-07-12.md"
    note.write_text(note.read_text("utf-8").replace(
        "Préparer l'atelier", "Préparer et animer l'atelier"), "utf-8")
    avant = note.read_text("utf-8")
    assert not scan.annotate_task_line(vault, vt.rel_path, vt.raw_line, "🎯P4 x")
    assert note.read_text("utf-8") == avant   # aucune écriture


def test_apply_result_detail_toujours_cree(tmp_path):
    vault = make_vault(tmp_path)
    vt = scan.find_unprioritized(vault)[1]    # CV
    # aln=3 seul ⇒ I brut 20 → plancher objectifs à 55 (ajustement tracé)
    r = score(axes(aln=3), estimation=Estimation.M30_60,
              subjective=Priorite.P3)
    annotated, detail_rel = scan.apply_result(
        vault, "PRIORIS", vt, 42, r.justification, [], "2026-07-12")
    assert annotated
    detail = (vault / detail_rel).read_text("utf-8")
    assert "# PRIORIS #42 — Mettre à jour le CV" in detail
    assert "Tâche : Mettre à jour le CV" in detail
    assert "[[Journal/2026-07-12]]" in detail          # backlink source
    assert f"**{r.priorite.value}**" in detail
    assert "| BLK |" in detail                          # table des axes
    assert "plancher_objectifs" in detail               # ajustements tracés
    # marqueur dans la note source avec lien vers le détail
    src = (vault / "Journal" / "2026-07-12.md").read_text("utf-8")
    assert f"🎯{r.priorite.value} [[{detail_rel.removesuffix('.md')}]]" in src


def test_clean_title_emojis_tasks_et_gras(tmp_path):
    """Format réel du vault : gras, emojis de priorité du plugin Tasks."""
    (tmp_path / "n.md").write_text(
        "- [ ] #sujet/kallipr **Finaliser le modèle de données** "
        "📅  2026-07-15🔺  \n"
        "- [ ]\n", "utf-8")   # tâche vide : ignorée
    found = scan.find_unprioritized(tmp_path)
    assert len(found) == 1
    assert found[0].titre == "Finaliser le modèle de données"
    assert found[0].sujet_tag == "kallipr"
    assert found[0].due == "2026-07-15"


def test_slug_caracteres_interdits():
    assert scan.detail_note_rel("PRIORIS", 1, 'a/b:c*"d[e]#f') == "PRIORIS/1.md"
    assert scan.detail_note_rel("PRIORIS", 7, "x" * 100) == "PRIORIS/7.md"


def test_find_marked_accepte_ancien_format_details(tmp_path):
    (tmp_path / "n.md").write_text(
        "- [ ] Ancienne tâche 🎯P3 [[PRIORIS/details/9 - x|détail]]\n",
        "utf-8",
    )
    marked = scan.find_marked(tmp_path)
    assert len(marked) == 1
    assert marked[0].task_id == 9
