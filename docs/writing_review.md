# Writing review: findings and suggested changes

This report lists the writing defects found in `docs/documentation.html` and
in the `zbemt/` docstrings, measured against the `writing-rules` skill
(`.claude/skills/writing-rules/SKILL.md`).

**Status: applied.** The rules `G25` to `G31` of Section 8 are now in the
skill. The revisions below were applied to the source, in these passes:

- Every British spelling became American (`G31`), in the manual and in the
  code.
- Every Portuguese user-facing string, warning and comment became English.
- 161 prose semicolons in `docs/documentation.html` became sentences
  (`G14`), and its Latin abbreviations became words (`G20`).
- The 24 bare `argparse` help strings became real instructions (`P2`).
- The module docstrings named below were rewritten.

Two things were deliberately **not** done, and remain open:

- The blanket sweep of the roughly 950 ` -- ` prose dashes in the
  docstrings. Only the dashes in the findings below were changed. A
  mechanical sweep of the rest risks changing meaning, and needs a pass of
  its own.
- The 284 `&mdash;` entities in `docs/documentation.html`, for the same
  reason. Many sit in headings, where changing the text would also mean
  changing every cross-reference `title` that quotes it.

---

## 1. Scope and method

Reviewed:

- `docs/documentation.html`, prose only. Lines 1 to 633 hold CSS and
  JavaScript and were excluded.
- The module, class, and function docstrings of `zbemt/bemt.py`,
  `api.py`, `models.py`, `nomenclature.py`, `cli.py`, `validation.py`,
  `studies.py`, `airfoils.py`, and `geometry.py`.
- The `argparse` help strings and the user-facing error and warning
  messages in those modules.

Excluded on purpose, because `CLAUDE.md` exempts them:

- HTML `id` attributes. Several are Portuguese, and they are addresses
  rather than text.
- Code identifiers. The skill governs prose, not names.
- Greek symbols and mathematical notation, which `CLAUDE.md` requires.

Total: **214 findings**. Findings 1 to 208 are style defects against the
skill. Findings 209 to 214 are language defects that break `CLAUDE.md`
directly, and they are listed separately in Section 7.

---

## 2. Measured counts

`docs/documentation.html`, prose only:

| Rule | Counted | Hits |
|---|---|---|
| `G14` | Semicolons joining clauses | 363 |
| `G15` | Em or en dashes | 35 |
| `G20` | `e.g.`, `i.e.`, `etc.` | 12 |
| `G3` | Passive voice with a named actor | 8 |
| `G4` | "has been", "have been", "had been" | 6 |

`zbemt/*.py`:

| Rule | Counted | Hits |
|---|---|---|
| `G15` | Lines with an em or en dash | 103 |
| `G20` | Latin abbreviations | 65 |
| `G6` | Contractions | 12 |

Two things are already correct and must not be changed:
`docs/documentation.html` contains **no contractions**, and its Portuguese
`id` attributes are deliberate.

`G14` at 363 hits is the largest single problem in the project.

---

## 3. Findings: `docs/documentation.html`

### Chapter 0, How to think about zBEMT

**1.** Line 769, rules `G15`, `G14`, `G16`

- now: `zBEMT solves the blade-element and momentum formulations on a common radial--azimuthal mesh. ... both formulations describe the same local load; their equality determines the induced velocity. The integrated solution follows from these local aerodynamic states and a consistent momentum balance.`
- suggested: `zBEMT solves the blade-element and momentum formulations on a common radial and azimuthal mesh. ... both formulations describe the same local load. Their equality therefore determines the induced velocity. The integrated solution then follows from these local aerodynamic states and a consistent momentum balance.`

**2.** Lines 777, 778 and 785, rule `G30` (proposed)

- now: `the local flow the airfoil actually sees` and `says nothing about what that induced velocity should be` and `says nothing about airfoils`
- suggested: `the local flow at the airfoil` and `does not determine that induced velocity` and `does not describe the airfoil`

**3.** Line 788, rules `G22`, `D1`

- now: `The solver couples them iteratively: Blade Element Theory computes aerodynamic loads for an assumed induced velocity, while Momentum Theory updates the induced inflow until both momentum balance and blade loads converge.`
- suggested: `The solver couples them iteratively. Blade Element Theory computes the aerodynamic loads for an assumed induced velocity. Momentum Theory then updates the induced inflow until the momentum balance and the blade loads converge.`

**4.** Line 807, rules `G14`, `G16`

- now: `are included whenever they help select a value or diagnose a result; source-level details that do ...`
- suggested: Split at the semicolon. Open the second sentence with `However,`.

### Chapter 1, Installation

**5.** Line 821, rule `G14`

- now: `The core solver uses NumPy, SciPy, Matplotlib, and pandas; GUI, three-dimensional visualization, interactive reporting, and external polar generation are optional dependencies.`
- suggested: `The core solver uses NumPy, SciPy, Matplotlib, and pandas. The GUI, the three-dimensional visualization, the interactive reporting, and the external polar generation are optional dependencies.`

**6.** Line 889, rules `G14`, `G1`, `G22`

- now: `If the commands are not found, the installation directory is not on your path; running <code>python -m zbemt.gui.app</code> and <code>python -m zbemt.cli</code> does the same thing. Both accept no arguments at all, in which case they fall back to the starter rotor, so there is always something to look at.`
- suggested: `If the commands are not found, the installation directory is not on your path. In that case, run <code>python -m zbemt.gui.app</code> or <code>python -m zbemt.cli</code> instead. Both accept no arguments. Without arguments, both fall back to the starter rotor project.`

### Chapter 2, The three interfaces

**7.** Line 937, rule `G14`

- now: `They are the definition of the case; everything else reads from them.`
- suggested: `They are the definition of the case. Everything else reads from them.`

**8.** Line 998, rules `G14`, `G3`, `G31` (proposed)

- now: `A key that is present but not recognised is reported as unknown and ignored; it does not stop the run, but the value is not used, and the field falls back to its default.`
- suggested: `zBEMT reports a key that is present but not recognized as unknown, and ignores it. The run does not stop. However, the value is not used, and the field falls back to its default.`

**9.** Line 1015, rules `G14`, `G15`, `G22`

- now: `Typing a value into a field changes the project held in memory; nothing reaches disk until you save, at which point the whole project is written back to <span class="bemt">.bemt</span> files &mdash; the same files you could have edited by hand.`
- suggested: `Typing a value into a field changes the project held in memory. Nothing reaches disk until you save. At that point, zBEMT writes the whole project back to the <span class="bemt">.bemt</span> files. These are the same files you could have edited by hand.`

**10.** Lines 1109 and 1110, the interface comparison table, rules `G14`, `G6`, `G12`, `G7`

- now: `Summary metrics table in Run Case tab; detailed radial cuts, residual history, and 2D disk maps available in Results tab.` and `Progress bar and condition status table; batch runs saved to Results tab for comparative sweep overlays.`
- suggested: `The Run Case tab shows the summary metrics table. The Results tab shows the detailed radial cuts, the residual history, and the 2D disk maps.` and `A progress bar and a condition status table report the run. The Results tab keeps the batch runs, so sweeps can be overlaid for comparison.`

**11.** Line 1122, rule `G3`

- now: `Nothing below is written unless it is asked for, except the results table, which is written by default from the <span class="cli">CLI</span>.`
- suggested: `zBEMT writes nothing below unless you ask for it. The one exception is the results table, which the <span class="cli">CLI</span> writes by default.`

**12.** Line 1157, rule `G20`

- now: `(or specific field, e.g. <code>--plots disk_map_CT</code>)`
- suggested: `(or a specific field, for example <code>--plots disk_map_CT</code>)`

### Chapter 3, Tutorial

**13.** Line 1247, rule `G14`

- now: `<i>Ne</i> discretizes the radius and <i>Npsi</i> discretizes the azimuth; together they define the mesh over which the solver integrates forces.`
- suggested: `<i>Ne</i> discretizes the radius and <i>Npsi</i> discretizes the azimuth. Together, they define the mesh over which the solver integrates the forces.`

**14.** Line 1250, rule `G15`

- now: `The static validation runs on its own — the panel at the bottom of the tab restates it after every edit, ...`
- suggested: `The static validation runs on its own. The panel at the bottom of the tab restates it after every edit, ...`

**15.** Line 1261, rule `G14`

- now: `Both paths feed the same queue; review it before running.`
- suggested: `Both paths feed the same queue. Review the queue before you run it.`

**16.** Line 1284, rules `G22`, `G21`, `G3`

- now: One 60-word sentence chaining all seven tabs with `&rarr;`.
- suggested: One short lead-in sentence, then the seven tabs as a numbered list, one per item.

**17.** Line 1296, rule `G15`

- now: `Clicking any indicator jumps directly to the corresponding tab — useful for resuming a large project without navigating sequentially through the tabs.`
- suggested: `Click any indicator to jump directly to the matching tab. This helps you resume a large project without stepping through the tabs in order.`

**18.** Line 1314, rule `G4`

- now: `The asterisk means the work has not been written to disk, not that it has not been applied.`
- suggested: `The asterisk means that zBEMT did not yet write the work to disk. It does not mean that the work was not applied.`

**19.** Line 1324, rule `G15`

- now: `<b>Restore</b> — labelled <b>Restore</b> in the Geometry and Airfoil tabs — does the opposite: ...`
- suggested: `<b>Restore</b> does the opposite. The Geometry and Airfoil tabs label the same control <b>Restore</b>. It reloads ...`

**20.** Line 1332, rule `G15`

- now: `... choosing Save writes exactly what was on the screen — there is no second category of pending edit that the dialog could silently drop.`
- suggested: `... choosing Save writes exactly what was on the screen. There is no second category of pending edit that the dialog could drop without telling you.`

### Chapter 4, Nomenclature and axes

**21.** Line 2159, rule `G20`

- now: `... harmonic inflow variations (e.g., Pitt-Peters harmonic coefficients) evaluate to zero.`
- suggested: `... harmonic inflow variations (for example, the Pitt-Peters harmonic coefficients) evaluate to zero.`

**22.** Line 2262, rules `G20`, `G15`

- now: `<b>Positive when the flow arrives from below</b>, i.e. the disk is tilted nose-up relative to the free stream. Axial descent &mdash; flow arriving on the front face &mdash; reads $180^\circ$.`
- suggested: `<b>Positive when the flow arrives from below</b>, that is, when the disk is tilted nose-up relative to the free stream. Axial descent reads $180^\circ$. In axial descent, the flow arrives on the front face.`

**23.** Line 2284, rule `G14`

- now: `Both coefficient families are computed at every evaluation regardless of <code>is_propeller</code> (...); the mode decides which family is displayed, plotted and swept by default.`
- suggested: `zBEMT computes both coefficient families at every evaluation, whatever <code>is_propeller</code> holds. The mode decides which family it displays, plots and sweeps by default.`

**24.** Line 2447, rules `G15`, `G20`, `G22`

- now: `Specifying the cruise case the wrong way &mdash; the $65$ m/s entered in the cross-flow field, i.e. <code>mu_x = 0.264</code> with <code>Vz = 0</code> &mdash; converges just as cleanly and reports $T=7336$ N, ...`
- suggested: `The cruise case can be specified the wrong way. That is, the $65$ m/s goes into the cross-flow field, which gives <code>mu_x = 0.264</code> with <code>Vz = 0</code>. This converges just as cleanly. It reports $T=7336$ N, ...`

**25.** Line 2454, rule `G22`

- now: A 56-word sentence listing every surface the convention holds on.
- suggested: Two sentences. The first states that the axis naming and the two angles are fixed conventions of the program. The second lists the surfaces.

**26.** Line 2513, rules `G14`, `G15`, `G22`, `G16`

- now: A ~70-word sentence carrying two semicolons and an em dash.
- suggested: Four sentences, one idea each, with connectors between them.

### Chapter 5, The method

**27.** Line 2745, rules `G3`, `G12`, `G7`

- now: `Sectional aerodynamic operating point is characterized by the blade loading coefficient $C_T/\sigma$, which reflects average sectional lift coefficient across the disk. Aerodynamic stall limits are defined in terms of $C_T/\sigma$ ...`
- suggested: `The blade loading coefficient $C_T/\sigma$ characterizes the sectional aerodynamic operating point. It reflects the average sectional lift coefficient across the disk. Therefore, zBEMT defines the aerodynamic stall limits in terms of $C_T/\sigma$ ...`

**28.** Line 2750, rules `G14`, `G21`, `G26` (proposed)

- now: `Helicopter main rotors typically operate at $\sigma \in [0.04, 0.10]$; multirotor/eVTOL rotors operate at $\sigma \in [0.10, 0.15]$; aircraft and UAV propellers typically exceed $\sigma \ge 0.15$ ...`
- suggested: A three-item list, one vehicle class per item. Write `multirotor and eVTOL rotors`.

**29.** Line 2759, rules `G14`, `G15`

- now: `$FM$ is the ratio of ideal disk-actuator power (...) to actual power <em>in hover</em>; $FM=1$ is the ideal limit, well-designed rotors operate at $0.7$–$0.8$.`
- suggested: `$FM$ is the ratio of the ideal disk-actuator power to the actual power <em>in hover</em>. $FM=1$ is the ideal limit. Well-designed rotors operate at $0.7$ to $0.8$.`

**30.** Line 2862, rule `G14`

- now: `Separation invalidates the attached-flow relation and changes both coefficients; the selected polar must therefore cover, or be extended to cover, the operating conditions of the blade.`
- suggested: `Separation invalidates the attached-flow relation and changes both coefficients. Therefore, the selected polar must cover the operating conditions of the blade, or be extended to cover them.`

**31.** Line 3221, rule `G14`

- now: `Each element $(r,\psi)$ has unknown $\lambda_i(r,\psi)$ solved essentially independently of neighboring elements; coupling between elements occurs only via the Prandtl factor`
- suggested: `Each element $(r,\psi)$ has the unknown $\lambda_i(r,\psi)$. The solver treats it as independent of the neighboring elements. Coupling between elements occurs only through the Prandtl factor.`

**32.** Line 3290, rules `G3`, `G14`

- now: `The returned aerodynamic state is used by the numerical solver and by the Results plots. ... The sequence is useful for diagnosing a solution; normal <span class="gui">GUI</span> use requires checking convergence and the physical inputs described above.`
- suggested: `The numerical solver and the Results plots use the returned aerodynamic state. ... The sequence helps you diagnose a solution. In normal <span class="gui">GUI</span> use, check the convergence and the physical inputs described above.`

**33.** Line 3297, rules `G22`, `G15`

- now: A ~75-word sentence with two em dashes carrying a parenthetical list.
- suggested: Three sentences. Move the list of inactive corrections into its own sentence, or into a vertical list.

**34.** Line 4483, rules `G1`, `G8`

- now: `A rotor blade in forward flight is never still: its angle of attack rises and falls once every revolution, and near stall the flow does not keep up.`
- suggested: `A rotor blade in forward flight is never still. Its angle of attack rises and falls once every revolution. Near stall, the flow does not follow that change fast enough.`

**35.** Line 4517, rules `G1`, `G3`

- now: `The static polar itself tells us what $f$ would be if the flow had time to settle.`
- suggested: `The static polar gives the value of $f$ for a flow that has time to settle.`

**36.** Line 4532, rule `G14`

- now: `The hysteresis is a consequence: while the angle rises, $f$ lags above $f_{st}$, so the blade is more attached than static, and lift is higher; while it falls, $f$ lags below, and lift is lower.`
- suggested: `The hysteresis follows from this. While the angle rises, $f$ lags above $f_{st}$. The blade is therefore more attached than the static case, and the lift is higher. While the angle falls, $f$ lags below, and the lift is lower.`

**37.** Line 4551, rule `G22`

- now: A 44-word sentence contrasting a wide-chord and a slender blade.
- suggested: Two sentences, one per blade type, joined by `However,`.

**38.** Line 4564, rules `G3`, `G22`

- now: `The correction is applied as post-processing on the converged solution, recomputing the section loads from the final inflow field rather than feeding back into the momentum balance.`
- suggested: `zBEMT applies the correction as post-processing on the converged solution. It recomputes the section loads from the final inflow field. It does not feed them back into the momentum balance.`

**39.** Line 5485, rule `G4`

- now: `Three settings that might be expected here are elsewhere, because they belong to what is being modelled rather than to how it is solved`
- suggested: `Three settings that you might expect here are elsewhere. They belong to the thing being modeled, not to the way the solver solves it.`

**40.** Line 5498, rule `G14`

- now: `The mesh decides how finely the disk is sampled; the air properties describe what it turns in.`
- suggested: `The mesh decides how finely zBEMT samples the disk. The air properties describe the medium the rotor turns in.`

**41.** Line 5526, rules `G15`, `G22`

- now: `In a purely axisymmetric case &mdash; hover, or any climb or descent with no in-plane component &mdash; every azimuthal station returns the same answer, so $N_\psi=1$ solves the problem exactly and raising it costs time and changes nothing.`
- suggested: `A purely axisymmetric case is hover, or any climb or descent with no in-plane component. In such a case, every azimuthal station returns the same answer. Therefore, $N_\psi=1$ solves the problem exactly. Raising it costs time and changes nothing.`

**42.** Line 5581, rule `G4`

- now: `It should be changed together with the density whenever an altitude is being modelled, ...`
- suggested: `Change it together with the density whenever you model an altitude, ...`

**43.** Lines 5705 and 5797, rule `G15`

- now: `it treats the disk as a whole and carries three states — a uniform component and two first-harmonic components — governed by a linearised unsteady actuator-disk model.`
- suggested: `it treats the disk as a whole and carries three states. These are a uniform component and two first-harmonic components. A linearized unsteady actuator-disk model governs them.`

**44.** Line 5804, rule `G14`

- now: `The outer iteration count, the relaxation and the tolerance are the three controls on that loop; the state count decides how many harmonics the disk field carries.`
- suggested: `The outer iteration count, the relaxation and the tolerance are the three controls on that loop. The state count decides how many harmonics the disk field carries.`

### Chapters 6 to 12, the GUI tabs

**45.** Line 3481, rule `G4`

- now: `Return here and press <b>Save</b>. Until then, nothing has been written to disk.`
- suggested: `Return here and press <b>Save</b>. Until then, zBEMT writes nothing to disk.`

**46.** Line 3494, rule `G14`

- now: `For a rotor, $x$ lies in the disk plane and $z$ runs along the shaft; for a propeller the two are exchanged.`
- suggested: `For a rotor, $x$ lies in the disk plane and $z$ runs along the shaft. For a propeller, the two are exchanged.`

**47.** Line 3497, rule `G14`

- now: `The window relabels both flow rows when the mode is switched, so the labels can be trusted; the letters cannot be assumed.`
- suggested: `The window relabels both flow rows when you switch the mode. You can therefore trust the labels. Do not assume the letters.`

**48.** Line 3552, rule `G14`

- now: `The list on the left shows the projects found in the repository's own projects folder; a project kept anywhere else is reached with the open button.`
- suggested: `The list on the left shows the projects found in the repository's own projects folder. Use the open button to reach a project kept anywhere else.`

**49.** Line 3788, rule `G14`

- now: `A rectangular blade needs only its chord; a tapered one needs the root chord and how far it narrows; an elliptic one needs its widest chord.`
- suggested: A three-item list, one planform per item.

**50.** Line 3799, rules `G22`, `G2`

- now: A 55-word sentence explaining why twist exists.
- suggested: Three sentences: what varies, what follows, what goes wrong without twist.

**51.** Line 3812, rule `G14`

- now: `Fifteen to twenty-five stations describe most blades; more is worth having only where the planform changes quickly.`
- suggested: `Fifteen to twenty-five stations describe most blades. More stations are worth having only where the planform changes quickly.`

**52.** Line 3879, rules `G8`, `G22`

- now: `<i>Chord/Twist</i> plots the two distributions against radius, which is where a twist column entered with the wrong sign shows up as a line sloping the wrong way.`
- suggested: `<i>Chord/Twist</i> plots the two distributions against the radius. A twist column entered with the wrong sign appears there as a line that slopes the wrong way.`

**53.** Line 5106, rules `G15`, `G22`

- now: `A missing <em>required</em> column is the one rejection at this stage: the importer raises, naming the column it could not find and listing the headers it did see, rather than guessing by position &mdash; a file whose first column happens to be $C_l$ would otherwise import silently as an angle sweep.`
- suggested: `A missing <em>required</em> column is the one rejection at this stage. The importer raises an error. It names the column it could not find and lists the headers it did see, instead of guessing by position. Without this, a file whose first column is $C_l$ would import as an angle sweep, with no warning.`

**54.** Line 5122, rule `G14`

- now: `A single CSV may span multiple radial stations, Reynolds numbers, and Mach numbers; the solver interpolates across all supplied dimensions during execution.`
- suggested: `A single CSV may span several radial stations, Reynolds numbers, and Mach numbers. The solver interpolates across all supplied dimensions while it runs.`

**55.** Line 5128, rules `G20`, `G14`, `G7`

- now: `Upon file ingestion, the UI reports the file path, total ingested polar slices, and detected multidimensional axes (e.g., <code>Extra axes detected: reynolds, mach</code> ...). This summary validates column parsing; unrecognized column headers (e.g., <code>Reynolds_number</code> ...) are ignored, ...`
- suggested: `After it reads the file, the window reports the file path, the number of polar slices read, and the extra axes it detected (for example, <code>Extra axes detected: reynolds, mach</code>). This summary confirms that the columns were parsed correctly. zBEMT ignores a column header it does not recognize (for example, <code>Reynolds_number</code> instead of <code>reynolds</code>), which produces a single polar with no stratification.`

**56.** Line 5191, rules `G14`, `G22`

- now: `The four-digit family encodes the maximum camber, its position and the thickness, so <code>2412</code> is a section with two per cent camber at forty per cent of the chord and twelve per cent thickness; the five-digit family encodes a different camber line.`
- suggested: Split at the semicolon into two sentences.

**57.** Line 6431, rules `G3`, `G22`

- now: `The operational upper boundary is determined by aerodynamic stall: because built-in twist and induced inflow vary radially, critical stall margin is reached progressively along the span, beyond which additional pitch input triggers blade stall, reducing total thrust and increasing torque.`
- suggested: `Aerodynamic stall determines the operational upper boundary. The built-in twist and the induced inflow vary radially. Therefore, the blade reaches the critical stall margin progressively along the span. Beyond that point, more pitch input triggers blade stall, which reduces the total thrust and increases the torque.`

**58.** Line 6466, rules `G22`, `G3`

- now: A 48-word sentence about raising the rotational speed.
- suggested: Three sentences: what it is, what raising it does, how a real machine treats it.

**59.** Line 6480, rule `G3`

- now: `The practical ceiling is set by the tip Mach number $M_{tip}=\Omega R/a$: beyond roughly $0.85$ the drag rise near the tip starts to dominate the power`
- suggested: `The tip Mach number $M_{tip}=\Omega R/a$ sets the practical ceiling. Beyond approximately $0.85$, the drag rise near the tip starts to dominate the power.`

**60.** Line 6548, rule `G14`

- now: `The key <code>name</code> is the label shown in the dropdown and in the command line listing; it defaults to <code>"Case 1"</code> and must be unique within the file, since a case is selected by it.`
- suggested: `The key <code>name</code> is the label shown in the dropdown and in the command line listing. It defaults to <code>"Case 1"</code>. It must be unique within the file, because zBEMT selects a case by it.`

**61.** Line 6721, rule `G4`

- now: `it also doubles the local Reynolds and Mach numbers, so the section polars are being read at a different place.`
- suggested: `it also doubles the local Reynolds and Mach numbers. Therefore, zBEMT reads the section polars at a different place.`

**62.** Line 6731, rules `G3`, `G22`

- now: `That inequality traces a circle of diameter $\mu_x R$ tangent to the hub and lying on the retreating side: the reverse-flow region, whose existence and size are set by the value typed in the fixed advance field and by nothing else.`
- suggested: `That inequality traces a circle of diameter $\mu_x R$. The circle is tangent to the hub and lies on the retreating side. This is the reverse-flow region. The value typed in the fixed advance field sets its existence and its size, and nothing else does.`

**63.** Line 6815, rules `G4`, `G3`

- now: `Save a batch once its queue has been reviewed.`
- suggested: `Review the queue, then save the batch.`

**64.** Line 6825, rules `G14`, `G22`

- now: A 70-word sentence describing `sweep_kind` and `sweep_params`, joined by a semicolon.
- suggested: One sentence per key, or a two-item list.

**65.** Line 6879, rules `G3`, `G8`

- now: `so it can be sent on with nothing alongside it. It is produced by the report button in the Results tab and by <code>--report</code> on the command line`
- suggested: `so you can send it on with nothing alongside it. The report button in the Results tab produces it, and so does <code>--report</code> on the command line.`

**66.** Line 6985, rules `G14`, `G7`

- now: `Masking reverse flow is a visualization toggle; underlying force integrations and exported tabular metrics retain all blade element contributions.`
- suggested: `Masking reverse flow changes the visualization only. The force integrations underneath, and the exported tables, keep every blade element contribution.`

**67.** Line 7000, rules `G14`, `G6`

- now: `Plotted against a variable that was held fixed, many conditions land on the same abscissa and the connecting line becomes meaningless zig-zag; a vertical stack of points is the signature of that mistake.`
- suggested: `If you plot against a variable that was held fixed, many conditions land on the same abscissa. The connecting line then becomes a meaningless zig-zag. A vertical stack of points is the signature of that mistake.`

**68.** Line 7006, rules `G20`, `G7`, `G22`

- now: `The <i>Group tolerance</i> setting (default $0.01$) defines the numerical threshold for grouping discrete sweep levels, filtering numerical precision variations in derived kinematic parameters (e.g., trigonometric reconstruction of flight angles).`
- suggested: `The <i>Group tolerance</i> setting (default $0.01$) sets the threshold for grouping discrete sweep levels. It filters out small numerical differences in derived kinematic parameters, for example in the trigonometric reconstruction of the flight angles.`

**69.** Line 7012, rules `G15`, `G22`

- now: A ~60-word sentence with two em dashes describing thrust against collective.
- suggested: Three sentences: the linear rise, the reason, the progressive stall.

**70.** Line 7051, rules `G15`, `G8`

- now: `A point here is an integral over the whole disk, so it cannot say whether a drop in the figure of merit came from a stalled inboard band or from tip compressibility &mdash; two causes with opposite remedies. When a curve bends, go back to the spatial views to find out why.`
- suggested: `A point here is an integral over the whole disk. Therefore, it cannot show whether a drop in the figure of merit came from a stalled inboard band or from tip compressibility. The two causes have opposite remedies. When a curve bends, return to the spatial views to find the reason.`

**71.** Line 7094, rule `G30` (proposed)

- now: `value from a performance curve says nothing about it.`
- suggested: `value from a performance curve does not show it.`

**72.** Line 7302, rules `G1`, `G16`

- now: `The figure of merit grows past unity. It is the ratio of a rising numerator to a mostly falling denominator, so it has to.`
- suggested: `The figure of merit grows past unity. It is the ratio of a rising numerator to a mostly falling denominator. Therefore, it must grow.`

**73.** Line 7314, rules `G14`, `G3`

- now: `Two of the three are computed by zBEMT; the third belongs to the airframe and is added outside it.`
- suggested: `zBEMT computes two of the three. The third belongs to the airframe, and you add it outside zBEMT.`

**74.** Lines 7346 and 7361, rules `G15`, `G14`

- now: `Falling induced power and rising parasite power give a curve with a minimum at an intermediate speed &mdash; the classical bucket. The bottom of the bucket is the speed of minimum power and therefore of maximum endurance; the speed for maximum range is where a line from the origin is tangent to the curve, ...`
- suggested: `Falling induced power and rising parasite power give a curve with a minimum at an intermediate speed. This is the classical bucket. The bottom of the bucket is the speed of minimum power, and therefore of maximum endurance. The speed for maximum range is where a line from the origin is tangent to the curve.`

### Chapter 13, Command line

**75.** Line 7596, rules `G20`, `G14`, `G15`

- now: `<code>--set NAMESPACE.FIELD=VALUE</code> (e.g., <code>--set config.Ne=90 ...</code>) &mdash; reaches any configuration or airfoil field, with or without a dedicated flag; the name is checked against the project schema, so a typo becomes an error message rather than silence`
- suggested: `<code>--set NAMESPACE.FIELD=VALUE</code> (for example, <code>--set config.Ne=90</code>) reaches any configuration or airfoil field, with or without a dedicated flag. zBEMT checks the name against the project schema. Therefore, a typo becomes an error message instead of silence.`

**76.** Line 7610, rules `G15`, `G22`

- now: A ~60-word sentence with two em dashes listing the fields with no dedicated flag.
- suggested: One sentence stating the fact, then the list as a vertical list.

### Chapter 14, Limitations

This chapter is written in a verbless, telegraphic register throughout. It
is the most concentrated `G6` defect in the document.

**77.** Line 7713, rule `G6`

- now: `The following limitations bound the interpretation of every result. Mesh refinement and tighter ...`
- suggested: Give the second sentence a subject and a verb.

**78.** Line 7723, rules `G6`, `G16`, `G26` (proposed)

- now: `Neglects aeroelastic blade deflection and flapping dynamics. Hub pitching/rolling moments represent rigid-structure loads.`
- suggested: `zBEMT neglects aeroelastic blade deflection and flapping dynamics. Therefore, the hub pitching and rolling moments represent rigid-structure loads only.`

**79.** Line 7727, rules `G3`, `G16`, `G7`

- now: `Each radial annulus is solved via isolated 1D momentum conservation. Inter-annulus turbulent mixing and full 3D wake roll-up are approximated via empirical tip/root loss models.`
- suggested: `zBEMT solves each radial annulus with isolated 1D momentum conservation. Therefore, empirical tip and root loss models approximate the turbulent mixing between annuli and the full 3D wake roll-up.`

**80.** Line 7731, rule `G14`

- now: `Classical momentum theory lacks unique real roots in steep axial descent; empirical momentum extensions provide approximate trends.`
- suggested: `Classical momentum theory has no unique real roots in steep axial descent. Empirical momentum extensions therefore give approximate trends only.`

**81.** Line 7735, rule `G16`

- now: `Trim operates via 1D root-finding on collective pitch. Multivariable trim (coupled collective, cyclic pitch, and 6-DOF moments) is not supported.`
- suggested: `Trim uses 1D root-finding on the collective pitch. Therefore, zBEMT does not support multivariable trim, which would couple the collective, the cyclic pitch, and the 6-DOF moments.`

**82.** Line 7739, rules `G20`, `G14`

- now: `External solvers (e.g., NeuralFoil) execute offline to produce polar tables; coupled on-the-fly aerodynamic calls during solver iterations are not supported`
- suggested: `External solvers, for example NeuralFoil, run offline to produce the polar tables. zBEMT does not support coupled aerodynamic calls during the solver iterations.`

**83.** Line 7743, rules `G16`, `G7`

- now: `Linearized Prandtl-Glauert scaling applies up to $M_{\max} = 0.9$ (amplification factor bound $2.29$). Transonic shock formation and drag divergence above $M \approx 0.75$ require specialized CFD polar data`
- suggested: `Linearized Prandtl-Glauert scaling applies up to $M_{\max} = 0.9$, which bounds the amplification factor at $2.29$. However, transonic shock formation and drag divergence above $M \approx 0.75$ need specialized CFD polar data.`

**84.** Line 7746, rule `G7`

- now: `Tabulated polar compressibility coupling`
- suggested: `Coupling of compressibility to a tabulated polar`

**85.** Line 7756, rules `G15`, `G22`

- now: `None of these invalidate a result by themselves — they define the conditions under which a result should be trusted at face value versus treated as an estimate needing outside corroboration (a trim loop, a wake model, or a reference dataset).`
- suggested: `None of these invalidate a result on their own. They define when you can trust a result at face value, and when you must treat it as an estimate. An estimate needs outside corroboration, such as a trim loop, a wake model, or a reference dataset.`

---

## 4. Findings: `zbemt/bemt.py`

`CLAUDE.md` reserves this file for direct work. No subagent should edit it.

**86.** Lines 4 to 6, rules `G15`, `G14`, `G16`, `G26` (proposed)

- now: `Solve blade-element/momentum cases on a radial--azimuthal mesh, aggregate loads, and expose convergence data. This is the physics layer; it does not parse projects or write files.`
- suggested: `Solve blade-element and momentum cases on a radial and azimuthal mesh, aggregate loads, and expose convergence data. This module is the physics layer. Therefore, it does not parse projects and it does not write files.`

**87.** Lines 15 to 17, rules `G14`, `G21`

- now: `` ``solve_bemt`` solves a case; ``element_state`` evaluates local quantities; ``aggregate_results`` integrates loads; solver helpers implement the configured numerical methods. ``
- suggested: A four-item vertical list, one operation per item.

**88.** Line 20, rules `G3`, `G26` (proposed)

- now: `Rotor/propeller display labels are applied outside this module.`
- suggested: `Code outside this module applies the rotor and propeller display labels.`

**89.** Lines 20 to 23, rules `G22`, `G2`, `D1`

- now: `The model is quasi-steady except for explicitly configured dynamic-stall and time-marching options, uses annular momentum theory, and requires external validation in strongly separated or highly unsteady regimes.`
- suggested: Three sentences, one claim each.

**90.** Lines 23 to 25, rules `G2`, `G21`, `G16`

- now: `` ``models.py`` supplies data, ``airfoils.py`` supplies polars, ``studies.py`` prepares cases, and ``api.py`` is the GUI/CLI execution boundary. ``
- suggested: A four-item vertical list.

**91.** Line 32, rules `G3`, `G16`, `G22`

- now: `In each element (r,psi), two independent theories describe the same aerodynamic load and are equated to find the induced velocity:`
- suggested: `In each element (r,psi), two independent theories describe the same aerodynamic load. The solver equates them to find the induced velocity.`

**92.** Line 37, rules `G3`, `G15`, `G22`, `G6`

- now: `(1) Blade element theory: the load is computed directly from the local flow seen by the airfoil (angle of attack, Cl/Cd from the airfoil polar) -- see `element_state`.`
- suggested: `(1) Blade element theory. This computes the load directly from the local flow at the airfoil, using the angle of attack and the Cl and Cd from the airfoil polar. See `element_state`.`

**93.** Line 45, rule `G29` (proposed)

- now: `solved numerically per element (Sec.5, "ITERATIVE SOLVERS")`
- suggested: `solved numerically per element (Section 5, "ITERATIVE SOLVERS")`

**94.** Line 51, rule `G15`

- now: `independent of its neighbors -- there is no spatial coupling within the iteration`
- suggested: `independent of its neighbors. There is no spatial coupling within the iteration.`

**95.** Lines 52 to 55, rule `G27` (proposed)

- now: A 30-word parenthetical carrying the only statement of when elements couple.
- suggested: Lift it out of the parentheses into its own sentence.

**96.** Line 58, rule `G28` (proposed)

- now: `typically 5-30 iterations to convergence, not thousands`
- suggested: `typically 5 to 30 iterations to convergence, not thousands`

**97.** Lines 62 and 63, rules `G15`, `G16`

- now: `- 'fixed_point' : Picard iteration with relaxation -- the simplest and most robust method, but the slowest to converge.`
- suggested: `- 'fixed_point' : Picard iteration with relaxation. This is the simplest and most robust method. However, it is the slowest to converge.`

**98.** Lines 64 to 66, rules `G15`, `G6`, `G25` (proposed)

- now: `(central difference), ~quadratic convergence near the root -- default method.`
- suggested: `(central difference). Convergence is approximately quadratic near the root. This is the default method.`

**99.** Line 67, rule `G14`

- now: `- 'bisection'    : vectorized bisection, needs no derivative; used as a fallback ...`
- suggested: `- 'bisection'    : vectorized bisection. It needs no derivative. The solver uses it as a fallback ...`

**100.** Line 73, rules `G3`, `G15`, `G22`, `G7`

- now: `the convergence test is always performed on the TRUE RESIDUAL g(lambda)-lambda (pre-relaxation), never on the already-relaxed step -- near the root/tip/azimuth crossing the relaxation factor drops significantly ...`
- suggested: `The solver always tests convergence on the true residual g(lambda)-lambda, before relaxation. It never tests the already-relaxed step. Near the root, the tip and the azimuth crossing, the relaxation factor drops sharply.`
- note: this behaviour is required by `EN-1`. Keep the requirement code visible in any rewrite.

**101.** Line 83, rule `G14`

- now: `Each model below is detailed in the corresponding code block; here is just ...`
- suggested: `The corresponding code block describes each model below. This section gives only ...`

**102.** Line 86, rules `G3`, `G15`, `G22`, `G24`

- now: `a) `reverse_flow_model='thin_plate_blend'` -- reverse flow (Ut<0, the region where the blade "walks backwards" relative to the air, ...) modeled by thin flat-plate theory ..., smoothly blended (smoothstep) with the direct airfoil polar.`
- suggested: Split into three sentences: what the region is, what models it, how it blends.

**103.** Line 92, rules `G6`, `G12`

- now: `Other options: 'simple_flip', 'flat_plate' (fixed Cd=1.9 in reverse flow, with a discontinuity at Ut=0) and 'alpha_blending'.`
- suggested: `The other options are 'simple_flip', 'flat_plate' and 'alpha_blending'.` Then describe `flat_plate` in its own sentence.

**104.** Line 95, rules `G3`, `G15`, `G22`, `D1`

- now: A ~70-word sentence with two `--` dashes describing `viterna_full_range`.
- suggested: Four sentences: what it is, what it replaces, what it does, what it eliminates.

**105.** Line 104, rules `G6`, `G15`, `G7`

- now: `b) `use_rotational_augmentation=True` -- Himmelskamp effect / Snel correction: Cl increase near the root from centrifugal pumping ...`
- suggested: `b) `use_rotational_augmentation=True` applies the Himmelskamp effect, also called the Snel correction. It increases Cl near the root, ...`

**106.** Line 110, rules `G15`, `G6`

- now: `in forward flight the spanwise (radial) flow component reduces the effective Cd -- zero at psi=90/270 deg, maximum at psi=0/180 deg.`
- suggested: `In forward flight, the spanwise flow component reduces the effective Cd. The reduction is zero at psi=90 and psi=270 deg, and maximum at psi=0 and psi=180 deg.`

**107.** Line 120, rules `G15`, `G14`, `G6`

- now: `e) Flapping -- not implemented; this code only solves the aerodynamic field of a rigid disk, without blade structural dynamics.`
- suggested: `e) Flapping. This is not implemented. This code solves only the aerodynamic field of a rigid disk, with no blade structural dynamics.`

**108.** Line 128, rules `G20`, `G15`, `G22`, `G9`

- now: A ~70-word sentence with two `--` dashes and a trailing `etc.`
- suggested: Three sentences. Replace `etc.` with `and so on`, or name the remaining items.

**109.** Line 164, rules `G20`, `G15`, `G14`, `G22`

- now: The `_trapz_psi_periodic` docstring, a ~110-word passage with `i.e.`, two `--` dashes and a semicolon.
- suggested: Five sentences. Keep every fact, including the `~1/Npsi` bias figure.

**110.** Line 176, rules `G6`, `G14`, `G15`

- now: `Fix: add the missing closing panel, (f[-1]+f[0])/2 * d_psi_closing -- a NEW panel, between the last sampled point and the first point of "the next revolution"; no data is counted twice.`
- suggested: `The fix adds the missing closing panel, (f[-1]+f[0])/2 * d_psi_closing. This is a new panel between the last sampled point and the first point of the next revolution. No data is counted twice.`

**111.** Lines 899 and 940, `ViternaExtendedAirfoil`, rules `G20`, `G15`, `G22`, `D3`

- now: Two long passages using `e.g.`, `i.e.` and `--` dashes.
- suggested: Split each into sentences of 25 words or fewer. Replace the Latin abbreviations.

**112.** Line 2086, `_check_early_stop`, rules `G22`, `G14`, `G6`

- now: `Decides whether the iterative loop can already stop: either the converged-fraction target was reached, or the fraction has stagnated ... while already reasonably high.`
- suggested: `Decides whether the iterative loop can stop. It stops when the converged-fraction target is reached. It also stops when the fraction stagnates while it is already high.`

**113.** Line 2141, `solve_fixed_point`, rules `G15`, `G22`, `G6`, `G2`

- now: `... advances lambda_i by a `relax` fraction of the residual g(lambda)-lambda, instead of the full step -- avoids oscillation/divergence near strong nonlinearities (stall, reverse-flow boundary), at the cost of slower convergence than Newton.`
- suggested: Three sentences. Write `oscillation and divergence`, not `oscillation/divergence`.

**114.** Line 2176, `solve_newton`, rules `G6`, `G15`

- now: `Typically quadratic convergence -- a few dozen iterations in total.`
- suggested: `Convergence is typically quadratic. A few dozen iterations are enough.`

**115.** Line 2214, `solve_bisection`, rules `G3`, `G15`, `G22`

- now: `Assumes h(lambda)=g(lambda)-lambda is monotonically decreasing (valid over most of the envelope; near stall this can fail locally -- elements with an invalid bracket get the best candidate found and are marked not-converged).`
- suggested: Three sentences, with the parenthetical lifted out.

**116.** Line 2955, `resolve_advance_velocity`, rules `G15`, `G22`, `G6`

- now: `... (mu_x, mu_z, J_x, J_z, alpha_rotor_deg, alpha_disk_deg, Vx) -- allows reporting the result in whichever convention the user prefers, ...`
- suggested: `... This lets zBEMT report the result in whichever convention the user prefers, ...`

**117.** Lines 3113 and 3120, `aggregate_results`, rules `G14`, `G3`, `G22`

- now: `That flag does not decide what is computed/exported (that is always everything); it is only used elsewhere ... to choose which of the two families is "natural" for that case.`
- suggested: `That flag does not decide what zBEMT computes or exports, which is always everything. zBEMT uses it only elsewhere, to choose which of the two families is natural for that case.`

**118.** Line 3129, `aggregate_results`, rules `G14`, `G15`, `G22`

- now: `` `Vz` is the axial component of the FREE stream (symbol V_inf,z in the report/GUI); `Vz` is NOT a synonym for it here -- it is the TOTAL axial velocity through the disk ... ``
- suggested: Three sentences. Note that the passage names two different things `Vz`, which is itself a `G10` defect and should be resolved against `nomenclature.py`.

---

## 5. Findings: `zbemt/api.py`, `models.py`, `nomenclature.py`

### `api.py`

**119.** Lines 3 to 6, rules `G22`, `G2`, `D1`

- now: A 34-word sentence stating what the module accepts, does, and returns.
- suggested: Three sentences, one per idea.

**120.** Lines 7 and 8, rules `G14`, `G2`, `G22`

- now: `GUI and CLI callers use this boundary; it delegates physics, geometry, airfoil construction, and nomenclature to their dedicated modules and owns direct project-file access.`
- suggested: `GUI and CLI callers use this boundary. It delegates physics, geometry, airfoil construction, and nomenclature to their dedicated modules. It also owns direct project-file access.`

**121.** Line 9, rules `G3`, `G6`, `G16`

- now: `Results remain limited by selected models, input validity, and convergence status.`
- suggested: `The selected models, the validity of the inputs, and the convergence status all limit the results.`

**122.** Line 57, rules `G15`, `G6`, `G12`

- now: `` ``outputs/`` folder of a project -- the CANONICAL definition, in one place. ``
- suggested: `` The ``outputs/`` folder of a project. This is the canonical definition, in one place. ``

**123.** Line 62, rules `G13`, `G1`

- now: `so that a project not yet saved keeps exporting instead of blowing up.`
- suggested: `so that a project that is not yet saved keeps exporting instead of raising an error.`

**124.** Line 67, rules `G15`, `G22`, `G13`

- now: `A repeated literal is not a bug today, but it is the mechanism by which one surface's output folder silently drifts from the others' -- exactly the problem `api` exists to not have.`
- suggested: `A repeated literal is not a bug today. However, it is how one surface's output folder drifts from the others, with no warning. The `api` module exists to prevent exactly that.`

**125.** Line 203, `validate_project`, rules `G15`, `G6`, `G22`

- now: `Passing them, the check also covers each condition's RPM -- a missing RPM falls back to a placeholder and a zero RPM breaks the engine's non-dimensionalization, ...`
- suggested: `If you pass them, the check also covers the RPM of each condition. A missing RPM falls back to a placeholder. A zero RPM breaks the engine's non-dimensionalization.`

**126.** Line 224, `run_case`, rules `G15`, `G16`, `G13`, `G1`

- now: `raises ``bemt.SolveCancelled`` -- an interrupted solve does not converge, and returning it halfway would hand back half a solution dressed up as a result.`
- suggested: `raises ``bemt.SolveCancelled``. An interrupted solve does not converge. Therefore, returning it halfway would present an incomplete solution as a result.`

**127.** Line 235, `run_case_trimmed`, rules `G15`, `G22`, `G26` (proposed)

- now: `... until it hits a thrust/CT target -- see ``studies.run_case_trimmed`` for the full semantics of ``trim_mode``/``target_kind``/``bracket``.`
- suggested: `... until it reaches a thrust or CT target. See ``studies.run_case_trimmed`` for the full semantics of ``trim_mode``, ``target_kind`` and ``bracket``.`

**128.** Line 277, `build_factorial_conditions`, rules `G1`, `G13`, `G8`

- now: `This is what allows reviewing the cases before firing off N solves.`
- suggested: `This lets you review the cases before you start N solves.`

**129.** Line 450, `sanitize_filename`, rules `G15`, `G22`, `G13`

- now: `... which is legal in a condition name and ILLEGAL in a filename on Windows. Without this, export would blow up in the middle of an already-run batch.`
- suggested: `... Without this, the export would fail in the middle of a batch that has already run.`

**130.** Line 469, `sanitize_filename`, rules `G15`, `G22`

- now: `... and one would silently overwrite the other's file -- pass the set so that collisions get a numeric suffix.`
- suggested: `... and one would overwrite the other's file, with no warning. Pass the set, so that a collision gets a numeric suffix.`

**131.** Line 505, `mapa_de_nomes_de_arquivo`, rules `G11`, `G3`, `G15`, `G22`

- now: `... so resolving the collision on each call would give `_2`, `_3`, `_4` for the SAME condition -- files scattered around instead of overwritten, which is just another form of wrong.`
- suggested: `... Therefore, resolving the collision on each call would give `_2`, `_3` and `_4` for the same condition. The files would be scattered instead of overwritten, which is equally incorrect.`

**132.** Line 511, `mapa_de_nomes_de_arquivo`, rules `G22`, `G15`, `G14`

- now: A ~60-word sentence with a `--` dash and a semicolon.
- suggested: Three sentences.

**133.** Line 526, `rotulos_de_condicao`, rules `G15`, `G22`

- now: `... so a selection of five cases would arrive at the report as five "caso" rows -- no way to say "row 3" or cross-reference a row with a figure.`
- suggested: `... Therefore, five selected cases arrive at the report as five "caso" rows. There is then no way to name "row 3", or to cross-reference a row with a figure.`

**134.** Line 562, `_mascara_de_fluxo_reverso`, rules `G6`, `G12`

- now: `Whether (or not) to mask the reverse-flow region in the disk maps.`
- suggested: `Decides whether zBEMT masks the reverse-flow region in the disk maps.`

**135.** Line 574, `_mascara_de_fluxo_reverso`, rules `G15`, `G14`, `G22`, `G16`

- now: A ~90-word passage with a `--` dash and a semicolon.
- suggested: Five sentences, with connectors.

**136.** Line 600, `_result_plot_path`, rules `G3`, `G15`, `G22`, `D3`

- now: `NEVER returns a path that already exists: it goes through `_caminho_sem_sobrescrever` ... Without this, exporting the disk maps twice to the SAME folder would silently erase the first export -- the same class of data loss as the bug where ...`
- suggested: Four sentences. Replace `silently erase` with `erase ... with no warning`.

**137.** Line 1761, `_rotor_rpm_e_redundante`, rules `G15`, `G22`, `G3`

- now: `... the column reappears instead of hiding the divergence -- exactly when it would matter.`
- suggested: `... the column reappears instead of hiding the divergence. It reappears exactly when the divergence matters.`

**138.** Line 1782, `modo_helice`, rules `G14`, `G15`, `G6`, `G22`

- now: `The authoritative answer is the project (it is what the user edited); in its absence, the `cfg_is_propeller` echo ... With neither of the two, rotor -- which is `BEMTConfig`'s default ...`
- suggested: Three sentences, each with a verb.

**139.** Line 1808, `_chaves_ordenadas`, rules `G15`, `G22`, `G2`, `D1`

- now: A ~60-word sentence with a `--` dash.
- suggested: Three sentences.

### `models.py`

**140.** Lines 4 to 5, rules `G6`, `G7`, `G22`

- now: `Provide the shared data contract for GUI, CLI, API, studies, and engine layers, including defaults, nested definitions, and round trips.`
- suggested: `Provide the shared data contract for the GUI, the CLI, the API, the studies and the engine layers. The contract includes the defaults, the nested definitions, and the round trips.`

**141.** Line 13, rules `G14`, `G2`

- now: `` Constructors and conversion helpers build definitions; ``save_bemt`` and ``load_bemt`` implement file I/O. ``
- suggested: `` Constructors and conversion helpers build the definitions. ``save_bemt`` and ``load_bemt`` implement the file I/O. ``

**142.** Line 14, rules `G22`, `G2`, `G7`

- now: `Files use SI units, explicit field names, and string tokens for non-finite numbers so strict JSON readers remain compatible.`
- suggested: `Files use SI units, explicit field names, and string tokens for non-finite numbers. Therefore, strict JSON readers stay compatible.`

**143.** Line 73, `_to_jsonable`, rules `G15`, `G3`, `G22`, `G14`

- now: `` ``is_propeller`` rotates the axis letters ... -- the airspeed along a propeller's shaft is written as ``Vx``, not under the engine's ``Vz``. Nothing else in the file is touched, and nothing in memory is: the dataclass keeps its disk-axes fields, ... ``
- suggested: Four sentences. Name the actor for each passive.

**144.** Line 117, `load_bemt`, rules `G11`, `G3`, `G22`

- now: `Does a shallow recursive reconstruction: fields that are themselves dataclasses ... are resolved via ``cls``'s type annotations when possible; otherwise the value is passed through as it came from JSON ...`
- suggested: `Reconstructs the dataclass shallowly and recursively. It resolves a field that is itself a dataclass through ``cls``'s type annotations, where it can. Otherwise, it passes the value through as it came from JSON.`

**145.** Line 128, `save_bemt_list`, rules `G20`, `G15`, `G6`

- now: `Like ``save_bemt``, but for a LIST of dataclasses (e.g. ``Project.airfoil_sections`` -- Phase D, multi-section airfoil).`
- suggested: `Works like ``save_bemt``, but for a list of dataclasses, for example ``Project.airfoil_sections`` (Phase D, multi-section airfoil).`

**146.** Line 144, `_migrate_airfoil_raw`, rules `G14`, `G15`, `G22`, `G3`

- now: A ~65-word sentence with a `--` dash and a semicolon.
- suggested: Three sentences.

**147.** Line 263, `avisar_nomenclatura_antiga`, rules `G15`, `G22`, `G6`, `G16`

- now: `There is no back-compat by decision -- but a SILENT misread is worse than a missing feature. Under the new schema a propeller file's ``Vz`` is the CROSS-flow; ...`
- suggested: `zBEMT deliberately offers no backward compatibility here. However, a misread that gives no warning is worse than a missing feature. Under the new schema, the ``Vz`` of a propeller file is the cross-flow.`

**148.** Line 312, `PolarSlice`, rules `G22`, `G6`, `D1`

- now: A 42-word sentence about which labels are present.
- suggested: Two sentences.

**149.** Line 329, `ProfileGeometry`, rules `G4`, `G14`, `G15`, `G3`, `G26` (proposed)

- now: `Only needed when a polar is to be generated via an external engine (NeuralFoil — Phase 7); for the analytical/table models it is optional/illustrative.`
- suggested: `This is needed only when an external engine generates a polar (NeuralFoil, Phase 7). For the analytical and table models, it is optional.`

**150.** Line 354, `AirfoilDef`, rules `G15`, `G22`, `G7`

- now: A ~70-word passage with a `--` dash.
- suggested: Four sentences.

**151.** Lines 539 to 542, `Results`, rules `G6`, `G15`, `G3`

- now: `Lightweight container for the result of one case/batch. The real heavy payload (arrays, DataFrames) is NOT serialized here -- it only circulates in memory between api.py, studies.py, plots.py.`
- suggested: `A lightweight container for the result of one case or one batch. zBEMT does not serialize the heavy payload, meaning the arrays and the DataFrames. That payload circulates only in memory, between api.py, studies.py and plots.py.`

### `nomenclature.py`

**152.** Lines 4 to 9, rules `G14`, `G22`, `G3`

- now: `It accepts internal engine keys, display-mode flags, and mathematical symbols; it returns labels, renderings, and boundary key mappings. ... The engine remains in disk axes; only user-facing boundaries apply the rotor/propeller swap.`
- suggested: Four sentences. Write `rotor and propeller swap`.

**153.** Lines 85 to 88, rule `G14`

- now: `Reading the table: a row says "the engine calls this X; the rotor user reads it as Y; the propeller user reads it as Z". The `_x`/`_z` in the two display columns are vehicle axes and swap between the two; the key on the left never does.`
- suggested: Keep the quoted sentence, which is an example. Split the second sentence at the semicolon.

**154.** Lines 182 and 183, rules `G14`, `G22`

- now: `They are the SAME angle (alpha_rotor + alpha_disk = 90); showing both would invite reading one as if it were the other, so each mode shows only the one that is zero at its vehicle's normal condition.`
- suggested: `They are the same angle, because alpha_rotor + alpha_disk = 90. Showing both would invite the reader to take one for the other. Therefore, each mode shows only the angle that is zero at its vehicle's normal condition.`

**155.** Lines 197 to 203, the `alpha_disk_deg` tooltip shown to the user, rules `G20`, `G15`, `G14`, `G22`

- now: `This is THE angle of propeller mode -- 0 in straight cruise ..., and POSITIVE when the disk is tilted nose-up, i.e. the flow arrives from below. Its rotor-mode counterpart is &alpha;<sub>rotor</sub>, measured from the disk plane; each mode shows only its own`
- suggested: Four sentences. Replace `i.e.` with `that is`.

**156.** Lines 315 to 317, `_subscript_unicode`, rules `G22`, `G15`, `G13`

- now: `A half-lowered subscript reads worse than none at all ("Cᵢnf" vs "Cinf"), so the mixed case keeps the `_` that marked it: ...`
- suggested: Two sentences. Write `compared with`, not `vs`.

**157.** Lines 505 to 507, `is_visible`, rules `G22`, `G3`

- now: `Only the two angles are hidden, and only ever one of them: they are the same angle from different references, and two columns whose numbers never coincide invite reading one as the other.`
- suggested: `zBEMT hides only the two angles, and only ever one of them. They are the same angle seen from different references. Two columns whose numbers never coincide would invite the reader to take one for the other.`

**158.** Lines 608 to 611, a user-facing tooltip, rules `G14`, `G22`

- now: A ~75-word passage with two semicolons.
- suggested: Five sentences.

---

## 6. Findings: `cli.py`, `validation.py`, `studies.py`, `airfoils.py`, `geometry.py`

### `cli.py`

**159.** Lines 234, 244, 252, 279, 281, 299 to 302, rules `P2`, `G6`, `G12`

Twelve `argparse` help strings document themselves with a bare field name:

- now: `help="radius_m."`, `help="root_cutout_norm."`, `help="n_blades."`,
  `help="twist_root_deg."`, `help="twist_tip_deg."`,
  `help="AirfoilDef.source."`, `help="BEMTConfig.inflow_field_model."`,
  `help="BEMTConfig.prandtl_loss_mode."`, `help="BEMTConfig.solver."`,
  `help="BEMTConfig.max_iter."`, `help="BEMTConfig.tol."`,
  `help="BEMTConfig.relax."`
- suggested: An imperative sentence naming what the flag sets, with its unit.
  For example, `help="Set the rotor radius, in metres."` and
  `help="Set the number of blades."`

This is the most severe user-facing prose defect found. The user reads
these at the moment of use, and they say nothing.

**160.** Lines 6 to 9 and 14 to 16, module docstring, rules `G14`, `G6`, `G15`

- now: `This module contains no physics and no independent serialization; axis labels and keys follow ``nomenclature.py``.` and `Same ``api.py`` calls that ``zbemt.gui.app`` uses; zero widgets, zero physics, zero direct I/O -- everything goes through ``api.py``.`
- suggested: `This module contains no physics and no independent serialization. Axis labels and keys follow ``nomenclature.py``.` and `This module makes the same ``api.py`` calls that ``zbemt.gui.app`` makes. It has no widgets, no physics and no direct I/O. Everything goes through ``api.py``.`

**161.** Line 107, the parser description, rules `G15`, `G6`, `G12`, `P2`

- now: `Run a zBEMT project (new or existing) via api.py, without GUI — full parity with GUI (docs/parity_registry.md).`
- suggested: `Run a new or existing zBEMT project without the GUI. The CLI has full parity with the GUI.`

**162.** Lines 118 to 121, `--save-as`, rules `G6`, `G3`

- now: `Omit = does not persist flags to disk (only affects this call's execution).`
- suggested: `If you omit it, zBEMT does not write the flags to disk. They then affect this call only.`

**163.** Lines 146 to 154, the NeuralFoil sweep flags, rules `P2`, `G6`, `G20`, `G7`

- now: `List of Reynolds for NeuralFoil sweep, e.g. '1e5,5e5,1e6'.` and `Alpha [deg] range for NeuralFoil sweep (default: -10:20:0.5).`
- suggested: `Set the list of Reynolds numbers for the NeuralFoil sweep, for example '1e5,5e5,1e6'.` and `Set the range of angles of attack, in degrees, for the NeuralFoil sweep.`

**164.** Lines 156 to 159, `--export-table`, rules `G3`, `P3`

- now: `If omitted, the table is appended to project.airfoil.table_slices and the project is saved ...`
- suggested: `If you omit it, zBEMT appends the table to project.airfoil.table_slices and saves the project.`

**165.** Lines 216 to 226, `--alpha-rotor-deg`, rules `G22`, `G15`, `G6`, `G7`

- now: `Disk angle [deg] -- the ALONG-SHAFT component is derived from the in-plane one, --rpm ... Rotor mode only -- a propeller reads --alpha-disk-deg.`
- suggested: Five short sentences, each with a verb.

**166.** Lines 266 to 270, `--airfoil-stall-model`, rules `G16`, `G6`

- now: `'linear' keeps rising, 'clip'/'enhanced' plateau, 'viterna' extends to full range (+/-180deg).`
- suggested: A three-item list, one model per item. Write `'clip' and 'enhanced'`.

**167.** Lines 340 to 348, `--set`, rules `G20`, `G22`, `G3`, `G14`

- now: `PRECEDENCE: --set is applied AFTER all dedicated flags above (--inflow, --geom-radius, --dynamic-stall, etc.), so in case of conflict --set always wins. ...`
- suggested: `Precedence: zBEMT applies --set after every dedicated flag above, such as --inflow, --geom-radius and --dynamic-stall. Therefore, --set always wins a conflict.`

**168.** Lines 352 to 358, `--trim-mode`, rules `G14`, `G22`, `G3`

- now: A ~55-word opening sentence with a semicolon joining the two modes.
- suggested: One sentence naming the purpose, then a two-item list.

**169.** Lines 365 to 370, `--validate-only`, rules `G6`, `P5`

- now: `Useful before launching a long batch without supervision.`
- suggested: `Use it before you start a long batch that runs without supervision.`

**170.** Lines 783 to 787, an error message on stderr, rules `G22`, `G15`, `G6`

- now: A ~50-word message with a `--` dash.
- suggested: Four sentences. Keep the remedy imperative, per `P2`.

**171.** Lines 877 to 878, an error message, rules `G3`, `G15`

- now: `cli.py: {len(erros)} validation error(s) — nothing was run.`
- suggested: `cli.py: {len(erros)} validation error(s). zBEMT ran nothing.`

### `validation.py`

**172.** Lines 6 and 7, rule `G14`

- now: `` ``api.py`` invokes them; GUI and CLI layers present their messages. ``
- suggested: `` ``api.py`` invokes them. The GUI and CLI layers present their messages. ``

**173.** Lines 52 to 58, a user-facing error, rules `G22`, `G15`, `G6`

- now: `... Øye interpolates between the potential Cl and the Cl separated from the static polar -- without stall in the base polar there is no separation to model, and the result degenerates silently back to linear model.`
- suggested: `... Without stall in the base polar, there is no separation to model. Therefore, the result degenerates back to the linear model, with no warning.`

**174.** Lines 83 to 85, a user-facing message, rules `G4`, `G3`, `G15`, `P5`

- now: `'extend_full_range' only has effect with source='analytical' or 'table' (current: '{a.source}') -- this field is being ignored.`
- suggested: `'extend_full_range' has an effect only with source='analytical' or source='table'. The current source is '{a.source}'. Therefore, zBEMT ignores this field.`

**175.** Lines 99 to 101, a user-facing error, rules `G3`, `G6`, `G15`

- now: `source='table' selected, but no polar was imported (table_slices empty) -- import a CSV/DAT in block 'd'.`
- suggested: `You selected source='table', but no polar was imported, because table_slices is empty. Import a CSV or DAT file in block 'd'.`

**176.** Lines 203 to 209, a user-facing warning, rules `G14`, `G22`, `G3`

- now: `... so 'viterna_full_range' is normally the consistent choice; keep the current one only if you are deliberately comparing reverse-flow treatments.`
- suggested: `... Therefore, 'viterna_full_range' is normally the consistent choice. Keep the current one only if you are deliberately comparing reverse-flow treatments.`

**177.** Lines 246 to 251, a user-facing warning, rules `G20`, `G22`, `G11`

- now: `... applying Prandtl-Glauert on top is 'double counting', unless it is intentional (e.g., sensitivity study).`
- suggested: `... Applying Prandtl-Glauert on top counts the effect twice, unless you intend it, for example in a sensitivity study.`

**178.** Lines 262 to 265, a user-facing error, rules `G14`, `G22`

- now: `... this solver marches only 3 scalar DOF (nu0,nu_s,nu_c); Øye would need state per blade element (Ne*Npsi).`
- suggested: `... This solver marches only 3 scalar degrees of freedom. Øye would need a state per blade element.`

**179.** Lines 324 to 327, a user-facing warning, rules `G6`, `G15`, `G4`

- now: `This parameter applies to the entire blade -- will use {vence!r}, from the innermost section with dynamic stall enabled.`
- suggested: `This parameter applies to the entire blade. zBEMT uses {vence!r}, from the innermost section that has dynamic stall enabled.`

**180.** Lines 337 to 340, rules `G22`, `G8`, `G13`

- now: `... produced a perfectly plausible-looking thrust from a made-up rotation, with nothing to give it away.`
- suggested: `... produced a plausible thrust from an invented rotation speed, with nothing to reveal the error.`

**181.** Lines 384 to 396, `_validar_mach_de_ponta`, rules `G6`, `G15`, `G22`

- now: `Found while running: an 8.18 m rotor at 600 RPM gives 514 m/s at the tip, ...` and `Warning, not error: running is still allowed -- the user may be precisely investigating the limit --, but they now know they crossed the model's boundary ...`
- suggested: `This was found during a run. An 8.18 m rotor at 600 RPM gives 514 m/s at the tip, ...` and `This is a warning, not an error. zBEMT still allows the run, because the user may be investigating the limit deliberately. However, the user now knows that they crossed the model's boundary.`

**182.** Lines 469 to 482, `_validar_convencao_de_helice`, rules `G15`, `G6`, `G22`

- now: `The easiest mistake to make in propeller mode, and one that generates no error -- just wrong results.`
- suggested: `This is the easiest mistake to make in propeller mode. It generates no error. It only produces wrong results.`

### `studies.py`

**183.** Lines 9, 10, 19 and 20, rule `G14`

- now: `Outputs are ``Results`` or ordered result lists; this module never writes project or result files.` and `Conditions use engine disk axes; display conversion belongs to ``nomenclature.py``.`
- suggested: Split both at the semicolon.

**184.** Lines 18, 49 to 59, rules `G10`, `G13`

- now: The same concept is named three ways: `nondimensionalizes`,
  `non-dimensionalizes` and `adimensionalizes`.
- suggested: Use `non-dimensionalizes` everywhere. `adimensionalizes` is not
  an English word.

**185.** Lines 50 to 54, `_require_rpm`, rules `G22`, `G8`

- now: `... it produced plausible-looking results from a made-up rotation speed, with nothing to give it away.`
- suggested: `... it produced plausible results from an invented rotation speed, with nothing to reveal the error.`

**186.** Lines 72 to 77, `_to_rotor`, rules `G3`, `G15`, `G22`

- now: `` ``collective_deg`` is added as a RIGID offset ... on top of the geometric twist ... — exactly what a collective command does physically. Without this, a ``FlightCondition.collective_deg`` change has no effect at all ... ``
- suggested: `` zBEMT adds ``collective_deg`` as a rigid offset on top of the geometric twist. This is what a collective command does physically. Without it, a change to ``FlightCondition.collective_deg`` has no effect. ``

**187.** Lines 105 to 110, `_migrate_config_dict`, rules `G22`, `G7`

- now: One ~50-word sentence listing every old and new field.
- suggested: One sentence for the old schema, one for the new.

**188.** Lines 130 to 138, `_build_config`, rules `G6`, `G22`, `G14`

- now: `No longer copies dynamic-stall fields from ``airfoil_def`` into the BEMTConfig ...: now ``airfoils.to_airfoil()`` already attaches ... ; it no longer has any effect on the returned cfg.`
- suggested: Four sentences, each with a subject.

**189.** Lines 218 to 221, `run_case_trimmed`, rules `G6`, `G15`, `G22`

- now: `Bisection, not Newton/secant: robust even if CT(collective)/CT(rpm) is not perfectly smooth near stall -- the same `bisection` solver already exists in `bemt.py` ...`
- suggested: `This uses bisection, not Newton or the secant method. Bisection stays robust even when CT is not perfectly smooth near stall. The same `bisection` solver already exists in `bemt.py`, for the same reason.`

**190.** Lines 296 to 310, `_run_conditions`, rules `G3`, `G8`, `G15`, `G22`

- now: `each case is isolated in a ``try/except`` — a failure does not bring down the whole batch.` and `... (an interrupted solve does not converge -- returning it would hand over half a solution dressed up as a result).`
- suggested: `zBEMT isolates each case in a ``try`` and ``except`` block. Therefore, one failure does not stop the whole batch.` and `An interrupted solve does not converge. Returning it would present an incomplete solution as a result.`

**191.** Lines 473 to 476, `build_factorial_conditions`, rules `G22`, `G9`, `G1`

- now: `... a 3x4x2 factorial is 24 solves, and seeing the list before firing is the difference between reviewing and hoping.`
- suggested: `... A 3x4x2 factorial is 24 solves. Review of the list before the run replaces guesswork.`

### `airfoils.py`

**192.** Lines 8 to 11, rules `G14`, `G3`

- now: `The module does not invoke external polar engines implicitly; explicit integrations are handled by ``external_solvers.py``.`
- suggested: `` The module does not invoke external polar engines implicitly. ``external_solvers.py`` handles the explicit integrations. ``

**193.** Lines 49 to 52, `reference_reynolds_mach`, rules `G20`, `G15`, `G22`

- now: `... added to the advance ``mu_x*Omega*R`` -- i.e. the velocity that the reference section sees on average over the revolution.`
- suggested: `... added to the advance ``mu_x*Omega*R``. That is, the average velocity at the reference section over one revolution.`

**194.** Lines 88 to 94, `radial_reynolds_mach`, rules `G22`, `G14`, `G15`

- now: A ~50-word sentence with a semicolon and a `--` dash.
- suggested: Three sentences.

**195.** Lines 160 to 167, `suggest_reynolds_mach_lists`, rules `G22`, `G15`

- now: A ~45-word sentence with a `--` dash.
- suggested: Three sentences.

**196.** Lines 260 to 264, `build_table`, rules `G3`, `G15`, `G13`, `G22`

- now: `WARNING: if nothing is informed, EVERY slice scores 0.0 ... and the FIRST one is returned -- the table's extra axes get silently ignored.`
- suggested: `Warning: if you give no value, every slice scores 0.0, and zBEMT returns the first one. It then ignores the extra axes of the table, with no message.`
- note: `informed` here is a false friend of the Portuguese `informado`. The
  English word is `given` or `supplied`.

**197.** Lines 678 to 685, `condition_label`, rules `G22`, `G3`, `G8`, `G15`

- now: A ~60-word sentence with a `--` dash.
- suggested: Four sentences.

**198.** Lines 787 and 788, `import_polar_csv`, rules `G20`, `G22`

- now: `` `column_map`, if given, overrides the automatic detection (e.g.: {"alpha_deg": "AOA[deg]"}). ``
- suggested: `` If you give `column_map`, it overrides the automatic detection. For example: {"alpha_deg": "AOA[deg]"}. ``

**199.** Lines 1068 to 1074, `load_profile_dat`, rules `G22`, `G3`, `G15`

- now: A ~55-word sentence with a `--` dash.
- suggested: Four sentences.

**200.** Lines 1094 to 1102, a user-facing `ValueError`, rules `G22`, `G15`, `G3`

- now: One ~65-word sentence with two em dashes carrying three ideas.
- suggested: Five sentences. Keep every remedy, and keep them imperative per
  `P2`.

**201.** Lines 1117 to 1129, the `AIRFOIL_PRESETS` notes shown in the GUI combo, rules `G15`, `G6`, `G20`, `G26` (proposed)

- now: `Thin symmetric -- high-speed blade/propeller tip.` and `Symmetric, thicker -- inner blade sections (greater structural robustness).`
- suggested: `A thin symmetric section. It suits a high-speed blade tip or propeller tip.` and `A thicker symmetric section. It suits the inner blade sections, which need more structural strength.`

### `geometry.py`

**202.** Lines 8 and 9, rules `G14`, `G3`

- now: `Stations are normalized by radius; interpolation is piecewise linear and does not model structural deformation or three-dimensional airfoil geometry.`
- suggested: `zBEMT normalizes the stations by the radius. The interpolation is piecewise linear. It does not model structural deformation or three-dimensional airfoil geometry.`

**203.** Lines 15 to 17, rules `G15`, `G6`

- now: `Nothing here is 2D (airfoil) — that's ``airfoils.py``.` and `Nothing here runs the BEMT engine — that's ``bemt.py``/``studies.py`` via ``api.py``.`
- suggested: `Nothing here is 2D (airfoil). That is the job of ``airfoils.py``.` and `Nothing here runs the BEMT engine. That is the job of ``bemt.py`` and ``studies.py``, through ``api.py``.`

**204.** Lines 20 to 22, rules `G22`, `G15`, `G3`

- now: A ~50-word sentence with an em dash.
- suggested: Three sentences.

**205.** Lines 44 to 50, `_validate_and_sort_table`, rules `G22`, `G15`, `G6`

- now: `Decision: REORDER (not error) by increasing ``r_norm`` ... -- it's common to paste a tip->root table from a spreadsheet, and this neither loses nor corrupts information ...`
- suggested: `zBEMT reorders the table by increasing ``r_norm`` instead of raising an error. Pasting a tip-to-root table from a spreadsheet is common. The reorder loses no information and corrupts none.`

**206.** Lines 122 to 134, `generate_elliptic`, rules `G22`, `G15`

- now: One ~90-word sentence with two `--` dashes.
- suggested: Five sentences. This is the longest single sentence found in the
  project.

**207.** Lines 164 to 166, `generate_custom`, rules `G20`, `G3`

- now: `Build the geometry directly from user-supplied lists (e.g. pasted from a spreadsheet). The table is reordered by increasing ``r_norm`` if it comes out of order ...`
- suggested: `Build the geometry directly from user-supplied lists, for example lists pasted from a spreadsheet. zBEMT reorders the table by increasing ``r_norm`` if it arrives out of order.`

**208.** Lines 198 to 200, `interpolate_geometry`, rules `G15`, `G6`

- now: `Return (chord_norm, twist_deg) interpolated at the requested radial positions — used both by the conversion to ``Rotor`` (engine) and by the graphical preview ...`
- suggested: `Return (chord_norm, twist_deg), interpolated at the requested radial positions. Both the conversion to ``Rotor`` and the graphical preview use this function.`

---

## 7. Two defects that outrank the style rules

### 7a. Portuguese in user-facing strings

`CLAUDE.md` states: "Write everything in English ... Never mix languages
within one file." Several user-facing strings break this.

Counted by Portuguese function words, excluding Greek symbols and the
Danish name "Øye", which are legitimate: `api.py` 37 lines, `bemt.py` 22,
`gui/styles.py` 19, plus a few elsewhere.

**209.** `bemt.py` lines 2745 to 2750, a user-visible `ValueError`

- now: `"inflow_field_model={...!r} é a variante NÃO-ESTACIONÁRIA de Pitt-Peters: `solve_bemt` resolve só condições de voo isoladas (equilíbrio algébrico), não uma sequência temporal -- use `run_sweep_unsteady_pitt_peters(...)` para marchar o inflow no tempo, ou troque para 'pitt_peters_steady'."`
- suggested: The same message in English, in short sentences, with the
  remedy in the imperative. For example: `"inflow_field_model={...!r} is the unsteady variant of Pitt-Peters. `solve_bemt` solves isolated flight conditions only, at algebraic equilibrium. It does not solve a time sequence. Use `run_sweep_unsteady_pitt_peters(...)` to march the inflow in time, or change to 'pitt_peters_steady'."`

**210.** `bemt.py` lines 1028, 2707 and 3009

- now: `"'de tabela' para detectar; informe os ângulos de estol."` and
  `"adimensionaliza por Omega*R, então a rotação precisa ser > 0."` and
  `"componente fixa a escala da velocidade. Forneça um ângulo e uma "`
- suggested: English, imperative, with the semicolon removed per `G14`.

**211.** `airfoils.py` lines 478 to 481, a warning that changes language mid-sentence

- now: `"... This parameter is PÁ, não da seção -- o motor marcha uma vez por solve. Valendo: {...} (seção {...})"`
- suggested: Fully English. For example: `"... This parameter belongs to the blade, not to the section, because the engine marches once per solve. zBEMT uses {...}, from section {...}."`

**212.** `airfoils.py` lines 697 and 749, Portuguese labels drawn into plot legends

- now: `"polar única"` and `"modelo atual"`
- suggested: `"single polar"` and `"current model"`

**213.** `api.py` lines 1098 and 1146, Portuguese CSS comments in `_REPORT_CSS`

- now: `/* Metadados "o que foi rodado" em duas colunas lado a lado -- o bloco` and `` `overflow-y` como `auto` TAMBÉM (não dá pra rolar só um eixo e deixar ``
- suggested: English comments.

> Tests assert on error-message text. Before any of these is changed, search
> the test suite for the message and update the assertion in the same
> commit.

### 7b. British spelling mixed with American

ASD-STE100 Rule 1.14 requires American spelling. This project mixes both.
The two surfaces disagree with each other, which is the real problem:
**`docs/documentation.html` is mostly British, and `zbemt/` is mostly
American.**

`docs/documentation.html`, prose only:

| Word | British | American |
|---|---|---|
| behaviour, behavior | 11 | 2 |
| normalis-, normaliz- | 11 | 4 |
| labelled, labeled | 8 | 0 |
| neighbour, neighbor | 5 | 2 |
| modelled, modeled | 4 | 2 |
| centre, center | 4 | 0 |
| recognis-, recogniz- | 3 | 1 |
| travelling, traveling | 2 | 0 |
| **Total** | **48** | **11** |

`zbemt/*.py`:

| Word | British | American |
|---|---|---|
| behaviour, behavior | 5 | 37 |
| normalis-, normaliz- | 4 | 22 |
| neighbour, neighbor | 3 | 17 |
| **Total** | **12** | **76** |

A reader who moves from the manual to a docstring therefore changes
spelling convention halfway. `airfoils.py` alone carries both: `nearest
neighbour` at line 247 and `nearest-neighbor` at line 654, `behaviour` at
line 259 and `behavior` at line 507.

**214.** Convert all 60 British spellings to American, across
`docs/documentation.html` and `zbemt/`. This includes `recognised` at
`documentation.html` line 998, `labelled` at line 1324, and `behaviour` at
line 967.

This pass is mechanical and is a good candidate for a subagent, per the
`CLAUDE.md` subagent rule. Two cautions: do not change a quoted proper
name, and do not change any HTML `id`.

---

## 8. Proposed new rules, for review

The review found defects that the current 24 General rules do not name.
Each proposal below is justified by text found in this project. **None of
these are in the skill yet.**

| Proposed | Rule | Found in |
|---|---|---|
| `G25` | Don't use `--`, `-`, or `~` in place of a dash or a word. Write the sentence break, or write "approximately". | `bemt.py:4` `radial--azimuthal`, `bemt.py:65` `~quadratic` |
| `G26` | Don't use a slash to join two words. Write "and" or "or", so the reader does not have to guess which. | `bemt.py:4` `blade-element/momentum`, `bemt.py:20` `Rotor/propeller`, `documentation.html:7723` `pitching/rolling` |
| `G27` | Keep a parenthesis short. Never put a fact the reader needs inside one. | `bemt.py:52-55`, a 30-word parenthetical carrying the only statement of when elements couple |
| `G28` | Write a range in words: "5 to 30 iterations", not "5-30 iterations". | `bemt.py:58` |
| `G29` | Write a cross-reference in full: "Section 5", not "Sec.5". | `bemt.py:45` |
| `G30` | Don't give code or a theory human intent. Say what it computes, not what it "sees", "wants" or "says". | `documentation.html:777`, `:778`, `:785`, `:7094` |
| `G31` | Use American spelling. | `documentation.html` is mostly British (48 against 11), `zbemt/` mostly American (12 against 76). The two surfaces disagree. |

One further candidate, offered without a number because it may belong
inside `G13` instead: **watch for false friends**. `airfoils.py:260` uses
`if nothing is informed`, which carries the Portuguese sense of
`informado`. The English word is `given`.

---

## 9. Constraints on any future rewrite

These tests read the prose and would break. They constrain how a sentence
may be rewritten:

- `tests/test_documentation.py::TestReferenciasNumericasResolvem`. Every
  `Section N.M` in prose must exist, and must be an `<a class="xref">` link
  whose number matches the heading it opens. Never drop the link, and never
  change the number.
- `tests/test_documentation.py::TestCapitulosDeAbaSaoEstanques`. Chapters
  6 to 12 may not reference each other, outside the named exceptions.
- `tests/test_documentation.py::TestNumeracaoDosTitulos`. Heading numbers
  stay sequential and match their depth. Do not renumber.
- `tests/test_notation.py::TestDocumentacao`. Prose may not spell notation
  as `lambda_i` or `mu_x`. Every symbol stays inside `$...$`, `<code>` or
  `<pre>`.
- `tests/test_documentation.py::TestDocumentationIsSelfContained`. Prose
  stays justified, math delimiters stay paired, anchors keep resolving.

The rule of thumb: **change words, never structure.** Do not touch
headings, anchors, `id` attributes, links, math, or code samples.

Two things are already correct and must not be "fixed":
`docs/documentation.html` has no contractions, and its Portuguese `id`
attributes are deliberate and exempt.

---

## 10. Pending actions

1. **Branch deletion.** `claude/asd-ste100-technical-english-m27kqb` is
   fully merged into `main`. `git log origin/main..claude/asd-ste100-technical-english-m27kqb`
   returns nothing, so deleting it loses no work. It stays until you say so.

2. **Decide on `G25` to `G31`** (Section 8), before any rewrite starts. If
   they are accepted, they should land in the skill first, so each chapter
   is reviewed once against the final rule set instead of twice.

3. **Suggested order of work**, if the rewrite is later approved:
   1. Add the accepted new rules to the skill.
   2. The Language fixes of Section 7a, each paired with its test update.
      These are correctness defects, not style.
   3. The twelve `argparse` help strings (finding 159).
   4. `docs/documentation.html`, one commit per chapter. Chapter 14 has its
      own concentrated defect and deserves a separate commit.
   5. The `zbemt/` docstrings, one module per commit. `bemt.py` first and
      by hand, because `CLAUDE.md` reserves it.
   6. The spelling pass of Section 7b, which is mechanical.
   7. Run `python tests/run_all_tests.py` once, at the end.
