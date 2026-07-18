use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
};

use regex::Regex;
use walkdir::WalkDir;

use crate::core::DayPlan;

pub const MARK_START: &str = "<!-- prioris:start -->";
pub const MARK_END: &str = "<!-- prioris:end -->";
pub const MARKER_SIGIL: &str = "🎯P";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VaultTask {
    pub relative_path: String,
    pub line_number: usize,
    pub raw_line: String,
    pub title: String,
    pub subject_tag: String,
    pub due: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MarkedTask {
    pub task_id: i64,
    pub relative_path: String,
    pub checked: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FileChange {
    pub relative_path: String,
    pub before: String,
    pub after: String,
}

pub fn find_unprioritized(vault: &Path, prioris_dir: &str) -> Vec<VaultTask> {
    let task_re = Regex::new(r"^\s*[-*] \[ \] (.+)$").expect("static task regex");
    let subject_re = Regex::new(r"#sujet/([\w-]+)").expect("static subject regex");
    let due_re = Regex::new(r"[📅⏳]\s*(\d{4}-\d{2}-\d{2})").expect("static due regex");
    let ignore_re = Regex::new(r"(?m)^prioris:\s*ignore\s*$").expect("static ignore regex");
    markdown_files(vault, prioris_dir)
        .into_iter()
        .flat_map(|path| {
            let relative = path
                .strip_prefix(vault)
                .unwrap_or(&path)
                .to_string_lossy()
                .replace('\\', "/");
            let Ok(text) = fs::read_to_string(&path) else {
                return Vec::new();
            };
            if text.starts_with("---")
                && ignore_re.is_match(&text.chars().take(500).collect::<String>())
            {
                return Vec::new();
            }
            text.lines()
                .enumerate()
                .filter_map(|(index, line)| {
                    let captures = task_re.captures(line)?;
                    if line.contains(MARKER_SIGIL) {
                        return None;
                    }
                    let title = clean_title(captures.get(1)?.as_str());
                    if title.is_empty() {
                        return None;
                    }
                    Some(VaultTask {
                        relative_path: relative.clone(),
                        line_number: index + 1,
                        raw_line: line.to_owned(),
                        title,
                        subject_tag: subject_re
                            .captures(line)
                            .and_then(|value| value.get(1))
                            .map_or_else(String::new, |value| value.as_str().to_owned()),
                        due: due_re
                            .captures(line)
                            .and_then(|value| value.get(1))
                            .map(|value| value.as_str().to_owned()),
                    })
                })
                .collect::<Vec<_>>()
        })
        .collect()
}

pub fn find_marked(vault: &Path, prioris_dir: &str) -> Vec<MarkedTask> {
    let marker_re = Regex::new(
        r"^\s*[-*] \[([ xX])\] .*🎯P\d.*\[\[(?:[^\]|]*/)?(\d+)(?:\s+-[^\]|]*)?(?:\|[^\]]*)?\]\]",
    )
    .expect("static marker regex");
    markdown_files(vault, prioris_dir)
        .into_iter()
        .flat_map(|path| {
            let relative = path
                .strip_prefix(vault)
                .unwrap_or(&path)
                .to_string_lossy()
                .replace('\\', "/");
            let marker_re = marker_re.clone();
            fs::read_to_string(path)
                .ok()
                .into_iter()
                .flat_map(move |text| {
                    let relative = relative.clone();
                    let values = text
                        .lines()
                        .filter_map(|line| {
                            let captures = marker_re.captures(line)?;
                            Some(MarkedTask {
                                task_id: captures.get(2)?.as_str().parse().ok()?,
                                relative_path: relative.clone(),
                                checked: !captures.get(1)?.as_str().eq_ignore_ascii_case(" "),
                            })
                        })
                        .collect::<Vec<_>>();
                    values.into_iter()
                })
        })
        .collect()
}

pub fn apply_result(
    vault: &Path,
    prioris_dir: &str,
    task: &VaultTask,
    task_id: i64,
    priority: &str,
    justification: &serde_json::Value,
) -> std::io::Result<bool> {
    let detail_relative = format!("{prioris_dir}/{task_id}.md");
    let detail = render_detail_note(task, task_id, justification);
    write_note(vault, &detail_relative, &detail)?;
    let source = vault.join(&task.relative_path);
    let text = fs::read_to_string(&source)?;
    let mut changed = false;
    let lines = text
        .lines()
        .map(|line| {
            if !changed && line == task.raw_line && !line.contains(MARKER_SIGIL) {
                changed = true;
                format!(
                    "{} 🎯{} [[{}/{}]]",
                    line.trim_end(),
                    priority,
                    prioris_dir,
                    task_id
                )
            } else {
                line.to_owned()
            }
        })
        .collect::<Vec<_>>();
    if changed {
        let trailing = if text.ends_with('\n') { "\n" } else { "" };
        write_note(vault, &task.relative_path, &(lines.join("\n") + trailing))?;
    }
    Ok(changed)
}

pub fn check_task(vault: &Path, prioris_dir: &str, task_id: i64) -> std::io::Result<bool> {
    let pattern = Regex::new(&format!(
        r"🎯P\d.*\[\[(?:[^\]|]*/)?{}(?:\D|$)",
        regex::escape(&task_id.to_string())
    ))
    .expect("escaped task id regex");
    for path in markdown_files(vault, prioris_dir) {
        let text = fs::read_to_string(&path)?;
        let mut changed = false;
        let lines = text
            .lines()
            .map(|line| {
                if pattern.is_match(line) && line.contains("[ ]") {
                    changed = true;
                    line.replacen("[ ]", "[x]", 1)
                } else {
                    line.to_owned()
                }
            })
            .collect::<Vec<_>>();
        if changed {
            let relative = path.strip_prefix(vault).unwrap_or(&path).to_string_lossy();
            let trailing = if text.ends_with('\n') { "\n" } else { "" };
            write_note(
                vault,
                Path::new(relative.as_ref()),
                &(lines.join("\n") + trailing),
            )?;
            return Ok(true);
        }
    }
    Ok(false)
}

pub fn render_plan(plan: &DayPlan, date: &str, energy: u8) -> String {
    let energy_label = match energy {
        1 => "très faible",
        2 => "faible",
        3 => "normale",
        4 => "bonne",
        5 => "excellente",
        _ => "inconnue",
    };
    let mut lines = vec![
        MARK_START.to_owned(),
        format!("# Plan du jour — {date}"),
        format!(
            "*Énergie : {energy_label} · capacité utile : {} min*",
            plan.usable_capacity_minutes
        ),
        String::new(),
    ];
    if plan.items.is_empty() {
        lines.push("Aucune tâche planifiable aujourd'hui.".to_owned());
    }
    for item in &plan.items {
        let prefix = if item.partial { "entamer : " } else { "" };
        let gem = if item.task.gem { " 💎" } else { "" };
        lines.push(format!(
            "- [ ] {prefix}{}{gem} ({} min · {})",
            item.task.title,
            item.duration_minutes,
            item.task.priority.as_str(),
        ));
        if !item.note.is_empty() {
            lines.push(format!("  - {}", item.note));
        }
    }
    lines.push(MARK_END.to_owned());
    lines.join("\n") + "\n"
}

pub fn sync_preview(vault: &Path, relative_path: &str, after: String) -> FileChange {
    let before = fs::read_to_string(vault.join(relative_path)).unwrap_or_default();
    FileChange {
        relative_path: relative_path.to_owned(),
        before,
        after,
    }
}

pub fn apply_changes(vault: &Path, changes: &[FileChange]) -> std::io::Result<()> {
    for change in changes
        .iter()
        .filter(|change| change.before != change.after)
    {
        write_note(vault, &change.relative_path, &change.after)?;
    }
    Ok(())
}

pub fn write_note(
    vault: &Path,
    relative_path: impl AsRef<Path>,
    content: &str,
) -> std::io::Result<PathBuf> {
    let target = vault.join(relative_path);
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent)?;
    }
    let temporary = target.with_extension(format!("{}.tmp", std::process::id()));
    let mut file = fs::File::create(&temporary)?;
    file.write_all(content.as_bytes())?;
    file.sync_all()?;
    fs::rename(&temporary, &target)?;
    Ok(target)
}

fn markdown_files(vault: &Path, prioris_dir: &str) -> Vec<PathBuf> {
    let mut files = WalkDir::new(vault)
        .follow_links(false)
        .into_iter()
        .filter_map(Result::ok)
        .filter(|entry| entry.file_type().is_file())
        .map(|entry| entry.into_path())
        .filter(|path| {
            path.extension()
                .is_some_and(|extension| extension.eq_ignore_ascii_case("md"))
        })
        .filter(|path| {
            let Ok(relative) = path.strip_prefix(vault) else {
                return false;
            };
            !relative.components().any(|component| {
                let name = component.as_os_str().to_string_lossy();
                name.starts_with('.') || name.eq_ignore_ascii_case(prioris_dir)
            })
        })
        .collect::<Vec<_>>();
    files.sort();
    files
}

fn clean_title(text: &str) -> String {
    let date_re = Regex::new(r"[📅⏳✅🛫➕]\s*\d{4}-\d{2}-\d{2}").expect("static date regex");
    let tags_re = Regex::new(r"#[\w/-]+").expect("static tag regex");
    let wiki_re = Regex::new(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]").expect("static wiki regex");
    let spaces_re = Regex::new(r"\s+").expect("static spaces regex");
    let value = date_re.replace_all(text, "");
    let value = tags_re.replace_all(&value, "");
    let value = wiki_re.replace_all(&value, "$1");
    let value = value
        .replace(['🔺', '🔼', '🔽', '⏫', '⏬', '🔁', '🆔', '⛔'], "")
        .replace("**", "");
    spaces_re
        .replace_all(&value, " ")
        .trim_matches([' ', '.', '-'])
        .to_owned()
}

fn render_detail_note(task: &VaultTask, task_id: i64, justification: &serde_json::Value) -> String {
    let priority = justification["priority"]
        .as_str()
        .or_else(|| justification["priorite"].as_str())
        .unwrap_or("?");
    let quadrant = justification["quadrant"].as_str().unwrap_or("?");
    let score = justification["calculations"]["G"]["total"]
        .as_f64()
        .or_else(|| justification["calculs"]["G"]["total"].as_f64())
        .unwrap_or(0.0);
    format!(
        "# PRIORIS #{task_id} — {}\n\nTâche : {}\nSource : [[{}]]\n\n## Résultat\n\n**{priority}** — quadrant {quadrant} — score {score:.1}/100\n\n## Données\n\n```json\n{}\n```\n\n---\n*Généré par PRIORIS.*\n",
        task.title,
        task.title,
        task.relative_path.trim_end_matches(".md"),
        serde_json::to_string_pretty(justification).unwrap_or_default(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scans_and_excludes_prioris_directory() {
        let directory = tempfile::tempdir().unwrap();
        fs::write(
            directory.path().join("Inbox.md"),
            "- [ ] Faire quelque chose 📅 2030-01-01\n",
        )
        .unwrap();
        fs::create_dir(directory.path().join("PRIORIS")).unwrap();
        fs::write(directory.path().join("PRIORIS/1.md"), "- [ ] Ignore me\n").unwrap();
        let tasks = find_unprioritized(directory.path(), "PRIORIS");
        assert_eq!(tasks.len(), 1);
        assert_eq!(tasks[0].title, "Faire quelque chose");
        assert_eq!(tasks[0].due.as_deref(), Some("2030-01-01"));
    }
}
