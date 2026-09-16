"""Narrow repair for one explicitly identified pre-grind invalidation."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from espresso_dialin.schema import (
    CONFIRMED_NON_EXECUTION_TRIGGER,
    RESOLUTION_UPDATE_TRIGGER,
    SCHEMA_VERSION,
)

TARGET_QUERY = """SELECT
    s.id AS shot_id,
    s.session_id,
    s.sequence,
    s.created_at AS plan_frozen_at,
    s.selected_recommendation_id,
    p.setting AS planned_setting,
    p.duration_s AS planned_duration_s,
    r.status AS resolution_status,
    r.recorded_at AS resolution_recorded_at,
    r.reason AS resolution_reason,
    r.no_physical_grinding_confirmed,
    s.actual_setting,
    s.actual_duration_s,
    s.grinder_output_g,
    s.correction,
    s.puck_dose_g,
    s.grinding_recorded_at,
    s.brew_duration_s,
    s.final_yield_g,
    s.completed_at,
    s.purged_before_shot,
    s.obviously_bad_shot,
    s.notes
FROM shots s
JOIN recommendations p ON p.id = s.selected_recommendation_id
JOIN shot_resolutions r ON r.shot_id = s.id
WHERE s.session_id = ? AND s.id = ?"""

NULL_EVIDENCE_FIELDS = (
    "actual_setting",
    "actual_duration_s",
    "grinder_output_g",
    "correction",
    "puck_dose_g",
    "grinding_recorded_at",
    "brew_duration_s",
    "final_yield_g",
    "completed_at",
)


def _normalize_sql(value: str) -> str:
    return " ".join(value.strip().rstrip(";").split()).casefold()


def _read_only_uri(path: Path) -> str:
    return f"{path.resolve().as_uri()}?mode=ro"


def _target(db: sqlite3.Connection, session_id: str, shot_id: str) -> sqlite3.Row:
    row = db.execute(TARGET_QUERY, (session_id, shot_id)).fetchone()
    if row is None:
        raise ValueError("no resolution matches the explicit session and shot IDs")
    return cast(sqlite3.Row, row)


def _verified_trigger_sql(db: sqlite3.Connection, name: str, expected: str) -> str:
    rows = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
        (name,),
    ).fetchall()
    if len(rows) != 1 or rows[0][0] is None:
        raise ValueError(f"expected {name} trigger is missing")
    actual = str(rows[0][0])
    if _normalize_sql(actual) != _normalize_sql(expected):
        raise ValueError(f"{name} trigger definition is not the expected schema-v3 guard")
    return actual


def _validate_target(db: sqlite3.Connection, row: sqlite3.Row) -> None:
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        raise ValueError(f"repair requires schema version {SCHEMA_VERSION}, found {version}")
    if row["resolution_status"] != "INVALIDATED":
        raise ValueError("target resolution is not currently INVALIDATED")
    if row["no_physical_grinding_confirmed"] is not None:
        raise ValueError("target already carries a non-execution confirmation")
    unexpected = [name for name in NULL_EVIDENCE_FIELDS if row[name] is not None]
    if unexpected:
        raise ValueError(f"target contains physical evidence in: {', '.join(unexpected)}")
    if row["purged_before_shot"] or row["obviously_bad_shot"] or row["notes"]:
        raise ValueError("target contains brew metadata despite having no completed brew result")
    if not str(row["resolution_reason"]).strip() or not str(row["resolution_recorded_at"]).strip():
        raise ValueError("original resolution metadata is incomplete")
    _verified_trigger_sql(db, "resolution_update", RESOLUTION_UPDATE_TRIGGER)
    _verified_trigger_sql(
        db,
        "confirmed_non_execution_insert",
        CONFIRMED_NON_EXECUTION_TRIGGER,
    )


def inspect_target(database: Path, session_id: str, shot_id: str) -> dict[str, Any]:
    """Return the exact candidate after validating every repair precondition."""
    with sqlite3.connect(_read_only_uri(database), uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        row = _target(db, session_id, shot_id)
        _validate_target(db, row)
        return dict(row)


def _backup(database: Path, now: datetime) -> Path:
    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    backup = database.with_name(f"{database.stem}.pregrind-repair-{stamp}{database.suffix}")
    if backup.exists():
        raise FileExistsError(f"refusing to overwrite backup: {backup}")
    with (
        sqlite3.connect(_read_only_uri(database), uri=True) as source,
        sqlite3.connect(backup) as destination,
    ):
        source.backup(destination)
        integrity = destination.execute("PRAGMA integrity_check").fetchall()
        foreign_keys = destination.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != [("ok",)] or foreign_keys:
            raise sqlite3.IntegrityError("backup did not pass SQLite integrity checks")
    return backup


def _audit_reason(row: sqlite3.Row, repaired_at: datetime) -> str:
    original_reason = json.dumps(row["resolution_reason"], ensure_ascii=False)
    return (
        f"Maintenance correction at {repaired_at.astimezone(UTC).isoformat()}: "
        "operator explicitly confirmed no physical grinding occurred. "
        "Original resolution: "
        f"status={row['resolution_status']}; "
        f"recorded_at={row['resolution_recorded_at']}; reason={original_reason}."
    )


def apply_repair(
    database: Path,
    session_id: str,
    shot_id: str,
    *,
    confirmed_no_physical_grinding: bool,
    now: datetime | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Back up and atomically reclassify one verified resolution."""
    if not confirmed_no_physical_grinding:
        raise ValueError("explicit confirmation of no physical grinding is required")
    repaired_at = now or datetime.now(UTC)
    candidate = inspect_target(database, session_id, shot_id)
    backup = _backup(database, repaired_at)

    db = sqlite3.connect(database, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        db.execute("BEGIN IMMEDIATE")
        row = _target(db, session_id, shot_id)
        _validate_target(db, row)
        trigger_sql = _verified_trigger_sql(db, "resolution_update", RESOLUTION_UPDATE_TRIGGER)
        db.execute("DROP TRIGGER resolution_update")
        cursor = db.execute(
            "UPDATE shot_resolutions SET status='ABANDONED', reason=?, "
            "no_physical_grinding_confirmed=1 "
            "WHERE shot_id=? AND status='INVALIDATED' "
            "AND no_physical_grinding_confirmed IS NULL",
            (_audit_reason(row, repaired_at), shot_id),
        )
        if cursor.rowcount != 1:
            raise sqlite3.IntegrityError("target resolution changed before repair")
        db.execute(trigger_sql)
        _verified_trigger_sql(db, "resolution_update", RESOLUTION_UPDATE_TRIGGER)
        _verified_trigger_sql(
            db,
            "confirmed_non_execution_insert",
            CONFIRMED_NON_EXECUTION_TRIGGER,
        )
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise sqlite3.IntegrityError("foreign-key check failed after repair")
        if [result[0] for result in db.execute("PRAGMA integrity_check")] != ["ok"]:
            raise sqlite3.IntegrityError("integrity check failed after repair")
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()

    corrected = dict(inspect_corrected(database, session_id, shot_id))
    if candidate["resolution_recorded_at"] != corrected["resolution_recorded_at"]:
        raise sqlite3.IntegrityError("repair unexpectedly changed the resolution timestamp")
    return backup, corrected


def inspect_corrected(database: Path, session_id: str, shot_id: str) -> sqlite3.Row:
    """Read the repaired row and verify both immutable guards remain present."""
    with sqlite3.connect(_read_only_uri(database), uri=True) as db:
        db.row_factory = sqlite3.Row
        row = _target(db, session_id, shot_id)
        if row["resolution_status"] != "ABANDONED":
            raise ValueError("target resolution was not reclassified to ABANDONED")
        if row["no_physical_grinding_confirmed"] != 1:
            raise ValueError("target resolution lacks confirmed non-execution")
        _verified_trigger_sql(db, "resolution_update", RESOLUTION_UPDATE_TRIGGER)
        _verified_trigger_sql(
            db,
            "confirmed_non_execution_insert",
            CONFIRMED_NON_EXECUTION_TRIGGER,
        )
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise sqlite3.IntegrityError("foreign-key check failed after commit")
        if [result[0] for result in db.execute("PRAGMA integrity_check")] != ["ok"]:
            raise sqlite3.IntegrityError("integrity check failed after commit")
        return row


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reclassify one explicitly identified, unexecuted invalidated plan."
    )
    parser.add_argument("database", type=Path, help="explicit SQLite database path")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--shot-id", required=True)
    parser.add_argument("--apply", action="store_true", help="apply after creating a backup")
    parser.add_argument(
        "--confirm-no-physical-grinding",
        action="store_true",
        help="required with --apply; confirms the physical grinder was not run",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    candidate = inspect_target(args.database, args.session_id, args.shot_id)
    if not args.apply:
        print(json.dumps({"mode": "dry-run", "candidate": candidate}, indent=2))
        return
    backup, corrected = apply_repair(
        args.database,
        args.session_id,
        args.shot_id,
        confirmed_no_physical_grinding=args.confirm_no_physical_grinding,
    )
    print(
        json.dumps(
            {
                "mode": "applied",
                "backup": str(backup),
                "corrected": corrected,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
