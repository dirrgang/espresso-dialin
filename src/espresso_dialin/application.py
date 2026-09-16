"""Prospective acquisition orchestration, independent of Streamlit."""

from dataclasses import dataclass, replace
from uuid import uuid4

from espresso_dialin.domain import Plan, Shot, compatible_dose_block, utc_now
from espresso_dialin.dose_control import (
    DoseController,
    DoseObservation,
    DoseTarget,
    InsufficientDoseHistoryError,
    LastShotProportionalController,
    MedianRateController,
)
from espresso_dialin.repository import Repository

CONTROLLERS: tuple[DoseController, ...] = (
    LastShotProportionalController(),
    MedianRateController(),
)


@dataclass(frozen=True)
class Preview:
    target: DoseTarget
    plans: tuple[Plan, ...]


class Acquisition:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def preview(self, session_id: str, setting: str) -> Preview:
        session = self.repository.session(session_id)
        if session.ended_at is not None:
            raise ValueError("session has ended")
        shots = self.repository.shots(session_id)
        if any(shot.pending for shot in shots):
            raise ValueError("complete or resolve the pending shot first")
        # A setting change starts a new contiguous block, including a return to a label.
        compatible = compatible_dose_block(shots, setting)
        sequence = len(shots) + 1
        block_id = f"{session_id}:{compatible[0].sequence if compatible else sequence}"
        now = utc_now()
        target = DoseTarget(
            next_sequence=sequence,
            bean_id=session.bean_id,
            session_id=session_id,
            block_id=block_id,
            grinder_setting=setting,
            target_output_g=session.target_puck_dose_g,
            created_at=now,
        )
        history = [
            DoseObservation(
                observation_id=shot.id,
                sequence=shot.sequence,
                bean_id=session.bean_id,
                session_id=session_id,
                block_id=block_id,
                grinder_setting=shot.grinding.setting,
                grind_duration_s=shot.grinding.duration_s,
                grinder_output_g=shot.grinding.output_g,
            )
            for shot in compatible
            if shot.grinding is not None and shot.terminal_at is not None and shot.terminal_at < now
        ]
        plans: list[Plan] = []
        for controller in CONTROLLERS:
            try:
                model = controller.recommend(target, history)
            except InsufficientDoseHistoryError:
                continue
            plans.append(
                Plan(
                    id=model.recommendation_id,
                    session_id=session_id,
                    target_sequence=sequence,
                    created_at=now,
                    setting=setting,
                    duration_s=model.recommended_duration_s,
                    target_output_g=target.target_output_g,
                    selected=False,
                    model=model,
                )
            )
        return Preview(target, tuple(plans))

    def freeze(
        self,
        session_id: str,
        setting: str,
        expected_sequence: int,
        strategy_id: str,
        manual_duration_s: float | None = None,
        *,
        experiment_step_id: str | None = None,
    ) -> Shot:
        preview = self.preview(session_id, setting)
        if preview.target.next_sequence != expected_sequence:
            raise ValueError("stale preview; reload before freezing")
        plans = [replace(plan, selected=plan.strategy_id == strategy_id) for plan in preview.plans]
        if strategy_id == "manual":
            if manual_duration_s is None:
                raise ValueError("manual fallback requires an explicit duration")
            assert preview.target.created_at is not None
            plans.append(
                Plan(
                    id=str(uuid4()),
                    session_id=session_id,
                    target_sequence=expected_sequence,
                    created_at=preview.target.created_at,
                    setting=setting,
                    duration_s=manual_duration_s,
                    target_output_g=preview.target.target_output_g,
                    selected=True,
                )
            )
        return self.repository.freeze(
            session_id, expected_sequence, plans, experiment_step_id=experiment_step_id
        )

    def freeze_experiment_step(self, experiment_id: str, expected_step_id: str) -> Shot:
        progress = self.repository.experiment_progress(experiment_id)
        step = progress.next_step
        if step is None or step.id != expected_step_id:
            raise ValueError("stale or unavailable experiment step; reload before freezing")
        session_id = progress.experiment.session_id
        return self.freeze(
            session_id,
            step.setting,
            len(self.repository.shots(session_id)) + 1,
            "manual",
            step.duration_s,
            experiment_step_id=step.id,
        )
