-- PRIORIS — schéma SQLite (§2.3, §9). Définitif dès le MVP.
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  label TEXT NOT NULL,
  cible_hebdo_pct REAL DEFAULT 0,
  protegee INTEGER DEFAULT 0
);

INSERT OR IGNORE INTO categories (code, label, cible_hebdo_pct, protegee) VALUES
  ('travail',  'Travail',            55, 0),
  ('carriere', 'Carrière',           10, 1),
  ('sante',    'Santé',              10, 1),
  ('finances', 'Finances',            5, 1),
  ('ia',       'IA',                 10, 0),
  ('formation','Formation',           5, 0),
  ('famille',  'Famille',             0, 1),
  ('loisirs',  'Loisirs',             0, 0),
  ('perso',    'Projets personnels',  5, 1);

CREATE TABLE IF NOT EXISTS goals (
  id INTEGER PRIMARY KEY,
  category_id INTEGER REFERENCES categories(id),
  titre TEXT NOT NULL,
  description TEXT DEFAULT '',
  horizon TEXT DEFAULT '',
  statut TEXT DEFAULT 'actif',          -- actif|atteint|suspendu
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY,
  titre TEXT NOT NULL,
  description TEXT DEFAULT '',
  category_id INTEGER REFERENCES categories(id),
  sujet_tag TEXT DEFAULT '',
  source TEXT DEFAULT 'telegram',       -- telegram|obsidian
  goal_id INTEGER REFERENCES goals(id),
  obsidian_path TEXT,
  estimation TEXT,                      -- enum EST
  estimation_min INTEGER,
  effort INTEGER DEFAULT 2,             -- EFF 1..3
  deadline_reelle TEXT,
  delegable INTEGER DEFAULT 0,
  statut TEXT DEFAULT 'inbox',          -- inbox|evaluee|planifiee|faite|reportee|abandonnee|deleguee
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  done_at TEXT
);

CREATE TABLE IF NOT EXISTS interviews (
  id INTEGER PRIMARY KEY,
  task_id INTEGER NOT NULL REFERENCES tasks(id),
  started_at TEXT DEFAULT (datetime('now')),
  finished_at TEXT,
  canal TEXT DEFAULT 'telegram',
  mode TEXT DEFAULT 'express',
  statut TEXT DEFAULT 'en_cours'        -- en_cours|termine|abandonne
);

CREATE TABLE IF NOT EXISTS answers (
  id INTEGER PRIMARY KEY,
  interview_id INTEGER NOT NULL REFERENCES interviews(id),
  axe TEXT NOT NULL,
  valeur INTEGER,
  valeur_brute_texte TEXT DEFAULT '',
  incertitude INTEGER DEFAULT 0,
  asked_at TEXT DEFAULT (datetime('now'))
);

-- Append-only : jamais d'UPDATE ni de DELETE (§10).
CREATE TABLE IF NOT EXISTS evaluations (
  id INTEGER PRIMARY KEY,
  task_id INTEGER NOT NULL REFERENCES tasks(id),
  interview_id INTEGER REFERENCES interviews(id),
  version_algo INTEGER NOT NULL,
  score_urgence REAL NOT NULL,
  score_importance REAL NOT NULL,
  score_global REAL NOT NULL,
  quadrant TEXT NOT NULL,
  priorite TEXT NOT NULL,
  priorite_subjective TEXT,
  provisoire INTEGER DEFAULT 0,
  pepite INTEGER DEFAULT 0,
  justification_json TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bias_flags (
  id INTEGER PRIMARY KEY,
  evaluation_id INTEGER NOT NULL REFERENCES evaluations(id),
  type_biais TEXT NOT NULL,
  gravite TEXT NOT NULL,
  preuve_json TEXT NOT NULL,
  message TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contradictions (
  id INTEGER PRIMARY KEY,
  interview_id INTEGER NOT NULL REFERENCES interviews(id),
  regle TEXT NOT NULL,
  axe_a TEXT, axe_b TEXT,
  resolue INTEGER DEFAULT 0,
  resolution_note TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS plans (
  id INTEGER PRIMARY KEY,
  date_plan TEXT NOT NULL,
  horizon TEXT DEFAULT 'jour',
  scenario TEXT DEFAULT 'equilibre',
  capacite_min INTEGER NOT NULL,
  energie INTEGER,
  retenu INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plan_items (
  id INTEGER PRIMARY KEY,
  plan_id INTEGER NOT NULL REFERENCES plans(id),
  task_id INTEGER NOT NULL REFERENCES tasks(id),
  ordre INTEGER NOT NULL,
  duree_min INTEGER NOT NULL,
  entamer INTEGER DEFAULT 0,
  fait INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS time_log (
  id INTEGER PRIMARY KEY,
  task_id INTEGER REFERENCES tasks(id),
  category_id INTEGER REFERENCES categories(id),
  date TEXT NOT NULL,
  minutes INTEGER NOT NULL,
  energie INTEGER,
  source TEXT DEFAULT 'declaratif'
);

CREATE TABLE IF NOT EXISTS outcomes (
  id INTEGER PRIMARY KEY,
  task_id INTEGER NOT NULL REFERENCES tasks(id),
  consequence_reelle INTEGER NOT NULL,   -- 0 aucune·1 gêne·2 problème·3 grave
  delai_jours INTEGER,
  note TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS task_notes (
  id INTEGER PRIMARY KEY,
  task_id INTEGER NOT NULL REFERENCES tasks(id),
  source TEXT DEFAULT 'manual',
  note TEXT NOT NULL,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY,
  date TEXT NOT NULL,
  balance_json TEXT NOT NULL,
  retard_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS config (
  cle TEXT PRIMARY KEY,
  valeur TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_calls (
  id INTEGER PRIMARY KEY,
  type TEXT NOT NULL,
  modele TEXT NOT NULL,
  tokens INTEGER, cout REAL, latence_ms INTEGER,
  valide INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now'))
);

-- V0.6 : mémoire de décision (créée dès maintenant, inutilisée par le MVP).
CREATE TABLE IF NOT EXISTS task_embeddings (
  task_id INTEGER PRIMARY KEY REFERENCES tasks(id),
  vecteur BLOB,
  modele TEXT
);

CREATE INDEX IF NOT EXISTS idx_eval_task ON evaluations(task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_statut ON tasks(statut);
CREATE INDEX IF NOT EXISTS idx_timelog_date ON time_log(date, category_id);

CREATE VIEW IF NOT EXISTS v_task_current AS
SELECT t.*, c.code AS cat_code, e.score_global, e.priorite, e.quadrant,
       e.pepite, e.provisoire, e.created_at AS evalue_le
FROM tasks t
LEFT JOIN categories c ON c.id = t.category_id
JOIN evaluations e ON e.id = (
  SELECT id FROM evaluations WHERE task_id = t.id
  ORDER BY created_at DESC, id DESC LIMIT 1);
