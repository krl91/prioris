use std::{collections::HashMap, path::Path};

use rusqlite::{Connection, OptionalExtension, params};

use crate::core::{Axis, DayPlan, Effort, Estimate, PlanTask, Priority, ScoreResult};

const SCHEMA: &str = include_str!("../../prioris/store/schema.sql");

#[derive(Debug, Clone)]
pub struct Category {
    pub code: String,
    pub label: String,
}

#[derive(Debug, Clone)]
pub struct TaskRow {
    pub id: i64,
    pub title: String,
    pub status: String,
    pub category: String,
    pub priority: Option<Priority>,
    pub global_score: Option<f64>,
    pub quadrant: Option<String>,
    pub deadline: Option<String>,
}

#[derive(Debug, Clone)]
pub struct GoalRow {
    pub id: i64,
    pub title: String,
    pub category: String,
    pub task_count: i64,
    pub done_count: i64,
}

pub struct Store {
    connection: Connection,
}

impl Store {
    pub fn open(path: impl AsRef<Path>) -> rusqlite::Result<Self> {
        let connection = Connection::open(path)?;
        connection.pragma_update(None, "foreign_keys", true)?;
        connection.execute_batch(SCHEMA)?;
        Ok(Self { connection })
    }

    pub fn connection(&self) -> &Connection {
        &self.connection
    }

    pub fn create_task(
        &self,
        title: &str,
        category_code: &str,
        deadline: Option<&str>,
        source: &str,
        obsidian_path: Option<&str>,
    ) -> rusqlite::Result<i64> {
        let category_id = self
            .connection
            .query_row(
                "SELECT id FROM categories WHERE code=?1",
                [category_code],
                |row| row.get::<_, i64>(0),
            )
            .optional()?;
        self.connection.execute(
            "INSERT INTO tasks (titre, category_id, deadline_reelle, source, obsidian_path) VALUES (?1,?2,?3,?4,?5)",
            params![title, category_id, deadline, source, obsidian_path],
        )?;
        Ok(self.connection.last_insert_rowid())
    }

    pub fn categories(&self) -> rusqlite::Result<Vec<Category>> {
        let mut statement = self
            .connection
            .prepare("SELECT code,label FROM categories ORDER BY id")?;
        statement
            .query_map([], |row| {
                Ok(Category {
                    code: row.get(0)?,
                    label: row.get(1)?,
                })
            })?
            .collect()
    }

    pub fn create_category(&self, label: &str) -> rusqlite::Result<String> {
        let clean = label.split_whitespace().collect::<Vec<_>>().join(" ");
        if clean.is_empty() {
            return Err(rusqlite::Error::InvalidParameterName(
                "empty category".to_owned(),
            ));
        }
        let base = category_code(&clean);
        if base.is_empty() {
            return Err(rusqlite::Error::InvalidParameterName(
                "invalid category".to_owned(),
            ));
        }
        let mut candidate = base.clone();
        let mut suffix = 2;
        loop {
            let existing = self
                .connection
                .query_row(
                    "SELECT label FROM categories WHERE code=?1",
                    [&candidate],
                    |row| row.get::<_, String>(0),
                )
                .optional()?;
            match existing {
                Some(existing) if existing.eq_ignore_ascii_case(&clean) => return Ok(candidate),
                Some(_) => {
                    candidate = format!("{base}_{suffix}");
                    suffix += 1;
                }
                None => break,
            }
        }
        self.connection.execute(
            "INSERT INTO categories(code,label) VALUES (?1,?2)",
            params![candidate, clean],
        )?;
        Ok(candidate)
    }

    pub fn save_evaluation(
        &self,
        task_id: i64,
        result: &ScoreResult,
        subjective: Option<Priority>,
        estimate: Estimate,
        effort: Effort,
    ) -> rusqlite::Result<i64> {
        self.connection.execute(
            "INSERT INTO evaluations (task_id, interview_id, version_algo, score_urgence, score_importance, score_global, quadrant, priorite, priorite_subjective, provisoire, pepite, justification_json) VALUES (?1,NULL,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11)",
            params![
                task_id,
                result.justification["version_algo"].as_i64().unwrap_or(1),
                result.urgency,
                result.importance,
                result.global,
                result.quadrant,
                result.priority.as_str(),
                subjective.map(Priority::as_str),
                result.provisional,
                result.gem,
                result.justification.to_string(),
            ],
        )?;
        let evaluation_id = self.connection.last_insert_rowid();
        self.connection.execute(
            "UPDATE tasks SET statut='evaluee', estimation=?1, estimation_min=?2, effort=?3, updated_at=datetime('now') WHERE id=?4",
            params![estimate.db_value(), estimate.minutes(), effort as u8, task_id],
        )?;
        Ok(evaluation_id)
    }

    pub fn tasks(&self) -> rusqlite::Result<Vec<TaskRow>> {
        let mut statement = self.connection.prepare(
            "SELECT t.id,t.titre,t.statut,COALESCE(c.label,''),e.priorite,e.score_global,e.quadrant,t.deadline_reelle FROM tasks t LEFT JOIN categories c ON c.id=t.category_id LEFT JOIN evaluations e ON e.id=(SELECT id FROM evaluations WHERE task_id=t.id ORDER BY created_at DESC,id DESC LIMIT 1) WHERE t.statut!='abandonnee' ORDER BY CASE e.priorite WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 WHEN 'P4' THEN 4 ELSE 5 END,e.score_global DESC,t.id",
        )?;
        statement
            .query_map([], |row| {
                let priority = row
                    .get::<_, Option<String>>(4)?
                    .and_then(|value| value.parse().ok());
                Ok(TaskRow {
                    id: row.get(0)?,
                    title: row.get(1)?,
                    status: row.get(2)?,
                    category: row.get(3)?,
                    priority,
                    global_score: row.get(5)?,
                    quadrant: row.get(6)?,
                    deadline: row.get(7)?,
                })
            })?
            .collect()
    }

    pub fn current_tasks_for_plan(
        &self,
        today: chrono::NaiveDate,
    ) -> rusqlite::Result<Vec<PlanTask>> {
        let mut statement = self.connection.prepare(
            "SELECT t.id,t.titre,e.priorite,e.score_global,t.estimation_min,t.effort,COALESCE(c.label,''),e.pepite,t.deadline_reelle FROM tasks t JOIN evaluations e ON e.id=(SELECT id FROM evaluations WHERE task_id=t.id ORDER BY created_at DESC,id DESC LIMIT 1) LEFT JOIN categories c ON c.id=t.category_id WHERE t.statut IN ('evaluee','planifiee') ORDER BY t.id",
        )?;
        statement
            .query_map([], |row| {
                let deadline = row.get::<_, Option<String>>(8)?;
                let deadline_days = deadline
                    .as_deref()
                    .and_then(|value| chrono::NaiveDate::parse_from_str(value, "%Y-%m-%d").ok())
                    .map(|date| (date - today).num_days());
                let priority_text: String = row.get(2)?;
                Ok(PlanTask {
                    task_id: row.get(0)?,
                    title: row.get(1)?,
                    priority: priority_text.parse().unwrap_or(Priority::P4),
                    global_score: row.get(3)?,
                    estimate_minutes: row.get::<_, Option<u32>>(4)?,
                    effort: Effort::from_u8(row.get::<_, u8>(5)?),
                    category: row.get(6)?,
                    gem: row.get(7)?,
                    deadline_days,
                    deadline,
                })
            })?
            .collect()
    }

    pub fn save_plan(
        &self,
        date: &str,
        capacity: u32,
        energy: u8,
        plan: &DayPlan,
    ) -> rusqlite::Result<i64> {
        self.connection.execute(
            "INSERT INTO plans(date_plan,capacite_min,energie) VALUES (?1,?2,?3)",
            params![date, capacity, energy],
        )?;
        let plan_id = self.connection.last_insert_rowid();
        for (index, item) in plan.items.iter().enumerate() {
            self.connection.execute(
                "INSERT INTO plan_items(plan_id,task_id,ordre,duree_min,entamer) VALUES (?1,?2,?3,?4,?5)",
                params![plan_id, item.task.task_id, (index + 1) as i64, item.duration_minutes, item.partial],
            )?;
            self.connection.execute(
                "UPDATE tasks SET statut='planifiee' WHERE id=?1 AND statut='evaluee'",
                [item.task.task_id],
            )?;
        }
        Ok(plan_id)
    }

    pub fn mark_done(&self, task_id: i64) -> rusqlite::Result<bool> {
        Ok(self.connection.execute(
            "UPDATE tasks SET statut='faite',done_at=datetime('now'),updated_at=datetime('now') WHERE id=?1",
            [task_id],
        )? > 0)
    }

    pub fn create_goal(&self, title: &str, category_code: &str) -> rusqlite::Result<i64> {
        let category_id = self
            .connection
            .query_row(
                "SELECT id FROM categories WHERE code=?1",
                [category_code],
                |row| row.get::<_, i64>(0),
            )
            .optional()?;
        self.connection.execute(
            "INSERT INTO goals(titre,category_id) VALUES (?1,?2)",
            params![title, category_id],
        )?;
        Ok(self.connection.last_insert_rowid())
    }

    pub fn goals(&self) -> rusqlite::Result<Vec<GoalRow>> {
        let mut statement = self.connection.prepare(
            "SELECT g.id,g.titre,COALESCE(c.label,''),(SELECT COUNT(*) FROM tasks WHERE goal_id=g.id),(SELECT COUNT(*) FROM tasks WHERE goal_id=g.id AND statut='faite') FROM goals g LEFT JOIN categories c ON c.id=g.category_id WHERE g.statut='actif' ORDER BY g.id",
        )?;
        statement
            .query_map([], |row| {
                Ok(GoalRow {
                    id: row.get(0)?,
                    title: row.get(1)?,
                    category: row.get(2)?,
                    task_count: row.get(3)?,
                    done_count: row.get(4)?,
                })
            })?
            .collect()
    }

    pub fn add_task_note(&self, task_id: i64, source: &str, note: &str) -> rusqlite::Result<i64> {
        self.connection.execute(
            "INSERT INTO task_notes(task_id,source,note) VALUES (?1,?2,?3)",
            params![task_id, source, note],
        )?;
        Ok(self.connection.last_insert_rowid())
    }

    pub fn latest_axes(&self, task_id: i64) -> rusqlite::Result<Option<HashMap<Axis, u8>>> {
        let text = self.connection.query_row(
            "SELECT justification_json FROM evaluations WHERE task_id=?1 ORDER BY created_at DESC,id DESC LIMIT 1",
            [task_id],
            |row| row.get::<_, String>(0),
        ).optional()?;
        let Some(text) = text else { return Ok(None) };
        let json: serde_json::Value = serde_json::from_str(&text).unwrap_or_default();
        let mut result = HashMap::new();
        for axis in Axis::ALL {
            let value = json["axes"][axis.code()]["valeur"]
                .as_u64()
                .or_else(|| json["axes"][axis.code()]["value"].as_u64());
            if let Some(value) = value {
                result.insert(axis, value as u8);
            }
        }
        Ok((result.len() == Axis::ALL.len()).then_some(result))
    }
}

fn category_code(label: &str) -> String {
    let mut code = String::new();
    for character in label.trim().to_lowercase().chars() {
        let replacement = match character {
            'à' | 'á' | 'â' | 'ä' => 'a',
            'ç' => 'c',
            'è' | 'é' | 'ê' | 'ë' => 'e',
            'ì' | 'í' | 'î' | 'ï' => 'i',
            'ñ' => 'n',
            'ò' | 'ó' | 'ô' | 'ö' => 'o',
            'ù' | 'ú' | 'û' | 'ü' => 'u',
            character if character.is_ascii_alphanumeric() => character,
            _ => '_',
        };
        if replacement != '_' || !code.ends_with('_') {
            code.push(replacement);
        }
    }
    code.trim_matches('_').to_owned()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn creates_persistent_custom_categories() {
        let store = Store::open(":memory:").unwrap();
        let code = store.create_category("Maison & Jardin").unwrap();
        assert_eq!(code, "maison_jardin");
        assert!(
            store
                .categories()
                .unwrap()
                .iter()
                .any(|category| category.code == code)
        );
    }
}
