-- Original schema from Phase 3, commit 7c6f496. No runtime data.

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY, bean_id TEXT NOT NULL, bean_name TEXT NOT NULL,
    started_at TEXT NOT NULL, ended_at TEXT, grinder TEXT NOT NULL, machine TEXT NOT NULL,
    roaster TEXT, roast_date TEXT, target_puck_dose_g REAL NOT NULL,
    target_yield_g REAL NOT NULL, target_time_min_s REAL NOT NULL,
    target_time_max_s REAL NOT NULL
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
    completed_at TEXT, selected_recommendation_id TEXT NOT NULL,
    actual_setting TEXT, actual_duration_s REAL, grinder_output_g REAL,
    correction TEXT CHECK(correction IN ('NONE', 'TO_TARGET', 'MEASURED')),
    puck_dose_g REAL, brew_duration_s REAL, final_yield_g REAL,
    purged_before_shot INTEGER NOT NULL DEFAULT 0,
    obviously_bad_shot INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '',
    UNIQUE(session_id, sequence),
    FOREIGN KEY(selected_recommendation_id, session_id, sequence)
      REFERENCES recommendations(id, session_id, target_sequence)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_shot
ON shots(session_id) WHERE completed_at IS NULL;
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

PRAGMA user_version = 1;
