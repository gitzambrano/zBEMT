# `documentation.html` — refactor skeleton

## The rules this structure serves

These are the standing rules. They also live in `CLAUDE.md` and in
`docs/software_requirements.md` §3.5, and most of them are enforced by
`tests/test_documentation.py` and `tests/test_help_content.py`.

1. **One chapter per GUI tab, in tab order.** No exceptions among the page
   chapters. Only the introductory chapters, which explain the whole, sit
   outside that rule. Never bury a page inside a physics chapter.
2. **Within a chapter, the GUI's own order**: block by block as they appear
   on screen, field by field within each block.
3. **No links out of a field's section.** Everything needed to understand
   and set it is there. A named model is explained where its control is.
4. **Every field**: the physics, the equation it enters, every option it
   offers, and how to set it in **GUI**, **`.bemt`** and **CLI** — three
   separate paragraphs, in that order.
5. **No internal code detail**: no class or function names, no paths inside
   the package, no development notes.
6. **GUI / CLI / `.bemt`** are the only names for the three interfaces.
7. **Plain, formal, explicative English.** Full sentences, no fragments.
8. **Each page chapter opens with its tab's screenshot.** Tabs are numbered
   1-7 for the reader.
9. **Help popups open the right place**: a field or block on a tab opens a
   section inside that tab's chapter.

---

## Status

The restructure is **done**. The document now reads:

```
0-5   Introduction  how to think · installation · GUI/CLI/.bemt · tutorial ·
                    nomenclature and axes · the method
6-12  THE PAGES     Project · Geometry · Airfoil · Config/Engine ·
                    Run Case · Run Batch · Results
13-14 Reference     outside the GUI · limitations
```

Dissolved into the pages, and deleted as chapters:

| Was | Now lives in |
|---|---|
| Inflow models | Config/Engine § inflow model |
| Physical corrections | Prandtl and 3-D → Config; reverse flow, Øye, compressibility → Airfoil |
| Numerical solver | Config/Engine § the solver |
| Propeller mode | Nomenclature § propeller mode |
| Hover · Forward flight | The method |
| Parameter index by tab | deleted — the per-chapter field lists replace it |
| Worked walkthrough | deleted |
| Rotor and blade geometry | Geometry chapter |

## Remaining

Nothing. The structure and the prose pass are complete.

---

## Part I — Introduction (may explain across tabs)

### 0. How to think about zBEMT
The two-theory idea stated once: blade element theory gives the load from the
local flow, momentum theory gives the induced velocity from the load, and the
solution is the inflow at which they agree. Everything else is a correction on
one side or the other. *(keep, already written)*

### 1. Installation
Python version; the base install and each optional group (`gui`, `viz3d`,
`neuralfoil`, `interactive`, `dev`, `all`); the two commands; what happens when
an optional package is absent. *(written, pending insertion)*

### 2. The GUI, the CLI and the `.bemt` files
What each is for. The project folder and what each file holds. How a value is
set in each of the three. Validation. **A full outputs table**: GUI / CLI ×
single case / batch → which files appear, where, and the control that asks for
each one. *(written; outputs table to be expanded — item D2)*

### 3. Nomenclature and axes
Symbols, units, and the rotor/propeller axis convention with the SVG. The one
place the letter rotation is explained; each page chapter then states its own
field's letters directly, without pointing here.

### 4. The method
The shared derivation, once: blade element velocities and angles, the loads,
momentum theory on an annulus, the coupled fixed-point equation, and the range
of validity. Everything here is model-independent — nothing that changes when a
dropdown changes.

---

## Part II — The pages (chapters 5-11, GUI tab order)

### 5. Project  — *tab 0*
- 5.1 Operation mode: rotor or propeller — `is_propeller`
- 5.2 Project name — `name`
- 5.3 Existing projects, new, open, save

### 6. Geometry — *tab 1*
- 6.1 Global geometry: `n_blades`, `radius_m`
  *(absorbs: solidity and blade aspect ratio)*
- 6.2 Radial distribution table: `r_norm`, `chord_norm`, `twist_deg`
  *(absorbs: why chord tapers, why twist falls outboard, spanwise loading)*
- 6.3 Generate table: presets, `root_cutout_norm`, `origin`, `origin_params`
- 6.4 The blade section: `airfoil_name`
- 6.5 Preview: plan view, chord/twist, rotor 3D

### 7. Airfoil — *tab 2*
- 7.1 Radial sections: `r_norm`, single vs multi-section, what is per-section
- 7.2 Aerodynamic model: `name`, `source`, `cl_alpha`, `alpha0_deg`, `cd0`, `k`,
      `stall_model`, `alpha_stall_pos_deg`, `alpha_stall_neg_deg`,
      `extend_full_range`, `viterna_blend_width_deg`
      *(absorbs: the four stall models, Viterna-Corrigan full-range extension)*
- 7.3 Dynamic stall: `use_dynamic_stall`, `dynamic_stall_A`,
      `dynamic_stall_fade_start_deg`, `dynamic_stall_fade_end_deg`,
      `dynamic_stall_method`, `dynamic_stall_model`, `dynamic_stall_f_reg`,
      time-marching settings
      **← absorbs the whole Øye derivation, today in chapter 14.4**
- 7.4 Reverse flow: `reverse_flow_model`, `reverse_flow_blend_factor`,
      `thin_plate_blend_center_deg`, `thin_plate_blend_width_deg`
      **← absorbs the five reverse-flow models, today in chapter 14.2**
- 7.5 Compressibility: `use_compressibility`
      **← absorbs Prandtl-Glauert, today in chapter 14.3.3**
- 7.6 Tabulated polar: import and export, the CSV format
- 7.7 Profile geometry: `naca_code`, `cst_upper`, `cst_lower`,
      `bezier_control_points`, `geometry`, coordinate files
- 7.8 NeuralFoil: `external_engine`, `external_reynolds_list`,
      `external_mach_list`, `external_alpha_min_deg`, `external_alpha_max_deg`,
      `external_alpha_step_deg`
- 7.9 Preview

### 8. Config/Engine — *tab 3*
- 8.1 Mesh and atmosphere: `Ne`, `Npsi`, `rho`, `a_sound`, `nu_air`,
      `integration_offset`
      *(absorbs the radial-azimuthal mesh derivation)*
- 8.2 Inflow model: `inflow_field_model`, `pitt_peters_states`,
      `pitt_peters_outer_iter`, `pitt_peters_relax`, `pitt_peters_tol`
      **← absorbs all of chapter 13: Glauert, Coleman, Drees, Pitt-Peters**
- 8.3 Tip and root loss: `prandtl_loss_mode`
      **← absorbs the Prandtl derivation, today in chapter 14.1**
- 8.4 Three-dimensional effects: `use_rotational_augmentation`,
      `use_radial_flow_correction`, `radial_flow_max_skew_deg`
      **← absorbs Himmelskamp/Snel and the independence principle, chapter 14.3**
- 8.5 Induced-inflow solver: `solver`, `max_iter`, `tol`, `relax`,
      `relax_schedule` and the five schedule parameters
      **← absorbs chapter 15: Newton, fixed point, bisection, Aitken**
- 8.6 Early exit: `early_exit_fraction`, `stagnation_patience`,
      `stagnation_min_frac`
- 8.7 Diagnostics: `collect_history`, `mask_reverse_flow_plots`

### 9. Run Case — *tab 4*
- 9.1 Run mode and trim: `trim_mode`, `target_kind`, `target_value`
- 9.2 In-plane flow: `mu_x` and every unit it offers
- 9.3 Along-shaft flow: `Vz` and every unit it offers
- 9.4 Collective: `collective_deg`
- 9.5 Rotational speed: `rpm`
- 9.6 Saved cases: `name`
- 9.7 The summary table
      *(absorbs hover and forward-flight worked cases, chapters 4 and 5)*

### 10. Run Batch — *tab 5*
- 10.1 Generate cases: the sweep axes
- 10.2 Fixed values
- 10.3 The case queue: `conditions`
- 10.4 Saved batches: `name`, `sweep_kind`, `sweep_params`
- 10.5 Run
- 10.6 Export: `outdir`, `plots`

### 11. Results — *tab 6*
- 11.1 The session list
- 11.2 Disk map
- 11.3 Coefficients versus axis
- 11.4 Azimuth and radius
- 11.5 3D
- 11.6 Export and report
- 11.7 The coefficients: $C_T$, $C_Q$, $C_P$, $FM$, $\eta_{prop}$, $H$, $Y$,
      $M_x$, $M_y$ *(absorbs the coefficient definitions and the
      rotor-versus-propeller conventions from chapter 16)*

---

## Part III — Reference

### 12. Command-line reference
Every flag, grouped as the GUI groups them.

### 13. Limitations and validity
What the method does not model, and the bands where results are unreliable.

### References

---

## What is dissolved

| Today | Goes to |
|---|---|
| 3. Physics fundamentals | split: nomenclature → ch 3, method → ch 4, geometry/solidity → ch 6, coefficients → ch 11 |
| 4. Hover · 5. Forward flight | worked cases → ch 9; validity → ch 13 |
| 13. Inflow models | **ch 8.2** |
| 14. Physical corrections | Prandtl → **8.3**; 3-D → **8.4**; reverse flow → **7.4**; Øye → **7.3**; compressibility → **7.5** |
| 15. Numerical solver | **ch 8.5** |
| 16. Propeller mode | mode → ch 5.1; letters → ch 3; coefficients → ch 11.7 |
| 17. Parameter index by tab | deleted — the per-chapter field lists replace it |
| 2. Tutorial | trimmed to the workflow order; the rest is already in the page chapters |

## Order of work

1. Chapters 3 and 4 (nomenclature, method) — the shared base the pages rely on.
2. Chapter 7 (Airfoil), absorbing Øye, reverse flow, compressibility, Viterna.
3. Chapter 8 (Config/Engine), absorbing inflow, Prandtl, 3-D, solvers.
4. Chapters 5, 6, 9, 10, 11 — already partly written to the standard; complete
   them and remove their outbound links.
5. Delete the dissolved chapters; renumber; regenerate index and field lists.
6. Add a test: no page chapter contains an internal link.
