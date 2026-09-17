"""Local prospective espresso acquisition UI. Run with ``streamlit run``."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import streamlit as st

from espresso_dialin.application import Acquisition
from espresso_dialin.domain import (
    BrewingResult,
    CorrectionMode,
    GrindingResult,
    Session,
    ShotStatus,
    utc_now,
)
from espresso_dialin.experiments import (
    ExperimentFamily,
    build_experiment,
    build_extraction_experiment,
)
from espresso_dialin.repository import Repository

DEFAULT_DATABASE = Path(__file__).parent / "data" / "live.sqlite3"
CURRENT_BEAN = "REWE Bio Espresso ganze Bohnen, 1000 g"


@contextmanager
def input_errors():
    """Keep the rest of the page and its widget state alive after a rejected action."""
    try:
        yield
    except (ValueError, sqlite3.Error) as error:
        st.error(str(error))


def puck_dose_evidence(grind, target_g):
    if grind is None:
        return None
    if grind.correction == CorrectionMode.TO_TARGET:
        return f"Approximately {target_g:g} g (TO_TARGET; uncertainty unknown)"
    if grind.correction == CorrectionMode.NONE:
        return f"{grind.output_g:g} g (uncorrected grinder output)"
    return f"{grind.puck_dose_g:g} g (separately measured)"


def learning_mode(repo, app, session, shots, pending):
    st.header("Learning / Experiment mode")
    st.caption(
        "Follow a predefined schedule to answer a research question. "
        "These are experimental shots, not ordinary dial-in recommendations."
    )
    experiments = repo.experiments(session.id)
    if session.ended_at is None and pending is None:
        with st.expander("Create experiment", expanded=not experiments):
            family = st.selectbox("Experiment design", list(ExperimentFamily))
            default_question = {
                ExperimentFamily.REPLICATION: (
                    "How variable is grinder output at this fixed condition in this session?"
                ),
                ExperimentFamily.DURATION: (
                    "Does output scale proportionally with duration near this operating point?"
                ),
                ExperimentFamily.EXTRACTION: (
                    "How do these two settings affect brew duration and final yield "
                    "with puck dose controlled at the session target?"
                ),
            }[family]
            question = st.text_input("Research question", value=default_question, key=f"q_{family}")
            last = next((s.grinding for s in reversed(shots) if s.grinding), None)
            setting = st.text_input("Reference grinder setting", value=last.setting if last else "")
            comparison = ""
            if family == ExperimentFamily.EXTRACTION:
                comparison = st.text_input("Comparison grinder setting")
                st.caption(
                    "Choose two distinct labels. No distance or finer/coarser order is assumed."
                )
            duration = st.number_input(
                "Shared grind duration (s)"
                if family == ExperimentFamily.EXTRACTION
                else "Reference grind duration (s)",
                value=last.duration_s if last else None,
                min_value=0.001,
                format="%.3f",
            )
            expected = st.number_input(
                "Estimated reference output (g)", value=session.target_puck_dose_g, min_value=0.001
            )
            replicates = 3
            delta = 0.5
            if family == ExperimentFamily.REPLICATION:
                replicates = st.number_input(
                    "Predefined replicate count", value=3, min_value=3, max_value=6
                )
            elif family == ExperimentFamily.DURATION:
                delta = st.number_input("Duration offset (s)", value=0.5, min_value=0.001)
            if setting.strip() and duration is not None:
                with input_errors():
                    if family == ExperimentFamily.EXTRACTION:
                        design = build_extraction_experiment(
                            session.id,
                            setting,
                            comparison,
                            duration,
                            expected,
                            question=question,
                        )
                        st.caption(
                            f"Session targets: {session.target_puck_dose_g:g} g puck; "
                            f"{session.target_yield_g:g} g beverage; "
                            f"{session.target_time_min_s:g}-{session.target_time_max_s:g} s brew."
                        )
                    else:
                        design = build_experiment(
                            session.id,
                            ExperimentFamily(family),
                            setting,
                            duration,
                            expected,
                            replicates=replicates,
                            delta_s=delta,
                            question=question,
                        )
                    st.write(design.controls)
                    st.write(
                        {
                            ExperimentFamily.REPLICATION: (
                                "Varied: nothing deliberately; repeat the same inputs."
                            ),
                            ExperimentFamily.DURATION: "Varied: grind duration.",
                            ExperimentFamily.EXTRACTION: "Varied: categorical grinder setting.",
                        }[family]
                    )
                    st.table(
                        [
                            {
                                "Step": s.sequence,
                                "Setting": s.setting,
                                "Duration (s)": s.duration_s,
                                "Condition": s.condition,
                                "Replicate": s.replicate,
                                "Role": s.role,
                            }
                            for s in design.steps
                        ]
                    )
                    st.write(
                        f"{len(design.steps)} planned shots; approximately "
                        f"{design.estimated_coffee_g:.1f} g of grinder output."
                    )
                    st.caption(
                        (
                            "Budget uses six times the estimated reference output; output at the "
                            "comparison setting may differ. "
                            if family == ExperimentFamily.EXTRACTION
                            else "Planning estimate assumes proportional output. "
                        )
                        + "Excludes purge or extra correction coffee. This is not a prediction."
                    )
                    st.write(design.stopping_rule)
                    if st.button("Freeze experiment plan"):
                        repo.add_experiment(design)
                        st.session_state[f"experiment_{session.id}"] = design.id
                        st.rerun()
    if not experiments:
        return
    choices = {e.id: e for e in experiments}
    selected = st.selectbox(
        "Experiment",
        list(choices),
        format_func=lambda key: f"{choices[key].family} · {key[:8]}",
        key=f"experiment_{session.id}",
    )
    progress = repo.experiment_progress(selected)
    st.write(progress.experiment.question)
    st.caption(progress.experiment.controls)
    st.write(progress.experiment.stopping_rule)
    st.write(
        f"{progress.status}: {progress.finished}/{len(progress.observations)} attempts "
        f"finished; {progress.completed} completed brews; "
        f"{sum(o.shot is None for o in progress.observations)} steps not started."
    )
    if progress.stop_reason:
        st.write(f"Stopped: {progress.stop_reason}")
    if progress.experiment.family == ExperimentFamily.EXTRACTION:
        st.caption(
            "Puck differences are recorded mass minus session target, not a tolerance decision. "
            "TO_TARGET is approximate: its numerical difference is unknown. "
            "NONE means no correction; inspect output and describe any departure in the note."
        )
    st.dataframe(
        [
            {
                "Step": o.step.sequence,
                "Condition": o.step.condition,
                "Replicate": o.step.replicate,
                "Planned setting": o.step.setting,
                "Planned s": o.step.duration_s,
                "State": o.shot.status.value if o.shot else "NOT_STARTED",
                "Actual setting": o.shot.grinding.setting if o.shot and o.shot.grinding else None,
                "Actual s": o.shot.grinding.duration_s if o.shot and o.shot.grinding else None,
                "Output g": o.shot.grinding.output_g if o.shot and o.shot.grinding else None,
                "Correction": o.shot.grinding.correction.value
                if o.shot and o.shot.grinding
                else None,
                "Puck dose evidence": puck_dose_evidence(
                    o.shot.grinding if o.shot else None, session.target_puck_dose_g
                ),
                "Puck minus target g": o.puck_dose_difference_g,
                "Brew s": o.shot.brewing.duration_s if o.shot and o.shot.brewing else None,
                "Yield g": o.shot.brewing.yield_g if o.shot and o.shot.brewing else None,
                "Purged": o.shot.brewing.purged_before_shot if o.shot and o.shot.brewing else None,
                "Resolution reason": o.shot.resolution.reason
                if o.shot and o.shot.resolution
                else None,
                "Deviations": ", ".join(o.deviations),
                "Deviation note": o.shot.grinding.deviation_note
                if o.shot and o.shot.grinding
                else None,
            }
            for o in progress.observations
        ],
        hide_index=True,
    )
    step = progress.next_step
    if step and pending is None and session.ended_at is None:
        st.info(f"Next experimental step {step.sequence}: {step.setting} · {step.duration_s:.3f} s")
        st.caption(
            "Record any intervening grinding as ordinary shots and describe interruptions "
            "in the deviation note. Unrecorded grinding limits interpretation."
        )
        if st.button("Freeze next experimental shot"):
            with input_errors():
                app.freeze_experiment_step(selected, step.id)
                st.rerun()
    if progress.status in ("READY", "IN_PROGRESS") and pending is None:
        with st.form(f"stop_{selected}", enter_to_submit=False):
            reason = st.text_input("Reason for stopping experiment")
            if st.form_submit_button("Stop experiment"):
                with input_errors():
                    repo.stop_experiment(selected, reason)
                    st.rerun()


def main():
    st.title("Espresso dial-in")
    repo = Repository(Path(os.environ.get("ESPRESSO_DIALIN_DB", DEFAULT_DATABASE)))
    app = Acquisition(repo)
    sessions = repo.sessions()
    st.header("Session")
    with st.expander("Start a session", expanded=not sessions):
        known_beans = {s.bean_name: s.bean_id for s in sessions}
        bean_choice = st.selectbox(
            "Bean",
            ["New bean…", *known_beans, *([] if CURRENT_BEAN in known_beans else [CURRENT_BEAN])],
        )
        with st.form("session", enter_to_submit=False):
            bean_name = st.text_input(
                "Bean name", value="" if bean_choice == "New bean…" else bean_choice
            )
            roaster = st.text_input("Roaster (optional)")
            roast_date = st.date_input("Roast date (optional)", value=None)
            bag_opened = st.date_input("Bag opened date (optional)", value=None)
            grinder = st.text_input("Grinder", value="Baratza Sette 270")
            machine = st.text_input("Machine", value="Sage/Breville Dual Boiler (BES920/SES920)")
            dose = st.number_input("Target puck dose (g)", value=18.0, min_value=0.01)
            target_yield = st.number_input("Target beverage yield (g)", value=36.0, min_value=0.01)
            lower = st.number_input("Target brew time minimum (s)", value=30.0, min_value=0.01)
            upper = st.number_input("Target brew time maximum (s)", value=35.0, min_value=0.01)
            if st.form_submit_button("Create session"):
                with input_errors():
                    if bean_name is None:
                        raise ValueError("bean name is required")
                    session = Session(
                        id=str(uuid4()),
                        bean_id=known_beans.get(bean_name, str(uuid4())),
                        bean_name=bean_name,
                        started_at=utc_now(),
                        roaster=roaster or None,
                        roast_date=roast_date,
                        bag_opened_date=bag_opened,
                        grinder=grinder,
                        machine=machine,
                        target_puck_dose_g=dose,
                        target_yield_g=target_yield,
                        target_time_min_s=lower,
                        target_time_max_s=upper,
                    )
                    repo.add_session(session)
                    st.session_state["current_session"] = session.id
                    st.rerun()
    if not sessions:
        st.info("Create a session to record your first espresso.")
        return
    by_id = {s.id: s for s in sessions}
    if st.session_state.get("current_session") not in by_id:
        latest_active = next((s for s in reversed(sessions) if s.ended_at is None), sessions[-1])
        st.session_state["current_session"] = latest_active.id
    session_id = st.selectbox(
        "Current session",
        list(by_id),
        key="current_session",
        format_func=lambda key: (
            f"{by_id[key].bean_name} · "
            f"{by_id[key].started_at:%Y-%m-%d %H:%M} UTC · {key[:8]}"
            + (" (ended)" if by_id[key].ended_at else "")
        ),
    )
    session = by_id[session_id]
    st.write(f"{session.grinder} · {session.machine}")
    if session.bag_opened_date:
        st.caption(f"Bag opened: {session.bag_opened_date.isoformat()}")
    st.write(
        f"Target: {session.target_puck_dose_g:g} g puck → {session.target_yield_g:g} g "
        f"in {session.target_time_min_s:g}-{session.target_time_max_s:g} s"
    )
    shots = repo.shots(session_id)
    pending = next((s for s in shots if s.pending), None)
    if session.ended_at is None and pending is None and st.button("End session"):
        with input_errors():
            repo.end_session(session_id)
            st.rerun()
    st.session_state.setdefault(
        "use_mode", "Learning" if pending and pending.experiment_step_id else "Assisted"
    )
    use_mode = st.radio("Use mode", ["Assisted", "Learning"], key="use_mode")
    if use_mode == "Learning":
        learning_mode(repo, app, session, shots, pending)
    if pending:
        if pending.experiment_step_id:
            st.info(f"Experimental shot · step {pending.experiment_step_id}")
        plans = repo.plans(session_id, pending.sequence)
        selected = next(p for p in plans if p.selected)
        st.header(f"Shot {pending.sequence} · frozen plan")
        st.success(
            f"Saved before grinding: {selected.strategy_id} · {selected.setting} · "
            f"{selected.duration_s:.3f} s"
        )
        st.caption("Record what you actually did, including deviations from this plan.")
        if pending.grinding is None:
            st.subheader("Grinding result")
            mode = st.selectbox("Dose correction", list(CorrectionMode), key=f"mode_{pending.id}")
            st.caption(
                "NONE: brewed unchanged. TO_TARGET: approximately corrected to target. "
                "MEASURED: final puck dose weighed separately."
            )
            with st.form(f"grinding_{pending.id}", enter_to_submit=False):
                actual_setting = st.text_input("Actual grinder setting", value=selected.setting)
                duration = st.number_input(
                    "Actual grind duration (s)", value=None, min_value=0.001, format="%.3f"
                )
                output = st.number_input("Grinder output (g)", value=None, min_value=0.001)
                puck = st.number_input(
                    "Measured puck dose (g)",
                    value=None,
                    min_value=0.001,
                    disabled=mode != CorrectionMode.MEASURED,
                )
                deviation_note = st.text_input("Deviation / interruption note (optional)")
                if st.form_submit_button("Save grinding result"):
                    with input_errors():
                        if duration is None or output is None:
                            raise ValueError("enter actual duration and grinder output")
                        repo.save_grinding(
                            pending.id,
                            GrindingResult(
                                deviation_note=deviation_note,
                                setting=actual_setting,
                                duration_s=duration,
                                output_g=output,
                                correction=CorrectionMode(mode),
                                puck_dose_g=puck if mode == CorrectionMode.MEASURED else None,
                            ),
                        )
                        st.rerun()
            with st.container(border=True):
                st.markdown("**Frozen plan was not executed?**")
                st.caption(
                    "Use this only when no physical grinding occurred. The frozen plan and "
                    "audit trail remain saved, and the session is released for the next shot."
                )
                with st.form(f"cancel_pregrind_{pending.id}", enter_to_submit=False):
                    reason = st.text_area("Reason for cancelling frozen plan (required)")
                    confirmed = st.checkbox(
                        "I confirm that no physical grinding occurred for this plan"
                    )
                    if st.form_submit_button("Cancel frozen plan — no grinding performed"):
                        with input_errors():
                            if not confirmed:
                                raise ValueError("confirm that no physical grinding occurred")
                            repo.resolve(
                                pending.id,
                                ShotStatus.ABANDONED,
                                reason,
                                no_physical_grinding_confirmed=True,
                            )
                            st.rerun()
        else:
            st.write(
                f"Grinding saved: {pending.grinding.duration_s:g} s / "
                f"{pending.grinding.output_g:g} g · {pending.grinding.correction}"
            )
            st.subheader("Brewing result")
            with st.form(f"brewing_{pending.id}", enter_to_submit=False):
                brew = st.number_input("Brew duration (s)", value=None, min_value=0.001)
                final_yield = st.number_input(
                    "Final beverage yield (g)", value=None, min_value=0.001
                )
                purge = st.checkbox("Purged before shot")
                bad = st.checkbox("Obviously bad shot")
                notes = st.text_area("Notes (optional)")
                if st.form_submit_button("Complete shot"):
                    with input_errors():
                        if brew is None or final_yield is None:
                            raise ValueError("enter brew duration and actual final yield")
                        repo.complete(
                            pending.id,
                            BrewingResult(
                                duration_s=brew,
                                yield_g=final_yield,
                                purged_before_shot=purge,
                                obviously_bad_shot=bad,
                                notes=notes,
                            ),
                        )
                        st.rerun()
    elif session.ended_at is None and use_mode == "Assisted":
        st.header("Next shot")
        st.caption("Choose the grinder setting manually. Freeze the plan before grinding.")
        setting = st.text_input("Grinder setting", key=f"setting_{session_id}_{len(shots) + 1}")
        if setting.strip():
            preview = app.preview(session_id, setting)
            if preview.plans:
                st.table(
                    [
                        {
                            "Strategy": p.strategy_id,
                            "Duration (s)": p.duration_s,
                            "Expected output (g)": p.model.expected_output_g,
                        }
                        for p in preview.plans
                        if p.model
                    ]
                )
            else:
                st.info(
                    "Insufficient compatible live history. Enter a manual duration; "
                    "no model prediction is available."
                )
            strategy = st.selectbox(
                "Selected strategy", ["manual", *[p.strategy_id for p in preview.plans]]
            )
            manual = st.number_input(
                "Manual planned duration (s)",
                value=None,
                min_value=0.001,
                format="%.3f",
                disabled=strategy != "manual",
            )
            if st.button("Freeze plan before grinding"):
                with input_errors():
                    app.freeze(session_id, setting, preview.target.next_sequence, strategy, manual)
                    st.rerun()
    st.header("Recent history")
    history = []
    for shot in reversed(shots[-20:]):
        plan = next(p for p in repo.plans(session_id, shot.sequence) if p.selected)
        grind, brew_result = shot.grinding, shot.brewing
        history.append(
            {
                "Shot": shot.sequence,
                "State": shot.status.value,
                "Intent": shot.intent.value if shot.intent else "Unknown (legacy)",
                "Experiment step": shot.experiment_step_id,
                "Deviation note": grind.deviation_note if grind else None,
                "Input deviation": bool(
                    grind and (grind.setting != plan.setting or grind.duration_s != plan.duration_s)
                ),
                "Strategy": plan.strategy_id,
                "Planned setting": plan.setting,
                "Actual setting": grind.setting if grind else None,
                "Planned s": plan.duration_s,
                "Actual s": grind.duration_s if grind else None,
                "Output g": grind.output_g if grind else None,
                "Correction": grind.correction.value if grind else None,
                "Measured puck g": grind.puck_dose_g if grind else None,
                "Brew s": brew_result.duration_s if brew_result else None,
                "Yield g": brew_result.yield_g if brew_result else None,
                "Purged": brew_result.purged_before_shot if brew_result else None,
                "Bad": brew_result.obviously_bad_shot if brew_result else None,
                "Notes": brew_result.notes if brew_result else None,
                "Plan frozen (UTC)": shot.plan_frozen_at.isoformat(),
                "Grinding recorded (UTC)": shot.grinding_recorded_at.isoformat()
                if shot.grinding_recorded_at
                else None,
                "Brewing recorded (UTC)": shot.brewing_recorded_at.isoformat()
                if shot.brewing_recorded_at
                else None,
                "Resolution recorded (UTC)": shot.resolution.recorded_at.isoformat()
                if shot.resolution
                else None,
                "No grinding confirmed": shot.resolution.no_physical_grinding_confirmed
                if shot.resolution
                else None,
                "Resolution reason": shot.resolution.reason if shot.resolution else None,
            }
        )
    if history:
        st.dataframe(history, hide_index=True)
    actionable = {shot.id: shot for shot in shots if shot.resolution is None}
    if actionable:
        with st.expander("Abandon or invalidate a shot"):
            shot_id = st.selectbox(
                "Shot to resolve",
                list(reversed(actionable)),
                format_func=lambda key: (
                    f"Shot {actionable[key].sequence} ({actionable[key].status.value})"
                ),
                key=f"resolve_{session_id}",
            )
            target_shot = actionable[shot_id]
            labels = {
                ShotStatus.ABANDONED: "Abandon brew — keep valid grinder result"
                if target_shot.grinding
                else "Abandon before grinding — confirm no physical grinding occurred",
                ShotStatus.INVALIDATED: "Invalidate — execution or evidence is uncertain",
            }
            actions = (
                [ShotStatus.ABANDONED, ShotStatus.INVALIDATED]
                if target_shot.pending
                else [ShotStatus.INVALIDATED]
            )
            action = st.selectbox(
                "Action", actions, format_func=lambda value: labels[value], key=f"action_{shot_id}"
            )
            pregrind_abandonment = action == ShotStatus.ABANDONED and target_shot.grinding is None
            if pregrind_abandonment:
                st.caption(
                    "Pre-grind abandonment is an explicit physical fact: no grinding occurred. "
                    "It keeps the frozen plan but is transparent to grinder continuity."
                )
                confirmation = "I confirm that no physical grinding occurred for this plan"
            elif action == ShotStatus.ABANDONED:
                st.caption(
                    "Post-grind abandonment keeps the saved grinder result as valid while "
                    "recording that brewing was abandoned."
                )
                confirmation = (
                    "I confirm the saved grinding result is valid and brewing was abandoned"
                )
            else:
                st.caption(
                    "Use invalidation when physical execution or recorded evidence is wrong or "
                    "uncertain. It breaks grinder continuity. Original values and frozen "
                    "predictions stay unchanged."
                )
                confirmation = "I confirm that execution or recorded evidence is wrong or uncertain"
            with st.form(f"resolution_{shot_id}_{action.value}", enter_to_submit=False):
                reason = st.text_area("Reason (required)")
                confirmed = st.checkbox(confirmation)
                if st.form_submit_button("Confirm shot resolution"):
                    with input_errors():
                        if not confirmed:
                            raise ValueError("confirm the action before saving")
                        repo.resolve(
                            shot_id,
                            action,
                            reason,
                            no_physical_grinding_confirmed=True if pregrind_abandonment else None,
                        )
                        st.rerun()
    st.caption(
        "Timestamps record data entry, not exact physical grinder or pump events. "
        "Unknown legacy grinding-entry times remain blank."
    )
    st.caption(
        "TO_TARGET means approximately the session target; no precise puck mass is inferred. "
        "NONE means the grinder output was brewed unchanged."
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, sqlite3.Error) as error:
        st.error(str(error))
