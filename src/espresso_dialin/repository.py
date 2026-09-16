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
    ShotIntent,
    ShotResolution,
    ShotStatus,
    compatible_dose_block,
    required,
    utc_now,
)
from espresso_dialin.dose_control import DoseRecommendation
from espresso_dialin.experiments import (
    Experiment,
    ExperimentFamily,
    ExperimentObservation,
    ExperimentProgress,
    ExperimentStep,
)
from espresso_dialin.schema import initialize

SHOT_QUERY = """SELECT s.*, r.status AS resolution_status,
    r.recorded_at AS resolution_recorded_at, r.reason AS resolution_reason,
    r.no_physical_grinding_confirmed AS resolution_no_physical_grinding_confirmed
    FROM shots s LEFT JOIN shot_resolutions r ON r.shot_id = s.id"""


def _timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


class Repository:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            initialize(db)

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
                "INSERT INTO sessions (id, bean_id, bean_name, started_at, ended_at, grinder, "
                "machine, roaster, roast_date, target_puck_dose_g, target_yield_g, "
                "target_time_min_s, target_time_max_s, bag_opened_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                    session.bag_opened_date.isoformat() if session.bag_opened_date else None,
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
                        "bag_opened_date": date.fromisoformat(row["bag_opened_date"])
                        if row["bag_opened_date"]
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
                "SELECT 1 FROM shots s LEFT JOIN shot_resolutions r ON r.shot_id=s.id "
                "WHERE s.session_id=? AND s.completed_at IS NULL AND r.shot_id IS NULL",
                (session_id,),
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
                SHOT_QUERY + " WHERE s.session_id=? ORDER BY s.sequence", (session_id,)
            ).fetchall()
        return [self._shot(row) for row in rows]

    @staticmethod
    def _shot(row: sqlite3.Row) -> Shot:
        confirmed = row["resolution_no_physical_grinding_confirmed"]
        return Shot(
            id=row["id"],
            session_id=row["session_id"],
            sequence=row["sequence"],
            created_at=datetime.fromisoformat(row["created_at"]),
            selected_recommendation_id=row["selected_recommendation_id"],
            intent=ShotIntent(row["intent"]) if row["intent"] else None,
            experiment_step_id=row["experiment_step_id"],
            grinding=GrindingResult(
                setting=row["actual_setting"],
                duration_s=row["actual_duration_s"],
                output_g=row["grinder_output_g"],
                correction=CorrectionMode(row["correction"]),
                puck_dose_g=row["puck_dose_g"],
                deviation_note=row["deviation_note"] or "",
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
            grinding_recorded_at=datetime.fromisoformat(row["grinding_recorded_at"])
            if row["grinding_recorded_at"]
            else None,
            resolution=ShotResolution(
                status=ShotStatus(row["resolution_status"]),
                recorded_at=datetime.fromisoformat(row["resolution_recorded_at"]),
                reason=row["resolution_reason"],
                no_physical_grinding_confirmed=bool(confirmed) if confirmed is not None else None,
            )
            if row["resolution_status"]
            else None,
        )

    def freeze(
        self,
        session_id: str,
        sequence: int,
        plans: Sequence[Plan],
        *,
        experiment_step_id: str | None = None,
    ) -> Shot:
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
            intent=ShotIntent.EXPERIMENT if experiment_step_id else ShotIntent.ASSISTED,
            experiment_step_id=experiment_step_id,
        )
        if shot.created_at > utc_now():
            raise ValueError("plan creation cannot be in the future")
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            session = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if session is None or session["ended_at"] is not None:
                raise ValueError("unknown or ended session")
            rows = db.execute(
                SHOT_QUERY + " WHERE s.session_id=? ORDER BY s.sequence", (session_id,)
            ).fetchall()
            previous = [self._shot(row) for row in rows]
            if sequence != len(previous) + 1 or any(s.pending for s in previous):
                raise ValueError("stale sequence or pending shot; reload before freezing")
            if any(
                s.terminal_at is not None and s.terminal_at >= shot.created_at for s in previous
            ):
                raise ValueError("plan must follow earlier terminal shots")
            sources = {s.id: s for s in compatible_dose_block(previous, selected[0].setting)}
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
                            or not source.dose_eligible
                            or source.terminal_at is None
                            or source.terminal_at >= plan.created_at
                        ):
                            raise ValueError(
                                "model source must be a prior compatible terminal shot"
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
                "selected_recommendation_id, intent, experiment_step_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    shot.id,
                    session_id,
                    sequence,
                    _timestamp(shot.created_at),
                    shot.selected_recommendation_id,
                    shot.intent,
                    shot.experiment_step_id,
                ),
            )
        return shot

    def save_grinding(self, shot_id: str, result: GrindingResult) -> None:
        with self._connection() as db:
            cursor = db.execute(
                "UPDATE shots SET actual_setting=?, actual_duration_s=?, grinder_output_g=?, "
                "correction=?, puck_dose_g=?, grinding_recorded_at=?, deviation_note=? "
                "WHERE id=? AND completed_at IS NULL AND actual_duration_s IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM shot_resolutions WHERE shot_id=shots.id)",
                (
                    result.setting,
                    result.duration_s,
                    result.output_g,
                    result.correction.value,
                    result.puck_dose_g,
                    _timestamp(utc_now()),
                    result.deviation_note,
                    shot_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("unknown shot, grinding result already saved, or shot resolved")

    def complete(self, shot_id: str, result: BrewingResult) -> None:
        with self._connection() as db:
            cursor = db.execute(
                "UPDATE shots SET brew_duration_s=?, final_yield_g=?, purged_before_shot=?, "
                "obviously_bad_shot=?, notes=?, completed_at=? "
                "WHERE id=? AND actual_duration_s IS NOT NULL AND completed_at IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM shot_resolutions WHERE shot_id=shots.id)",
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
                raise ValueError(
                    "shot must have grinding results and not already be completed or resolved"
                )

    def resolve(
        self,
        shot_id: str,
        status: ShotStatus,
        reason: str,
        *,
        no_physical_grinding_confirmed: bool | None = None,
    ) -> None:
        """Append one immutable resolution; never UPDATE the original shot or predictions."""
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(SHOT_QUERY + " WHERE s.id=?", (shot_id,)).fetchone()
            if row is None:
                raise ValueError("unknown shot")
            resolution = ShotResolution(
                status=status,
                recorded_at=utc_now(),
                reason=reason,
                no_physical_grinding_confirmed=no_physical_grinding_confirmed,
            )
            self._shot(row).validate_resolution(resolution)
            db.execute(
                "INSERT INTO shot_resolutions "
                "(shot_id, status, recorded_at, reason, no_physical_grinding_confirmed) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    shot_id,
                    resolution.status.value,
                    _timestamp(resolution.recorded_at),
                    resolution.reason,
                    1 if resolution.no_physical_grinding_confirmed is True else None,
                ),
            )

    def add_experiment(self, experiment: Experiment) -> None:
        """Seal the entire schedule in one transaction, before any linked shot exists."""
        if experiment.created_at > utc_now():
            raise ValueError("experiment creation cannot be in the future")
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            # Deferred FK permits inserting steps first. The header seals their membership.
            for step in experiment.steps:
                db.execute(
                    "INSERT INTO experiment_steps VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        step.id,
                        experiment.id,
                        step.sequence,
                        step.setting,
                        step.duration_s,
                        step.condition,
                        step.replicate,
                        step.role,
                        step.reference_sequence,
                    ),
                )
            db.execute(
                "INSERT INTO experiments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    experiment.id,
                    experiment.session_id,
                    _timestamp(experiment.created_at),
                    experiment.family.value,
                    experiment.question,
                    experiment.stopping_rule,
                    experiment.controls,
                    experiment.estimated_coffee_g,
                    len(experiment.steps),
                ),
            )

    def experiments(self, session_id: str) -> list[Experiment]:
        with self._connection() as db:
            rows = db.execute(
                "SELECT * FROM experiments WHERE session_id=? ORDER BY created_at, id",
                (session_id,),
            ).fetchall()
            result = []
            for row in rows:
                steps = db.execute(
                    "SELECT id, sequence, setting, duration_s, condition, replicate, role, "
                    "reference_sequence FROM experiment_steps WHERE experiment_id=? "
                    "ORDER BY sequence",
                    (row["id"],),
                ).fetchall()
                result.append(
                    Experiment(
                        id=row["id"],
                        session_id=row["session_id"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        family=ExperimentFamily(row["family"]),
                        question=row["question"],
                        stopping_rule=row["stopping_rule"],
                        controls=row["controls"],
                        estimated_coffee_g=row["estimated_coffee_g"],
                        steps=tuple(ExperimentStep(**dict(s)) for s in steps),
                    )
                )
        return result

    def experiment_progress(self, experiment_id: str) -> ExperimentProgress:
        """Return every planned step, raw shot evidence and derived input deviations."""
        with self._connection() as db:
            row = db.execute(
                "SELECT session_id FROM experiments WHERE id=?", (experiment_id,)
            ).fetchone()
            if row is None:
                raise ValueError("unknown experiment")
            stop = db.execute(
                "SELECT * FROM experiment_stops WHERE experiment_id=?", (experiment_id,)
            ).fetchone()
        experiment = next(e for e in self.experiments(row["session_id"]) if e.id == experiment_id)
        shots = {s.experiment_step_id: s for s in self.shots(experiment.session_id)}
        return ExperimentProgress(
            experiment,
            tuple(ExperimentObservation(s, shots.get(s.id)) for s in experiment.steps),
            datetime.fromisoformat(stop["recorded_at"]) if stop else None,
            stop["reason"] if stop else None,
        )

    def stop_experiment(self, experiment_id: str, reason: str) -> None:
        required(reason, "stop reason")
        with self._connection() as db:
            db.execute(
                "INSERT INTO experiment_stops VALUES (?, ?, ?)",
                (experiment_id, _timestamp(utc_now()), reason),
            )
