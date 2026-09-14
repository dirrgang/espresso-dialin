"""SQLite storage with atomic freezes and append-only completed evidence."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from espresso_dialin.domain import (
    BrewingResult,
    CorrectionMode,
    GrindingResult,
    Plan,
    Session,
    Shot,
    utc_now,
)
from espresso_dialin.dose_control import DoseRecommendation

SCHEMA_VERSION = 1
SCHEMA = """
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
"""


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


class Repository:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise ValueError(f"unsupported database schema version: {version}")
            db.executescript(
                "BEGIN IMMEDIATE;\n" + SCHEMA + f"\nPRAGMA user_version = {SCHEMA_VERSION}; COMMIT;"
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_session(self, session: Session) -> None:
        with self._connection() as db:
            db.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session.id,
                    session.bean_id,
                    session.bean_name,
                    _timestamp(session.started_at),
                    _timestamp(session.ended_at) if session.ended_at else None,
                    session.grinder,
                    session.machine,
                    session.roaster,
                    session.roast_date.isoformat() if session.roast_date else None,
                    session.target_puck_dose_g,
                    session.target_yield_g,
                    session.target_time_min_s,
                    session.target_time_max_s,
                ),
            )

    def sessions(self) -> list[Session]:
        with self._connection() as db:
            rows = db.execute("SELECT * FROM sessions ORDER BY started_at, id").fetchall()
        return [
            Session(
                **(
                    dict(row)
                    | {
                        "started_at": datetime.fromisoformat(row["started_at"]),
                        "ended_at": datetime.fromisoformat(row["ended_at"])
                        if row["ended_at"]
                        else None,
                        "roast_date": date.fromisoformat(row["roast_date"])
                        if row["roast_date"]
                        else None,
                    }
                )
            )
            for row in rows
        ]

    def session(self, session_id: str) -> Session:
        for session in self.sessions():
            if session.id == session_id:
                return session
        raise ValueError("unknown session")

    def end_session(self, session_id: str) -> None:
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM shots WHERE session_id=? AND completed_at IS NULL", (session_id,)
            ).fetchone():
                raise ValueError("complete the pending shot before ending the session")
            cursor = db.execute(
                "UPDATE sessions SET ended_at=? WHERE id=? AND ended_at IS NULL",
                (_timestamp(utc_now()), session_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("unknown or ended session")

    def plans(self, session_id: str, sequence: int) -> list[Plan]:
        with self._connection() as db:
            rows = db.execute(
                "SELECT * FROM recommendations WHERE session_id=? AND target_sequence=? "
                "ORDER BY strategy_id",
                (session_id, sequence),
            ).fetchall()
        return [
            Plan(
                id=row["id"],
                session_id=row["session_id"],
                target_sequence=row["target_sequence"],
                created_at=datetime.fromisoformat(row["created_at"]),
                setting=row["setting"],
                duration_s=row["duration_s"],
                target_output_g=row["target_output_g"],
                selected=bool(row["selected"]),
                model=DoseRecommendation.from_dict(json.loads(row["model_json"]))
                if row["model_json"]
                else None,
            )
            for row in rows
        ]

    def shots(self, session_id: str) -> list[Shot]:
        with self._connection() as db:
            rows = db.execute(
                "SELECT * FROM shots WHERE session_id=? ORDER BY sequence", (session_id,)
            ).fetchall()
        return [self._shot(row) for row in rows]

    @staticmethod
    def _shot(row: sqlite3.Row) -> Shot:
        return Shot(
            id=row["id"],
            session_id=row["session_id"],
            sequence=row["sequence"],
            created_at=datetime.fromisoformat(row["created_at"]),
            selected_recommendation_id=row["selected_recommendation_id"],
            grinding=GrindingResult(
                setting=row["actual_setting"],
                duration_s=row["actual_duration_s"],
                output_g=row["grinder_output_g"],
                correction=CorrectionMode(row["correction"]),
                puck_dose_g=row["puck_dose_g"],
            )
            if row["actual_duration_s"] is not None
            else None,
            brewing=BrewingResult(
                duration_s=row["brew_duration_s"],
                yield_g=row["final_yield_g"],
                purged_before_shot=bool(row["purged_before_shot"]),
                obviously_bad_shot=bool(row["obviously_bad_shot"]),
                notes=row["notes"],
            )
            if row["completed_at"]
            else None,
            completed_at=datetime.fromisoformat(row["completed_at"])
            if row["completed_at"]
            else None,
        )

    def freeze(self, session_id: str, sequence: int, plans: Sequence[Plan]) -> Shot:
        """Atomically persist every candidate and exactly one choice before any outcome."""
        selected = [plan for plan in plans if plan.selected]
        if len(selected) != 1:
            raise ValueError("exactly one plan must be selected")
        if any(p.session_id != session_id or p.target_sequence != sequence for p in plans):
            raise ValueError("recommendation linked to wrong session/shot")
        if len({p.setting for p in plans}) != 1 or len({p.created_at for p in plans}) != 1:
            raise ValueError("candidate context must agree")
        shot = Shot(
            id=str(uuid4()),
            session_id=session_id,
            sequence=sequence,
            created_at=selected[0].created_at,
            selected_recommendation_id=selected[0].id,
        )
        if shot.created_at > utc_now():
            raise ValueError("plan creation cannot be in the future")
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            session = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if session is None or session["ended_at"] is not None:
                raise ValueError("unknown or ended session")
            rows = db.execute(
                "SELECT * FROM shots WHERE session_id=? ORDER BY sequence", (session_id,)
            ).fetchall()
            if sequence != len(rows) + 1 or any(r["completed_at"] is None for r in rows):
                raise ValueError("stale sequence or pending shot; reload before freezing")
            if any(datetime.fromisoformat(r["completed_at"]) >= shot.created_at for r in rows):
                raise ValueError("plan must follow earlier completed shots")
            sources = {row["id"]: row for row in rows}
            for plan in plans:
                if plan.target_output_g != session["target_puck_dose_g"]:
                    raise ValueError("plan target differs from session target")
                if plan.created_at < datetime.fromisoformat(session["started_at"]):
                    raise ValueError("plan predates session")
                model = plan.model
                if model:
                    if model.bean_id != session["bean_id"]:
                        raise ValueError("model bean differs from session")
                    for source_id in model.observation_ids:
                        source = sources.get(source_id)
                        if (
                            source is None
                            or source["actual_setting"] != plan.setting
                            or datetime.fromisoformat(source["completed_at"]) >= plan.created_at
                        ):
                            raise ValueError(
                                "model source must be a prior compatible completed shot"
                            )
                db.execute(
                    "INSERT INTO recommendations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        plan.id,
                        session_id,
                        sequence,
                        _timestamp(plan.created_at),
                        plan.setting,
                        plan.duration_s,
                        plan.target_output_g,
                        plan.strategy_id,
                        model.model_version if model else "1",
                        model.estimated_rate_g_s if model else None,
                        model.expected_output_g if model else None,
                        model.to_json() if model else None,
                        int(plan.selected),
                    ),
                )
            db.execute(
                "INSERT INTO shots (id, session_id, sequence, created_at, "
                "selected_recommendation_id) VALUES (?, ?, ?, ?, ?)",
                (
                    shot.id,
                    session_id,
                    sequence,
                    _timestamp(shot.created_at),
                    shot.selected_recommendation_id,
                ),
            )
        return shot

    def save_grinding(self, shot_id: str, result: GrindingResult) -> None:
        with self._connection() as db:
            cursor = db.execute(
                "UPDATE shots SET actual_setting=?, actual_duration_s=?, grinder_output_g=?, "
                "correction=?, puck_dose_g=? WHERE id=? AND completed_at IS NULL "
                "AND actual_duration_s IS NULL",
                (
                    result.setting,
                    result.duration_s,
                    result.output_g,
                    result.correction.value,
                    result.puck_dose_g,
                    shot_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("unknown shot or grinding result already saved")

    def complete(self, shot_id: str, result: BrewingResult) -> None:
        with self._connection() as db:
            cursor = db.execute(
                "UPDATE shots SET brew_duration_s=?, final_yield_g=?, purged_before_shot=?, "
                "obviously_bad_shot=?, notes=?, completed_at=? "
                "WHERE id=? AND actual_duration_s IS NOT NULL AND completed_at IS NULL",
                (
                    result.duration_s,
                    result.yield_g,
                    int(result.purged_before_shot),
                    int(result.obviously_bad_shot),
                    result.notes,
                    _timestamp(utc_now()),
                    shot_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("shot must have grinding results and not already be completed")
