# Prospective extraction-feedback baseline

Implemented 2026-10-07 as `linear_yield_direction_baseline` version `1`.
The pure typed `recommend_extraction` function and immutable `ExtractionRecommendation`
are separate from dose control, SQLite and Streamlit.

For actual recorded brew duration $t_{\mathrm{brew}}$, actual final yield $Y$ and
session target yield $Y^{\ast}$, the derived session-target estimate is
$T_{\mathrm{target}}^{\mathrm{linear}}$:

```math
T_{\mathrm{target}}^{\mathrm{linear}} = t_{\mathrm{brew}}\frac{Y^{\ast}}{Y}.
```

These symbols are also defined in [notation.md](notation.md). This assumes constant average
flow and is a crude comparator, not validated physical truth. Below the session time minimum
means `FINER`, above the maximum means `COARSER`, and the inclusive interval means `KEEP`.
No default recipe constants are embedded in the controller. Learned joint
`(brew_duration, final_yield)` models remain future work.

Use the latest eligible completed brew in the current session, with positive finite recorded
measurements and no invalidation. Experimental brews may supply raw evidence, but evaluation
must retain their experimental intent. A latest eligible brew marked obviously bad yields
`NO_UPDATE_BAD_SHOT`, without falling back to an older good brew. No source gives no recommendation.
Bad shots remain raw persisted evidence. Puck-dose departures are retained; this baseline
does not invent a dose tolerance, uncertainty estimate or causal correction.

## Assisted workflow

Review the saved extraction feedback before entering the next grinder setting. The UI shows
the estimated time at the session yield, time band, direction/status, source ID/sequence,
creation timestamp and strategy/version. The first-shot/no-source message asks for a manual
initial setting. Bad-shot suppression explains why no setting-change recommendation is issued.
The concrete grinder-label field remains editable and starts empty for each next shot.
`FINER`/`COARSER` are physical directions only; no Sette label, step size, label arithmetic
or numeric fineness mapping is supplied. Dose duration remains a separate model/manual choice.
Learning mode continues its frozen schedule without adapting settings to this feedback.

## Persistence and chronology

Schema v5 adds immutable `extraction_recommendations` and nullable
`shots.extraction_recommendation_id`. Each feedback row stores its ID, session FK,
next `target_sequence`, source-shot FK, `history_through_sequence` (the single source sequence),
UTC `created_at`, target yield and time bounds, `linear_target_yield_time_s`, direction/status,
strategy ID and model version. Raw duration/yield and the bad-shot flag remain on the source shot.
The suppression status is persisted alongside its derived estimate.

Completion saves feedback for the next sequence atomically with the brew. Assisted review
persists missing current feedback, including from eligible legacy brews, at the actual review
time. Repeated review reuses the same session/target/source record. Dose previews still persist
only on freeze. Migration creates no feedback or historical shot links.

Freeze revalidates current source eligibility under `BEGIN IMMEDIATE` and links the Assisted
shot to feedback before grinding/outcome. Learning shots have no extraction link. No source
leaves the link NULL. Later invalidation never changes existing feedback or frozen shot links.
New decisions exclude invalidated sources and can append replacement feedback for the same
target sequence. Superseded rows remain auditable; the shot FK identifies the frozen decision.
Analysis must distinguish linked decisions from unlinked feedback and account for later
source-resolution annotations rather than silently refitting history.

SQL guards reject feedback updates/deletes, late inserts for existing target shots,
noncompleted/invalidated or foreign-session sources, and mutation of frozen shot links.
Initialization migrates v1-v4 transactionally to v5, preserving all earlier fields and leaving
legacy links NULL. Fresh databases use v5; reopening is idempotent. Migration failure rolls
back DDL/data/version together. Back up before upgrading; older app versions reject v5.

## Validation boundary and next increment

Synthetic tests cover 31 s / 34 g and 31 s / 39 g at target 36 g; all directions and inclusive
boundaries; custom targets; no source; session/sequence/timestamp eligibility; invalidation;
latest-bad-shot suppression; completion/review persistence; frozen provenance; superseded sources;
restart; SQL immutability; and additive migration/rollback. AppTest verifies visible feedback
before freeze and freely entered labels without automatic Sette selection.

These establish acquisition integrity, not empirical extraction optimisation or coffee savings.
Linear normalization, monotone physical setting response, puck-dose uncertainty and robustness
remain unresolved. Prospective evaluation must retain actual operator choices and deviations,
separate Assisted and experimental intent, and compare shots/coffee-to-target under predefined
strategies. Direction alone does not specify action size or establish a causal benefit.
Before adding a learned model, collect and inspect the existing designed categorical contrasts
and baseline decisions, then define the joint-outcome model and evaluation in a separate increment.
