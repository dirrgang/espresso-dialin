# Mathematical notation

This page defines the **project-specific mathematical notation** used across `docs/`. Method-specific textbook notation is handled locally where needed.

The intended reader may be assumed to have mathematical background roughly equivalent to an Informatik/Computer-Science bachelor's degree. Standard algebra, calculus, linear-algebra notation, basic probability/statistics notation, and commonplace operators are therefore not re-explained merely for completeness. The documentation focuses instead on project-specific meanings, non-obvious modelling assumptions, and specialist methods where additional context is useful.

The aim is to avoid two failure modes:

- forcing readers to infer what a project-specific symbol means;
- reusing the same symbol for different concepts without saying so.

GitHub Markdown conventions in this repository are `$...$` for inline mathematics and fenced `math` blocks for display equations.

## Indexing and general conventions

- $n$ denotes the chronological index of a shot or grinder event within the relevant sequence.
- A missing shot index denotes a generic value rather than a specific chronological observation. For example, $G$ means a generic grinder setting, while $G_n$ means the setting used for shot $n$.
- A superscript star, as in $Y^*$, denotes a target value.
- $\varepsilon$ denotes a residual disturbance/error term. Unless a section says otherwise, it can contain measurement error, shot-to-shot process variation, and effects omitted from the current model; it must not automatically be interpreted as pure measurement noise.

## Core observed espresso variables

For shot $n$:

| Symbol | Meaning | Typical unit / representation |
| --- | --- | --- |
| $G_n$ | Grinder setting actually used | Structured/categorical setting such as `3E`; not assumed to be a linear numeric scale |
| $t_{\mathrm{grind},n}$ | Actual grinder run time | seconds |
| $D_{\mathrm{out},n}$ | Raw coffee mass produced by the grinder before any manual correction | grams |
| $D_{\mathrm{puck},n}$ | Coffee mass actually brewed after any manual correction | grams |
| $t_{\mathrm{brew},n}$ | Recorded brew duration | seconds |
| $Y_n$ | Final beverage yield | grams |

The distinction between $D_{\mathrm{out},n}$ and $D_{\mathrm{puck},n}$ is fundamental: manual correction of the puck dose must never overwrite the raw grinder output.

## Targets

The default recipe targets are:

```math
D_{\mathrm{puck}}^* = 18.0\,\mathrm g,
\qquad
Y^* = 36.0\,\mathrm g,
```

with an acceptable brew-duration interval of $30$ – $35\,\mathrm s$ and nominal centre $32.5\,\mathrm s$.

For grinder-dose control, $D_{\mathrm{out}}^\*$ denotes the target **raw grinder output**. It is initially also $18.0\,\mathrm g$, but it is conceptually distinct from $D_{\mathrm{puck}}^*$ because the puck may be manually corrected after grinding.

Some older formulas or implementation-facing documents use $D_{\mathrm{target}}$ as shorthand for $D_{\mathrm{out}}^*$ in the dose-controller context.

## Bean/session context and process state

### $B_n$ — bean/session context

$B_n$ denotes the known coffee/session context associated with shot $n$. It is a shorthand for contextual information, not necessarily one scalar number. Depending on the model it may represent or index information such as bean identity, dial-in session, roast/opening context, or a calibration epoch.

A model must state which parts of $B_n$ it actually uses. Writing $B_n$ in a conceptual model does **not** mean that every possible bean property is measured.

### $\mathbf z_n^{(g)}$ — grinder state/context

$\mathbf z_n^{(g)}$ is a conceptual placeholder for additional grinder-related state or context that may affect output beyond the current setting and duration. Candidate components include, for example:

- previous grinder setting or a structured description of the setting change;
- whether this is the first grind after a setting change;
- time since the previous grind;
- purge history;
- slow drift or thermal state;
- a latent retention/exchange state if prospective evidence eventually justifies one.

It is **not** a claim that all of these variables are observed, useful, or implemented. A concrete model must replace the placeholder with explicit measured features and/or a defined latent state.

### $\mathbf z_n^{(e)}$ — extraction/brew state/context

$\mathbf z_n^{(e)}$ is the analogous placeholder for additional state or context affecting extraction. Candidate components could include machine conditions, puck-preparation variation, temperature-related state, or other measured/latent effects.

Again, this is only conceptual notation. Concrete models must say what is actually included.

## Process functions and residuals

The high-level system-identification framing uses:

- $f_D(\cdot)$ for the unknown grinder-output mapping;
- $f_E(\cdot)$ for the unknown extraction/flow mapping;
- $\varepsilon_n^{(D)}$ for grinder-output residual disturbance;
- $\boldsymbol\varepsilon_n^{(E)}$ for residual disturbance in a vector-valued extraction outcome such as $(t_{\mathrm{brew},n},Y_n)$.

A structured grinder model may additionally use:

- $r(G_n,B_n,\ldots)$ for a learned grinder output rate, typically in g/s;
- $h(\cdot)$ for an optional history/transition correction, for example a retention-related effect.

Neither $r$ nor $h$ is assumed to exist in the final model merely because the notation is available.

## Grinder-setting representation

$G_n$ is the **user-facing grinder setting**, not a guaranteed physical fineness coordinate. For a Baratza Sette 270, a label such as `3E` is therefore not automatically converted to a number on an equally spaced axis.

If a later model needs arithmetic on grinder fineness, it must first define and justify a numerical representation such as

```math
z(G),
```

where $z(G)$ maps a physical/user setting to a validated numerical or latent fineness coordinate. Expressions such as $G_n-G_{n-1}$ are invalid for opaque/categorical settings unless such a representation has been established.

For models that do not require a numeric fineness axis, use explicit feature encodings instead, for example:

- $\boldsymbol\phi(G_n)$ for features representing the current setting;
- $\boldsymbol\psi(G_{n-1},G_n)$ for features representing the transition between settings.

These functions may be categorical/one-hot, structured macro/micro features, or a later calibrated numeric representation; their meaning must be stated by the model using them.

## Time-to-target notation

$T_{36}$ means the time at which the beverage would reach a final yield of $36\,\mathrm g$ under a defined measurement convention.

In the historical data this value is generally **not directly observed**. The deliberately crude linear normalization is written

```math
T_{36}^{\mathrm{linear}}
=
t_{\mathrm{brew}}\frac{36}{Y}.
```

It assumes constant average flow and must not be treated as ground truth. Model estimates are written $\hat T_{36}$ to distinguish them from the historical linear approximation.

## Recommendation/action superscripts

Where recommendation and execution must be distinguished:

- $t_{\mathrm{grind},n}^{\mathrm{rec}}$ is the recommended grind duration for shot $n$;
- $t_{\mathrm{grind},n}^{\mathrm{actual}}$ is the duration actually used;
- analogous `rec` / `actual` notation may be used for other controllable quantities.

This distinction matters because historical or live operators may deviate from a recommendation.

## Method-local notation

Method-local textbook notation follows conventional usage and need not be redefined merely for completeness. Documents should define only non-standard meanings, specialist-method notation that is not reasonably obvious to the intended audience, or local roles that would otherwise be ambiguous.

Do not assume that a symbol used in one methodological example has the same semantics elsewhere unless the document says so.
