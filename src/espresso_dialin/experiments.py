"""Small frozen experimental schedules and descriptive execution views."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from espresso_dialin.domain import Shot, ShotStatus, aware, positive, required, utc_now


class ExperimentFamily(StrEnum):
    REPLICATION = "Fixed-condition replication"
    DURATION = "Local grind-duration response"


@dataclass(frozen=True, kw_only=True)
class ExperimentStep:
    id: str
    sequence: int
    setting: str
    duration_s: float
    condition: str
    replicate: int
    role: str
    reference_sequence: int | None = None

    def __post_init__(self) -> None:
        for name in ("id", "setting", "condition", "role"):
            required(getattr(self, name), name)
        positive(self.duration_s, "planned duration")
        if self.sequence < 1 or self.replicate < 1:
            raise ValueError("sequence and replicate must be positive")
        if self.reference_sequence is not None and not 1 <= self.reference_sequence < self.sequence:
            raise ValueError("reference must identify an earlier step")


@dataclass(frozen=True, kw_only=True)
class Experiment:
    id: str
    session_id: str
    created_at: datetime
    family: ExperimentFamily
    question: str
    stopping_rule: str
    controls: str
    estimated_coffee_g: float
    steps: tuple[ExperimentStep, ...]

    def __post_init__(self) -> None:
        for name in ("id", "session_id", "question", "stopping_rule", "controls"):
            required(getattr(self, name), name)
        aware(self.created_at)
        positive(self.estimated_coffee_g, "estimated coffee")
        if not isinstance(self.family, ExperimentFamily):
            raise ValueError("unknown experiment family")
        if not self.steps or tuple(s.sequence for s in self.steps) != tuple(
            range(1, len(self.steps) + 1)
        ):
            raise ValueError("experiment requires a contiguous predefined sequence")
        if len({s.id for s in self.steps}) != len(self.steps):
            raise ValueError("step identities must be unique")
        conditions: dict[str, tuple[str, float]] = {}
        replicates: dict[str, int] = {}
        for step in self.steps:
            inputs = (step.setting, step.duration_s)
            if conditions.setdefault(step.condition, inputs) != inputs:
                raise ValueError("a condition must retain the same planned inputs")
            replicates[step.condition] = replicates.get(step.condition, 0) + 1
            if step.replicate != replicates[step.condition]:
                raise ValueError("replicates must be numbered within each condition")
            if step.reference_sequence is not None:
                reference = self.steps[step.reference_sequence - 1]
                if (reference.setting, reference.duration_s) != inputs:
                    raise ValueError("reference revisit must repeat its planned inputs")


def build_experiment(
    session_id: str,
    family: ExperimentFamily,
    setting: str,
    duration_s: float,
    reference_output_g: float,
    *,
    replicates: int = 3,
    delta_s: float = 0.5,
    question: str,
) -> Experiment:
    """Deterministic pilot designs; the coffee budget is an explicit proportional estimate."""
    positive(duration_s, "reference duration")
    positive(reference_output_g, "estimated reference output")
    if family == ExperimentFamily.REPLICATION:
        if not 3 <= replicates <= 6:
            raise ValueError("choose 3 to 6 replicates before outcomes")
        schedule = [("reference", duration_s)] * replicates
    elif family == ExperimentFamily.DURATION:
        positive(delta_s, "duration offset")
        if delta_s >= duration_s:
            raise ValueError("duration offset must be smaller than reference duration")
        durations = {
            "reference": duration_s,
            "low": duration_s - delta_s,
            "high": duration_s + delta_s,
        }
        schedule = [
            (c, durations[c])
            for c in ("reference", "low", "high", "reference", "high", "low", "reference")
        ]
    else:
        raise ValueError("unknown experiment family")
    steps = []
    counts: dict[str, int] = {}
    first: dict[str, int] = {}
    for sequence, (condition, duration) in enumerate(schedule, 1):
        counts[condition] = counts.get(condition, 0) + 1
        reference = first.get(condition)
        steps.append(
            ExperimentStep(
                id=str(uuid4()),
                sequence=sequence,
                setting=setting,
                duration_s=duration,
                condition=condition,
                replicate=counts[condition],
                role="reference revisit" if reference else "initial condition",
                reference_sequence=reference,
            )
        )
        first.setdefault(condition, sequence)
    return Experiment(
        id=str(uuid4()),
        session_id=session_id,
        created_at=utc_now(),
        family=family,
        question=question,
        stopping_rule=f"Stop after {len(steps)} planned attempts, including resolved attempts; "
        "no automatic replacements. Stop early with a recorded reason if needed.",
        controls="Keep bean/session and exact grinder setting fixed. Keep preparation and "
        "hopper/purge practice consistent; record interruptions. For extraction "
        "comparisons, correct puck dose to the session target and retain actual yield.",
        estimated_coffee_g=sum(s.duration_s / duration_s * reference_output_g for s in steps),
        steps=tuple(steps),
    )


@dataclass(frozen=True)
class ExperimentObservation:
    step: ExperimentStep
    shot: Shot | None

    @property
    def deviations(self) -> tuple[str, ...]:
        if self.shot is None or self.shot.grinding is None:
            return ()
        grind = self.shot.grinding
        return tuple(
            name
            for name, differs in (
                ("setting", grind.setting != self.step.setting),
                ("duration_s", grind.duration_s != self.step.duration_s),
            )
            if differs
        )


@dataclass(frozen=True)
class ExperimentProgress:
    experiment: Experiment
    observations: tuple[ExperimentObservation, ...]
    stopped_at: datetime | None = None
    stop_reason: str | None = None

    @property
    def finished(self) -> int:
        return sum(o.shot is not None and not o.shot.pending for o in self.observations)

    @property
    def completed(self) -> int:
        return sum(
            o.shot is not None and o.shot.status == ShotStatus.COMPLETED for o in self.observations
        )

    @property
    def status(self) -> str:
        if self.stopped_at is not None:
            return "STOPPED"
        if self.finished == len(self.observations):
            return "FINISHED"
        return "IN_PROGRESS" if any(o.shot for o in self.observations) else "READY"

    @property
    def next_step(self) -> ExperimentStep | None:
        if self.stopped_at or any(o.shot and o.shot.pending for o in self.observations):
            return None
        return next((o.step for o in self.observations if o.shot is None), None)
