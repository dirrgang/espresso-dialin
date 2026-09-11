"""Small, read-only historical analysis; settings are categorical, never a scale."""

from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from statistics import mean, median, stdev
from types import MappingProxyType
from typing import Literal, cast

Analysis = Literal["output", "setting_output", "extraction", "yield_pair"]
NUMERIC_FIELDS = (
    "grind_macro",
    "grind_duration_s",
    "grinder_output_g",
    "puck_dose_g",
    "brew_duration_s",
    "final_yield_g",
)
FIELDS = (
    "sequence",
    "bean_label",
    "grind_setting",
    "grind_macro",
    "grind_micro",
    "grind_duration_s",
    "grinder_output_g",
    "dose_correction_mode",
    "puck_dose_g",
    "brew_duration_s",
    "final_yield_g",
    "transcription_status",
    "source_region",
    "notes",
)


def nullable_number(value: str) -> float | None:
    """Only blanks are missing; malformed/nonfinite numbers fail loudly."""
    if not value.strip():
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Nonfinite measurement: {value!r}")
    return result


@dataclass(frozen=True)
class Shot:
    """Raw CSV strings preserved separately from parsed values and block identity."""

    raw: Mapping[str, str]
    numbers: Mapping[str, float | None]
    block: int

    @property
    def sequence(self) -> int:
        return int(self.raw["sequence"])

    @property
    def setting(self) -> str:
        return self.raw["grind_setting"]

    @property
    def bean(self) -> str:
        return self.raw["bean_label"]

    def positive(self, field: str) -> float | None:
        value = self.numbers[field]
        return value if value is not None and value > 0 else None

    @property
    def puck_interpretation(self) -> str | None:
        mode = self.raw["dose_correction_mode"]
        if mode in {"TO_TARGET", "MEASURED"} and self.positive("puck_dose_g") is not None:
            return "approximate_target" if mode == "TO_TARGET" else "measured"
        if mode == "NONE" and self.positive("grinder_output_g") is not None:
            puck = self.positive("puck_dose_g")
            if puck is None or puck == self.positive("grinder_output_g"):
                return "uncorrected_output"
        return None

    @property
    def puck_group(self) -> tuple[str | None, float | None]:
        field = (
            "grinder_output_g"
            if self.puck_interpretation == "uncorrected_output"
            else "puck_dose_g"
        )
        return self.puck_interpretation, self.positive(field)

    @property
    def output_rate_g_s(self) -> float | None:
        duration, output = self.positive("grind_duration_s"), self.positive("grinder_output_g")
        return output / duration if duration is not None and output is not None else None

    @property
    def t36_linear_approx_s(self) -> float | None:
        time, yield_g = self.positive("brew_duration_s"), self.positive("final_yield_g")
        return time * 36 / yield_g if time is not None and yield_g is not None else None


def load_shots(path: Path) -> tuple[Shot, ...]:
    """Preserve file order; reject duplicates/reversal, never sort or forward-fill.

    Contiguous bean labels define conservative blocks, not verified real sessions.
    """
    shots: list[Shot] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(FIELDS):
            raise ValueError("Unexpected staging CSV schema")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Malformed CSV row")
            sequence = int(row["sequence"])
            if sequence <= 0 or (shots and sequence <= shots[-1].sequence):
                raise ValueError("Sequence must be positive and strictly increasing")
            if row["transcription_status"] not in {"ok", "partial", "approximate"}:
                raise ValueError("Unknown transcription status; review uncertainty before use")
            if row["dose_correction_mode"] not in {"NONE", "TO_TARGET", "MEASURED", "UNKNOWN"}:
                raise ValueError("Unknown dose correction mode")
            block = shots[-1].block if shots else 0
            if shots and row["bean_label"] != shots[-1].bean:
                block += 1
            shots.append(
                Shot(
                    MappingProxyType(dict(row)),
                    MappingProxyType(
                        {field: nullable_number(row[field]) for field in NUMERIC_FIELDS}
                    ),
                    block,
                )
            )
    return tuple(shots)


def exclusion_reasons(shot: Shot, analysis: Analysis) -> tuple[str, ...]:
    """Partial rows remain eligible when the relevant cells are available.

    Approximate measurements are retained explicitly; notebook reports sensitivity.
    UNKNOWN correction is not rescued by a possibly default-filled puck mass.
    """
    fields = (
        ("grind_duration_s", "grinder_output_g")
        if analysis in {"output", "setting_output"}
        else ("brew_duration_s", "final_yield_g")
    )
    reasons = [field for field in fields if shot.positive(field) is None]
    if analysis in {"setting_output", "extraction"}:
        if not shot.setting:
            reasons.append("grind_setting")
        if not shot.bean:
            reasons.append("bean_label")
    if analysis == "extraction" and shot.puck_interpretation is None:
        reasons.append("usable_puck_dose")
    return tuple(reasons)


def eligible(shots: Iterable[Shot], analysis: Analysis) -> list[Shot]:
    return [shot for shot in shots if not exclusion_reasons(shot, analysis)]


@dataclass(frozen=True)
class Transition:
    previous: Shot
    current: Shot
    changed: bool


def transitions(shots: Sequence[Shot]) -> list[Transition]:
    """Immediate raw neighbours only; unknown settings/gaps break the chain."""
    return [
        Transition(previous, current, previous.setting != current.setting)
        for previous, current in pairwise(shots)
        if current.sequence == previous.sequence + 1
        and current.block == previous.block
        and current.bean
        and previous.setting
        and current.setting
    ]


def describe(values: Sequence[float]) -> dict[str, float | int | None]:
    """Sample SD and unscaled median absolute deviation; no deletion."""
    if not values:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "sd": None,
            "mad": None,
            "min": None,
            "max": None,
        }
    center = median(values)
    return {
        "n": len(values),
        "mean": mean(values),
        "median": center,
        "sd": stdev(values) if len(values) > 1 else None,
        "mad": median([abs(value - center) for value in values]),
        "min": min(values),
        "max": max(values),
    }


def metric(shot: Shot, field: str) -> float:
    value = (
        shot.output_rate_g_s
        if field == "rate"
        else shot.t36_linear_approx_s
        if field == "t36"
        else shot.positive(field)
    )
    if value is None:
        raise ValueError(f"Shot {shot.sequence} lacks valid {field}")
    return value


def grouped_summary(shots: Sequence[Shot], analysis: Analysis) -> list[dict[str, object]]:
    groups: dict[tuple[int, str, str, tuple[str | None, float | None] | None], list[Shot]] = (
        defaultdict(list)
    )
    for shot in eligible(shots, analysis):
        groups[
            (
                shot.block,
                shot.bean,
                shot.setting,
                shot.puck_group if analysis == "extraction" else None,
            )
        ].append(shot)
    fields = (
        ("grind_duration_s", "grinder_output_g", "rate")
        if analysis in {"output", "setting_output"}
        else ("brew_duration_s", "final_yield_g", "t36")
    )
    return [
        {
            "block": block,
            "bean": bean,
            "setting": setting,
            "puck": puck,
            "sequences": [s.sequence for s in members],
            "metric": field,
            **describe([metric(s, field) for s in members]),
        }
        for (block, bean, setting, puck), members in groups.items()
        for field in fields
    ]


def robust_flags(shots: Sequence[Shot]) -> list[dict[str, object]]:
    """Descriptive modified z > 3.5 for n>=5 within extraction comparison groups.

    Zero MAD is reported as unscorable, never replaced with an arbitrary epsilon.
    This uses the full group retrospectively, never feeds rolling predictions.
    """
    rows: list[dict[str, object]] = []
    by_sequence = {s.sequence: s for s in shots}
    for group in grouped_summary(shots, "extraction"):
        if group["metric"] not in {"brew_duration_s", "t36"}:
            continue
        # Reconstruct membership without relying on heterogeneous summary types.
        members = [
            s
            for s in by_sequence.values()
            if s.block == group["block"]
            and s.setting == group["setting"]
            and s.puck_group == group["puck"]
            and not exclusion_reasons(s, "extraction")
        ]
        if len(members) < 5:
            continue
        field = str(group["metric"])
        values = [metric(s, field) for s in members]
        center = median(values)
        mad = median([abs(v - center) for v in values])
        for shot, value in zip(members, values, strict=True):
            score = 0.67448975 * abs(value - center) / mad if mad > 0 else None
            rows.append(
                {
                    "sequence": shot.sequence,
                    "bean": shot.bean,
                    "setting": shot.setting,
                    "metric": field,
                    "value": value,
                    "modified_z": score,
                    "flag": score > 3.5 if score is not None else None,
                }
            )
    return rows


def proportional_duration(shot: Shot, target_g: float = 18.0) -> float:
    if not math.isfinite(target_g) or target_g <= 0:
        raise ValueError("Target must be positive and finite")
    return metric(shot, "grind_duration_s") * target_g / metric(shot, "grinder_output_g")


def dose_backtest(shots: Sequence[Shot]) -> list[dict[str, object]]:
    """Predict next observed output at its actual duration, same-setting neighbours.

    This evaluates the proportional rate assumption, not an unobserved intervention.
    """
    rows: list[dict[str, object]] = []
    for pair in transitions(shots):
        previous, current = pair.previous, pair.current
        if (
            pair.changed
            or exclusion_reasons(previous, "output")
            or exclusion_reasons(current, "output")
        ):
            continue
        prediction = metric(previous, "rate") * metric(current, "grind_duration_s")
        rows.append(
            {
                "previous": previous.sequence,
                "sequence": current.sequence,
                "bean": current.bean,
                "setting": current.setting,
                "recommended_duration_s": proportional_duration(previous),
                "actual_duration_s": metric(current, "grind_duration_s"),
                "prediction_g": prediction,
                "actual_g": metric(current, "grinder_output_g"),
                "error_g": prediction - metric(current, "grinder_output_g"),
                "carry_output_error_g": metric(previous, "grinder_output_g")
                - metric(current, "grinder_output_g"),
                "rate_change_pct": 100 * (metric(current, "rate") / metric(previous, "rate") - 1),
            }
        )
    return rows


def extraction_backtest(shots: Sequence[Shot]) -> list[dict[str, object]]:
    """Expanding exact-setting median, past-only within block and puck interpretation.

    Both methods scored against observed brew time. Normalized median is mapped
    back using *observed* yield, hence conditional reconstruction, not deployable
    next-shot prediction or validation of true T36 (which is unobserved).
    """
    history: dict[tuple[int, str, tuple[str | None, float | None]], list[Shot]] = defaultdict(list)
    rows: list[dict[str, object]] = []
    for shot in eligible(shots, "extraction"):
        past = history[(shot.block, shot.setting, shot.puck_group)]
        if past:
            raw = median([metric(s, "brew_duration_s") for s in past])
            normalized = median([metric(s, "t36") for s in past])
            actual = metric(shot, "brew_duration_s")
            rows.append(
                {
                    "sequence": shot.sequence,
                    "bean": shot.bean,
                    "setting": shot.setting,
                    "n_train": len(past),
                    "train_through": past[-1].sequence,
                    "raw_error_s": raw - actual,
                    "normalized_error_s": normalized * metric(shot, "final_yield_g") / 36 - actual,
                }
            )
        past.append(shot)
    return rows


def audit(shots: Sequence[Shot]) -> dict[str, object]:
    analyses: tuple[Analysis, ...] = ("output", "setting_output", "yield_pair", "extraction")
    return {
        "rows": len(shots),
        "beans": dict(Counter(s.bean for s in shots)),
        "statuses": dict(Counter(s.raw["transcription_status"] for s in shots)),
        "missingness": {field: sum(not s.raw[field].strip() for s in shots) for field in FIELDS},
        "eligibility": {a: len(eligible(shots, a)) for a in analyses},
        "eligibility_by_bean": {
            bean: {a: len(eligible([s for s in shots if s.bean == bean], a)) for a in analyses}
            for bean in dict.fromkeys(s.bean for s in shots)
        },
        "exclusions": {
            a: {s.sequence: exclusion_reasons(s, a) for s in shots if exclusion_reasons(s, a)}
            for a in analyses
        },
        "known_transitions": len(transitions(shots)),
        "dose_pairs": len(dose_backtest(shots)),
        "rolling_extraction": len(extraction_backtest(shots)),
    }


def error_summary(
    rows: Sequence[Mapping[str, object]], field: str
) -> dict[str, float | int | None]:
    errors = [cast(float, row[field]) for row in rows]
    return {
        "n": len(errors),
        "mae": mean([abs(e) for e in errors]) if errors else None,
        "rmse": math.sqrt(mean([e * e for e in errors])) if errors else None,
        "median_absolute_error": median([abs(e) for e in errors]) if errors else None,
    }


def chronology_rows(shots: Sequence[Shot]) -> list[dict[str, object]]:
    """Extraction on current shot with known previous setting; no skipped rows."""
    return [
        {
            "sequence": p.current.sequence,
            "bean": p.current.bean,
            "block": p.current.block,
            "setting": p.current.setting,
            "previous_setting": p.previous.setting,
            "changed": p.changed,
            "brew_duration_s": metric(p.current, "brew_duration_s"),
            "t36": metric(p.current, "t36"),
        }
        for p in transitions(shots)
        if not exclusion_reasons(p.current, "extraction")
    ]


def change_followups(shots: Sequence[Shot]) -> list[dict[str, object]]:
    """First changed shot versus its immediate same-setting repeat, same puck group."""
    pairs = {p.current.sequence: p for p in transitions(shots)}
    rows: list[dict[str, object]] = []
    for sequence, first in pairs.items():
        repeat = pairs.get(sequence + 1)
        if not first.changed or repeat is None or repeat.changed:
            continue
        a, b = first.current, repeat.current
        if (
            exclusion_reasons(a, "extraction")
            or exclusion_reasons(b, "extraction")
            or a.puck_group != b.puck_group
        ):
            continue
        rows.append(
            {
                "first": a.sequence,
                "repeat": b.sequence,
                "bean": a.bean,
                "setting": a.setting,
                "previous_setting": first.previous.setting,
                "raw_repeat_minus_first_s": metric(b, "brew_duration_s")
                - metric(a, "brew_duration_s"),
                "t36_repeat_minus_first_s": metric(b, "t36") - metric(a, "t36"),
            }
        )
    return rows


def variability_comparison(shots: Sequence[Shot]) -> list[dict[str, object]]:
    """Matched repeated groups, pooled within-group SD with n-1 weighting.

    SD scales differ when yield differs; this is descriptive, not accuracy.
    """
    summaries = grouped_summary(shots, "extraction")
    result: list[dict[str, object]] = []
    for bean in dict.fromkeys(s.bean for s in shots):
        for field in ("brew_duration_s", "t36"):
            groups = [
                g
                for g in summaries
                if g["bean"] == bean and g["metric"] == field and cast(int, g["n"]) >= 2
            ]
            df = sum(cast(int, g["n"]) - 1 for g in groups)
            variance_sum = sum((cast(int, g["n"]) - 1) * cast(float, g["sd"]) ** 2 for g in groups)
            result.append(
                {
                    "bean": bean,
                    "metric": field,
                    "groups": len(groups),
                    "n": sum(cast(int, g["n"]) for g in groups),
                    "pooled_within_sd": math.sqrt(variance_sum / df) if df else None,
                }
            )
    return result


def research_report(shots: Sequence[Shot]) -> dict[str, object]:
    """Machine-readable tables used by the notebook and research note."""
    dose, extraction = dose_backtest(shots), extraction_backtest(shots)
    metrics = [
        {
            "bean": bean,
            "method": method,
            **error_summary([r for r in rows if r["bean"] == bean], method),
        }
        for bean in dict.fromkeys(s.bean for s in shots)
        for rows, method in [
            (dose, "error_g"),
            (dose, "carry_output_error_g"),
            (extraction, "raw_error_s"),
            (extraction, "normalized_error_s"),
        ]
    ]
    return {
        "audit": audit(shots),
        "output_groups": grouped_summary(shots, "setting_output"),
        "extraction_groups": grouped_summary(shots, "extraction"),
        "variability": variability_comparison(shots),
        "flags": robust_flags(shots),
        "chronology": chronology_rows(shots),
        "change_followups": change_followups(shots),
        "dose_pairs": dose,
        "rolling_extraction": extraction,
        "errors": metrics,
    }
