# zBEMT Documentation Prose Improvement Plan

## Purpose

This plan defines a controlled rewrite of `docs/documentation.html` so that it becomes a precise, formal, maintainable physics reference and the authoritative source for embedded-help content.

The rewrite must remain aligned with `AGENTS.md` and `docs/software_requirements.md`, and must improve clarity without reducing technical physics content.

## Governing requirements

The rewrite must preserve the repository requirements, especially:

- English everywhere.
- Formal explanatory prose.
- One chapter per GUI tab, in tab order.
- Sections following the GUI block-by-block and field-by-field.
- Every field section self-contained.
- User-facing mathematics written in LaTeX.
- No class names, function names, package paths, or development notes in user documentation.
- GUI, `.bemt`, and CLI configuration paths documented separately.
- `docs/documentation.html` remains the authoritative long-form physics reference.
- Generated TOC, field indexes, screenshots, and inventories remain generated artifacts.
- Existing documentation/help/notation/nomenclature tests remain acceptance gates.
- Rotor/propeller terminology and axis conventions must remain consistent with the software requirements.
- Documentation must remain self-contained and usable offline.

## Current prose assessment

### Strengths

The current documentation already contains substantial technical material. It explains physical meaning, equations, numerical behavior, model limitations, rotor/propeller conventions, solver behavior, and result interpretation.

The field-help structure is also strong: definition, equation, physical effect, range/options, and interface-specific configuration. This structure should be preserved.

### Main problems

#### 1. User documentation is mixed with implementation notes

Some sections explain internal storage, implementation history, internal keys, package organization, or obsolete development artifacts.

Keep:

- physical explanations;
- user-observable behavior;
- `.bemt` keys;
- CLI flags;
- configuration conventions.

Remove or rewrite:

- internal variable names;
- module/package paths;
- implementation history;
- obsolete planning-document references;
- explanations of why the code internally stores something a certain way.

The reader needs to understand the model and how to configure it, not the internal architecture.

#### 2. Prose is sometimes too conversational

Several passages in documentation.html use editorial or conversational language. Rewrite them into formal engineering prose.

Preferred structure:

1. physical fact;
2. governing equation;
3. consequence of changing the parameter;
4. applicability/limitation;
5. configuration instructions.

#### 3. Repetition

Workflow, axis conventions, propeller terminology, solver convergence, reporting, and batch behavior are explained in several places.

Separate the roles:

- introduction: conceptual understanding;
- method chapters: derivations;
- GUI chapters: configuration, detailed physics and mathematics; limitations
- reference chapters: concise authoritative reference.

Field sections (in GUI chapters) must remain self-contained and should avoid links to theory. All the physics, derivations and mathematics pertaining that field should be in the field sections. Do not duplicate.

#### 4. Terminology needs normalization

Use consistent terminology throughout:

- airfoil;
- radial station;
- airfoil section;
- in-plane flow;
- along-shaft flow;
- collective pitch;
- geometric twist;
- induced velocity;
- advance ratio;
- rotor convention;
- propeller convention.

Avoid switching between several names for the same quantity.

#### 5. Overloaded paragraphs

Split paragraphs that simultaneously contain physics, mathematics, configuration instructions, implementation details, and historical rationale.

#### 6. Technical/prose defects

Audit and correct incomplete or misleading statements, including passages that appear to contain unfinished references.

Specifically verify:

- dynamic stall versus unsteady/time-marching terminology;
- Pitt-Peters terminology, particularly where the supported model is steady;
- statements about numerical iteration behavior;
- claims about model validity outside nominal regimes;
- default behavior claims;
- references to obsolete files or plans.

## Repository-wide docstring findings

The documentation rewrite should be coordinated with the durable docstrings because they form the same documentation ecosystem.

Important findings from the repository review:

- `zbemt/bemt.py` uses terminology describing Pitt-Peters as dynamic inflow. This must be reconciled with the requirements describing the supported model as steady.
- `zbemt/bemt.py` contains a reference to `zBEMT.md` that should be verified against the current repository and removed/replaced if obsolete.
- `zbemt/api.py` contains references to old interface names and obsolete planning artifacts. These should be updated.
- `zbemt/studies.py` contains future-work wording that should be checked against current NeuralFoil functionality and requirements.
- `zbemt/validation.py` references obsolete planning documents such as `docs/plano.md` and `docs/plano_v2.md`.
- `zbemt/nomenclature.py` contains implementation-history material that should be reduced to the durable public invariant.
- `zbemt/gui/help_content.py` contains useful physics explanations but also Unicode mathematical symbols. User-facing mathematical notation should be normalized to LaTeX where required.
- Some test documentation/identifiers contain Portuguese despite the English-everywhere requirement. This belongs in the documentation cleanup backlog.

Do not blindly copy docstrings into `documentation.html`. Use them as technical source material, then rewrite them according to the user-documentation rules.

No stale reference should survive merely because it is inside a comment or docstring.

All docstrings should state the script purpose and objectives, list and explain each input, output and functions, conventions, limitations, interactions with other files (and anything that is important to understand about that file). We should avoid historical decisions and so on. Be very clear, concise, direct, formal and informative.

## Target information architecture

Preserve the required chapter structure.

### Chapters 0–5: introduction and theory

These chapters should answer:

- What is zBEMT?
- How is a case configured?
- What physical conventions are used?
- What are the rotor/propeller differences?
- What mathematical model is being solved?

### Chapters 6–12: GUI tabs

One chapter per GUI page, in exact tab order:

1. Project
2. Geometry
3. Airfoil
4. Config/Engine
5. Run Case
6. Run Batch
7. Results

Each chapter starts with its generated screenshot and then follows the visible GUI order.

For each field, we shall have de definition, the physics, mathematics, derivations, applicability, limitations, options and how to configure the GUI, the .bemt and the CLI.

### Chapters 13–14: reference

Keep reference material that does not naturally belong to a GUI tab. Do not use reference chapters as a dumping ground for material that belongs in field sections.

## Field-section template

Every configurable field or coherent field block should use this structure.

### Definition

State exactly what the quantity represents physically, units and so on.

### Mathematics

Give the governing equation in LaTeX. Define symbols, units, and sign conventions. You may have here useful derivations.

### Physical effect

Explain what increasing/decreasing/changing the value does to loads, inflow, polar selection, convergence, or results.

Distinguish direct effects from secondary effects.

### Options

Document every option at the point where it is selected.

### Applicability and limitations

Explain when the field is ignored, incompatible with other fields, or physically inappropriate.

### GUI

State the exact tab and block/field name. Explain each option.

### `.bemt`

State the exact stored key and representation.

### CLI

State the exact flag or `--set` path and valid values.

Keep GUI, `.bemt`, and CLI sections separate by a paragraph and follow the color representation.

If a input file is imported or a output file is exported, a clear explanation of the format

## Physics prose standards

### Define before interpreting

Do not say that a quantity controls another quantity before defining it.

### Dimensional versus nondimensional quantities

Whenever introducing quantities such as:

`V`, `mu`, `J`, `lambda`, `T`, `Q`, `P`, `C_T`, `C_Q`, `C_P`, efficiency,

state the reference scales and conventions.

### Sign conventions

Explicitly define positive directions where relevant, especially for:

- axial velocity;
- in-plane velocity;
- angle of attack;
- collective;
- torque;
- power;
- reverse flow.

### Semi-empirical models

For models such as Prandtl, Himmelskamp/Snel, Viterna-Corrigan, Oye, radial-flow corrections, stall models, and inflow models, distinguish:

1. governing equation;
2. assumptions;
3. empirical/semi-empirical nature;
4. useful range;
5. behavior outside the useful range.

### Avoid unsupported universal claims

Do not present typical solver iteration counts, convergence behavior, or model accuracy as universal invariants unless explicitly guaranteed by the requirements or implementation.

### Preserve physical intuition

Keep concise explanations of important physical mechanisms, such as:

- solidity and loading;
- tip/root loss;
- reverse flow;
- retreating/advancing asymmetry;
- inflow;
- propeller advance ratio;
- effects of Reynolds and Mach number.

## Rotor/propeller terminology

Use one conceptual model consistently:

- vehicle `x` is longitudinal/forward;
- vehicle `z` is vertical;
- rotor shaft is vertical;
- propeller shaft is horizontal;
- the same physical flow component may use different displayed symbols depending on the configured vehicle;
- user-facing terminology must describe the configured machine, not internal storage.

Do not expose internal-key mappings unless required to explain a `.bemt` field.

## LaTeX and notation cleanup

Perform a user-facing notation audit.

Replace Unicode mathematical symbols with LaTeX where required.

Avoid plain-text mathematical forms such as:

- `lambda_i`;
- `mu_x`;
- `alpha_rotor`.

Use LaTeX for mathematical notation and `<code>` for actual `.bemt` keys or CLI flags.

Do not mix code identifiers with mathematical symbols.

Verify that all equations render correctly offline with the bundled KaTeX resources.

## Links and cross-references

Links should primarily answer:

1. Where is the complete derivation?
2. Where is the complete configuration reference?

A field section must still be understandable without following a link. Avoid creating links in each chapter.

Remove links to obsolete plans, source files, development artifacts, or nonexistent documents.

Verify every remaining anchor and referenced image.

## Figures and captions

Keep repository-hosted figures. If need, generate new ones through screenshots or exported figures results.

Every figure caption should state:

- what is plotted;
- relevant operating condition;
- independent/dependent quantities when needed;
- units when needed;
- physical interpretation.

For disk maps, explicitly document the azimuth convention and operating condition.

Do not make a caption claim broader than the plotted case.

## Documentation/help synchronization

Use the following hierarchy:

- HTML field section: complete explanation;
- popup help: concise version of the same physics;
- tooltip: one-sentence operational description.

Do not maintain independent conflicting physics descriptions.

If a popup contains a statement that is not represented in the corresponding HTML section, update the HTML first.

## Chapter priorities

### Priority 1 — Introduction and nomenclature

Normalize terminology and notation and remove implementation-history material.

### Priority 2 — Method

Improve derivation order:

assumptions → variables → equation → physical interpretation → limitations → solver relationship.

### Priority 3 — Airfoil

Clarify analytical, tabulated, NeuralFoil, stall, reverse-flow, and compressibility behavior.

### Priority 4 — Config/Engine

Clarify mesh, inflow, corrections, and numerical solver behavior without exposing implementation internals unnecessarily.

### Priority 5 — Run Case / Run Batch

Clearly distinguish operating-condition definition from study/batch definition.

Explain fixed inputs versus trimming without duplicating the same theory excessively.

### Priority 6 — Results

Organize around engineering questions:

- where is the load?
- how does performance vary?
- how does blade loading vary with azimuth/radius?
- did the solution converge?
- what can be exported?
- how are the output files formatted?

### Priority 7 — Reference

Make the reference concise and authoritative.

## Stale-content cleanup

Search the complete documentation/docstring corpus for:

- obsolete filenames;
- obsolete module names;
- obsolete CLI commands;
- obsolete planning documents;
- implementation-history language;
- future-work statements for already implemented features;
- claims conflicting with `software_requirements.md`;
- nonexistent files;
- inconsistent GUI names;
- old rotor/propeller axis terminology;
- Unicode mathematical notation;
- Portuguese user-facing text.

No stale reference should survive merely because it is inside a comment or docstring.

All docstrings should state the script purpose and objectives, list and explain each input, output and functions, conventions, limitations, interactions with other files (and anything that is important to understand about that file) We should avoid historical decisions and so on. Be very clear, concise, direct, formal and informative.

## Acceptance and generated artifacts

The rewrite is complete only when:

1. the TOC generator succeeds;
2. the field index generator succeeds;
3. GUI screenshots remain valid;
4. field inventory remains consistent;
5. documentation tests pass;
6. help-content tests pass;
7. notation tests pass;
8. nomenclature and rotor/propeller parity tests pass;
9. the complete required test suite passes;
10. there are no unresolved links, missing images, obsolete commands, nonexistent file references, or invalid mathematical notation.

## Implementation sequence

### Phase A — inventory

- regenerate TOC;
- regenerate field index;
- inventory every field section;
- inventory terminology variants;
- inventory obsolete references.

### Phase B — introduction

Rewrite workflow, interface concepts, nomenclature, and propeller convention.

### Phase C — physics

Rewrite method sections while preserving verified equations and technical depth.

### Phase D — GUI chapters

Work tab-by-tab and strictly in screen order. Verify every GUI/`.bemt`/CLI mapping against the field inventory.

### Phase E — help and docstrings

Check popup help consistency with HTML, normalize notation, remove obsolete references, and correct stale model terminology.

### Phase F — verification

Regenerate all generated artifacts and run documentation, notation, nomenclature, help, and complete-suite tests.

## Definition of done

The documentation is complete when a technically competent engineer can configure, run, and interpret zBEMT from `docs/documentation.html` without reading source code.

Every configurable field must have:

- a self-contained physical definition;
- governing mathematics;
- physical consequences;
- units, range, options and limitations;
- GUI instructions;
- `.bemt` representation;
- CLI configuration.
- if a input file is imported or a output file is exported, a clear explanation of the format.

Rotor and propeller terminology must be unambiguous, mathematical notation must be rendered as LaTeX, and the documentation must reference only current repository artifacts.

The objective is not to make the document shorter. The objective is to ensure that every paragraph has a clear technical purpose and that every documented statement agrees with the current software or with an explicitly stated physical model.
