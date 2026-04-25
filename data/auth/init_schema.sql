-- 地铁出行指南系统 — 用户与查询历史
-- 运行：由 scripts/init_auth_db.py 或首次启动时 src/auth_db.py 自动应用

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
  role          TEXT NOT NULL DEFAULT 'passenger',
  avatar        TEXT NOT NULL DEFAULT '🙂',
  password_hash TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS query_history (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id              INTEGER NOT NULL,
  from_station         TEXT NOT NULL,
  to_station           TEXT NOT NULL,
  strategy             TEXT NOT NULL,
  total_time_minutes   REAL,
  transfer_count       INTEGER,
  estimated_fare_yuan  INTEGER,
  created_at           TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_query_history_user_time
  ON query_history (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_users_username
  ON users (username);

CREATE TABLE IF NOT EXISTS feedback (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id         INTEGER NOT NULL,
  from_station    TEXT,
  to_station      TEXT,
  strategy        TEXT,
  issue_type      TEXT NOT NULL,
  severity        TEXT NOT NULL DEFAULT 'medium',
  content         TEXT NOT NULL,
  reproducible    INTEGER NOT NULL DEFAULT 0,
  contact         TEXT,
  status          TEXT NOT NULL DEFAULT 'pending',
  resolution_note TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_feedback_user_time
  ON feedback (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feedback_status_time
  ON feedback (status, created_at DESC);
