"""Scan the Obsidian vault and write priority markers back.

Safety principles for user notes:
- read broadly, write surgically: only the exact task line is modified by
  appending a marker, nothing else;
- if the line changed between scan and evaluation, the source note is not
  modified; the detail note is still created;
- all writes are atomic through a temporary file and rename;
- the PRIORIS/ folder is never scanned.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .export import write_note

# Marker appended to task lines: when present, the task was already prioritized.
MARKER_SIGIL = "🎯P"
_TASK_RE = re.compile(r"^\s*[-*] \[ \] (.+)$")
_SUJET_RE = re.compile(r"#sujet/([\w-]+)")
_DUE_RE = re.compile(r"[📅⏳]\s*(\d{4}-\d{2}-\d{2})")
_IGNORE_RE = re.compile(r"^prioris:\s*ignore\s*$", re.M)


@dataclass(frozen=True)
class VaultTask:
    rel_path: str          # note path relative to the vault
    line_no: int           # 1-based, informational; raw_line is authoritative
    raw_line: str          # original full line, used for re-identification
    titre: str             # cleaned task title for PRIORIS
    sujet_tag: str         # first #sujet/x tag if present
    due: str | None = None  # 📅YYYY-MM-DD when present, used as real deadline


def _clean_title(text: str) -> str:
    """Remove tags, dates, Tasks plugin emojis and links for a readable title."""
    text = re.sub(r"[📅⏳✅🛫➕]\s*\d{4}-\d{2}-\d{2}", "", text)
    text = re.sub(r"[🔺🔼🔽⏫⏬🔁🆔⛔]", "", text)   # Tasks priority/recurrence icons
    text = re.sub(r"#[\w/-]+", "", text)
    text = re.sub(r"\[\[([^\]|]+)(\|[^\]]+)?\]\]", r"\1", text)
    text = text.replace("**", "")
    return re.sub(r"\s+", " ", text).strip(" .-")


def find_unprioritized(vault_path: str | Path,
                       prioris_dir: str = "PRIORIS") -> list[VaultTask]:
    """Return every unchecked vault task without a PRIORIS marker."""
    vault = Path(vault_path)
    found: list[VaultTask] = []
    for note in sorted(vault.rglob("*.md")):
        rel = note.relative_to(vault)
        if rel.parts and rel.parts[0].lower() == prioris_dir.lower():
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        try:
            text = note.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # Frontmatter opt-out.
        if text.startswith("---") and _IGNORE_RE.search(text[:500]):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            m = _TASK_RE.match(line)
            if not m or MARKER_SIGIL in line:
                continue
            body = m.group(1).strip()
            titre = _clean_title(body)
            if not titre:
                continue
            sujet = _SUJET_RE.search(line)
            due = _DUE_RE.search(line)
            found.append(VaultTask(rel.as_posix(), i, line, titre,
                                   sujet.group(1) if sujet else "",
                                   due.group(1) if due else None))
    return found


_MARKED_RE = re.compile(
    r"^\s*[-*] \[(?P<check>[ xX])\] .*🎯P\d.*\[\[(?:[^\]|]*/)?(?P<id>\d+)(?:\s+-[^\]|]*)?(?:\|[^\]]*)?\]\]")


@dataclass(frozen=True)
class MarkedTask:
    """Already-prioritized task found in the vault, with id from its marker."""
    task_id: int
    rel_path: str
    checked: bool


def find_marked(vault_path: str | Path,
                prioris_dir: str = "PRIORIS") -> list[MarkedTask]:
    """Return all lines carrying a PRIORIS marker, checked or unchecked.

    The task id comes from the detail-note link, so sync remains reliable even
    when the line text was manually edited.
    """
    vault = Path(vault_path)
    found: list[MarkedTask] = []
    for note in sorted(vault.rglob("*.md")):
        rel = note.relative_to(vault)
        if rel.parts and rel.parts[0].lower() == prioris_dir.lower():
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        try:
            text = note.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.splitlines():
            m = _MARKED_RE.match(line)
            if m:
                found.append(MarkedTask(int(m.group("id")), rel.as_posix(),
                                        m.group("check").lower() == "x"))
    return found


def check_task_line(vault_path: str | Path, task_id: int,
                    prioris_dir: str = "PRIORIS") -> tuple[bool, str]:
    """Check `- [ ]` to `- [x]` on the marked line carrying this id.

    PRIORIS-to-vault direction, symmetric with /scan sync. Idempotent:
    an already checked line is a success without writing. Returns success and
    the relative note path.
    """
    vault = Path(vault_path)
    for note in sorted(vault.rglob("*.md")):
        rel = note.relative_to(vault)
        if rel.parts and rel.parts[0].lower() == prioris_dir.lower():
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        try:
            text = note.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            m = _MARKED_RE.match(line)
            if not m or int(m.group("id")) != task_id:
                continue
            if m.group("check").lower() == "x":
                return True, rel.as_posix()    # already checked: nothing to write
            lines[i] = line.replace("[ ]", "[x]", 1)
            newline = "\n" if text.endswith("\n") else ""
            write_note(vault_path, str(rel), "\n".join(lines) + newline)
            return True, rel.as_posix()
    return False, ""


def build_marker(priorite: str, detail_rel: str) -> str:
    """Ex. : 🎯P2 [[PRIORIS/12]]"""
    return f"{MARKER_SIGIL[:-1]}{priorite} [[{detail_rel.removesuffix('.md')}]]"


def annotate_task_line(vault_path: str | Path, rel_path: str,
                       raw_line: str, marker: str) -> bool:
    """Append the marker to the exact source line. False when not found."""
    note = Path(vault_path) / rel_path
    try:
        text = note.read_text("utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    lines = text.splitlines(keepends=False)
    for i, line in enumerate(lines):
        if line == raw_line and MARKER_SIGIL not in line:
            lines[i] = line.rstrip() + " " + marker
            newline = "\n" if text.endswith("\n") else ""
            write_note(vault_path, rel_path, "\n".join(lines) + newline)
            return True
    return False


def _slug(text: str, max_len: int = 40) -> str:
    text = re.sub(r'[\\/:*?"<>|#^\[\]]', "", text).strip()
    return text[:max_len].strip() or "tache"


def detail_note_rel(prioris_dir: str, task_id: int, titre: str) -> str:
    return f"{prioris_dir}/{task_id}.md"


def render_detail_note(titre: str, rel_source: str, justification: dict,
                       flags: list, date_str: str,
                       task_id: int | None = None,
                       notes: list[tuple[str, str]] | None = None) -> str:
    j = justification
    heading = f"PRIORIS #{task_id} — {titre}" if task_id is not None else f"PRIORIS — {titre}"
    lines = [f"# {heading}", "",
             f"Tâche : {titre}",
             f"Source : [[{rel_source.removesuffix('.md')}]]",
             f"Évalué le {date_str} · mode {j['mode']} · algo v{j['version_algo']}", "",
             f"## Résultat",
             f"**{j['priorite']}** — quadrant {j['quadrant']} — "
             f"score {j['calculs']['G']['total']}/100",
             f"Urgence {j['calculs']['U']['total']} · "
             f"Importance {j['calculs']['I']['total']}"]
    if j.get("subjective"):
        lines.append(f"Instinct déclaré : {j['subjective']} "
                     f"(écart {j['ecart_subjectif']:+d})")
    lines += ["", "## Axes", "", "| Axe | Valeur | Défaut |", "|---|---|---|"]
    lines += [f"| {a} | {d['valeur']} | {'oui' if d['defaut'] else ''} |"
              for a, d in j["axes"].items()]
    if j["ajustements"]:
        lines += ["", "## Ajustements"]
        for adjustment in j["ajustements"]:
            if "avant" in adjustment and "apres" in adjustment:
                lines.append(
                    f"- {adjustment['regle']} : {adjustment['avant']:.1f} → "
                    f"{adjustment['apres']:.1f}")
            else:
                lines.append(
                    f"- {adjustment['regle']} : {adjustment.get('motif', '')}".rstrip())
    if flags:
        lines += ["", "## Biais détectés"]
        lines += [f"- **{f.type_biais}** ({f.gravite}) : {f.message}" for f in flags]
    if notes:
        lines += ["", "## Informations ajoutées"]
        lines += [f"- {created_at} — {note}" for created_at, note in notes]
    if j.get("provisoire"):
        lines += ["", "⚠️ Évaluation provisoire (incertitude ou estimation inconnue)."]
    lines += ["", "---", "*Généré par PRIORIS — ne pas éditer (régénéré).*"]
    return "\n".join(lines) + "\n"


def apply_result(vault_path: str | Path, prioris_dir: str, task: VaultTask,
                 task_id: int, justification: dict, flags: list,
                 date_str: str) -> tuple[bool, str]:
    """Write the detail note, then annotate the source note.

    Returns whether the line was annotated and the detail note relative path.
    The detail note is always written, even when source annotation fails.
    """
    detail_rel = detail_note_rel(prioris_dir, task_id, task.titre)
    content = render_detail_note(task.titre, task.rel_path, justification,
                                 flags, date_str, task_id=task_id)
    write_note(vault_path, detail_rel, content)
    marker = build_marker(justification["priorite"], detail_rel)
    annotated = annotate_task_line(vault_path, task.rel_path,
                                   task.raw_line, marker)
    return annotated, detail_rel
