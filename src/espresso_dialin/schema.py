"""Explicit, transactional SQLite schema initialization and v1 to v2 migration."""

import sqlite3

SCHEMA_VERSION = 2

LIFECYCLE_SCHEMA = """
CREATE TABLE shot_resolutions (
    shot_id TEXT PRIMARY KEY REFERENCES shots(id),
    status TEXT NOT NULL CHECK(status IN ('ABANDONED', 'INVALIDATED')),
    recorded_at TEXT NOT NULL,
    reason TEXT NOT NULL CHECK(length(trim(reason)) > 0)
);
CREATE TRIGGER resolution_update BEFORE UPDATE ON shot_resolutions
BEGIN SELECT RAISE(ABORT, 'resolution records are immutable'); END;
CREATE TRIGGER resolution_delete BEFORE DELETE ON shot_resolutions
BEGIN SELECT RAISE(ABORT, 'resolution records are immutable'); END;
CREATE TRIGGER resolution_transition BEFORE INSERT ON shot_resolutions
WHEN NOT EXISTS (SELECT 1 FROM shots WHERE id = NEW.shot_id)
  OR (NEW.status = 'ABANDONED' AND EXISTS
      (SELECT 1 FROM shots WHERE id = NEW.shot_id AND completed_at IS NOT NULL))
  OR EXISTS (SELECT 1 FROM shots WHERE id = NEW.shot_id AND
      julianday(NEW.recorded_at) < julianday(coalesce(completed_at,
                                                   grinding_recorded_at, created_at)))
BEGIN SELECT RAISE(ABORT, 'invalid lifecycle transition or timestamp'); END;
CREATE TRIGGER resolved_shot_update BEFORE UPDATE ON shots
WHEN EXISTS (SELECT 1 FROM shot_resolutions WHERE shot_id = OLD.id)
BEGIN SELECT RAISE(ABORT, 'resolved shot evidence is immutable'); END;
CREATE TRIGGER one_pending_shot BEFORE INSERT ON shots
WHEN EXISTS (SELECT 1 FROM shots s LEFT JOIN shot_resolutions r ON r.shot_id = s.id
             WHERE s.session_id = NEW.session_id AND s.completed_at IS NULL
             AND r.shot_id IS NULL)
BEGIN SELECT RAISE(ABORT, 'session already has a pending shot'); END;
CREATE TRIGGER frozen_grinding BEFORE UPDATE ON shots
WHEN OLD.actual_duration_s IS NOT NULL AND (
    NEW.actual_setting IS NOT OLD.actual_setting
    OR NEW.actual_duration_s IS NOT OLD.actual_duration_s
    OR NEW.grinder_output_g IS NOT OLD.grinder_output_g
    OR NEW.correction IS NOT OLD.correction OR NEW.puck_dose_g IS NOT OLD.puck_dose_g
    OR NEW.grinding_recorded_at IS NOT OLD.grinding_recorded_at)
BEGIN SELECT RAISE(ABORT, 'saved grinding evidence is immutable'); END;
CREATE TRIGGER phase_timestamps BEFORE UPDATE ON shots
WHEN (OLD.actual_duration_s IS NULL AND NEW.actual_duration_s IS NOT NULL AND
      (NEW.grinding_recorded_at IS NULL OR
       julianday(NEW.grinding_recorded_at) < julianday(NEW.created_at)))
  OR (NEW.completed_at IS NOT NULL AND
      julianday(NEW.completed_at) < julianday(coalesce(NEW.grinding_recorded_at, NEW.created_at)))
BEGIN SELECT RAISE(ABORT, 'invalid recording timestamp'); END;
CREATE TRIGGER frozen_bag_context BEFORE UPDATE OF bag_opened_date ON sessions
WHEN NEW.bag_opened_date IS NOT OLD.bag_opened_date
BEGIN SELECT RAISE(ABORT, 'session bag context is immutable'); END;
"""


def _execute_schema(db: sqlite3.Connection, script: str) -> None:
    """Execute DDL without executescript's implicit commit of the migration transaction."""
    statement = ""
    for line in script.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            db.execute(statement)
            statement = ""
    if statement.strip():
        raise ValueError("incomplete schema statement")


def migrate_v1_to_v2(db: sqlite3.Connection) -> None:
    """Add only new nullable context/timestamps and immutable lifecycle annotations."""
    db.execute("ALTER TABLE sessions ADD COLUMN bag_opened_date TEXT")
    db.execute("ALTER TABLE shots ADD COLUMN grinding_recorded_at TEXT")
    db.execute("DROP INDEX one_pending_shot")
    _execute_schema(db, LIFECYCLE_SCHEMA)


def initialize(db: sqlite3.Connection) -> None:
    db.execute("BEGIN IMMEDIATE")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        _execute_schema(db, FRESH_SCHEMA)
        _execute_schema(db, LIFECYCLE_SCHEMA)
    elif version == 1:
        migrate_v1_to_v2(db)
    elif version != SCHEMA_VERSION:
        raise ValueError(f"unsupported database schema version: {version}")
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


FRESH_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, bean_id TEXT NOT NULL, bean_name TEXT NOT NULL,
    started_at TEXT NOT NULL, ended_at TEXT, grinder TEXT NOT NULL, machine TEXT NOT NULL,
    roaster TEXT, roast_date TEXT, target_puck_dose_g REAL NOT NULL,
    target_yield_g REAL NOT NULL, target_time_min_s REAL NOT NULL,
    target_time_max_s REAL NOT NULL, bag_opened_date TEXT
);
CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
    target_sequence INTEGER NOT NULL CHECK(target_sequence > 0), created_at TEXT NOT NULL,
    setting TEXT NOT NULL, duration_s REAL NOT NULL CHECK(duration_s > 0),
    target_output_g REAL NOT NULL CHECK(target_output_g > 0),
    strategy_id TEXT NOT NULL, model_version TEXT NOT NULL,
    estimated_rate_g_s REAL, expected_output_g REAL, model_json TEXT,
    selected INTEGER NOT NULL CHECK(selected IN (0, 1)),
    UNIQUE(session_id, target_sequence, strategy_id),
    UNIQUE(id, session_id, target_sequence)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_selected_plan
ON recommendations(session_id, target_sequence) WHERE selected = 1;
CREATE TABLE IF NOT EXISTS shots (
    id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id),
    sequence INTEGER NOT NULL CHECK(sequence > 0), created_at TEXT NOT NULL,
    grinding_recorded_at TEXT, completed_at TEXT, selected_recommendation_id TEXT NOT NULL,
    actual_setting TEXT, actual_duration_s REAL, grinder_output_g REAL,
    correction TEXT CHECK(correction IN ('NONE', 'TO_TARGET', 'MEASURED')),
    puck_dose_g REAL, brew_duration_s REAL, final_yield_g REAL,
    purged_before_shot INTEGER NOT NULL DEFAULT 0,
    obviously_bad_shot INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '',
    UNIQUE(session_id, sequence),
    FOREIGN KEY(selected_recommendation_id, session_id, sequence)
      REFERENCES recommendations(id, session_id, target_sequence)
);
CREATE TRIGGER IF NOT EXISTS frozen_plan_update BEFORE UPDATE ON recommendations
BEGIN SELECT RAISE(ABORT, 'recommendations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS frozen_plan_delete BEFORE DELETE ON recommendations
BEGIN SELECT RAISE(ABORT, 'recommendations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS no_late_plan BEFORE INSERT ON recommendations
WHEN EXISTS (SELECT 1 FROM shots WHERE session_id = NEW.session_id
             AND sequence = NEW.target_sequence)
BEGIN SELECT RAISE(ABORT, 'cannot add predictions after shot creation'); END;
CREATE TRIGGER IF NOT EXISTS selected_plan_link BEFORE INSERT ON shots
WHEN NOT EXISTS (SELECT 1 FROM recommendations WHERE id = NEW.selected_recommendation_id
                 AND selected = 1)
BEGIN SELECT RAISE(ABORT, 'shot must link to selected plan'); END;
CREATE TRIGGER IF NOT EXISTS frozen_shot_context BEFORE UPDATE ON shots
WHEN NEW.id != OLD.id OR NEW.session_id != OLD.session_id OR NEW.sequence != OLD.sequence
  OR NEW.created_at != OLD.created_at
  OR NEW.selected_recommendation_id != OLD.selected_recommendation_id
  OR OLD.completed_at IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'shot context and completed outcomes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS no_shot_delete BEFORE DELETE ON shots
BEGIN SELECT RAISE(ABORT, 'shots must be retained'); END;
CREATE TRIGGER IF NOT EXISTS frozen_session_context BEFORE UPDATE ON sessions
WHEN NEW.id != OLD.id OR NEW.bean_id != OLD.bean_id OR NEW.bean_name != OLD.bean_name
  OR NEW.grinder != OLD.grinder OR NEW.machine != OLD.machine
  OR NEW.started_at != OLD.started_at OR NEW.roaster IS NOT OLD.roaster
  OR NEW.roast_date IS NOT OLD.roast_date
  OR NEW.target_puck_dose_g != OLD.target_puck_dose_g
  OR NEW.target_yield_g != OLD.target_yield_g
  OR NEW.target_time_min_s != OLD.target_time_min_s
  OR NEW.target_time_max_s != OLD.target_time_max_s
BEGIN SELECT RAISE(ABORT, 'session context is immutable'); END;
"""
