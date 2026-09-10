# Data

This directory contains small, versioned datasets that are part of the research record.

## `historical_shots_staging.csv`

A manually transcribed staging dataset from handwritten espresso notes. It is intended for exploratory analysis, rolling backtests, and regression tests.

Important semantics:

- row order is chronological and must be preserved;
- blank cells mean unknown/unreadable values and must not be silently imputed in the source file;
- `grinder_output_g` is the measured output of the grinder, not necessarily the dose that was brewed;
- historical shots were generally corrected to approximately the target puck dose before brewing when `dose_correction_mode=TO_TARGET`;
- `puck_dose_g=18.0` for those rows is therefore an approximate controlled target, not a second high-precision measurement;
- `transcription_status` and `notes` record uncertainty in the transcription;
- known bean/session boundaries must remain explicit.

Do not edit historical measurements merely to make a model fit better. Corrections to transcription errors should be reviewable in Git history.

## Runtime data

Local SQLite databases, temporary exports, model caches, and other runtime state are intentionally ignored by Git. Only small datasets with clear provenance and research value should be committed here.
