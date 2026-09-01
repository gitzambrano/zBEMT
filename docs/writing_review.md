# Writing review - docs/documentation.html and GUI help

Date: 2026-09-01. Rules applied: writing-rules skill in full (G1-G32, P1-P5, D1-D3), strict mode.

Part 1 covers the documentation: every prose paragraph, list item, note and caption of docs/documentation.html, chapters 0-18 plus References, and the document title (Block 0). Part 2 covers the GUI popup help: help_blocks.py (BLOCK_HELP) and help_content.py (FIELD_HELP and other help).

Each entry gives the broken rules, the current text, and a full proposed replacement. Facts, physics, equations and hedge strength are preserved; HTML tags, ids, classes, spans, links and math entities are kept intact. A structural-defect appendix per block lists plain-text cross-references, broken anchors and duplicated content found along the way.

Every entry carries a **Setting:** line that names the documented setting the paragraph concerns: the GUI control (name and tab/window), the .bemt key and file, or the CLI flag or command. Entries that describe general prose with no single setting say
one (prose).

# Part 1 - Documentation (docs/documentation.html)

| Block | Lines | Chapters | Status |
|-------|-------|----------|--------|
| 0 | 639-643 | Document title | complete |
| A | 809-1236 | 0 How to think · 1 Installation · 2 Interfaces | complete |
| B | 1237-2536 | 3 Tutorial · 4 Nomenclature and axes | complete |
| C | 2537-3531 | 5 The method | complete |
| D | 3532-4248 | 6 Project · 7 Geometry | complete |
| E | 4249-6208 | 8 Airfoil | complete |
| F | 6209-7480 | 9 Config/Engine · 10 Run Case | complete |
| G | 7481-8630 | 11 Run Batch · 12 Results | complete |
| H | 8631-9984 | 13-16 Designer · Optimization · Transient · Stability | complete |
| I | 9985-end | 17 CLI · 18 Limitations · References | complete |

# Part 2 - GUI popup help

The field and block popups extract their text from the documentation sections mapped in ield_help_data.py, so their prose is covered by Part 1. This part reviews the independent help text that lives in the code: help_blocks.py (BLOCK_HELP) and help_content.py (FIELD_HELP).
---

# Block 0: document title (lines 639–643)

## Subtitle / title block
- Paragraphs reviewed: 2 | OK: 1 | Proposals: 1

### ¶1 "A practical guide to configuring, running and interpreting..." (L640)
- **Rules broken:** none
- **Setting:** none (prose; document subtitle)
- **Current:** A practical guide to configuring, running and interpreting BEMT simulations for rotary-wing rotors and propellers
- **Proposed:** no change.

### ¶2 "User guide with the physical and mathematical model..." (L642)
- **Rules broken:** G24 (ambiguous "with" — reads as accompaniment or as means)
- **Setting:** none (prose; document subtitle)
- **Current:** User guide with the physical and mathematical model behind each control
- **Proposed:** User guide that explains the physical and mathematical model behind each control.

---

# Block A: chapters 0–2 (lines 809–1236)

## Section 0 — How to think about zBEMT (anchor: how-to-think)
- Paragraphs reviewed: 7 | OK: 1 | Proposals: 6

### ¶1 "zBEMT solves the blade-element and momentum formulations..."
- **Rules broken:** G3 ("The blade is discretized" is passive; zBEMT is the known actor).
- **Setting:** none (prose)
- **Current:** zBEMT solves the blade-element and momentum formulations on a common radial-azimuthal mesh. The blade is discretized into radial and azimuthal stations. At each element $(r,\psi)$, both formulations describe the same local load. Their equality determines the induced velocity. The integrated solution follows from these local aerodynamic states and a consistent momentum balance.
- **Proposed:** zBEMT solves the blade-element and momentum formulations on a common radial-azimuthal mesh. It discretizes the blade into radial and azimuthal stations. At each element $(r,\psi)$, both formulations describe the same local load, and their equality determines the induced velocity. The integrated solution follows from these local aerodynamic states and a consistent momentum balance.

### ¶2 "**Blade element theory** (Section 5.6) computes..."
- **Rules broken:** G26 ("$C_l$/$C_d$" joins two items with a slash in prose).
- **Setting:** none (prose)
- **Current:** **Blade element theory** (Section 5.6) computes the load directly from the local flow at the airfoil: angle of attack, then $C_l$/$C_d$ from the airfoil polar. It needs the induced velocity as an input (it changes the local angle of attack) but does not determine what that induced velocity should be.
- **Proposed:** **Blade element theory** (Section 5.6) computes the load directly from the local flow at the airfoil: it takes the angle of attack and reads $C_l$ and $C_d$ from the airfoil polar. It needs the induced velocity as an input (the induced velocity changes the local angle of attack) but does not determine what that induced velocity should be.

### ¶3 "**Momentum theory** (Section 5.7), applied to..."
- **Rules broken:** G30 ("says the opposite" gives the theory a human voice); G22 (the main sentence carries 33 words and two subordinate constructions).
- **Setting:** none (prose)
- **Current:** **Momentum theory** (Section 5.7), applied to an elementary annular ring of the disk (Section 5.7.5), says the opposite: given a load, conservation of momentum for the air passing through that ring determines the induced velocity ($\lambda_i$) required to sustain it. It needs the load as an input and does not describe the airfoil.
- **Proposed:** **Momentum theory** (Section 5.7), applied to an elementary annular ring of the disk (Section 5.7.5), does the reverse. Given a load, conservation of momentum for the air passing through that ring determines the induced velocity ($\lambda_i$) required to sustain that load. It needs the load as an input and does not describe the airfoil.

### ¶4 "Neither theory alone closes the governing..."
- **Rules broken:** G3 ("are described in Section 9.5", "is given in Section 5.8" are passive; the document is the known actor).
- **Setting:** none (prose)
- **Current:** Neither theory alone closes the governing system. The solver couples them iteratively. Blade Element Theory computes the aerodynamic loads for an assumed induced velocity. Momentum Theory then updates the induced inflow until the momentum balance and the blade loads converge. Numerical controls for this iteration are described in Section 9.5, and the analytical derivation is given in Section 5.8.
- **Proposed:** Neither theory alone closes the governing system. The solver couples them iteratively. Blade Element Theory computes the aerodynamic loads for an assumed induced velocity. Momentum Theory then updates the induced inflow until the momentum balance and the blade loads converge. Section 9.5 describes the numerical controls for this iteration, and Section 5.8 gives the analytical derivation.

### ¶5 "Secondary physical effects (such as reverse flow,..."
- **Rules broken:** G26 ("tip/root losses" joins two words with a slash); G3 ("are formulated" passive; zBEMT is the actor).
- **Setting:** none (prose)
- **Current:** Secondary physical effects (such as reverse flow, dynamic stall, non-uniform inflow, tip/root losses, rotational augmentation, and compressibility in Section 8.5) are formulated as modular corrections applied to either the blade element loads or the momentum equations. Diagnostic analysis should therefore isolate discrepancies to the corresponding branch of this coupled formulation.
- **Proposed:** zBEMT formulates secondary physical effects (such as reverse flow, dynamic stall, non-uniform inflow, tip and root losses, rotational augmentation, and compressibility in Section 8.5) as modular corrections applied to either the blade element loads or the momentum equations. Diagnostic analysis should therefore isolate discrepancies to the corresponding branch of this coupled formulation.

### ¶6 "Use this guide in the same order as..."
- **Rules broken:** P1/G21 (five sequential instructions merged into one sentence; a sequence of 3 or more items needs a list); G3 ("are included", "are intentionally omitted" are passive; the guide is the actor).
- **Setting:** none (prose)
- **Current:** Use this guide in the same order as the GUI. First describe the aircraft or propeller, then the blade geometry and airfoil data, choose the physical corrections and solver settings, define one case or a batch, and finally inspect the results. The equations are included whenever they help select a value or diagnose a result. Source-level details that do not change that decision are intentionally omitted.
- **Proposed:** Use this guide in the same order as the GUI:
1. Describe the aircraft or propeller.
2. Define the blade geometry and the airfoil data.
3. Choose the physical corrections and the solver settings.
4. Define one case or a batch.
5. Inspect the results.

This guide includes the equations whenever they help select a value or diagnose a result. It intentionally omits source-level details that do not change that decision.

## Section 1 — Installation (anchor: cap-instalacao)
- Paragraphs reviewed: 11 | OK: 3 | Proposals: 8

### ¶1 "From the repository root, the simplest choice..."
- **Rules broken:** G32 ("the simplest choice" is a superlative; the fact is that one command installs everything).
- **Setting:** none (prose)
- **Current:** From the repository root, the simplest choice installs everything:
- **Proposed:** From the repository root, one command installs everything:

### ¶2 "If that is more than you need,..."
- **Rules broken:** G3 ("they can be combined" is passive; the user is the actor).
- **Setting:** none (prose)
- **Current:** If that is more than you need, install only the groups you will use. Each is independent, and they can be combined.
- **Proposed:** If that is more than you need, install only the groups you will use. Each group is independent, and you can combine them.

### ¶3 "Installing puts two commands on the..."
- **Rules broken:** G9 ("Installing" is an "-ing" form used as the verb's subject; use the noun "installation").
- **Setting:** none (prose)
- **Current:** Installing puts two commands on the path.
- **Proposed:** The installation puts two commands on the path.

### ¶4 "If the commands are not found, the..."
- **Rules broken:** G9 ("Running ..." gerund subject); G1 ("does the same thing", "there is always something to look at" is conversational and vague); G32 ("something to look at" is a vague non-claim).
- **Setting:** none (prose)
- **Current:** If the commands are not found, the installation directory is not on your path. Running `python -m zbemt.gui.app` and `python -m zbemt.cli` does the same thing. Both accept no arguments at all, in which case they fall back to the starter rotor, so there is always something to look at.
- **Proposed:** If the commands are not found, the installation directory is not on your path. The two commands `python -m zbemt.gui.app` and `python -m zbemt.cli` do the same thing. Both of them work with no arguments: they then fall back to the starter rotor, so a working installation always opens or runs an example.

### ¶5 "A missing optional package never stops..."
- **Rules broken:** G19 ("says so" leaves the referent unstated).
- **Setting:** none (prose)
- **Current:** A missing optional package never stops zBEMT from starting, and never changes a result. Each feature that depends on one checks for it and says so:
- **Proposed:** A missing optional package never stops zBEMT from starting, and never changes a result. Each feature that depends on an optional package checks for that package and reports it when it is missing:

### ¶6 "Without **PyVista**, the three-dimensional view is..."
- **Rules broken:** G8 ("carry on" is a phrasal verb) and G1 ("as normal" is conversational).
- **Setting:** none (prose)
- **Current:** Without **PyVista**, the three-dimensional view is unavailable and the two-dimensional plots carry on as normal.
- **Proposed:** Without **PyVista**, the three-dimensional view is unavailable and the two-dimensional plots continue to work normally.

### ¶7 "Without **NeuralFoil**, or without the XFOIL..."
- **Rules broken:** G6 ("reports at the click" is telegraphic: the missing article hides what is being clicked).
- **Setting:** GUI: Airfoil tab, polar generation
- **Current:** Without **NeuralFoil**, or without the XFOIL executable when XFOIL is the chosen engine, polar generation reports at the click what is missing and how to install it. Analytical polars and imported tables are unaffected.
- **Proposed:** Without **NeuralFoil**, or without the XFOIL executable when XFOIL is the chosen engine, polar generation reports, when you click the button, what is missing and how to install the missing package. Analytical polars and imported tables are unaffected.

### ¶8 "Without **Plotly**, reports are generated with..."
- **Rules broken:** G18 ("ones" is a pronoun whose noun, "figures", should be repeated).
- **Setting:** none (prose)
- **Current:** Without **Plotly**, reports are generated with static figures instead of interactive ones.
- **Proposed:** Without **Plotly**, reports are generated with static figures instead of interactive figures.

## Section 2 — The GUI, the CLI and the .bemt files (anchor: cap-interfaces)
- Paragraphs reviewed: 25 | OK: 8 | Proposals: 17

### ¶1 "The **GUI** is where a configuration..."
- **Rules broken:** G3 ("a configuration is built and checked" is passive; the user is the actor).
- **Setting:** GUI: main window
- **Current:** The **GUI** is where you build and check a configuration. It shows the consequences of a choice immediately: the blade preview redraws as the geometry changes, options that do not apply disappear, and the bar at the top of the GUI reports whether each step is complete. Use the GUI to define a rotor and to understand a result.
- **Proposed:** The **GUI** is where you build and check a configuration. It shows the consequences of a choice immediately: the blade preview redraws as the geometry changes, options that do not apply disappear, and the bar at the top of the GUI reports whether each step is complete. Use the GUI to define a rotor and to understand a result.

### ¶2 "The **.bemt files** are the record..."
- **Rules broken:** G3 ("which can be read, edited, copied..." is a passive chain; the user is the actor).
- **Setting:** .bemt files (project folder)
- **Current:** The **.bemt files** are the record of what was configured. A project is a folder of small text files in JSON format, one per subject, which can be read, edited, copied between machines and tracked in version control. They are the definition of the case. Everything else reads from them.
- **Proposed:** The **.bemt files** are the record of what was configured. A project is a folder of small text files in JSON format, one per subject, which you can read, edit, copy between machines and track in version control. These files are the definition of the case. Everything else reads from them.

### ¶3 "A project is a folder containing two..."
- **Rules broken:** G12 ("Inputs", "Outputs" drop the article); G4 ("what a run produced" mixes past tense into a standing description).
- **Setting:** .bemt project folder
- **Current:** A project is a folder containing two subfolders. Inputs are the definition of the case. Outputs are what a run produced.
- **Proposed:** A project is a folder containing two subfolders. The inputs are the definition of the case. The outputs are what a run produces.

### ¶4 "A key that is absent from a..."
- **Rules broken:** G3 ("is reported as unknown and ignored", "the value is not used" are passive; zBEMT is the actor).
- **Setting:** .bemt key handling
- **Current:** A key that is absent from a file takes its default value, so a short file is valid and describes a rotor using defaults for everything it does not mention. A key that is present but not recognized is reported as unknown and ignored. It does not stop the run, but the value is not used, and the field falls back to its default. This is the usual cause of a hand-edited file that appears to have no effect.
- **Proposed:** A key that is absent from a file takes its default value, so a short file is valid and describes a rotor using defaults for everything it does not mention. When a key is present but not recognized, zBEMT reports that key as unknown and ignores it. The unknown key does not stop the run, but zBEMT does not use its value, and the field falls back to its default. This behavior is the usual cause of a hand-edited file that appears to have no effect.

### ¶5 "The GUI edits and writes the..."
- **Rules broken:** G4 ("could have edited" is a compound tense with an auxiliary); G32 ("the easiest way" is a superlative claim; the fact is that the GUI writes the same files).
- **Setting:** GUI: save
- **Current:** The GUI edits and writes the files. Typing a value into a field changes the project held in memory. Nothing reaches disk until you save, at which point the whole project is written back to .bemt files. These are the same files you could have edited by hand. This is what makes the GUI the easiest way to author a project: build it on screen, save it, and the folder is ready for any of the three.
- **Proposed:** The GUI edits and writes the files. When you type a value into a field, the GUI changes the project held in memory. Nothing reaches disk until you save, at which point the GUI writes the whole project back to .bemt files. These are the same files you can edit by hand. This is why the GUI is a good way to author a project: build the project on screen, save it, and the folder is ready for any of the three interfaces.

### ¶6 "The CLI runs a project and can..."
- **Rules broken:** G14 (a semicolon joins two full sentences); G3 ("every other field is reached with `--set`" is passive).
- **Setting:** CLI: --set
- **Current:** The CLI runs a project and can override any field for that one run. It does not write the project back: an override changes what is solved, not what is stored, so the folder is exactly as it was when the run ends. Use the field's own flag where one exists, for example `--rpm 300` or `--inflow coleman_local`; every other field is reached with `--set`, which takes the file group, the field and the value:
- **Proposed:** The CLI runs a project and can override any field for that one run. It does not write the project back: an override changes what is solved, not what is stored, so the folder is exactly as it was when the run ends. Use the field's own flag where one exists, for example `--rpm 300` or `--inflow coleman_local`. Reach every other field with `--set`, which takes the file group, the field and the value:

### ¶7 "The group is `config`, `airfoil` or..."
- **Rules broken:** G3 ("When a field is given both by its own flag and by `--set`" is passive with the actor known).
- **Setting:** CLI: --set
- **Current:** The group is `config`, `airfoil` or `geom`, matching the files above. A field name that does not exist, or a value that does not match the field's type, stops the run with an error rather than being silently ignored. When a field is given both by its own flag and by `--set`, the `--set` value is the one used.
- **Proposed:** The group is `config`, `airfoil` or `geom`, matching the files above. A field name that does not exist, or a value that does not match the field's type, stops the run with an error rather than being silently ignored. When you supply a field both by its own flag and by `--set`, zBEMT uses the `--set` value.

### ¶8 "**Only the GUI.** Open it with..."
- **Rules broken:** P1 (four sequential instructions merged into one sentence); G8 ("fill in" is a phrasal verb).
- **Setting:** GUI: Run Case / Run Batch tabs
- **Current:** **Only the GUI.** Open it with `zbemt-gui`, create a project, fill in the tabs, and run from the Run Case or Run Batch tab. Saving writes the .bemt files. You never need to look at them. This is the recommended route for a first project.
- **Proposed:** **Only the GUI.** Open it with `zbemt-gui` and create a project. Complete the tabs. Run from the Run Case or Run Batch tab. Saving writes the .bemt files. You never need to look at the files. This is the recommended route for a first project.

### ¶9 "**Only .bemt files.** Write the files..."
- **Rules broken:** P1 ("copy an example project from `projects/` and edit it" merges two sequential steps into one sentence).
- **Setting:** .bemt files; CLI: --project
- **Current:** **Only .bemt files.** Write the files by hand, or copy an example project from `projects/` and edit it. Then solve the saved cases with `zbemt --project projects/MyRotor`. The project defines the geometry, the airfoil, the configuration and the conditions to run, so the command needs nothing but the folder. Nothing here requires PyQt6, which is why this is the route for a headless machine.
- **Proposed:** **Only .bemt files.** Write the files by hand. Alternatively, copy an example project from `projects/` and edit the copy. Then solve the saved cases with `zbemt --project projects/MyRotor`. The project defines the geometry, the airfoil, the configuration and the conditions to run, so the command needs nothing but the folder. Nothing here requires PyQt6. Therefore, this is the route for a headless machine.

### ¶10 "**Only the CLI.** A project folder..."
- **Rules broken:** G3 ("A project folder is always required" is passive; the CLI/the user is the actor).
- **Setting:** CLI: --new
- **Current:** **Only the CLI.** A project folder is always required (it is where the geometry, the airfoil and the configuration live), but the CLI can create one: `zbemt --new projects/MyRotor` writes a folder with default geometry and airfoil, which you then shape with flags. A fresh project has no saved case, so that first command creates the folder and runs nothing. From then on, a condition given on the command line is what gets solved:
- **Proposed:** **Only the CLI.** The CLI always needs a project folder: the folder is where the geometry, the airfoil and the configuration live. The CLI can create a folder: `zbemt --new projects/MyRotor` writes a folder with default geometry and airfoil, which you then shape with flags. A fresh project has no saved case, so that first command creates the folder and runs nothing. From then on, zBEMT solves the condition given on the command line:

(Note: "--save-as" code sample block between ¶10 and ¶11 is exempt; it is code.)

### ¶11 "`--save-as` is what turns an override..."
- **Rules broken:** G32 ("the quickest way" is a superlative); G2/G6 ("Run with no arguments at all, zbemt validates..." opens with an elliptical participle whose subject is unclear).
- **Setting:** CLI: --save-as
- **Current:** `--save-as` is what turns an override into a stored setting: without it the flags affect the run and nothing else. Run with no arguments at all, `zbemt` validates the `starter_rotor` example and exits without solving, which is the quickest way to confirm that an installation works.
- **Proposed:** `--save-as` is what turns an override into a stored setting: without it the flags affect the run and nothing else. When you run `zbemt` with no arguments at all, it validates the `starter_rotor` example and exits without solving. Therefore, that command is a fast way to confirm that an installation works.

### ¶12 "Validation applies the same rules in..."
- **Rules broken:** G4 ("a run that starts has already passed" uses a compound tense with an auxiliary).
- **Setting:** none (prose)
- **Current:** Validation applies the same rules in all three interfaces, and it always runs before the solver does: pressing Run, or launching a run from the command line, checks the project first and stops if a check fails. You never have to ask for it, and a run that starts has already passed.
- **Proposed:** Validation applies the same rules in all three interfaces, and it always runs before the solver does: pressing Run, or launching a run from the command line, checks the project first and stops if a check fails. You never have to ask for validation, and a run that starts already passed validation.

### ¶13 "Findings are of two kinds: errors,..."
- **Rules broken:** G3 ("`--ignore-validation-errors` is required" is passive; the user is the actor).
- **Setting:** CLI: --ignore-validation-errors
- **Current:** Findings are of two kinds: errors, which stop the run, and warnings, which do not. To run in spite of an error, for instance to reproduce a known bad configuration deliberately, `--ignore-validation-errors` is required.
- **Proposed:** Findings are of two kinds: errors, which stop the run, and warnings, which do not. If you want to run in spite of an error, for instance to reproduce a known bad configuration deliberately, use `--ignore-validation-errors`.

### ¶14 "There are two kinds of run. A..."
- **Rules broken:** G3 ("whichever way the run was started" is passive; the user is the actor).
- **Setting:** none (prose)
- **Current:** There are two kinds of run. A **single case** solves one flight condition. A **batch** solves a list of conditions one after another, with everything except the condition held fixed, so the results are directly comparable. The numbers are the same whichever way the run was started. What differs is what is shown and what is written to disk.
- **Proposed:** There are two kinds of run. A **single case** solves one flight condition. A **batch** solves a list of conditions one after another, with everything except the condition held fixed, so the results are directly comparable. The numbers are the same whichever way you start the run. What differs is what zBEMT shows and what it writes to disk.

### ¶15 "zBEMT writes nothing below unless you..."
- **Rules broken:** G18/G19 ("it" has no clear single referent; "another" stands alone for "another folder").
- **Setting:** .bemt outputs folder
- **Current:** zBEMT writes nothing below unless you ask for it. The one exception is the results table, which the CLI writes by default. The output folder is `outputs/` inside the project unless another is given.
- **Proposed:** zBEMT writes none of the files below unless you ask for them. The one exception is the results table, which the CLI writes by default. The output folder is `outputs/` inside the project unless you give another folder.

### ¶16 "**Where the files go.** From the..."
- **Rules broken:** G24 ("With many conditions" is open to reading as means rather than circumstance); G16 (the consequence needs a connector).
- **Setting:** CLI: --outdir / --export-layout
- **Current:** **Where the files go.** From the CLI, `--outdir PATH` chooses the folder, and a batch may carry its own `outdir`, which the flag overrides. With many conditions the per-condition images are numerous, so `--export-layout per_case` puts each condition's figures in its own subfolder instead of naming them all in one.
- **Proposed:** **Where the files go.** From the CLI, `--outdir PATH` chooses the folder, and a batch may carry its own `outdir`, which the flag overrides. When a batch has many conditions, the per-condition images are numerous. Therefore, `--export-layout per_case` puts each condition's figures in its own subfolder instead of naming them all in one.

### ¶17 "**The plots and the report are independent.**..."
- **Rules broken:** G6 ("the second what is embedded in the HTML" drops the repeated verb); G9 ("Asking for..." used twice as a gerund subject).
- **Setting:** none (prose)
- **Current:** **The plots and the report are independent.** Asking for no plots does not empty the report, and asking for a report does not write loose images: the first controls what sits on disk as PNG files, the second what is embedded in the HTML. When a report would carry a very large number of figures it is written as a small main page with companion pages beside it, so the main page stays quick to open. Nothing is left out.
- **Proposed:** **The plots and the report are independent.** If you ask for no plots, the report is not emptied; if you ask for a report, no loose images are written. The plots setting controls what sits on disk as PNG files. The report setting controls what is embedded in the HTML. When a report would carry a very large number of figures, zBEMT writes it as a small main page with companion pages beside it, so the main page stays quick to open. Nothing is left out.

## Structural defects (appendix items)
- none. All six cross-reference anchors in this range (`sec-28-blade-element-theory`, `sec-29-momentum-theory`, `cap-18-5`, `cap-4-5`, `sec-210-the-fixed-point-equation`, `cap-3-5`) resolve to existing `id` targets, and no plain-text section references without links occur in lines 809–1236.

---

# Block B: chapters 3–4 (lines 1237–2536)

## Section 3 — Tutorial: first result (anchor: tutorial)
- Paragraphs reviewed: 28 | OK: 5 | Proposals: 23

### ¶1 "Create or open a project…” (l. 1240)
- **Rules broken:** P1 (six sequential steps merged into one sentence); G21 (a sequence of 6 items belongs in a list, not inline prose).
- **Setting:** none (prose; overview of tabs 1–7)
- **Current:** Create or open a project, define the blade and aerodynamic model, configure the engine, specify an operating condition, execute the case, and interpret the results.
- **Proposed:** `<p>The workflow has six steps:</p><ol><li>Create or open a project.</li><li>Define the blade and the aerodynamic model.</li><li>Configure the engine.</li><li>Specify an operating condition.</li><li>Execute the case.</li><li>Interpret the results.</li></ol>`

### ¶2 "Reading order. The operational path…” (l. 1256)
- **Rules broken:** G2, G22 (the sentence "From there, each field…" holds about 45 words in two joined topics); G10 ("project file" here, ".bemt" elsewhere — rotate to one term).
- **Setting:** none (prose); mentions the per-field Help button (GUI)
- **Current:** From there, each tab has a chapter of its own, and each field is explained in full where its control is: the physics, the mathematics, the options, and how to set it in the GUI, in a project file and from the command line.
- **Proposed:** `… From there, each tab has a chapter of its own. Each chapter explains every field where its control is: the physics, the mathematics, the options, and how to set it in the <span class="gui">GUI</span>, in a <span class="bemt">.bemt</span> file and from the <span class="cli">CLI</span>. The Help button on any field opens exactly that section.`

### ¶3 "In the Project tab, create a project…” (l. 1268)
- **Rules broken:** G8/G9 (phrasal verb "filling in" used as a gerund).
- **Setting:** GUI: Project tab, mode selector (Rotor or Propeller), Save button
- **Current:** Choose Rotor or Propeller before filling in flight conditions: the engine solves the same physics, but the interface switches the input and coefficient conventions.
- **Proposed:** `… Choose Rotor or Propeller before you enter the flight conditions: the engine solves the same physics, but the interface switches the input and coefficient conventions. …`

### ¶4 "Enter the blade count and radius…” (l. 1275)
- **Rules broken:** P3 ("if needed" puts the condition after the command).
- **Setting:** GUI: Geometry tab — blade count, radius, geometry table (r/R, chord, twist), Save, Restore
- **Current:** Enter the blade count and radius, generate a starting table if needed, then review r/R, chord and twist.
- **Proposed:** `Enter the blade count and the radius. If you do not have a geometry table yet, generate a starting table. Then review <i>r/R</i>, chord and twist. …`

### ¶5 "The polar source is analytical…” (l. 1282)
- **Rules broken:** G1 ("on top of" is informal placement language).
- **Setting:** `.bemt` airfoil polar source: `analytical` or `table`
- **Current:** Dynamic stall, reverse flow and compressibility are independent corrections applied on top of that base polar.
- **Proposed:** `Dynamic stall, reverse flow and compressibility are independent corrections applied to that base polar.`

### ¶6 "Set the in-plane advance, axial velocity…” (l. 1296)
- **Rules broken:** G1/G13 ("numerical knobs" is informal); P1 ("Run the case and use the Results tab" merges two sequential steps).
- **Setting:** GUI: Run Case tab — collective, RPM, in-plane and axial velocity fields
- **Current:** Collective and RPM are not numerical knobs: they set the geometric angle and the velocity scale of the flow. Run the case and use the Results tab to compare against earlier runs.
- **Proposed:** `Collective and RPM are not numerical conveniences: they set the geometric angle and the velocity scale of the flow. Run the case. Then use the <b>Results</b> tab to compare the case against earlier runs.`

### ¶7 "Select one or more runs…” (l. 1305)
- **Rules broken:** G9 ("Generating a report" — gerund as sentence subject).
- **Setting:** GUI: Results tab — run history, Export, report generation
- **Current:** Generating a report creates the self-contained HTML of the run.
- **Proposed:** `The report command creates the self-contained HTML of the run.`

### ¶8 "How to open zBEMT.” (l. 1313)
- **Rules broken:** G6 ("two commands, one for each interface:" drops the verb).
- **Setting:** CLI: `zbemt-gui`, `zbemt --help`
- **Current:** After `pip install -e ".[all]"` at the repository root, two commands, one for each interface:
- **Proposed:** `After <code>pip install -e ".[all]"</code> at the repository root, two commands open the two interfaces:`

### ¶9 "The bar fixed at the top…” (l. 1334)
- **Rules broken:** G6 + G27 (the legend "(green = configured and valid. Amber = …)" is a long parenthesis of telegraphic fragments carrying a needed fact); G2 ("The Tools button sits … and opens" joins two topics).
- **Setting:** GUI: flow indicator bar, Help button (F1), Tools button
- **Current:** …shows a colored indicator for each of the seven steps above (green = configured and valid. Amber = configured with warnings. Red = blocking error. Gray = not yet configured). […] The Tools button sits immediately to the left of Help and opens the Geometry Designer …
- **Proposed:** `The bar fixed at the top of the <span class="gui">GUI</span> shows a colored indicator for each of the seven steps above. Green means the step is configured and valid. Amber means it is configured with warnings. Red means a blocking error. Gray means it is not yet configured. Click any indicator to jump directly to the corresponding tab. This jump helps you resume a large project without stepping through the tabs in order. The <b>Help</b> button opens this document; its shortcut <b>F1</b> sits at the far right of the same bar. The <b>Tools</b> button sits immediately to the left of Help. It opens the Geometry Designer (<a class="xref" href="#cap-designer" title="13. Geometry Variation Studies">Chapter 13</a>).`

### ¶10 "The Geometry, Airfoil and Config/Engine tabs…” (l. 1344)
- **Rules broken:** G3 ("is written" passive, actor zBEMT known); G2 (two topics joined by "and").
- **Setting:** GUI: Geometry, Airfoil, Config/Engine tabs (live-edit behavior)
- **Current:** Every value you type is written straight into the project held in memory, and the previews and the validation panel update immediately.
- **Proposed:** `Every value you type goes straight into the project held in memory. The previews and the validation panel update immediately. …`

### ¶11 "Writing to disk is the one thing…” (l. 1349)
- **Rules broken:** G3 ("an edit can be made, examined and abandoned" passive with the user as known actor).
- **Setting:** GUI: Save (project on disk)
- **Current:** …so an edit can be made, examined and abandoned without consequence.
- **Proposed:** `…so you can make an edit, examine it and abandon it without consequence.`

### ¶12 "The asterisk.” (l. 1353)
- **Rules broken:** G3 ("an asterisk is added" passive).
- **Setting:** GUI: unsaved-changes asterisk on Geometry, Airfoil, Config/Engine tabs
- **Current:** While the project in memory differs from the project on disk, an asterisk is added to the title of each tab you edited
- **Proposed:** `While the project in memory differs from the project on disk, zBEMT adds an asterisk to the title of each tab you edited: <i>Geometry *</i>, <i>Airfoil *</i>, <i>Config/Engine *</i>. …`

### ¶13 "Restore.” (l. 1366)
- **Rules broken:** G15/G25 (em dashes "&mdash;labeled … tabs&mdash;" joining ideas); G8 ("restore over them") ; G2 (colon-joined recipe "change values, watch the preview, then either save…").
- **Setting:** GUI: Restore button, Geometry and Airfoil tabs
- **Current:** <b>Restore</b> — labeled <b>Restore</b> in the Geometry and Airfoil tabs — does the opposite: it reloads … and discards every unsaved edit. […] This is what makes free experimentation safe: change values, watch the preview, then either save them or restore over them.
- **Proposed:** `<b>Restore</b>, labeled <b>Restore</b> in the Geometry and Airfoil tabs, does the opposite. It reloads the project folder exactly as it stands on disk and discards every unsaved edit. It is a full reload, not a step-by-step undo, and it asks for confirmation first when there is unsaved work. This reload is what makes free experimentation safe. Change values and watch the preview. Then either save the changes or discard them with Restore.`

### ¶14 "When closing the GUI with unsaved work…” (l. 1373)
- **Rules broken:** G9 ("When closing… offering", "before exiting": gerunds as verb forms).
- **Setting:** GUI: exit dialog (Save / Discard / Cancel)
- **Current:** When closing the GUI with unsaved work, zBEMT asks before exiting, offering Save, Discard and Cancel.
- **Proposed:** `When you close the <span class="gui">GUI</span> with unsaved work, zBEMT asks before it exits and offers <b>Save</b>, <b>Discard</b> and <b>Cancel</b>. …`

### ¶15 "Every field of a project can be set…” (l. 1421)
- **Rules broken:** G3 ("can be set" passive, actor known).
- **Setting:** all settings (GUI / `.bemt` / CLI equivalence)
- **Current:** Every field of a project can be set from the GUI, from the project files or from the command line, and the three produce the same numbers.
- **Proposed:** `You can set every field of a project from the <span class="gui">GUI</span>, from the project files or from the command line. The three produce the same numbers. …`

### ¶16 "The repository ships 16 ready-to-run projects…” (l. 1429)
- **Rules broken:** G6/G1 ("The remaining fourteen are the projects the worked examples" is ungrammatical, a word is missing); G32 ("the shortest way to understand" — non-measurable superlative claim); G9 ("Opening one").
- **Setting:** none (prose; example projects under `projects/`)
- **Current:** The remaining fourteen are the projects the worked examples, and they are worth opening for the same reason: between them they cover both modes … Opening one is the shortest way to understand the tool, because it already carries saved flight cases and sweeps.
- **Proposed:** `The remaining fourteen are the projects of the worked examples, and they are worth opening for the same reason: between them they cover both modes, the range of machine sizes zBEMT is used on, and most of the models it implements. An opened example is a fast way to understand the tool, because it already carries saved flight cases and sweeps.`

### ¶17 "The set falls into three groups…” (l. 1578)
- **Rules broken:** G9 ("knowing"); G32 ("the quickest way").
- **Setting:** none (prose)
- **Current:** …and knowing which group a project belongs to is the quickest way to pick one.
- **Proposed:** `…and the group a project belongs to tells you which project to pick.`

### ¶18 "Aircraft of different sizes.” (l. 1581)
- **Rules broken:** G10 ("Tests test3 and test6" — inconsistent label for the same projects named elsewhere as bare `test3`); G9 ("doubling").
- **Setting:** none (prose; projects `test1`–`test7`, `test3`, `test6`)
- **Current:** Tests <code>test3</code> and <code>test6</code> take the scale in the other direction, an eVTOL lift rotor and a small drone propeller, where the disk is small and the tip is slow.
- **Proposed:** `<code>test3</code> and <code>test6</code> take the scale in the other direction, an eVTOL lift rotor and a small drone propeller, where the disk is small and the tip is slow.`

### ¶19 "Projects that exercise a model rather than an aircraft.” (l. 1589)
- **Rules broken:** G22 (single sentence of ~50 words with five appositive clauses, D1 front-load).
- **Setting:** none (prose; projects `test4`, `test8`–`test10`, `test12`)
- **Current:** <code>test8</code> is set up for the Pitt-Peters inflow family, <code>test9</code> for the enhanced stall model, <code>test10</code> for a multi-section blade with different profiles at root, mid-span and tip, and <code>test4</code> and <code>test12</code> for a tabulated polar, the first resolved in Reynolds number.
- **Proposed:** `<code>test8</code> is set up for the Pitt-Peters inflow family. <code>test9</code> exercises the enhanced stall model. <code>test10</code> exercises a multi-section blade with different profiles at root, mid-span and tip. <code>test4</code> and <code>test12</code> exercise a tabulated polar, and <code>test4</code> resolves the polar in Reynolds number.`

### ¶20 "Via the GUI: open zbemt-gui…” (l. 1604)
- **Rules broken:** P1 (four sequential steps merged into one sentence); G21.
- **Setting:** GUI: Project tab project list; Run Case tab, Run button
- **Current:** open <code>zbemt-gui</code>, choose the project from the list in the Project tab, go to the Run Case tab and click Run.
- **Proposed:** `<b>Via the <span class="gui">GUI</span>:</b> open <code>zbemt-gui</code>. Choose the project from the list in the Project tab. Go to the Run Case tab and click Run. The saved cases appear in the selector.`

### ¶21 "The --report writes a self-contained HTML…” (l. 1611)
- **Rules broken:** G12 ("a self-contained HTML" lacks the noun — "HTML report"); G7/G10 ("summary table, graphs and record of the mesh, solver, and rotor" reads as an unfinished cluster).
- **Setting:** CLI: `--report` (batch run)
- **Current:** The <code>--report</code> writes a self-contained HTML with the summary table, graphs and record of the mesh, solver, and rotor used (…).
- **Proposed:** `The <code>--report</code> flag writes a self-contained HTML report with the summary table, the graphs, and a record of the mesh, the solver and the rotor used (<a class="xref" href="#cap-6-6" title="11.7 Reports">Section 11.7</a>).`

### ¶22 "To start from your own rotor…” (l. 1615)
- **Rules broken:** P1 ("begin with the Project tab and follow the tabs in order" merges two sequential steps).
- **Setting:** none (prose; Project tab)
- **Current:** To start from your own rotor instead of an example, begin with the Project tab and follow the tabs in order.
- **Proposed:** `To start from your own rotor instead of an example, begin with the Project tab. Then follow the tabs in order. …`

### ¶23 Shortcut table cells (l. 1387–1416)
- **Rules broken:** G6 (telegraphic cells: "Opens this document", "New project", "Jumps to tab 1–7"); G28 (range "1–7" written with a dash — table cell prose, not code).
- **Setting:** GUI shortcuts: F1, Ctrl+S, Ctrl+O, Ctrl+N, Ctrl+1…Ctrl+7, Ctrl+Enter, Ctrl+R
- **Current:** Jumps to tab 1–7 (same order as the flow bar)
- **Proposed:** `Jumps to tabs 1 to 7 (same order as the flow bar)` — and apply full-sentence or consistently fragmentary style across all cells (recommend full sentences with subject, for example "Opens this document (same target as the "?" button)" → "zBEMT opens this document…" is optional, but the range must become "1 to 7").

OK in Section 3 (no changes): ¶ at l. 1288 (Config/Engine), ¶ at l. 1360 (Save), ¶ at l. 1594 (Dynamic examples), ¶ at l. 1597 (Propeller mode), label at l. 1608 ("Via command line:").

## Section 4 — Nomenclature and axes (anchor: cap-nomenclatura)
- Paragraphs reviewed: 41 | OK: 12 | Proposals: 29

### ¶1 "Axis convention. The same physical component…” (figcaption, l. 1633)
- **Rules broken:** G15 (two em dashes "— which is why …", "keeps its own meaning — the tilt away from the shaft —" join ideas); G22 (several 35–50-word sentences).
- **Setting:** none (prose; symbols Vz, λz, α_rotor, α_disk)
- **Current:** …positive through the disk from above to below, the direction the induced velocity acts in — which is why λ_total=λ_z+λ_i is a sum and why a positive V_z lowers the thrust. […] α_disk keeps its own meaning — the tilt away from the shaft — and reads 0° for a propeller in straight cruise.
- **Proposed:** `… positive through the disk from above to below, the direction the induced velocity acts in. This is why $\lambda_{total}=\lambda_z+\lambda_i$ is a sum and why a positive $V_z$ lowers the thrust. … $\alpha_{disk}$ keeps its own meaning, the tilt away from the shaft, and reads $0^\circ$ for a propeller in straight cruise.`

### ¶2 "That split is physical and never changes.” (l. 1665)
- **Rules broken:** G6 ("A rotor has a vertical shaft and a propeller a horizontal one" drops the verb from the second clause).
- **Setting:** none (prose)
- **Current:** A rotor has a vertical shaft and a propeller a horizontal one, so the two components swap letters between them.
- **Proposed:** `A rotor has a vertical shaft and a propeller has a horizontal one, so the two components swap letters between them.`

### ¶3 "Axial flow is vertical: climb (positive)…” (l. 1674)
- **Rules broken:** G6 (telegraphic fragments after the colons; "the classic forward-flight advance" drops the verb).
- **Setting:** GUI: Run Case tab — axial and in-plane flow fields (rotor mode)
- **Current:** Axial flow is vertical: climb (positive) or descent (negative). In-plane flow is horizontal: the classic forward-flight advance.
- **Proposed:** `Axial flow is vertical. It is the climb, when positive, or the descent, when negative. In-plane flow is horizontal. It is the classic forward-flight advance.`

### ¶4 "The angle between the free stream and the disk plane…” (l. 1707)
- **Rules broken:** G14 (semicolon: "Level cruise is therefore μ_x>0 … ; hover is μ_x=μ_z=0").
- **Setting:** GUI: Run Case tab — α_rotor, μ_x fields (rotor mode)
- **Current:** Level cruise is therefore $\mu_x>0$ with $\alpha_{rotor}\approx0^\circ$; hover is $\mu_x=\mu_z=0$.
- **Proposed:** `Level cruise is therefore $\mu_x>0$ with $\alpha_{rotor}\approx0^\circ$. Hover is $\mu_x=\mu_z=0$.`

### ¶5 "The induced velocity acts along the shaft…” (l. 1784)
- **Rules broken:** G9 ("rather than contradicting it" — gerund as verb form); G19 ("That outcome" antecedent spans several preceding sentences).
- **Setting:** none (prose; v_i, λ_i)
- **Current:** That outcome follows from the rule rather than contradicting it. The rule attaches a letter to a direction …
- **Proposed:** `This result follows from the rule rather than contradicts it. The rule attaches a letter to a direction, and the induced velocity is defined by a direction to begin with.`

### ¶6 "The mode also decides which angle is shown.” (l. 1789)
- **Rules broken:** G6 ("a propeller α_disk" drops the verb); G22 (one sentence of ~45 words with a colon-joined second topic).
- **Setting:** GUI: Run Case tab — α_rotor or α_disk field (per mode)
- **Current:** A rotor offers α_rotor and a propeller α_disk, never both, because the two are the same physical angle measured from references that are perpendicular to each other: showing both would offer the reader two numbers for one quantity, differing by 90°.
- **Proposed:** `A rotor offers $\alpha_{rotor}$ and a propeller offers $\alpha_{disk}$, never both, because the two are the same physical angle measured from references that are perpendicular to each other. Showing both would give the reader two numbers for one quantity, and the two numbers would differ by $90^\circ$.`

### ¶7 "Idem, propeller convention.” (table cell, l. 2076)
- **Rules broken:** G1/G20 ("Idem" is a Latinism outside the spelled-out forms the rules require).
- **Setting:** none (prose; coefficients `C_T,prop`, `C_Q,prop`, `C_P,prop`)
- **Current:** Idem, propeller convention.
- **Proposed:** `Thrust, torque and power coefficients, propeller convention.`

### ¶8 "The formulation in the physics chapters…” (l. 2194)
- **Rules broken:** G9 ("when modeling"); G22 (second sentence runs ~35 words with four stacked objects).
- **Setting:** none (prose)
- **Current:** This chapter details the physical distinctions and coordinate transformations when modeling an airplane propeller: flow axis alignment, non-dimensional parameter conventions, incident inflow angle definitions, and applicable propulsive efficiency metrics.
- **Proposed:** `This chapter details the physical distinctions and the coordinate transformations that an airplane propeller introduces: flow axis alignment, non-dimensional parameter conventions, incident inflow angle definitions, and applicable propulsive efficiency metrics.`

### ¶9 "Summary. A propeller operates…” (boxed note, l. 2200)
- **Rules broken:** G9 ("Entering axial airspeed… resulting in…" — gerunds as verb forms).
- **Setting:** GUI: Run Case tab — along-shaft versus in-plane input field (propeller mode)
- **Current:** Entering axial airspeed into the in-plane input field models an edgewise rotor rather than an axial propeller, resulting in erroneous force projections and zero propulsive efficiency.
- **Proposed:** `If you enter the axial airspeed into the in-plane input field, zBEMT models an edgewise rotor rather than an axial propeller. The force projections are then erroneous and the propulsive efficiency is zero.`

### ¶10 "The core Blade Element Momentum Theory governing equations…” (l. 2209)
- **Rules broken:** G7 ("Blade Element Momentum Theory governing equations" is a five-noun cluster).
- **Setting:** none (prose)
- **Current:** The core Blade Element Momentum Theory governing equations remain identical across both modes.
- **Proposed:** `The core governing equations of Blade Element Momentum Theory remain identical across both modes.`

### ¶11 "Axial flight velocity alignment.” (l. 2215)
- **Rules broken:** G7 (bold lead-in is a four-noun cluster).
- **Setting:** none (prose)
- **Current:** <b>Axial flight velocity alignment.</b> In a helicopter rotor, …
- **Proposed:** `<b>Alignment of the axial flight velocity.</b> In a helicopter rotor, …`

### ¶12 "Axisymmetry in pure axial flow.” list (l. 2220–2234)
- **Rules broken:** G26 ("Absence of advancing/retreating asymmetry" — joining slash in prose); G9 ("rendering reverse-flow corrections inactive").
- **Setting:** none (prose; reverse-flow corrections, Pitt-Peters, N_ψ)
- **Current:** Absence of advancing/retreating asymmetry: […] With zero in-plane cross-flow, U_T = Ωr > 0 across the entire disk, rendering reverse-flow corrections … inactive.
- **Proposed:** `<b>Absence of advancing and retreating asymmetry:</b> …` and `… With zero in-plane cross-flow, $U_T = \Omega r > 0$ across the entire disk, so the reverse-flow corrections (<a class="xref" href="#cap-3-4" title="8.4 Reverse flow">Section 8.4</a>) are inactive.`

### ¶13 "Active aerodynamic effects.” (l. 2237)
- **Rules broken:** G9 ("making transonic compressibility corrections essential").
- **Setting:** none (prose; compressibility corrections, Section 8.5)
- **Current:** Propeller blade tips frequently operate at elevated tip Mach numbers, making transonic compressibility corrections (Section 8.5) essential.
- **Proposed:** `Propeller blade tips frequently operate at elevated tip Mach numbers. Therefore, the transonic compressibility corrections (<a class="xref" href="#cap-3-5" title="8.5 Compressibility">Section 8.5</a>) are necessary.`

### ¶14 "Non-axisymmetric propeller flight regimes.” (l. 2242)
- **Rules broken:** G26 ("pitch/yaw misalignment"); G3 ("must be specified" passive, actor is the user).
- **Setting:** GUI: Run Case tab — axial and in-plane velocity fields; α_disk (propeller mode)
- **Current:** Tilt-rotor transition flight, aircraft pitch/yaw misalignment, and propeller cross-wind introduce non-zero in-plane flow components. In these cases, both axial and in-plane velocities (…) must be specified.
- **Proposed:** `Tilt-rotor transition flight, aircraft pitch or yaw misalignment, and propeller cross-wind introduce non-zero in-plane flow components. In these cases, specify both the axial and the in-plane velocities (or the flight angle $\alpha_{disk}$; see <a class="xref" href="#cap-5-2" title="10.2 Along-shaft flow — the second row">Section 10.2</a>).`

### ¶15 "Section 4.1 establishes the reference convention…” (l. 2249)
- **Rules broken:** G26 ("x longitudinal/forward, z vertical/up" — joining slashes in prose).
- **Setting:** none (prose; display keys)
- **Current:** coordinate axes remain vehicle-fixed ($x$ longitudinal/forward, $z$ vertical/up)
- **Proposed:** `coordinate axes remain vehicle-fixed ($x$ longitudinal and forward, $z$ vertical and up)`

### ¶16 "To prevent ambiguity between axial advance…” (l. 2306)
- **Rules broken:** G3 ("advance ratios are explicitly subscripted" passive; actor zBEMT).
- **Setting:** GUI: Run Case tab — J_x, J_z fields (propeller mode)
- **Current:** To prevent ambiguity between axial advance and cross-flow components, advance ratios are explicitly subscripted ($J_x, J_z$).
- **Proposed:** `To prevent ambiguity between the axial advance and the cross-flow components, zBEMT always subscripts the advance ratios ($J_x, J_z$).`

### ¶17 "J_z, shown in propeller mode…” (l. 2317)
- **Rules broken:** G32 ("the quickest way to confirm" — non-measurable superlative phrasing); G19 ("which is the quickest way" — "which" points at the whole preceding clause).
- **Setting:** GUI: Run Case tab — J_x, J_z fields (propeller mode)
- **Current:** In a correctly specified propeller case exactly one of the two is non-zero, which is the quickest way to confirm that a condition was entered in the field it belongs in.
- **Proposed:** `In a correctly specified propeller case, exactly one of the two is non-zero. This check is a fast way to confirm that a condition was entered in the field it belongs in.`

### ¶18 "There are exactly two angles in the program…” (l. 2325)
- **Rules broken:** G6 ("Propeller mode's is α_disk" — possessive with the verb dropped, telegraphic).
- **Setting:** GUI: Run Case tab — α_disk field (propeller mode)
- **Current:** Propeller mode's is $\alpha_{disk}$, measured from the shaft, normalized to $(-180^\circ,\,180^\circ]$:
- **Proposed:** `Propeller mode uses $\alpha_{disk}$, measured <b>from the shaft</b> and normalized to $(-180^\circ,\,180^\circ]$:`

### ¶19 "Zero in straight cruise…” (list, l. 2330)
- **Rules broken:** G1 ("That is the whole point of having a second name" is conversational); G27 (the parenthesis "(The rotor angle is still computed and still exported. In cruise it reads α_rotor=90°.)" holds two needed facts); G9 ("of having").
- **Setting:** GUI: Run Case tab — α_disk field (propeller mode)
- **Current:** That is the whole point of having a second name: a propeller reader checking a two-degree misalignment reads 2°, not 88°. (The rotor angle is still computed and still exported. In cruise it reads α_rotor=90°.)
- **Proposed:** `That is the reason for the second name: a propeller reader who checks a two-degree misalignment reads $2^\circ$, not $88^\circ$. The rotor angle is still computed and still exported. In cruise it reads $\alpha_{rotor}=90^\circ$.`

### ¶20 "The absolute value |V_shaft| ensures…” (l. 2346)
- **Rules broken:** G9 ("Defining the angle…" and "Defining angular values on both axes…" — gerunds as verb forms, twice).
- **Setting:** none (prose; α_disk coupling, V_cross)
- **Current:** Defining the angle relative to the cross-flow axis instead would introduce a singularity (tan(0)=0) in axial cruise. […] Defining angular values on both axes simultaneously is invalid because no reference velocity scale is established.
- **Proposed:** `An angle defined relative to the cross-flow axis instead would introduce a singularity ($\tan(0)=0$) in axial cruise. Therefore, both operating modes enforce the convention: <b>the $x$-axis specifies velocity scale, and the $z$-axis defines angle of incidence</b>. Angular values on both axes simultaneously are invalid, because then no reference velocity scale is established.`

### ¶21 "zBEMT computes both coefficient families…” (l. 2356)
- **Rules broken:** G3 ("the choice between them is argued in 5.4.6" passive); G6 ("In short:" as a telegraphic lead-in after the sentence); plus the plain-text "5.4.6" (see Structural defects).
- **Setting:** `.bemt` key `is_propeller` in `config.bemt`
- **Current:** The definitions are in Sections 5.4.4 and 5.4.5, and the choice between them is argued in 5.4.6. In short:
- **Proposed:** `The definitions are in Sections <a class="xref" href="#cap-14-4" title="5.4.4 Force, torque, and power coefficients: rotor convention">5.4.4</a> and <a class="xref" href="#cap-14-5" title="5.4.5 Force, torque, and power coefficients: propeller convention">5.4.5</a>, and <a class="xref" href="#cap-14-6" title="5.4.6 Choosing between the two conventions">Section 5.4.6</a> explains the choice between them. In summary:`

### ¶22 "The two coefficient families differ by fixed factors…” (l. 2402)
- **Rules broken:** G9 ("reading one as the other").
- **Setting:** none (prose; coefficient conventions)
- **Current:** Therefore reading one as the other is a large error with nothing to signal it. Set the convention to match the reference data the result will be compared against.
- **Proposed:** `Therefore, if you read one convention as the other, the error is large and nothing signals it. Set the convention to match the reference data the result will be compared against.`

### ¶23 "η_prop is useful power over shaft power…” (list item, l. 2410)
- **Rules broken:** G27 (the trailing parenthesis "(T<0, where thrust and power both go negative and the raw ratio would come back positive and flattering)" hides a needed fact); G1 ("flattering" is figurative).
- **Setting:** none (prose; η_prop output)
- **Current:** …and is reported as 0 in the windmill regime (T<0, where thrust and power both go negative and the raw ratio would come back positive and flattering).
- **Proposed:** `…It rises with $J_x$ and peaks at a finite advance ratio. In the windmill regime ($T<0$) it is reported as $0$. In that regime thrust and power both go negative, and the raw ratio would come back positive even though the propeller extracts no useful work.`

### ¶24 "FM compares actual power against the ideal hover power…” (list item, l. 2416)
- **Rules broken:** G2 (three independent clauses joined by commas: "the numerator is no longer…, the ratio is no longer…, and values above unity…"); G19/G18 ("shows exactly that, and it is a property" — "that"/"it" antecedents spread over three preceding clauses).
- **Setting:** none (prose; FM output, μ_x sweep in Section 12.2)
- **Current:** Away from hover the numerator is no longer the ideal power of the condition being flown, the ratio is no longer bounded by 1, and values above unity carry no physical meaning. However, the untrimmed μ_x sweep in Section 12.2 shows exactly that, and it is a property of the definition, not a solver error.
- **Proposed:** `Away from hover, the numerator is no longer the ideal power of the condition being flown. The ratio is no longer bounded by $1$, and values above unity carry no physical meaning. However, the untrimmed $\mu_x$ sweep in <a class="xref" href="#sec-122-results-aggregation" title="12.2 Results Aggregation">Section 12.2</a> shows exactly such values above unity. Those values are a property of the definition, not a solver error. For a propeller, read $FM$ at the static point and $\eta_{prop}$ everywhere else.`

### ¶25 "projects/starter_propeller is a three-bladed…” (l. 2430)
- **Rules broken:** G1 ("the shape every propeller case should have" is informal).
- **Setting:** `.bemt` key `is_propeller: true` in `config.bemt`; `.bemt` keys `mu_z`, `Vx`, `collective_deg`, `rpm` in cases
- **Current:** Its three saved cases have the shape every propeller case should have: the whole condition on the shaft, and the cross-flow left at zero:
- **Proposed:** `Its three saved cases have the form that every propeller case requires: the whole condition on the shaft, and the cross-flow left at zero:`

### ¶26 "In a propeller project the cross-flow is stored as mu_z…” (l. 2438)
- **Rules broken:** G9 ("Running these three cases…" gerund).
- **Setting:** `.bemt` keys `mu_z`, `Vx` (case file)
- **Current:** Running these three cases and two faster ones gives the canonical propeller picture:
- **Proposed:** `These three cases, plus two faster ones, give the canonical propeller picture:`

### ¶27 "The tabulated progression illustrates these aerodynamic metrics…” (l. 2509)
- **Rules broken:** G9 ("decaying in forward flight"), G3 ("η_prop is set to 0 by convention" passive, actor zBEMT); G22 (the FM sentence runs long).
- **Setting:** none (prose; outputs η_prop, FM)
- **Current:** Conversely, the hover Figure of Merit (FM) is physically meaningful only at static conditions (FM = 0.66), decaying in forward flight where the static momentum reference is invalid. […] Thrust becomes negative (windmilling), and η_prop is set to 0 by convention to prevent ambiguous positive efficiency values from negative thrust and power.
- **Proposed:** `Conversely, the hover Figure of Merit ($FM$) is physically meaningful only at static conditions ($FM = 0.66$). It decreases in forward flight, where the static momentum reference is invalid. … Thrust becomes negative (windmilling), and zBEMT sets $\eta_{prop}$ to $0$ by convention, to prevent ambiguous positive efficiency values from negative thrust and power. These evaluations represent fixed-collective (untrimmed) operating points.`

### ¶28 "Specifying the cruise case the wrong way…” (l. 2519)
- **Rules broken:** G9 ("Specifying"); G1 ("the wrong way", "looks respectable" are informal/figurative); G22 (first sentence ~50 words).
- **Setting:** GUI: Run Case tab — cross-flow field; `.bemt` keys `mu_x` = 0.264, `Vz` = 0
- **Current:** Specifying the cruise case the wrong way (the 65 m/s entered in the cross-flow field, that is, mu_x = 0.264 with Vz = 0) converges just as cleanly and reports T=7336 N, P=291 kW, η_prop=0 and FM=0.83: a figure of merit that looks respectable, a thrust two and a half times too large, and an efficiency of zero. Nothing but the validation warning and the shape of the disk map says which of the two runs describes the airplane.
- **Proposed:** `A misspecified cruise case, with the $65$ m/s entered in the cross-flow field instead (that is, <code>mu_x = 0.264</code> with <code>Vz = 0</code>), converges just as cleanly. It reports $T=7336$ N, $P=291$ kW, $\eta_{prop}=0$ and $FM=0.83$: a figure of merit in a normal range, a thrust two and a half times too large, and an efficiency of zero. Only the validation warning and the shape of the disk map tell which of the two runs describes the airplane.`

### ¶29 "The axis naming and the two angles are fixed conventions…” (l. 2526)
- **Rules broken:** G2/G22 (one sentence of ~55 words joining three independent facts).
- **Setting:** none (prose; `.bemt` files)
- **Current:** The axis naming and the two angles are fixed conventions of the program: they are the same in the window, in the results table, in the plots, in the report and in the .bemt file, and a project written in one mode and read back in the other reports the same physical condition under the other mode's letters.
- **Proposed:** `The axis naming and the two angles are fixed conventions of the program. They are the same in the window, in the results table, in the plots, in the report and in the <span class="bemt">.bemt</span> file. A project written in one mode and read back in the other reports the same physical condition under the other mode's letters.`

OK in Section 4 (no changes): ¶ l. 1623 (chapter intro), ¶ l. 1652 ("The free stream is always split…"), the axial/in-plane list at l. 1657, ¶ l. 1713 (propeller flow), ¶ l. 1746 (α_disk), ¶ l. 1750 (J_x), ¶ l. 1794 (disk axes), ¶ l. 2254 (keys do not rotate), ¶ l. 2299 (consistency), ¶ l. 2311 (n, D identity), ¶ l. 2342 (coupling), bold lead at l. 2407.

## Structural defects (appendix items)
- **l. 2364:** plain-text cross-reference "the choice between them is argued in 5.4.6" — section number as plain text with no `<a class="xref">` link (documentation rule 11). Fixed in proposal ¶21 above.
- **l. 1405:** range written with a dash, "tab 1–7" (G28) — table-cell prose, not code. Write "tabs 1 to 7".
- **l. 1522:** "Scout/reconnaissance helicopter" — joining slash in prose (G26). Write "scout and reconnaissance helicopter" (or "scout-reconnaissance" is not justified; the slash joins two roles).
- **l. 1538:** "root/mid/tip" — joining slashes in prose (G26). Write "root, mid-span and tip".
- **l. 1764, 1861, 1895, 1969, 2094, 2155:** "climb/descent" — joining slash in prose (G26), repeated in the tables of Section 4. Write "climb or descent" (or "climb and descent" where both are meant) in each cell.
- **l. 2385 (table header):** "Torque / power" — spaced joining slash (G26). Write "Torque and power".
- **No broken anchors found** in the reviewed range: every `href="#…"` target id (cap-projeto, cap-0-5, cap-designer, cap-interfaces, cap-nomenclatura-helice, cap-13-2, cap-prop-2, cap-prop-4, cap-3-4, cap-3-5, cap-5-2, sec-210-the-fixed-point-equation, sec-122-results-aggregation, cap-14-1, cap-14-4, cap-14-5, sec-21-nomenclature, sec-28-blade-element-theory, cap-12-2, cap-4-4-1, cap-4-4-2, cap-18-1, cap-19-4, cap-6-6) is referenced consistently; the lone "5.4.6" listed above is the only unlinked reference in the block.

---

# Block C: chapter 5 (lines 2537–3531)

## Section 5 — The method (anchor: cap-metodo)
- Paragraphs reviewed: 1 | OK: 1 | Proposals: 0

## 5.1 Disk discretization: radial-azimuthal mesh
- Paragraphs reviewed: 6 | OK: 1 | Proposals: 5

### ¶1 "BEMT solves the physics on an..."
- **Rules broken:** G2 (three facts chained in one sentence), G22 (36 words), G3 ("is written", "is integrated", "is replaced" — actor known), G11 ("by means of" nominalized vehicle).
- **Setting:** none (prose)
- **Current:** <p>BEMT solves the physics on an elemental basis: a local equation is written at each point $(r,\psi)$ and the result is integrated numerically over the disk by means of a double Riemann integral approximated by the trapezoidal rule (detailed in …Section 12.2</a>). The continuous disk is replaced by a discrete mesh of $N_e$ radial stations by $N_\psi$ azimuthal stations: […]
- **Proposed:** `<p>BEMT solves the physics element by element. The method writes a local equation at each point $(r,\psi)$ and integrates the result numerically over the disk as a double Riemann integral, approximated by the trapezoidal rule (detailed in <a class="xref" href="#sec-122-results-aggregation" title="12.2 Results Aggregation">Section 12.2</a>). The discrete mesh replaces the continuous disk with $N_e$ radial stations by $N_\psi$ azimuthal stations: $N_e\times N_\psi$ elements, each with position $(r,\psi)$, interpolated chord and twist, and, after solution, its own aerodynamic state.</p>`

### ¶2 "Actual radial-azimuthal mesh, generated..." (figcaption)
- **Rules broken:** G14 (semicolon joins two caption facts), G6 (telegraphic "Inner white circle: root cutout…").
- **Setting:** none (prose)
- **Current:** <figcaption>Actual radial-azimuthal mesh, generated by the numerical model (here with $N_e=12$ and $N_\psi=24$ for visualization only). Inner white circle: root cutout $r_{root}$; outer circle: tip $r=R$. Each blue dot is a blade element, […]
- **Proposed:** `<figcaption>Actual radial-azimuthal mesh generated by the numerical model (here with $N_e=12$ and $N_\psi=24$ for visualization only). The inner white circle marks the root cutout $r_{root}$. The outer circle marks the tip $r=R$. Each blue dot is a blade element, the unit over which the local physics is evaluated.</figcaption>`

### ¶3 "In hover, and in any purely..."
- **Rules broken:** G1 ("buys nothing" is colloquial).
- **Setting:** none (prose)
- **Current:** […] The cost is redundant work in hover, which is why raising $N_\psi$ there buys nothing.</p>
- **Proposed:** `<p>In hover, and in any purely axial climb or descent, the in-plane component is zero and the solution does not depend on $\psi$. The full mesh is built even so, and every azimuthal column then returns the same result. This uniformity is deliberate: one formulation covers hover, climb, descent and forward flight, and the axisymmetric case is simply the limit of the general one rather than a separate treatment. The cost is redundant work in hover, so raising $N_\psi$ in hover gains no accuracy.</p>`

### ¶4 "Interior nodes..." (boxed)
- **Rules broken:** G14 (semicolon joins two full sentences), G6 ("Numerical reason:" heads a fragment without a main clause before the next colon).
- **Setting:** .bemt key integration_offset
- **Current:** <b>Interior nodes.</b> The mesh avoids nodes exactly at $r_{root}$ or $r=R$; an interior offset (<code>integration_offset</code>) moves the first and last nodes away from the boundary. Numerical reason: the Prandtl factor […] tends to zero at the boundaries, and $\phi$ is poorly defined when $U_T\to0$ at the root: exact evaluation over these singularities produces […]
- **Proposed:** `<b>Interior nodes.</b> The mesh avoids nodes exactly at $r_{root}$ or $r=R$. An interior offset (<code>integration_offset</code>) moves the first and last nodes away from the boundary. The numerical reason is the following: the Prandtl factor (<a class="xref" href="#cap-4-3" title="9.3 Tip and root loss">Section 9.3</a>) tends to zero at the boundaries, and $\phi$ is poorly defined when $U_T\to0$ at the root. Exact evaluation over these singularities produces division by zero or instability in the fixed-point solver.`

### ¶5 "$N_e$ controls the radial resolution..." (boxed note)
- **Rules broken:** G6 (after the colon, "directly affects fidelity…" has no subject), G15 (em dash joins "method" to the Nyquist requirement), G22 (final sentence 29 words).
- **Setting:** none (prose)
- **Current:** $N_e$ controls the radial resolution of the mesh: directly affects fidelity near the root […] $N_\psi$ controls azimuthal resolution: in pure hover ($\mu_x=0$) […] also the azimuthal resolution of the <code>frequency</code> method — the Nyquist theorem requires $N_\psi\gtrsim2\times$(largest harmonic of $f_{st}(\psi)$ to capture) to avoid aliasing.
- **Proposed:** `$N_e$ controls the radial resolution of the mesh. A higher $N_e$ increases the fidelity near the root (where $C_l$ and $C_d$ vary rapidly with the Himmelskamp correction, <a class="xref" href="#cap-4-4-1" title="9.4.1 Rotational augmentation">Section 9.4.1</a>) and near the tip (where the Prandtl factor, <a class="xref" href="#cap-4-3" title="9.3 Tip and root loss">Section 9.3</a>, varies rapidly). $N_\psi$ controls the azimuthal resolution. In pure hover ($\mu_x=0$) the flow is axisymmetric, and $N_\psi=1$ already solves the problem exactly. In forward flight, $N_\psi$ determines how well the azimuthal variation of $\alpha_{eff}$ is resolved. With dynamic stall active, $N_\psi$ also sets the azimuthal resolution of the <code>frequency</code> method. The Nyquist theorem requires $N_\psi\gtrsim2\times$ the largest harmonic of $f_{st}(\psi)$ to capture, in order to avoid aliasing.`

## 5.2 Blade element velocities: U_P, U_T, W
- Paragraphs reviewed: 8 | OK: 4 | Proposals: 4

### ¶1 "A blade element at $(r,\psi)$,..."
- **Rules broken:** G26 ("climbing/descending" joining slash in prose), G30 ("sees a relative velocity" gives perception to a blade element).
- **Setting:** none (prose)
- **Current:** <p>A blade element at $(r,\psi)$, with the rotor spinning at $\Omega$, advancing at $V_x$ and climbing/descending at $V_z$, sees a relative velocity given by the vector sum of three contributions: […]
- **Proposed:** `<p>At a blade element at $(r,\psi)$, with the rotor turning at $\Omega$, advancing at $V_x$ and climbing or descending at $V_z$, the relative velocity is the vector sum of three contributions: rotor rotation, aircraft forward motion, and induced velocity (<a class="xref" href="#sec-29-momentum-theory" title="5.7 Momentum Theory">Section 5.7</a>). This relative velocity decomposes into two orthogonal components: one in the disk plane ($U_T$) and one perpendicular to it ($U_P$).</p>`

### ¶2 "Tangential velocity along span:..." (figcaption)
- **Rules broken:** G13 ("vs." is an abbreviation in prose; use "versus").
- **Setting:** none (prose)
- **Current:** <figcaption>Tangential velocity along span: hover (symmetric) vs. forward flight at $\psi=90^\circ$ (shifted by $V_x$). […]
- **Proposed:** `<figcaption>Tangential velocity along the span: hover (symmetric) versus forward flight at $\psi=90^\circ$ (shifted by $V_x$). Source: <a href="https://kumar-sumeet.github.io/HeliAeroNotes/Lectures/4_ForwardFlight/ForwardFlight.html" target="_blank">S. Kumar, <i>Fundamentals of Helicopter Aerodynamics</i></a>.</figcaption>`

### ¶3 "where $\lambda_z = V_z / (\Omega R)$..."
- **Rules broken:** G27 (parenthesis carries its own full sentence plus a "See" cross-reference).
- **Setting:** none (prose)
- **Current:** <p>where $\lambda_z = V_z / (\Omega R)$ is the prescribed axial inflow ratio (climb or descent in rotor mode, or axial advance $\lambda_x$ in propeller mode. See …Section 4.2.2</a>), and $\lambda_i = v_i / (\Omega R)$ is […]
- **Proposed:** `<p>where $\lambda_z = V_z / (\Omega R)$ is the prescribed axial inflow ratio (climb or descent in rotor mode, or axial advance $\lambda_x$ in propeller mode), and $\lambda_i = v_i / (\Omega R)$ is the induced inflow ratio determined iteratively by the BEMT solver (<a class="xref" href="#sec-210-the-fixed-point-equation" title="5.8 The fixed-point equation">Section 5.8</a>). The axis rotation behind the equivalence with $\lambda_x$ is described in <a class="xref" href="#cap-prop-2" title="4.2.2 The axis rotation, and the name flips it causes">Section 4.2.2</a>. While $U_T$ is purely kinematic, $U_P$ depends on the aerodynamically induced field $\lambda_i$ and is updated at each solver iteration.</p>`

### ¶4 "These three components are evaluated..."
- **Rules broken:** G1 ("anyway", "in the first place" are conversational), G19 ("In both" has two plural antecedents close by; acceptable only after tightening).
- **Setting:** none (prose)
- **Current:** […] The evaluation therefore holds $W$ above a small floor, far below any speed a loaded element sees, so the guard acts only where the load is negligible anyway and leaves ordinary operating results unchanged. The mesh offset of …Section 9.1.4</a> exists for the same reason, and keeps stations off the two boundaries in the first place.</p>
- **Proposed:** `<p>These three components are evaluated at every station of the mesh. Two places need care. Near the hub, $U_T=\Omega r$ goes to zero with the radius. At the reverse-flow boundary, $U_T$ passes through zero by changing sign. In both places, $W$ can become very small, and quantities divided by $W$ would grow without bound. The evaluation therefore holds $W$ above a small floor, far below any speed a loaded element meets, so the guard acts only where the load is negligible and leaves ordinary operating results unchanged. The mesh offset of <a class="xref" href="#cap-4-1-4" title="9.1.4 Integration offset">Section 9.1.4</a> exists for the same reason and keeps the stations off the two boundaries from the outset.</p>`

## 5.3 Blade element angles: θ, φ, α
- Paragraphs reviewed: 11 | OK: 10 | Proposals: 1

### ¶1 "The pitch command splits into..."
- **Rules broken:** G9 ("Writing the first as…" is an "-ing" form used as a verb).
- **Setting:** none (prose)
- **Current:** <p>The pitch command splits into a part that is the same at every station and a part that varies around the azimuth. Writing the first as the collective $\theta_0$ and the second as $\theta_{cyc}(\psi)$,</p>
- **Proposed:** `<p>The pitch command splits into a part that is the same at every station and a part that varies around the azimuth. Denote the first as the collective $\theta_0$ and the second as $\theta_{cyc}(\psi)$:</p>`

## 5.4.1 Advance ratio, μ_x
- Paragraphs reviewed: 6 | OK: 2 | Proposals: 4

### ¶1 "The advance ratio is the single..."
- **Rules broken:** G30 (a number "says"), G4 ("has moved" is a compound tense).
- **Setting:** none (prose)
- **Current:** <p>The advance ratio is the single number that says how far a rotor has moved away from hover, and almost every asymmetry in this document is a consequence of it. It compares the speed at which the whole rotor translates through the air with the speed at which its own tips turn, so it is the ratio of the two velocities a blade section experiences at once.</p>
- **Proposed:** `<p>The advance ratio is the single number that measures the distance of a rotor from hover, and almost every asymmetry in this document is a consequence of it. It compares the speed at which the whole rotor translates through the air with the speed at which its own tips turn. It is therefore the ratio of the two velocities that a blade section meets at once.</p>`

### ¶2 "Forward flight operational boundaries...."
- **Rules broken:** G6 ("And (2) compressibility effects…" is a fragment starting with "And"), G22 (first sentence 22 words carrying an enumeration).
- **Setting:** none (prose)
- **Current:** <p><b>Forward flight operational boundaries.</b> Advance ratio establishes two aerodynamic limits: (1) reverse flow on the retreating blade ($U_T < 0$), forming a circular region of diameter $\mu_x R$ tangent to the hub (…Section 8.4</a>). And (2) compressibility effects on the advancing tip ($\Omega R + V_x$), which elevate the local Mach number toward transonic drag divergence (…Section 8.5</a>). The envelope between retreating blade stall and advancing tip compressibility dictates maximum forward speed.</p>
- **Proposed:** `<p><b>Forward flight operational boundaries.</b> Advance ratio establishes two aerodynamic limits. The first is reverse flow on the retreating blade ($U_T < 0$), which forms a circular region of diameter $\mu_x R$ tangent to the hub (<a class="xref" href="#cap-3-4" title="8.4 Reverse flow">Section 8.4</a>). The second is compressibility on the advancing tip ($\Omega R + V_x$), which raises the local Mach number toward transonic drag divergence (<a class="xref" href="#cap-3-5" title="8.5 Compressibility">Section 8.5</a>). The envelope between retreating blade stall and advancing tip compressibility dictates the maximum forward speed.</p>`

### ¶3 "Axis conventions in rotor vs. propeller..."
- **Rules broken:** G26 (<code>mu_z</code>/<code>J_z</code>/<code>Vz</code> joined by slashes inside prose; the slash is not part of any identifier), G13 ("vs." in the bold lead).
- **Setting:** none (prose)
- **Current:** <p><b>Axis conventions in rotor vs. propeller mode.</b> […] Internal solver variables maintain disk-aligned coordinates (axial flow stored under <code>mu_z</code>/<code>J_z</code>/<code>Vz</code>), while the user interface dynamically adjusts input labels based on operating mode […]
- **Proposed:** `<p><b>Axis conventions in rotor and propeller mode.</b> In rotor mode, $\mu_x$ denotes the in-plane advance ratio and $\mu_z$ denotes the axial inflow along the shaft. In propeller mode, the shaft is aligned longitudinally, so the displayed labels rotate: axial flight speed corresponds to $\mu_x$ (or $J_x$), while vertical cross-flow corresponds to $\mu_z$ (or $J_z$). The internal solver variables maintain disk-aligned coordinates (axial flow stored under <code>mu_z</code>, <code>J_z</code> and <code>Vz</code>), while the user interface adjusts the input labels according to the operating mode (<a class="xref" href="#cap-5-1" title="10.1 In-plane flow — the first row">Section 10.1</a>).</p>`

### ¶4 "Reading the number...."
- **Rules broken:** G18 ("so it can often be ignored" — both "the asymmetry" and "the reverse-flow circle" are candidate antecedents).
- **Setting:** none (prose)
- **Current:** […] Up to roughly $0.1$ the asymmetry is mild and the reverse-flow circle usually falls inside the root cutout, so it can often be ignored. […]
- **Proposed:** `<p><b>Reading the number.</b> $\mu_x=0$ is hover, where the disk is axisymmetric and every field depends on radius alone. Up to roughly $0.1$ the asymmetry is mild and the reverse-flow circle usually falls inside the root cutout, so the reverse-flow region can often be ignored. Between $0.15$ and $0.35$ is conventional cruise, where the choice of inflow model and of reverse-flow treatment starts to matter to the answer. Above $0.4$ both limits are active at once and the results should be treated as indicative: the models here are steady and do not represent the blade motion a real rotor uses to relieve the imbalance.</p>`

## 5.4.2 Inflow ratios
- Paragraphs reviewed: 1 | OK: 0 | Proposals: 1

### ¶1 "These parameters non-dimensionalize..."
- **Rules broken:** G27 (parenthesis contains a full sentence plus a "See" cross-reference).
- **Setting:** none (prose)
- **Current:** […] is defined by the flight condition (equivalent to axial advance $\lambda_x$ in propeller coordinates. See …Section 4.2.2</a>). […]
- **Proposed:** `<p>These parameters non-dimensionalize the axial velocity components by the tip speed $\Omega R$. The free-stream inflow ratio $\lambda_z = V_z / (\Omega R)$ is defined by the flight condition. It equals the axial advance $\lambda_x$ in propeller coordinates (see <a class="xref" href="#cap-prop-2" title="4.2.2 The axis rotation, and the name flips it causes">Section 4.2.2</a>). The induced inflow ratio $\lambda_i = v_i / (\Omega R)$ is computed iteratively by the BEMT solver (<a class="xref" href="#sec-210-the-fixed-point-equation" title="5.8 The fixed-point equation">Section 5.8</a> and <a class="xref" href="#sec-211-formal-coupling" title="5.9 Formal Coupling">Section 5.9</a>). Their sum, $\lambda_{total} = \lambda_z + \lambda_i$, governs the normal velocity component $U_P$ (<a class="xref" href="#cap-12-2" title="5.2.2 Component perpendicular to the disk, $U_P$">Section 5.2.2</a>) and the local inflow angle $\phi(r,\psi)$ (<a class="xref" href="#cap-13-2" title="5.3.2 Inflow angle, $\phi$">Section 5.3.2</a>).</p>`

## 5.4.3 Solidity
- Paragraphs reviewed: 4 | OK: 3 | Proposals: 1

### ¶1 "Solidity is the fraction of the disk..."
- **Rules broken:** G30 (a geometric number "says").
- **Setting:** none (prose)
- **Current:** […] It is dimensionless, and it is the one geometric number that says how much lifting surface the rotor has available for the disk area it sweeps.</p>
- **Proposed:** `<p>Solidity is the fraction of the disk that is blade: locally, the blade area in an annulus divided by the area of that annulus. Globally, the total blade area divided by the disk area. It is dimensionless, and it is the one geometric number that measures how much lifting surface the rotor has available for the disk area it sweeps.</p>`

## 5.4.4 Force, torque, and power coefficients: rotor convention
- Paragraphs reviewed: 2 | OK: 1 | Proposals: 1

### ¶1 "References: velocity $\Omega R$, area..."
- **Rules broken:** G6 (telegraphic; no verb).
- **Setting:** none (prose)
- **Current:** <p>References: velocity $\Omega R$, area $A=\pi R^2$.</p>
- **Proposed:** `<p>The reference velocity is $\Omega R$ and the reference area is $A=\pi R^2$.</p>`

## 5.4.5 Force, torque, and power coefficients: propeller convention
- Paragraphs reviewed: 2 | OK: 1 | Proposals: 1

### ¶1 "References: velocity $nD$..."
- **Rules broken:** G6 (telegraphic).
- **Setting:** none (prose)
- **Current:** <p>References: velocity $nD$ ($n=\Omega/2\pi$, $D=2R$).</p>
- **Proposed:** `<p>The reference velocity is $nD$, with $n=\Omega/2\pi$ and $D=2R$.</p>`

## 5.4.6 Choosing between the two conventions
- Paragraphs reviewed: 4 | OK: 4 | Proposals: 0

## 5.5 Problem formulation: two theories, one unknown
- Paragraphs reviewed: 4 | OK: 2 | Proposals: 2

### ¶1 "the Momentum Theory ... / the Blade Element Theory..." (list items)
- **Rules broken:** G9 ("relating", "calculating" are "-ing" forms used as verbs).
- **Setting:** none (prose)
- **Current:** <li>the <b>Momentum Theory</b> […] models each ring of the disk as an elementary actuator disk, relating the thrust $dT$ to the induced velocity $\lambda_i$ by conservation of mass and momentum, without information about blade shape;</li> <li>the <b>Blade Element Theory</b> […] applies 2D airfoil aerodynamics, $C_l(\alpha_{eff})$ and $C_d(\alpha_{eff})$, to each element, calculating the load produced given $\alpha_{eff}=\theta-\phi$, which depends on $\lambda_i$ […]
- **Proposed:** `<li>the <b>Momentum Theory</b> (<a class="xref" href="#sec-29-momentum-theory" title="5.7 Momentum Theory">Section 5.7</a>) models each ring of the disk as an elementary actuator disk and relates the thrust $dT$ to the induced velocity $\lambda_i$ by conservation of mass and momentum, without information about blade shape;</li>` `<li>the <b>Blade Element Theory</b> (<a class="xref" href="#sec-28-blade-element-theory" title="5.6 Blade Element Theory">Section 5.6</a>) applies 2D airfoil aerodynamics, $C_l(\alpha_{eff})$ and $C_d(\alpha_{eff})$, to each element and calculates the load for a given $\alpha_{eff}=\theta-\phi$, which depends on $\lambda_i$ (<a class="xref" href="#cap-13-3" title="5.3.3 Effective angle of attack, $\alpha_{eff}$">Section 5.3.3</a>).</li>`

### ¶2 "Neither theory alone closes the problem..."
- **Rules broken:** G14 (semicolon joins two full sentences), G12 ("without known $\lambda_i$" drops the article).
- **Setting:** none (prose)
- **Current:** <p>Neither theory alone closes the problem: momentum theory does not determine the load without known $\lambda_i$; blade element theory does not determine $\alpha_{eff}$ without the same $\lambda_i$. […]
- **Proposed:** `<p>Neither theory alone closes the problem. Momentum theory does not determine the load without a known $\lambda_i$. Blade element theory does not determine $\alpha_{eff}$ without the same $\lambda_i$. The BEMT coupling solves both equations simultaneously, element by element, by requiring that both produce the same local $\lambda_i$.</p>`

## 5.6.1 Aerodynamic independence hypothesis
- Paragraphs reviewed: 6 | OK: 6 | Proposals: 0

## 5.6.2 2D airfoil aerodynamics: the airfoil polar
- Paragraphs reviewed: 5 | OK: 5 | Proposals: 0

## 5.6.3 Elementary lift and drag
- Paragraphs reviewed: 5 | OK: 3 | Proposals: 2

### ¶1 "The dynamic pressure sets the scale...."
- **Rules broken:** G22 (two sentences of 33 and 38 words, each with three clauses), D2/D3 (one sentence carries density scaling and performance reporting in a single breath).
- **Setting:** .bemt key rho
- **Current:** […] Air density (<code>rho</code>) multiplies every force and every moment linearly, so thrust, torque and power all scale directly with it: the same rotor at the same collective and the same rotational speed produces about a quarter less thrust at $3000\,$m of altitude than at sea level, and this is the single dominant reason hover performance degrades with altitude and temperature. Because density scales lift and drag identically, it does not move the angle of attack at which a section is efficient, and it therefore leaves the dimensionless coefficients almost unchanged, which is precisely why performance is reported in coefficient form.</p>
- **Proposed:** `<p><b>The dynamic pressure sets the scale.</b> The factor $\tfrac12\rho W^2$ is the dynamic pressure of the flow the section actually meets. Air density (<code>rho</code>) multiplies every force and every moment linearly. Thrust, torque and power therefore all scale directly with density: the same rotor at the same collective and the same rotational speed produces about a quarter less thrust at $3000\,$m of altitude than at sea level. This density scaling is the single dominant reason hover performance degrades with altitude and temperature. Because density scales lift and drag identically, density does not move the angle of attack at which a section is efficient and leaves the dimensionless coefficients almost unchanged. This insensitivity is precisely why performance is reported in coefficient form.</p>`

### ¶2 "The velocity dependence is quadratic,..."
- **Rules broken:** G31 ("per cent" is the two-word British form; American is "percent"), G1 ("such a blunt instrument" is metaphorical and conversational).
- **Setting:** none (prose)
- **Current:** […] A ten per cent increase in rotational speed raises the load on every element by about twenty-one per cent and the profile power by about thirty-three per cent, since power carries an extra factor of velocity. This is why rotational speed is such a blunt instrument for changing thrust, and why the outer third of the blade dominates the integral even when the coefficients there are modest.</p>
- **Proposed:** `<p><b>The velocity dependence is quadratic, and it is not uniform.</b> $W$ varies as $\Omega r$ along the span and, in forward flight, additionally with azimuth. A ten percent increase in rotational speed raises the load on every element by about twenty-one percent and the profile power by about thirty-three percent, since power carries an extra factor of velocity. Rotational speed is therefore a coarse instrument for changing thrust, and the outer third of the blade dominates the integral even when the coefficients there are modest.</p>`

## 5.6.4 Normal and tangential projection to disk
- Paragraphs reviewed: 7 | OK: 4 | Proposals: 3

### ¶1 "Actual zBEMT calculation..." (figcaption)
- **Rules broken:** G1 (broken comparative "largest on the advancing side … than on the retreating side"), G22 (one sentence runs 38 words).
- **Setting:** none (prose)
- **Current:** […] $F_n$ is systematically positive and largest on the advancing side ($\psi\approx90^\circ$, where $U_T=\Omega r+V_x\sin\psi$ is maximum) than on the retreating side ($\psi\approx270^\circ$, where $U_T$ is minimum and can enter reverse flow near root, …Section 8.4</a>). […]
- **Proposed:** `<figcaption>Actual zBEMT calculation (<code>starter_rotor</code>, $\mu_x=0.30$, level flight, $\psi=90^\circ$ upward in the graph, advance in the $+y$ direction): normal load $F_n$ (thrust per unit span) and tangential load $F_t$ (torque per unit span) over the complete disk. $F_n$ is systematically positive, and it is larger on the advancing side ($\psi\approx90^\circ$, where $U_T=\Omega r+V_x\sin\psi$ is maximum) than on the retreating side ($\psi\approx270^\circ$, where $U_T$ is minimum and can enter reverse flow near the root, <a class="xref" href="#cap-3-4" title="8.4 Reverse flow">Section 8.4</a>). The longitudinal-lateral asymmetry of the field is the same harmonic signature of $\lambda_i(r,\psi)$ discussed in <a class="xref" href="#cap-4-2" title="9.2 Inflow model">Section 9.2</a>. $F_t$ changes sign: positive (absorbing torque from the shaft) over most of the disk, but locally negative in the reverse-flow region, where the blade can momentarily produce thrust rather than drag.</figcaption>`

### ¶2 "$P_i$, the induced power,..."
- **Rules broken:** G31 ("backwards"; American form is "backward").
- **Setting:** none (prose)
- **Current:** […] It exists because the resultant force has to be tilted backwards by $\phi$ in order to have a component along the shaft, and $\phi$ is non-zero only because the rotor is pushing air through its own disk. […]
- **Proposed:** `<p>$P_i$, the <b>induced power</b>, is the part paid for producing thrust. It exists because the resultant force must be tilted backward by $\phi$ in order to have a component along the shaft, and $\phi$ is non-zero only because the rotor pushes air through its own disk. It therefore scales with the induced velocity, and it falls as forward speed renews the mass flow through the disk.</p>`

### ¶3 "obtained for a constant drag coefficient..."
- **Rules broken:** G30 ("it says that" gives the closed form speech).
- **Setting:** none (prose)
- **Current:** <p>obtained for a constant drag coefficient and an untwisted rectangular blade. zBEMT does not use that expression (it integrates the actual $C_d$ element by element) but the form is worth carrying, because it says that profile power grows slowly with advance ratio and never disappears.</p>
- **Proposed:** `<p>obtained for a constant drag coefficient and an untwisted rectangular blade. zBEMT does not use that expression (it integrates the actual $C_d$ element by element), but the form is worth retaining, because it shows that profile power grows slowly with advance ratio and never disappears.</p>`

## 5.6.5 Solidity and disk loading
- Paragraphs reviewed: 1 | OK: 0 | Proposals: 1

### ¶1 "Solidity converts the load of one blade..."
- **Rules broken:** G10 (project name written "ZBEMT" here, "zBEMT" everywhere else), G1 ("which enters equality with momentum theory" is not grammatical).
- **Setting:** none (prose)
- **Current:** <p>Solidity converts the load of one blade (…Section 5.6.3</a>, per unit span) into the load of $N_b$ blades per unit annular area, which enters equality with momentum theory (…Section 5.7.5</a>). The linearized form above, obtained by assuming $C_l$ linear in $\alpha$ and integrating analytically, serves for order-of-magnitude estimation. ZBEMT solves numerically, element by element, with the actual airfoil polar, without this linearization.</p>
- **Proposed:** `<p>Solidity converts the load of one blade (<a class="xref" href="#cap-19-3" title="5.6.3 Elementary lift and drag">Section 5.6.3</a>, per unit span) into the load of $N_b$ blades per unit annular area, which is then equated to the load from momentum theory (<a class="xref" href="#cap-18-5" title="5.7.5 From global disk to elementary ring">Section 5.7.5</a>). The linearized form above, obtained from a $C_l$ linear in $\alpha$ and an analytical integration, serves for order-of-magnitude estimation. zBEMT solves the full problem numerically, element by element, with the actual airfoil polar and without this linearization.</p>`

## 5.7.1 Global actuator disk
- Paragraphs reviewed: 9 | OK: 5 | Proposals: 4

### ¶1 "Dividing the energy equation by..."
- **Rules broken:** G9 ("Dividing…" is an "-ing" form used as an imperative verb in descriptive text).
- **Setting:** none (prose)
- **Current:** <p>where $\dot m$ is the mass flow rate through the disk, $v$ the induced velocity at the disk plane, and $w$ the induced velocity in the far wake. Dividing the energy equation by the momentum equation (canceling $\dot m$):</p>
- **Proposed:** `<p>where $\dot m$ is the mass flow rate through the disk, $v$ the induced velocity at the disk plane, and $w$ the induced velocity in the far wake. The ratio of the energy equation to the momentum equation, with $\dot m$ canceled, gives:</p>`

### ¶2 "$v_h$ is the ideal hover-induced velocity...."
- **Rules broken:** G14 (semicolon joins two full sentences).
- **Setting:** none (prose)
- **Current:** <p>$v_h$ is the ideal hover-induced velocity. The ideal induced power, $P_i=Tv_h$, is the thermodynamic minimum to produce thrust $T$ with disk area $A$; the ratio of this minimum to actual power is the Figure of Merit (…Section 5.4.4</a>).</p>
- **Proposed:** `<p>$v_h$ is the ideal hover-induced velocity. The ideal induced power, $P_i=Tv_h$, is the thermodynamic minimum to produce thrust $T$ with disk area $A$. The ratio of this minimum to the actual power is the Figure of Merit (<a class="xref" href="#cap-14-4" title="5.4.4 Force, torque, and power coefficients: rotor convention">Section 5.4.4</a>).</p>`

### ¶3 "The relation $v=w/2$ follows..." (boxed)
- **Rules broken:** G14 (semicolon joins two full sentences).
- **Setting:** none (prose)
- **Current:** […] The power delivered to the air is $Tv$; the kinetic energy created per unit time is $\tfrac12\dot m w^2$. […]
- **Proposed:** `The relation $v=w/2$ follows directly from the three conservation laws, not from an additional hypothesis. The power delivered to the air is $Tv$. The kinetic energy created per unit time is $\tfrac12\dot m w^2$. Without losses, these quantities are equal, and solving this equality for $v$ as a function of $w$ yields a unique solution: $v=w/2$. Any other ratio would violate energy conservation under the ideal fluid assumptions adopted.`

### ¶4 "Numerical example...." (boxed note)
- **Rules broken:** G6 (telegraphic string of assignments; no verbs in the opening clause).
- **Setting:** none (prose)
- **Current:** <b>Numerical example.</b> Rotor with $R=0.5$ m ($A\approx0.785\,\text{m}^2$), $T=19.6$ N ($M=2$ kg, $\rho=1.225\,\text{kg/m}^3$): $v_h=\sqrt{19.6/(2\times1.225\times0.785)} \approx3.2\,\text{m/s}$, $P_i=Tv_h\approx62.7$ W. […]
- **Proposed:** `<b>Numerical example.</b> Consider a rotor with $R=0.5$ m ($A\approx0.785\,\text{m}^2$), $T=19.6$ N ($M=2$ kg) and $\rho=1.225\,\text{kg/m}^3$. The ideal induced velocity is $v_h=\sqrt{19.6/(2\times1.225\times0.785)} \approx3.2\,\text{m/s}$, and the ideal induced power is $P_i=Tv_h\approx62.7$ W. With $FM\approx0.7$, the actual induced power is $P_i/FM\approx90$ W. The profile power (<a class="xref" href="#cap-19-4" title="5.6.4 Normal and tangential projection to disk">Section 5.6.4</a>) adds to this value.`

## 5.7.2 Vertical climb and descent
- Paragraphs reviewed: 3 | OK: 2 | Proposals: 1

### ¶1 "Repeating the analysis with climb velocity..."
- **Rules broken:** G9 ("Repeating" used as a verb form).
- **Setting:** none (prose)
- **Current:** <p>Repeating the analysis with climb velocity $V_z$ imposed on the rotor (mass entering the disk at $V_z+v$):</p>
- **Proposed:** `<p>The same analysis, with the climb velocity $V_z$ imposed on the rotor so that mass enters the disk at $V_z+v$, gives:</p>`

## 5.7.3 Limits of validity: vortex ring and windmill brake
- Paragraphs reviewed: 6 | OK: 2 | Proposals: 4

### ¶1 "In descent the disk moves down..."
- **Rules broken:** G4 ("it has just accelerated" is a present perfect compound tense), G31 ("downwards"; American form "downward").
- **Setting:** none (prose)
- **Current:** <p>In descent the disk moves down into the air it has just accelerated downwards. When the descent rate and the induced velocity are of the same order (which is what that band means), the two nearly cancel, the wake cannot escape in either direction, and the reingested air rolls into an unstable recirculating torus around the disk: the <b>vortex ring state</b>. […]
- **Proposed:** `<p>In descent, the disk moves down into air that the disk itself accelerated downward a moment earlier. When the descent rate and the induced velocity are of the same order (which is what that band means), the two nearly cancel, the wake cannot escape in either direction, and the reingested air rolls into an unstable recirculating torus around the disk: the <b>vortex ring state</b>. Beside it, at a slightly faster descent, lies the <b>turbulent wake state</b>, where the wake is fragmented but still not convected clear.</p>`
- (This rewrite also covers ¶ "…wake is broken up…": G8, "broken up" is a phrasal verb → "fragmented".)

### ¶2 "Descend faster still and the wake..."
- **Rules broken:** G2 (an imperative plus a statement chained into one conditional), G1 (direct appeal "Descend faster still" in a descriptive chapter), G31 ("upwards"; American "upward").
- **Setting:** none (prose)
- **Current:** <p>Descend faster still and the wake escapes cleanly upwards, the streamtube is well defined again, and momentum theory recovers: the <b>windmill brake state</b>, in which the rotor extracts energy from the flow like a wind turbine while still producing thrust.</p>
- **Proposed:** `<p>At an even faster descent, the wake escapes cleanly upward, the streamtube is well defined again, and momentum theory recovers: the <b>windmill brake state</b>, in which the rotor extracts energy from the flow like a wind turbine while still producing thrust.</p>`

### ¶3 "Universal induced velocity curve..." (figcaption)
- **Rules broken:** G26 ("Johnson/Leishman" joins two names with a slash in prose).
- **Setting:** none (prose)
- **Current:** <figcaption>Universal induced velocity curve (Johnson/Leishman form, calculated from the momentum equations of Sections … […]
- **Proposed:** `<figcaption>Universal induced velocity curve (Johnson–Leishman form, calculated from the momentum equations of Sections <a class="xref" href="#cap-18-1" title="5.7.1 Global actuator disk">5.7.1</a> and <a class="xref" href="#cap-18-2" title="5.7.2 Vertical climb and descent">5.7.2</a> in the valid branches, with empirical fit in the shaded band): the formal solution of momentum theory exists over the entire domain, but does not describe the flow in the non-stationary recirculation band.</figcaption>`

## 5.7.4 Effect of advance ratio on induced velocity
- Paragraphs reviewed: 2 | OK: 2 | Proposals: 0

## 5.7.5 From global disk to elementary ring
- Paragraphs reviewed: 4 | OK: 1 | Proposals: 3

### ¶1 "The connection between the global analysis..."
- **Rules broken:** G12 ("the effect of finite number of blades" drops the article).
- **Setting:** none (prose)
- **Current:** […] The Prandtl correction (…Section 9.3</a>) reintroduces approximately the effect of finite number of blades that this hypothesis suppresses.</p>
- **Proposed:** `<p>The connection between the global analysis of Sections <a class="xref" href="#cap-18-1" title="5.7.1 Global actuator disk">5.7.1</a> to <a class="xref" href="#cap-18-4" title="5.7.4 Effect of advance ratio on induced velocity">5.7.4</a> and Blade Element Theory (<a class="xref" href="#sec-28-blade-element-theory" title="5.6 Blade Element Theory">Section 5.6</a>) requires a local version of momentum theory, applied to an elementary ring of radius $r$ to $r+dr$ (area $dA=2\pi r\,dr$). The central hypothesis (and the main conceptual limitation of classical BEMT) is that distinct radial rings do not exchange mass or momentum with each other: each ring behaves like an independent actuator disk, isolated from its neighbors. This hypothesis ignores radial turbulent mixing and tip vortex induction on inner rings. The Prandtl correction (<a class="xref" href="#cap-4-3" title="9.3 Tip and root loss">Section 9.3</a>) reintroduces approximately the effect of the finite number of blades that this hypothesis suppresses.</p>`

### ¶2 "Under this hypothesis, repeating..."
- **Rules broken:** G9 ("repeating" used as a verb form).
- **Setting:** none (prose)
- **Current:** <p>Under this hypothesis, repeating …Section 5.7.1</a> for the ring:</p>
- **Proposed:** `<p>Under this hypothesis, the analysis of <a class="xref" href="#cap-18-1" title="5.7.1 Global actuator disk">Section 5.7.1</a> applied to the ring gives:</p>`

### ¶3 "This equation, equated to the load..."
- **Rules broken:** G3 ("is accounted for by the blade element side" is passive with a known actor), G2 (final sentence carries the passive plus a trailing participial clause).
- **Setting:** none (prose)
- **Current:** […] Elementary momentum theory addresses only the axial balance (thrust). The angular momentum conservation required to produce torque is accounted for by the blade element side (tangential force, …Section 5.6.4</a>), not reintroduced here as an independent momentum unknown.</p>
- **Proposed:** `<p>This equation, equated to the load calculated by the blade element (<a class="xref" href="#sec-28-blade-element-theory" title="5.6 Blade Element Theory">Section 5.6</a>), determines $\lambda_i(r,\psi)$: the coupling formalized in <a class="xref" href="#sec-211-formal-coupling" title="5.9 Formal Coupling">Section 5.9</a>. Elementary momentum theory addresses only the axial balance (thrust). The blade element side (tangential force, <a class="xref" href="#cap-19-4" title="5.6.4 Normal and tangential projection to disk">Section 5.6.4</a>) supplies the tangential balance that produces torque. Angular momentum conservation therefore does not enter here as an independent momentum unknown.</p>`

## 5.8 The fixed-point equation
- Paragraphs reviewed: 9 | OK: 7 | Proposals: 2

### ¶1 "The two theories furnish two expressions..."
- **Rules broken:** G9 ("Defining $g$ as…" is an "-ing" verb form; sentence then runs 40 words, G22).
- **Setting:** none (prose)
- **Current:** […] Defining $g$ as the function that maps a trial field $\lambda_i$ to the value of $\lambda_i$ that momentum theory would produce to sustain the load calculated by blade element theory from that same field, the problem takes the form</p>
- **Proposed:** `<p>The two theories furnish two expressions for the same elementary normal load $dF_n$ (Sections <a class="xref" href="#sec-28-blade-element-theory" title="5.6 Blade Element Theory">5.6</a> and <a class="xref" href="#sec-29-momentum-theory" title="5.7 Momentum Theory">5.7</a>). Let $g$ be the function that maps a trial field $\lambda_i$ to the value of $\lambda_i$ that momentum theory would produce to sustain the load that blade element theory calculates from that same field. With this definition, the problem takes the form</p>`

### ¶2 "Each element $(r,\psi)$ has unknown..." (boxed note)
- **Rules broken:** G12 ("has unknown" drops the article).
- **Setting:** none (prose)
- **Current:** Each element $(r,\psi)$ has unknown $\lambda_i(r,\psi)$ solved essentially independently of neighboring elements. […]
- **Proposed:** `Each element $(r,\psi)$ has an unknown $\lambda_i(r,\psi)$, solved essentially independently of the neighboring elements. Coupling between elements occurs only via the Prandtl factor (<a class="xref" href="#cap-4-3" title="9.3 Tip and root loss">Section 9.3</a>) and the nonuniform inflow models (<a class="xref" href="#cap-4-2" title="9.2 Inflow model">Section 9.2</a>), without a dense coupling matrix. The system is therefore $N_e\times N_\psi$ independent scalar fixed-point equations, all advanced together at each iteration rather than one at a time.`

## 5.9 Formal Coupling
- Paragraphs reviewed: 13 | OK: 11 | Proposals: 2

### ¶1 "Two features of the denominator are worth..."
- **Rules broken:** G6/G2 (sentence opens with "And", chaining to the previous sentence), G3 ("a small constant is added" — the implementation is the actor), G18 (final "It" competes between "constant" and "expression").
- **Setting:** none (prose)
- **Current:** […] grows with the in-plane component in forward flight, which is why the same load needs less induced velocity as the rotor advances. And because both terms vanish together at the root of a hovering rotor, a small constant is added under the root so that the expression stays finite there. It is far below the tolerance of …Section 9.5.2</a> and does not affect a converged result.</p>
- **Proposed:** `<p>Two features of the denominator are worth reading. The factor $\sqrt{\lambda_{total}^{2}+\mu_x^{2}}$ is the speed of the mass flow through the ring: it reduces to the axial component alone in hover, where $\mu_x=0$, and grows with the in-plane component in forward flight, which is why the same load needs less induced velocity as the rotor advances. Both terms vanish together at the root of a hovering rotor, so the implementation adds a small constant under the root to keep the expression finite there. The constant is far below the tolerance of <a class="xref" href="#cap-4-5-2" title="9.5.2 Iteration limit and tolerance">Section 9.5.2</a> and does not affect a converged result.</p>`

### ¶2 "The numerical solver and the Results plots..."
- **Rules broken:** G1 ("helps you diagnose" uses the second person in a descriptive passage).
- **Setting:** GUI: Results tab
- **Current:** <p>The numerical solver and the Results plots use the returned aerodynamic state. The sequence helps you diagnose a solution. In normal <span class="gui">GUI</span> use, check the convergence and the physical inputs described above.</p>
- **Proposed:** `<p>The numerical solver and the Results plots use the returned aerodynamic state. This sequence also indicates where a failed solution departs from a physical one. In normal <span class="gui">GUI</span> use, check the convergence and the physical inputs described above.</p>`

## 5.10 Two worked cases: hover and forward flight
- Paragraphs reviewed: 21 | OK: 15 | Proposals: 6

### ¶1 "Hover ($\mu_x=0$, $V_x=0$) is the axisymmetric..."
- **Rules broken:** G26 ("tip/root loss" joining slash in prose), G1 ("no-op" is jargon), G22/G2 (one 60-word sentence carries four parenthesized cross-references and two topics).
- **Setting:** none (prose)
- **Current:** <p>Hover ($\mu_x=0$, $V_x=0$) is the axisymmetric limit of the general problem: no azimuthal variation, so the mesh's $N_\psi$ dimension carries no physics (…Section 5.1</a>) and every physical correction that exists specifically to handle forward-flight asymmetry (reverse flow (…Section 8.4</a>), non-uniform inflow harmonics (…Section 9.2</a>), the azimuth-crossing term of the relaxation schedule (…Section 9.5.3</a>)) is inactive or a no-op. What remains is the irreducible core: momentum theory (…Section 5.7</a>) against blade element theory (…Section 5.6</a>), tip/root loss (…Section 9.3</a>), and the solver (…Section 9.5</a>).</p>
- **Proposed:** `<p>Hover ($\mu_x=0$, $V_x=0$) is the axisymmetric limit of the general problem. There is no azimuthal variation, so the $N_\psi$ dimension of the mesh carries no physics (<a class="xref" href="#sec-23-disk-discretization-radial-azimuthal-mesh" title="5.1 Disk discretization: radial-azimuthal mesh">Section 5.1</a>). Every physical correction that exists specifically to handle forward-flight asymmetry is inactive or reduces to an identity: the reverse-flow models (<a class="xref" href="#cap-3-4" title="8.4 Reverse flow">Section 8.4</a>), the non-uniform inflow harmonics (<a class="xref" href="#cap-4-2" title="9.2 Inflow model">Section 9.2</a>), and the azimuth-crossing term of the relaxation schedule (<a class="xref" href="#cap-4-5-3" title="9.5.3 Relaxation">Section 9.5.3</a>). What remains is the irreducible core: momentum theory (<a class="xref" href="#sec-29-momentum-theory" title="5.7 Momentum Theory">Section 5.7</a>) against blade element theory (<a class="xref" href="#sec-28-blade-element-theory" title="5.6 Blade Element Theory">Section 5.6</a>), tip and root loss (<a class="xref" href="#cap-4-3" title="9.3 Tip and root loss">Section 9.3</a>), and the solver (<a class="xref" href="#cap-4-5" title="9.5 The induced-inflow solver">Section 9.5</a>).</p>`

### ¶2 "The coefficient form of..." (table cell, Figure of Merit row)
- **Rules broken:** G14 (semicolon joins two sentences), G28 (range written with an en dash, "&ndash;", in prose; code exemption does not apply).
- **Setting:** none (prose)
- **Current:** <td>The coefficient form of …Section 5.4.4</a>, $FM=(C_T^{3/2}/\sqrt2)/C_Q$, which in hover equals the ratio $P_i/P$ of the two rows above. Well-designed rotors sit at $0.7$&ndash;$0.8$; this reference geometry is slightly above that band</td>
- **Proposed:** `<td>The coefficient form of <a class="xref" href="#cap-14-4" title="5.4.4 Force, torque, and power coefficients: rotor convention">Section 5.4.4</a>, $FM=(C_T^{3/2}/\sqrt2)/C_Q$, which in hover equals the ratio $P_i/P$ of the two rows above. Well-designed rotors sit at $0.7$ to $0.8$. This reference geometry is slightly above that band</td>`

### ¶3 "zero to floating-point noise..." (table cell)
- **Rules broken:** G6 (telegraphic; no verb).
- **Setting:** none (prose)
- **Current:** <td>zero to floating-point noise. Axisymmetric loading has no preferred azimuthal direction to push the hub sideways</td>
- **Proposed:** `<td>The values are zero to floating-point noise. Axisymmetric loading has no preferred azimuthal direction to push the hub sideways</td>`

### ¶4 "Advancing-blade dynamic pressure increase..." (table cell)
- **Rules broken:** G12 (missing articles before "advancing-blade dynamic pressure increase" and "retreating-blade deficit").
- **Setting:** none (prose)
- **Current:** <td>Advancing-blade dynamic pressure increase exceeds retreating-blade deficit at fixed collective</td>
- **Proposed:** `<td>The advancing-blade dynamic pressure increase exceeds the retreating-blade deficit at constant collective</td>`

### ¶5 "At forward advance ($\mu_x = 0.3$),..."
- **Rules broken:** G9 ("introducing", "requiring" are "-ing" verb forms), G2 (final clause carries two new facts).
- **Setting:** none (prose)
- **Current:** […] Over the inboard retreating sector ($r/R < \mu_x$), reverse flow develops ($U_T < 0$, …Section 8.4</a>), introducing non-uniform induced inflow and requiring dynamic under-relaxation (…Section 9.5.3</a>).</p>
- **Proposed:** `<p>At forward advance ($\mu_x = 0.3$), the tangential velocity $U_T(r,\psi) = \Omega r + V_x\sin\psi$ generates a dynamic pressure asymmetry between the advancing blade ($\psi = 90^\circ$) and the retreating blade ($\psi = 270^\circ$). Over the inboard retreating sector ($r/R < \mu_x$), reverse flow develops ($U_T < 0$, <a class="xref" href="#cap-3-4" title="8.4 Reverse flow">Section 8.4</a>). The reverse flow introduces a non-uniform induced inflow and requires dynamic under-relaxation (<a class="xref" href="#cap-4-5-3" title="9.5.3 Relaxation">Section 9.5.3</a>).</p>`

### ¶6 "Comparing hover and forward flight..."
- **Rules broken:** G26 ("advancing/retreating dynamic pressure differentials" joining slash in prose).
- **Setting:** none (prose)
- **Current:** <p>Comparing hover and forward flight illustrates the transition from axisymmetric flow to azimuthal asymmetry. In forward flight, in-plane hub forces ($C_H, C_Y$) and tilting moments emerge directly from advancing/retreating dynamic pressure differentials, retreating-blade reverse flow, and non-uniform induced inflow.</p>
- **Proposed:** `<p>Comparing hover and forward flight illustrates the transition from axisymmetric flow to azimuthal asymmetry. In forward flight, the in-plane hub forces ($C_H, C_Y$) and the tilting moments emerge directly from the dynamic pressure differential between the advancing and the retreating blade, from the retreating-blade reverse flow, and from the non-uniform induced inflow.</p>`

## Structural defects (appendix items)
- Lines 2933–2951: duplicated content. The airfoil-polar paragraph, the thin-airfoil relation with its equation, the elemental-load equation and the "where ρ is air density…" paragraph appear twice: once inside §5.6.1 (lines 2934–2950) and again, nearly verbatim, as §5.6.2 (lines 2959–2987). One of the two copies should be removed. The stray equation `$$C_l=f(\alpha)\,,\qquad C_d=f(C_l^2)$$` (line 2951) sits orphaned after a completed paragraph with no sentence introducing it. Lines 2953–2955 contain empty paragraphs/whitespace.
- Line 2951: the equation block is not referenced by any prose (rule 2 of the chapter structure: sections must be self-contained; an equation with no lead-in sentence).
- Line 3445: table value cell uses `$\sim10^{-19}$`. The tilde here is math notation inside `$…$`, so it is exempt from G25, but the same value appears as `$\sim0$` in the second table (lines 3499, 3505) for a different quantity class ("exactly ~0" versus "machine-epsilon noise"); consider aligning the notation.
- Line 3393: `RPM$=1200$` mixes the RPM abbreviation with math mode while the rest of the chapter uses $n$ or $\Omega$; not a writing-rules violation, but a notation inconsistency this chapter otherwise avoids.
- Otherwise none: heading numbering, anchor/xref targets and chapter order in lines 2537–3531 are internally consistent.

---

# Block D: chapters 6–7 (lines 3532–4248)

Review basis: `SKILL.md` read in full; G1–G32, P1–P5, D1–D3 checked sentence by sentence. Intro/overview paragraphs are descriptive; the "GUI / .bemt / CLI" and "what to set" blocks are procedural where they issue commands. The fixed per-field pattern (physics → equation → options → interfaces) was not flagged, per the brief.

## Section 6 — Project (anchor: cap-projeto)
- Paragraphs reviewed: 23 | OK: 15 | Proposals: 8

### ¶1 "<figcaption 3543> The Project tab. The projects already..."
- **Rules broken:** G3 (the actor, the GUI, is known; "are listed" is passive), G24 ("with the active project and its folder reported underneath" reads ambiguously: location or accompanying information).
- **Setting:** none (prose)
- **Current:** The Project tab. The projects already on disk are listed on the left. The operation mode, the name and the create, open and save actions are on the right, with the active project and its folder reported underneath.
- **Proposed:** The Project tab. The list on the left shows the projects already on disk. The operation mode, the name and the create, open and save actions are on the right. The line underneath reports the active project and its folder.

### ¶2 (3575) "Because the shaft direction differs..."
- **Rules broken:** G6/G2 ("The letters cannot be assumed." drops the complement and leaves the claim incomplete).
- **Setting:** GUI: mode selector
- **Current:** Because the shaft direction differs, the same letter names different components in the two modes. For a rotor, $x$ lies in the disk plane and $z$ runs along the shaft. For a propeller the two are exchanged. This is the single most common source of a wrong propeller result: entering the airspeed in the field that means cross-flow. The window relabels both flow rows when the mode is switched, so the labels can be trusted. The letters cannot be assumed.
- **Proposed:** Because the shaft direction differs, the same letter names different components in the two modes. For a rotor, $x$ lies in the disk plane and $z$ runs along the shaft. For a propeller the two are exchanged. This is the single most common source of a wrong propeller result: entering the airspeed in the field that means cross-flow. The window relabels both flow rows when the mode is switched, so the labels can be trusted. The letters alone cannot be trusted to carry the same meaning.

### ¶3 (3581) "Configuration and limitation. Choose the mode..."
- **Rules broken:** G22 (one sentence of about 35 words chaining four clauses), G9 ("Switching mode" used as a verb form, not as a technical noun).
- **Setting:** GUI: mode selector
- **Current:** **Configuration and limitation.** Choose the mode before building the case. Switching mode on a project that already has saved conditions does not convert them: the stored numbers stay where they are and are reinterpreted under the new convention, which is almost never what is wanted. The mode also selects which coefficients are reported, since a propeller is judged by propulsive efficiency and a rotor by figure of merit.
- **Proposed:** **Configuration and limitation.** Choose the mode before building the case. A mode change on a project that already has saved conditions does not convert the conditions. The stored numbers stay where they are and are interpreted again under the new convention, which is almost never what is wanted. The mode also selects which coefficients are reported, since a propeller is judged by propulsive efficiency and a rotor by figure of merit.

### ¶4 (3592) ".bemt: the key is_propeller..."
- **Rules broken:** G18 ("changing it" — antecedent could be the mode or the letter assignment), G22 (last sentence about 30 words).
- **Setting:** .bemt key is_propeller in config.bemt
- **Current:** <span class="bemt">.bemt</span>: the key `is_propeller` in `config.bemt`, a switch, default `false` for a rotor. It sits with the solver settings rather than with the project name because the engine reads it. It also decides which letters are written into `saved_cases.bemt` and `batches.bemt`, so changing it by hand without rewriting those files leaves them stating the wrong components.
- **Proposed:** <span class="bemt">.bemt</span>: the key `is_propeller` in `config.bemt`, a switch, default `false` for a rotor. The key sits with the solver settings rather than with the project name because the engine reads it. The mode also decides which letters are written into `saved_cases.bemt` and `batches.bemt`. A hand edit of the key without a matching edit of those files leaves them stating the wrong components.

### ¶5 (3607) "Configuration and limitation. Use characters..."
- **Rules broken:** G2 (one sentence holds an instruction and its consequence); P1-adjacent merge.
- **Setting:** GUI: Save As / project name
- **Current:** **Configuration and limitation.** Use characters that are valid in a folder name. Renaming a project after it exists changes the stored name but not the folder it already lives in. To move it, save it under a new name and the folder follows.
- **Proposed:** **Configuration and limitation.** Use characters that are valid in a folder name. Renaming a project after it exists changes the stored name but not the folder it already lives in. To move the project, save it under a new name. The folder then follows.

### ¶6 (3623) "Definition and file representation. A project is a folder..."
- **Rules broken:** G22 (the sentence on creation runs about 35 words and chains three claims).
- **Setting:** none (prose)
- **Current:** **Definition and file representation.** A project is a folder, not a single file, and these three actions manage it. Creating one writes a folder of defaults that is immediately valid: it describes a plausible rotor and can be run without editing anything, which makes it a working starting point rather than an empty shell. Opening reads such a folder back. Saving writes the current state over it.
- **Proposed:** **Definition and file representation.** A project is a folder, not a single file, and these three actions manage it. Creating one writes a folder of defaults that is immediately valid. The default project describes a plausible rotor and runs without any edit, so it is a working starting point rather than an empty shell. Opening reads such a folder back. Saving writes the current state over it.

### ¶7 (3636) "GUI: New Project, Open from another folder..."
- **Rules broken:** G1 ("what you think it is" is conversational), G18 (final "it" has two candidate antecedents: the project and the GUI), G32 ("the quickest way" is an unmeasured superlative).
- **Setting:** GUI: New Project, Open from another folder, Save
- **Current:** <span class="gui">GUI</span>: *New Project*, *Open from another folder* and *Save*, with the *Existing Projects* list and its *Refresh List* button on the left. A project in the list opens on a double click. The line below the buttons reports which project is active and the folder it came from, which is the quickest way to confirm that the GUI is editing what you think it is.
- **Proposed:** <span class="gui">GUI</span>: *New Project*, *Open from another folder* and *Save*, with the *Existing Projects* list and its *Refresh List* button on the left. A project in the list opens on a double click. The line below the buttons reports the active project and its folder. Use this line to confirm which project the <span class="gui">GUI</span> edits.

### ¶8 (3651) "CLI: --new PATH creates a project..."
- **Rules broken:** G1 ("That last one" is conversational and deictic).
- **Setting:** CLI: --new, --project, --save-as
- **Current:** <span class="cli">CLI</span>: `--new PATH` creates a project, `--project PATH` opens one for the run, and `--save-as PATH` writes the project, including anything changed by flags in that same command, to a new folder. That last one is how a configuration explored from the command line becomes a project the <span class="gui">GUI</span> can open.
- **Proposed:** <span class="cli">CLI</span>: `--new PATH` creates a project, `--project PATH` opens one for the run, and `--save-as PATH` writes the project, including anything changed by flags in that same command, to a new folder. `--save-as` is the way a configuration explored from the command line becomes a project the <span class="gui">GUI</span> can open.

## Section 7 — Geometry (anchor: sec-5-geometry)
- Paragraphs reviewed: 105 | OK: 77 | Proposals: 28

### ¶1 (3663) "The Geometry tab describes the blade..."
- **Rules broken:** G8 ("typed in" is a phrasal verb), G22 (the final sentence runs about 35 words across a colon).
- **Setting:** none (prose)
- **Current:** The Geometry tab describes the blade. Two numbers apply to the rotor as a whole, the number of blades and the radius, and the rest of the blade is a table giving the chord and the twist at a series of radial stations. Whatever produced that table, the solver reads only the table: a blade generated from a preset and a blade typed in cell by cell are the same object once they are on screen.
- **Proposed:** The Geometry tab describes the blade. Two numbers apply to the rotor as a whole: the number of blades and the radius. The rest of the blade is a table that gives the chord and the twist at a series of radial stations. The solver reads only the table, independently of what produced it. A blade generated from a preset and a blade entered cell by cell are the same object once they are on screen.

### ¶2 (3694, order-of-use li1) "Set the number of blades and the radius..."
- **Rules broken:** G4 ("has been filled" is a compound passive tense).
- **Setting:** GUI: Geometry tab, number of blades and radius fields
- **Current:** Set the **number of blades** and the **radius**. They apply to the whole rotor and can be changed at any time, including after the table has been filled.
- **Proposed:** Set the **number of blades** and the **radius**. They apply to the whole rotor and can be changed at any time, including after the table is filled.

### ¶3 (3700, order-of-use li4) "Save when the blade is right..."
- **Rules broken:** G18 ("already reflects it" — the edit or the project?), G9 ("Saving is what writes it to disk" uses "-ing" as a verb form).
- **Setting:** GUI: Save and Restore buttons
- **Current:** **Save** when the blade is right. Every edit is already in the project held in memory and the preview already reflects it. Saving is what writes it to disk. **Restore** reloads the last saved version and discards the edits since.
- **Proposed:** **Save** when the blade is right. Every edit is already in the project held in memory, and the preview already shows that edit. **Save** writes the project to disk. **Restore** reloads the last saved version and discards the edits since.

### ¶4 (3708) "The physics. Number of blades and rotor radius..."
- **Rules broken:** G22 (the last sentence runs about 40 words and stacks four consequences).
- **Setting:** none (prose)
- **Current:** **The physics.** Number of blades and rotor radius set the scale of the whole problem. The radius fixes the disk area the rotor works on and, together with the rotational speed, the tip speed that every velocity in the solution is measured against. The number of blades fixes how much blade area is available to carry the load: for a given total thrust, more blades means less load on each, a smaller induced velocity behind each one and a weaker tip vortex, at the cost of more profile drag and more interference between blades.
- **Proposed:** **The physics.** Number of blades and rotor radius set the scale of the whole problem. The radius fixes the disk area the rotor works on and, together with the rotational speed, the tip speed that every velocity in the solution is measured against. The number of blades fixes how much blade area is available to carry the load. For a given total thrust, more blades means less load on each blade, a smaller induced velocity behind each blade, and a weaker tip vortex. The cost is more profile drag and more interference between blades.

### ¶5 (3723) "Configuration and valid range. Blade count is an integer..."
- **Rules broken:** G7 ("physical blade chord dimensions" stacks four nouns; "relative planform geometry" is borderline but passes).
- **Setting:** none (prose)
- **Current:** **Configuration and valid range.** Blade count is an integer ($N_b \ge 2$), and radius is specified in meters ($R > 0$). Both represent geometric design constants. Because chord distributions are stored non-dimensionally as $c/R$, modifying rotor radius proportionally scales physical blade chord dimensions without altering relative planform geometry.
- **Proposed:** **Configuration and valid range.** Blade count is an integer ($N_b \ge 2$), and radius is specified in meters ($R > 0$). Both represent geometric design constants. Because chord distributions are stored non-dimensionally as $c/R$, a change of rotor radius scales every physical chord in proportion, without altering the relative planform geometry.

### ¶6 (3731) ".bemt: the keys n_blades... in metres..."
- **Rules broken:** G31 ("metres" is British spelling; the same chapter writes "meters" at line 3725).
- **Setting:** .bemt keys n_blades and radius_m in geom.bemt
- **Current:** <span class="bemt">.bemt</span>: the keys `n_blades`, an integer defaulting to $2$, and `radius_m`, in metres, defaulting to $1.0$, both in `geom.bemt`.
- **Proposed:** <span class="bemt">.bemt</span>: the keys `n_blades`, an integer defaulting to $2$, and `radius_m`, in meters, defaulting to $1.0$, both in `geom.bemt`.

### ¶7 (3742–3752) "The physics. Up to here the blade has been fixed..."
- **Rules broken:** G4 ("has been fixed" compound tense), G15 (two "&mdash;" joins: "stays rigid — it does not bend — and the response carries no transient"), G14 (semicolon: "stays steady; only the motion adds terms").
- **Setting:** none (prose)
- **Current:** **The physics.** Up to here the blade has been fixed to the hub: it rotates about the shaft but cannot bend upwards or swing backwards. A real blade is hinged or flexible enough to move. This block gives the rigid blade two rigid-body freedoms, solved as one periodic response around the azimuth: flapping, an out-of-plane rotation $\beta(\psi)$ about a hinge at offset $e$, and lead-lag, an in-plane rotation $\zeta(\psi)$ at the same offset. The blade itself stays rigid &mdash; it does not bend &mdash; and the response carries no transient: each revolution repeats the previous one. The aerodynamics of one station stays steady; only the motion adds terms to the local flow,
- **Proposed:** **The physics.** So far the blade was fixed to the hub: it rotates about the shaft but cannot bend upwards or swing backwards. A real blade is hinged or flexible enough to move. This block gives the rigid blade two rigid-body freedoms, solved as one periodic response around the azimuth: flapping, an out-of-plane rotation $\beta(\psi)$ about a hinge at offset $e$, and lead-lag, an in-plane rotation $\zeta(\psi)$ at the same offset. The blade itself stays rigid and does not bend, and the response carries no transient, so each revolution repeats the previous one. The aerodynamics of one station stays steady. Only the motion adds terms to the local flow,

### ¶8 (3759–3775) "where M_β(ψ) is the moment of the normal force..."
- **Rules broken:** G14 (semicolon after "algebraic per harmonic"), G15 ("undefined &mdash; this is exactly"), D3 (the paragraph holds 8 sentences).
- **Setting:** none (prose)
- **Current:** where $M_\beta(\psi)$ is the moment of the normal force about the hinge, $I_\beta$ the flap inertia of one blade, and $d_\beta=...$ the aerodynamic damping that the blade's own flapping rate produces. The response is written as a truncated Fourier series, $\beta(\psi)=\beta_0+\sum_n[...]$, which turns the equation algebraic per harmonic; because a flapping blade changes its own loading, the solver exchanges the inflow solution with the blade solution until both stop moving. The lag freedom follows the same scheme without the leading $1$: $\nu_\zeta^{2}=...$. Two limits are worth remembering. First, the resonance limit: when $|\nu_\beta^2-n^2|$ falls below $10^{-3}$ for any kept harmonic $n$, the response of that harmonic is undefined &mdash; this is exactly the plain articulated rotor, whose $\nu_\beta$ equals $1$, and the software rejects it by name instead of returning a large number. Second, the sign convention of every reported angle: $\beta(\psi)=\beta_0+\beta_{1c}\cos\psi+\beta_{1s}\sin\psi$ with positive up, and each tip-path-plane tilt is the negative of its first harmonic. The coning angle raises thrust slightly in hover and tilts the disk in edgewise flight; the hinge also opens a structural path through which part of the load reaches the hub as a moment.
- **Proposed:** where $M_\beta(\psi)$ is the moment of the normal force about the hinge, $I_\beta$ the flap inertia of one blade, and $d_\beta=\gamma\left(\tfrac{1}{8}-\tfrac{e}{3}+\tfrac{e^2}{4}\right)$ the aerodynamic damping that the blade's own flapping rate produces. The response is written as a truncated Fourier series, $\beta(\psi)=\beta_0+\sum_n[\beta_{nc}\cos n\psi+\beta_{ns}\sin n\psi]$, which turns the equation algebraic per harmonic. Because a flapping blade changes its own loading, the solver exchanges the inflow solution with the blade solution until both stop moving. The lag freedom follows the same scheme without the leading $1$: $\nu_\zeta^{2}=\tfrac{3}{2}\,e/(1-e)+K_\zeta/(I_\zeta\Omega^{2})$.​</p><p>Two limits are worth remembering. First, the resonance limit: when $|\nu_\beta^2-n^2|$ falls below $10^{-3}$ for any kept harmonic $n$, the response of that harmonic is undefined. This is exactly the plain articulated rotor, whose $\nu_\beta$ equals $1$, and the software rejects it by name instead of returning a large number. Second, the sign convention of every reported angle: $\beta(\psi)=\beta_0+\beta_{1c}\cos\psi+\beta_{1s}\sin\psi$ with positive up, and each tip-path-plane tilt is the negative of its first harmonic. The coning angle raises thrust slightly in hover and tilts the disk in edgewise flight. The hinge also opens a structural path through which part of the load reaches the hub as a moment.

### ¶9 (3777) "Configuration and valid range. The hinge offset runs from..."
- **Rules broken:** G14 (semicolon: "two harmonics; more cost one solve each").
- **Setting:** none (prose)
- **Current:** **Configuration and valid range.** The hinge offset runs from $0$ to $0.3$; typical articulated rotors sit near $0.03$ to $0.08$. Lock numbers between $5$ and $12$ cover most rotors. Keep at least two harmonics; more cost one solve each per outer iteration. The defaults keep the blade fully rigid, which reproduces every result computed before this block existed.
- **Proposed:** **Configuration and valid range.** The hinge offset runs from $0$ to $0.3$. Typical articulated rotors sit near $0.03$ to $0.08$. Lock numbers between $5$ and $12$ cover most rotors. Keep at least two harmonics. Each additional harmonic costs one more solve per outer iteration. The defaults keep the blade fully rigid, which reproduces every result computed before this block existed.

### ¶10 (3811) "The physics. The hinge offset e is the distance..."
- **Rules broken:** G1 ("EFFECTIVE" in all caps is emphatic, not formal; the document marks emphasis with italics elsewhere).
- **Setting:** none (prose)
- **Current:** **The physics.** The hinge offset $e$ is the distance from the shaft to the flap hinge, as a fraction of the radius. It is an EFFECTIVE offset, not necessarily a real mechanical hinge. The blade is treated as rigid, and this one number carries the whole root restraint.
- **Proposed:** **The physics.** The hinge offset $e$ is the distance from the shaft to the flap hinge, as a fraction of the radius. It is an <i>effective</i> offset, not necessarily a real mechanical hinge. The blade is treated as rigid, and this one number carries the whole root restraint.

### ¶11 (3835) "The physics. The flap spring is a torsional stiffness..."
- **Rules broken:** G31 ("newton metres" is British spelling).
- **Setting:** none (prose)
- **Current:** **The physics.** The flap spring is a torsional stiffness $K_\beta$ at the root, in newton metres per radian. It represents the elastic restraint of a hub that does not hinge freely. The spring adds the term $K_\beta/(I_\beta\Omega^2)$ to the square of the flap frequency ratio.
- **Proposed:** **The physics.** The flap spring is a torsional stiffness $K_\beta$ at the root, in newton meters per radian. It represents the elastic restraint of a hub that does not hinge freely. The spring adds the term $K_\beta/(I_\beta\Omega^2)$ to the square of the flap frequency ratio.

### ¶12 (3874, list item) "Flap inertia: enter I_β in kilogram metres squared..."
- **Rules broken:** G31 ("kilogram metres" is British spelling).
- **Setting:** GUI: Geometry tab, flap inertia field
- **Current:** **Flap inertia**: enter $I_\beta$ in kilogram metres squared. Use this source when a structural model or a measurement gives the inertia itself.
- **Proposed:** **Flap inertia**: enter $I_\beta$ in kilogram meters squared. Use this source when a structural model or a measurement gives the inertia itself.

### ¶13 (3925) "What to set. Keep 2 unless the azimuthal loading..."
- **Rules broken:** P1 (one sentence holds two sequential instructions: raise, then confirm).
- **Setting:** GUI: Geometry tab, harmonics field
- **Current:** **What to set.** Keep $2$ unless the azimuthal loading is unusually sharp. Raise it to $3$ or $4$ for a strongly skewed wake at high advance ratio, and confirm that the answer stops changing. Every kept harmonic must sit off its own resonance, because the balance divides by $\nu_\beta^2-n^2$ for the $n$-th term. The software checks all of them, not the first alone, and refuses a combination that resonates.
- **Proposed:** **What to set.** Keep $2$ unless the azimuthal loading is unusually sharp. For a strongly skewed wake at high advance ratio, raise it to $3$ or $4$. Then confirm that the answer stops changing. Every kept harmonic must sit off its own resonance, because the balance divides by $\nu_\beta^2-n^2$ for the $n$-th term. The software checks all of them, not the first alone, and refuses a combination that resonates.

### ¶14 (3944) "What to set. Three fields govern that exchange:"
- **Rules broken:** D3/G2 (the lead sentence repeats, nearly verbatim, the closing sentence of the previous paragraph, "these three fields govern that exchange"; the topic is stated twice).
- **Setting:** GUI: Geometry tab, convergence controls
- **Current:** **What to set.** Three fields govern that exchange:
- **Proposed:** **What to set.** The three controls are:

### ¶15 (3956) "How to read a run. The achieved iteration count..."
- **Rules broken:** G1 ("OSCILLATES" in all caps).
- **Setting:** none (prose)
- **Current:** **How to read a run.** The achieved iteration count and the final residual travel with the results, and the Results tab draws the trace. A residual that never settles needs more iterations or a looser tolerance. A trace that OSCILLATES instead of falling needs a lower relaxation, because oscillation is the signature of a step that is too large, not of a limit that is too low.
- **Proposed:** **How to read a run.** The achieved iteration count and the final residual travel with the results, and the Results tab draws the trace. A residual that never settles needs more iterations or a looser tolerance. A trace that <i>oscillates</i> instead of falling needs a lower relaxation, because oscillation is the signature of a step that is too large, not of a limit that is too low.

### ¶16 (3973) "Toggling lag_enabled adds the in-plane freedom..."
- **Rules broken:** G15 ("&mdash;" join), G14 (semicolon before "leaving it off"), G22/G2 (several sentences exceed 30 words and chain multiple fields and effects), G9 ("Toggling" as a verb form), P2-adjacent (descriptive where the pattern calls for field-by-field prose, sentence on `lag_feeds_back` merges toggling on and off in one sentence).
- **Setting:** .bemt keys lag_enabled, lag_spring_nm_per_rad, lag_damping_nms_per_rad, lag_inertia_kg_m2 in geom.bemt
- **Current:** Toggling `lag_enabled` adds the in-plane freedom at the same offset. Its equation mirrors the flap one without thrust restoring: nothing in steady flight pulls the blade back against lead-lag, so the leading $1$ disappears from the frequency ratio and the freedom needs either an offset or a spring &mdash; with neither, the ratio is zero and the response is undefined. `lag_spring_nm_per_rad` ($K_\zeta$) supplies restoring stiffness, `lag_damping_nms_per_rad` ($C_\zeta$) plays the role a mechanical damper plays on real rotors and couples the sine and cosine parts of each harmonic into a small two-by-two solve, and `lag_inertia_kg_m2` ($I_\zeta$) normalizes the moment. When `lag_feeds_back` is set, the lag rate modifies the tangential speed of each element, closing the loop between lag motion and aerodynamics; leaving it off turns the lag into a diagnostic that does not act back on the loads.
- **Proposed:** The key `lag_enabled` adds the in-plane freedom at the same offset. Its equation mirrors the flap equation without thrust restoring: nothing in steady flight pulls the blade back against lead-lag, so the leading $1$ disappears from the frequency ratio. The freedom then needs either an offset or a spring. With neither, the ratio is zero and the response is undefined. The key `lag_spring_nm_per_rad` ($K_\zeta$) supplies restoring stiffness. The key `lag_damping_nms_per_rad` ($C_\zeta$) plays the role a mechanical damper plays on real rotors and couples the sine and cosine parts of each harmonic into a small two-by-two solve. The key `lag_inertia_kg_m2` ($I_\zeta$) normalizes the moment. When `lag_feeds_back` is set, the lag rate modifies the tangential speed of each element and closes the loop between lag motion and aerodynamics. When `lag_feeds_back` is clear, the lag is a diagnostic and does not act back on the loads.

### ¶17 (3999) "The physics. The blade does not begin at the axis..."
- **Rules broken:** G3 ("is occupied by" — the actors, hub, grips and bearings, are named in the same sentence), G22 (the closing sentence runs about 30 words with a colon and two chained subordinate clauses).
- **Setting:** none (prose)
- **Current:** **The physics.** The blade does not begin at the axis. The innermost part of the span is occupied by the hub, the grips and the pitch bearings, which carry no aerofoil section and produce no useful lift. The root cutout is where the lifting blade starts, expressed as a fraction of the radius, and the region inside it is excluded from the integration of thrust and torque. Ignoring it overestimates thrust, but only slightly: the inboard stations move slowly, so they contribute little, which is also why the exact value is not critical.
- **Proposed:** **The physics.** The blade does not begin at the axis. The hub, the grips and the pitch bearings occupy the innermost part of the span, and they carry no aerofoil section and produce no useful lift. The root cutout is where the lifting blade starts, expressed as a fraction of the radius, and the region inside it is excluded from the integration of thrust and torque. Ignoring the cutout overestimates thrust, but only slightly. The inboard stations move slowly, so they contribute little. This is also why the exact value is not critical.

### ¶18 (4009) "and the same lower limit applies to torque and power..."
- **Rules broken:** G31 ("per cent" is British spelling; American form is "percent").
- **Setting:** none (prose)
- **Current:** and the same lower limit applies to torque and power. Because the elemental thrust grows roughly with $r^{2}$, moving the cutout from $0$ to $0.15$ removes only a few per cent of the thrust.
- **Proposed:** and the same lower limit applies to torque and power. Because the elemental thrust grows roughly with $r^{2}$, moving the cutout from $0$ to $0.15$ removes only a few percent of the thrust.

### ¶19 (4012) "Configuration and valid range. A fraction of the radius between..."
- **Rules broken:** G6 (the first sentence has no verb: "A fraction of the radius between 0 and 1, in practice between 0.10 and 0.25...").
- **Setting:** none (prose)
- **Current:** **Configuration and valid range.** A fraction of the radius between $0$ and $1$, in practice between $0.10$ and $0.25$ for a helicopter rotor and often larger for a propeller with a substantial spinner. The default is $0.15$. The value must not lie above the first station of the radial table, since a cutout past that station leaves it and any station before it outside the integration.
- **Proposed:** **Configuration and valid range.** The cutout is a fraction of the radius between $0$ and $1$, in practice between $0.10$ and $0.25$ for a helicopter rotor and often larger for a propeller with a substantial spinner. The default is $0.15$. The value must not lie above the first station of the radial table, since a cutout past that station leaves that station and any station before it outside the integration.

### ¶20 (4017) "Where the table begins. The three parametric generators..."
- **Rules broken:** G31 ("fifteen per cent").
- **Setting:** none (prose)
- **Current:** **Where the table begins.** The three parametric generators place the first radial station of the table exactly at the cutout: the stations run from $r_{cut}$ to $1.0$ in equal steps. No station exists inside the cutout and none is discarded afterwards, so the table and the integration limit agree by construction, and the engine receives the same lower bound. A table entered as custom geometry takes its cutout from its own innermost station. Resampling a table keeps its current innermost station as the new first one. The elliptic generator scales its chord so that the value at that first station equals the requested maximum chord, and it floors the tip chord at fifteen per cent of that maximum so the shape never closes.
- **Proposed:** **Where the table begins.** The three parametric generators place the first radial station of the table exactly at the cutout: the stations run from $r_{cut}$ to $1.0$ in equal steps. No station exists inside the cutout and none is discarded afterwards, so the table and the integration limit agree by construction, and the engine receives the same lower bound. A table entered as custom geometry takes its cutout from its own innermost station. Resampling a table keeps its current innermost station as the new first one. The elliptic generator scales its chord so that the value at that first station equals the requested maximum chord, and it floors the tip chord at fifteen percent of that maximum so the shape never closes.

### ¶21 (4036) "The physics. The table is the blade. Each row gives..."
- **Rules broken:** G8 ("evens this out" is a phrasal verb), G19 ("this" has several candidate antecedents: the uneven loading or the angle of attack).
- **Setting:** none (prose)
- **Current:** [...] Twist that decreases towards the tip is what evens this out.
- **Proposed:** **The physics.** The table is the blade. Each row gives, at one radial station, the chord and the twist of the section there. Chord decides how much area that station has to generate lift with, and therefore the local solidity. Twist decides the angle at which the section meets the flow, and it matters because the inflow angle varies strongly along the span: a section near the root sees a much steeper approach than one near the tip, so a blade with no twist works at a very uneven angle of attack and stalls inboard while the tip is still lightly loaded. Twist that decreases towards the tip makes the angle of attack more uniform along the span.

### ¶22 (4052) "Configuration and valid range. Radial positions run from..."
- **Rules broken:** G31 ("towards" is British spelling; American form is "toward").
- **Setting:** none (prose)
- **Current:** **Configuration and valid range.** Radial positions run from the root cutout to $1.0$ and must increase down the column. Chord is normalized, so a chord of $0.08$ on a radius of $1.25$ m is $0.1$ m. Twist is in degrees and is normally positive at the root and falling towards the tip. A blade whose twist rises outboard is almost always a sign of a sign convention applied backwards. Ten to twenty stations describe most blades adequately, with more where the planform changes quickly.
- **Proposed:** **Configuration and valid range.** Radial positions run from the root cutout to $1.0$ and must increase down the column. Chord is normalized, so a chord of $0.08$ on a radius of $1.25$ m is $0.1$ m. Twist is in degrees and is normally positive at the root and falling toward the tip. A blade whose twist rises outboard is almost always a sign of a sign convention applied backwards. Ten to twenty stations describe most blades adequately, with more where the planform changes quickly.

### ¶23 (4074) "The physics. Rather than typing a table..."
- **Rules broken:** G31 ("narrows towards the tip").
- **Setting:** none (prose)
- **Current:** **The physics.** Rather than typing a table, a blade can be generated from a planform description. The three presets are the three classical planforms, and they differ in how the chord is distributed along the span. A rectangular blade has constant chord and is the simplest to build. A tapered blade narrows towards the tip, which moves area inboard and reduces the tip loading. An elliptic blade follows the distribution that minimizes induced drag for a given lift, and serves as the ideal against which the other two are judged. All three take a linear twist between a root value and a tip value.
- **Proposed:** **The physics.** Rather than typing a table, a blade can be generated from a planform description. The three presets are the three classical planforms, and they differ in how the chord is distributed along the span. A rectangular blade has constant chord and is the simplest to build. A tapered blade narrows toward the tip, which moves area inboard and reduces the tip loading. An elliptic blade follows the distribution that minimizes induced drag for a given lift, and serves as the ideal against which the other two are judged. All three take a linear twist between a root value and a tip value.

### ¶24 (4152) "The root cutout. The field labeled Root cutout (r/R)..."
- **Rules broken:** G29 plus structural rule 11 (the reference "7.2" is bare text, not a link) and factual defect (root cutout is documented in Section 7.3, not 7.2).
- **Setting:** GUI: Root cutout (r/R) field in the Generate Table dialog
- **Current:** **The root cutout.** The field labeled *Root cutout (r/R)* sets where the generated table starts: no station is produced inside it, because there is no lifting blade there. It is the same quantity documented in 7.2, which gives its key, its range and its effect on the integration, and this dialog is the only place the window offers a control for it.
- **Proposed:** **The root cutout.** The field labeled *Root cutout (r/R)* sets where the generated table starts: no station is produced inside it, because there is no lifting blade there. It is the same quantity documented in <a class="xref" href="#cap-2-5" title="7.3 Root cutout">Section 7.3</a>, which gives its key, its range and its effect on the integration, and this dialog is the only place the window offers a control for it.

### ¶25 (4189) "The same dialog can size the chord from a target solidity..."
- **Rules broken:** G22 (the final sentence runs about 35 words with three parallel gerund clauses), G9 ("scaling the constant chord..." used as verb forms, not technical nouns).
- **Setting:** GUI: solidity and aspect ratio fields in the Generate Table dialog
- **Current:** With the number of blades fixed, these two are not independent: raising the solidity necessarily lowers the aspect ratio. The dialog keeps them consistent while it scales the chord, scaling the constant chord of a rectangular blade, both chords of a tapered blade so that its taper ratio is preserved, and the maximum chord of an elliptic one. Root cutout and twist are unaffected.
- **Proposed:** With the number of blades fixed, these two are not independent: an increase of the solidity necessarily lowers the aspect ratio. The dialog keeps them consistent while it scales the chord. For a rectangular blade it scales the constant chord. For a tapered blade it scales both chords so that the taper ratio is preserved. For an elliptic blade it scales the maximum chord. Root cutout and twist are unaffected.

### ¶26 (4198) "A single source for both numbers. The dialog derives..."
- **Rules broken:** D3 (the paragraph holds 7 sentences).
- **Setting:** GUI: solidity and aspect ratio fields in the Generate Table dialog
- **Current:** **A single source for both numbers.** The dialog derives solidity and aspect ratio from one quantity: the planform area of one blade divided by $R^{2}$, integrated from the root cutout to the tip. For a rectangular planform this area is $c_{root}\,(1-r_{cut})$. For a tapered one it is $\tfrac{1}{2}(c_{root}+c_{tip})(1-r_{cut})$, which preserves the taper ratio when both chords are scaled together. For an elliptic one it is the exact integral of the rescaled $\sqrt{1-r^{2}}$ shape over the same span, using the same peak normalization as the generator. Solidity is $N_b$ times this area over $\pi R^{2}$, and the aspect ratio is its reciprocal. Editing either field solves this area for the chords. One consequence follows directly: moving the root cutout outward shortens the loaded span, so the same pair of chords gives a higher aspect ratio and a lower solidity.
- **Proposed:** **A single source for both numbers.** The dialog derives solidity and aspect ratio from one quantity: the planform area of one blade divided by $R^{2}$, integrated from the root cutout to the tip. For a rectangular planform this area is $c_{root}\,(1-r_{cut})$. For a tapered one it is $\tfrac{1}{2}(c_{root}+c_{tip})(1-r_{cut})$, which preserves the taper ratio when both chords are scaled together. For an elliptic one it is the exact integral of the rescaled $\sqrt{1-r^{2}}$ shape over the same span, using the same peak normalization as the generator. Solidity is $N_b$ times this area over $\pi R^{2}$, and the aspect ratio is its reciprocal. Editing either field solves this area for the chords.</p><p>One consequence follows directly. Moving the root cutout outward shortens the loaded span, so the same pair of chords gives a higher aspect ratio and a lower solidity.

### ¶27 (4221) "Configuration. Leave it empty when the blade uses..."
- **Rules broken:** P3 (the condition follows the command instead of preceding it).
- **Setting:** GUI: Geometry tab, section field
- **Current:** **Configuration.** Leave it empty when the blade uses a single section defined in the Airfoil tab, which is the common case. Set it when the geometry is meant to travel with a named section.
- **Proposed:** **Configuration.** When the blade uses a single section defined in the Airfoil tab, which is the common case, leave the field empty. When the geometry is meant to travel with a named section, set it.

### ¶28 (4235) "The panel on the right redraws whenever..."
- **Rules broken:** G32/G1 ("the quickest check" and "visible immediately" carry unmeasured superlatives in a conversational register).
- **Setting:** none (prose)
- **Current:** The panel on the right redraws whenever the geometry changes, and it is the quickest check that a table is what was intended. *Plan View* draws the planform of every blade in the disk, so an error in the chord column is visible immediately as a blade of the wrong shape. *Chord/Twist* plots the two distributions against the radius. A twist column entered with the wrong sign appears there as a line that slopes the wrong way. *Rotor 3D* shows the assembled rotor when the three-dimensional visualization package is installed, and is omitted when it is not.
- **Proposed:** The panel on the right redraws whenever the geometry changes, and it is the immediate check that a table is what was intended. *Plan View* draws the planform of every blade in the disk, so an error in the chord column appears as a blade of the wrong shape. *Chord/Twist* plots the two distributions against the radius. A twist column entered with the wrong sign appears there as a line that slopes the wrong way. *Rotor 3D* shows the assembled rotor when the three-dimensional visualization package is installed, and is omitted when it is not.

## Structural defects (appendix items)
- line 3687: bare section references "(7.4.1 and 7.4.2)" with no link, violating the documentation rule that every prose section reference is a linked `<a class="xref">`; also these anchor numbers do not match the actual subsection numbers of the Generate Table dialog (which the chapter introduces as 7.5.1 and 7.5.2 at lines 4132 and 4187).
- line 4154: cross-reference "documented in 7.2" points at the wrong target — root cutout is Section 7.3 (`cap-2-5`) — and carries no link.
- line 4171: cross-reference "the three radial-table lists in `geom.bemt` described in 7.3" points at the wrong target — the radial table is Section 7.4 (`cap-2-3`) — and carries no link.
- line 4036–4042 vs 4145–4150: the twist physics in 7.5.1 repeats the 7.4 twist paragraph almost word for word (including the same G8 "evens..."-class wording), duplicating content the per-chapter self-containment rule would currently allow but which also duplicates the defect flagged at ¶21; fix both copies in the same change if one is applied.
- No `--` or `~` appears in prose; all joining dashes found are `&mdash;` entities (flagged at lines 3747, 3768, 3976). No Latin abbreviations (e.g./i.e./etc.) found in the reviewed range. No British spellings other than those flagged (3532‑4248 occurrences: "metres" ×3, "towards" ×3, "per cent" ×2).

---

# Block E: chapter 8 (lines 4249–6208)

## Section 8 — Airfoil (anchor: sec-6-airfoil), organized by its subsections
- Paragraphs reviewed: 148 | OK: 78 | Proposals: 70

### ¶1 "Fields in this tab, in..." (L4258)
- **Rules broken:** G6 (telegraphic sentence, no verb)
- **Setting:** none (prose)
- **Current:** `<b>Fields in this tab, in the order they appear on screen</b> (37). The sections below are self-contained […]`
- **Proposed:** `<b>This tab has 37 fields, listed below in the order they appear on screen.</b> The sections below are self-contained and use the same explanations as the field Help in the window.`

### ¶2 "the file airfoil_sections.bemt, one entry per section..." (L4299)
- **Rules broken:** G24 ("With a single airfoil" reads as accompaniment, not condition)
- **Setting:** `.bemt` file `airfoil_sections.bemt`; key set under `airfoil.bemt`
- **Current:** `.bemt: the file <code>airfoil_sections.bemt</code>, one entry per section, when two or more sections are defined. With a single airfoil that file is empty or absent […]`
- **Proposed:** `<span class="bemt">.bemt</span>: the file <code>airfoil_sections.bemt</code>, one entry per section, when two or more sections are defined. When the blade uses a single airfoil, that file is empty or absent and the definition lives in <code>airfoil.bemt</code> alone.`

### ¶3 "loads a prepared set of sections..." (L4303)
- **Rules broken:** G3 (passive where the actor is known)
- **Setting:** CLI flag `--airfoil-sections-file PATH`
- **Current:** `CLI: --airfoil-sections-file PATH loads a prepared set of sections. […] A multi-section blade is built in the window and saved, or the file is written by hand.`
- **Proposed:** `<span class="cli">CLI</span>: <code>--airfoil-sections-file PATH</code> loads a prepared set of sections. There is no flag for editing one section at a time. Build a multi-section blade in the window and save it, or write the file by hand.`

### ¶4 "Uniform single-profile modeling is appropriate..." (L4328)
- **Rules broken:** G27 (a fact the reader needs hidden in a long parenthesis), G28 (ranges written with dashes: 18–24%, 8–12%)
- **Setting:** none (prose; section 8.1 scope guidance)
- **Current:** `However, full-scale rotorcraft and wind turbine blades incorporate spanwise aerodynamic tailoring (for example, thick 18&ndash;24% root sections […] transitioning to thin 8&ndash;12% transonic tip sections).`
- **Proposed:** `<b>Scope and modeling assumptions.</b> Uniform single-profile modeling is appropriate for constant-section blades, small-scale propellers, and idealized rotor studies. However, full-scale rotorcraft and wind turbine blades incorporate spanwise aerodynamic tailoring. A typical tailoring runs from thick root sections of 18 to 24 per cent thickness, which give the required structural depth, to thin tip sections of 8 to 12 per cent, which limit transonic drag. Enforcing a single profile throughout introduces systematic errors: applying the thick root profile at the tip overpredicts profile power due to high dynamic pressure, whereas applying the thin tip profile at the root underestimates low-Reynolds drag and delays root separation.`

### ¶5 "Move to multiple sections whenever thickness..." (L4336)
- **Rules broken:** G22 (first sentence exceeds 40 words, three conditions), G21 (three conditions in prose instead of a list)
- **Setting:** none (prose; guidance for adding radial sections)
- **Current:** `Move to multiple sections whenever thickness or camber actually varies along the blade, whenever the tip approaches drag divergence while the root sits at low Reynolds, or whenever the question being asked is <i>where</i> stall starts.`
- **Proposed:** `<b>The boundary.</b> Move to multiple sections when any of three conditions holds: thickness or camber varies along the blade, the tip approaches drag divergence while the root sits at low Reynolds number, or the question being asked is <i>where</i> stall starts. The answer to that question depends on the profile difference this mode cannot represent.`

### ¶6 "The behavior depends on how many sections..." (L4342)
- **Rules broken:** G24 ("with an extra field to get wrong" is ambiguous)
- **Setting:** GUI button `+ section`, Radial sections block, Airfoil tab
- **Current:** `[…] one section on its own would describe the same thing a single airfoil does, with an extra field to get wrong.`
- **Proposed:** `<b>What it does.</b> The behavior depends on how many sections already exist, because a multi-section blade needs at least two: one section on its own would describe the same thing a single airfoil does, and it would add a field that can be set wrongly.`

### ¶7 "From single-airfoil mode, the button turns..." (L4346)
- **Rules broken:** G22 (first sentence about 50 words)
- **Setting:** GUI button `+ section`, Radial sections block, Airfoil tab
- **Current:** `From <b>single-airfoil mode</b>, the button turns the current definition into <em>two</em> sections at once, one at $r/R=0.15$ named root and one at $r/R=1.0$ named tip, both carrying the airfoil that was on screen.`
- **Proposed:** `From <b>single-airfoil mode</b>, the button turns the current definition into <em>two</em> sections at once. One sits at $r/R=0.15$ and is named root, the other at $r/R=1.0$ and is named tip. Both carry the airfoil that was on screen. The blade is unchanged at that moment (two identical polars interpolate to themselves) and becomes a real multi-section blade as soon as one of the two sections is edited.`

### ¶8 "With two or more sections, the button copies..." (L4352)
- **Rules broken:** G24 (two uses of "with" where "when" is meant), G22 (first sentence about 45 words)
- **Setting:** GUI button `+ section`, Radial sections block, Airfoil tab
- **Current:** `With <b>two or more sections</b>, the button copies the section currently selected to a new radial position, chosen automatically at the midpoint of the largest gap between existing neighbors: with sections at $0.15$ and $1.0$, the next lands at $0.575$.`
- **Proposed:** `When <b>two or more sections</b> exist, the button copies the section currently selected to a new radial position. The new position is chosen automatically at the midpoint of the largest gap between existing neighbors: when sections sit at $0.15$ and $1.0$, the next section lands at $0.575$. The copy takes the original's name with a suffix, and its position can be moved afterwards.`

### ¶9 "Add sections where the profile actually..." (L4357)
- **Rules broken:** P1 (two sequential instructions merged in one sentence)
- **Setting:** GUI button `+ section`, Radial sections block, Airfoil tab
- **Current:** `Add sections where the profile actually changes, and edit the new one before running: an unedited copy adds mesh work and changes no result.`
- **Proposed:** `<b>Configuration.</b> Add sections where the profile actually changes. Edit the new section before running: an unedited copy adds mesh work and changes no result.`

### ¶10 "adding a section writes a new entry..." (L4363)
- **Rules broken:** G14 (semicolon joins two sentences)
- **Setting:** `.bemt` file `airfoil_sections.bemt`
- **Current:** `adding a section writes a new entry into <code>airfoil_sections.bemt</code>; the first use also moves the definition out of <code>airfoil.bemt</code> into two entries there.`
- **Proposed:** `<span class="bemt">.bemt</span>: adding a section writes a new entry into <code>airfoil_sections.bemt</code>. The first use also moves the definition out of <code>airfoil.bemt</code> into two entries there.`

### ¶11 "no flag. Sections are added in the window..." (L4368)
- **Rules broken:** G6 (telegraphic opening without a verb)
- **Setting:** CLI flag `--airfoil-sections-file PATH`
- **Current:** `CLI: no flag. Sections are added in the window or by editing the file, and loaded with <code>--airfoil-sections-file PATH</code>.`
- **Proposed:** `<span class="cli">CLI</span>: there is no flag for adding a section. Add sections in the window or by editing the file, and load them with <code>--airfoil-sections-file PATH</code>.`

### ¶12 "A real blade rarely uses one aerofoil..." (L4373)
- **Rules broken:** G31/G10 ("aerofoil" is British spelling and rotates the term against the rest of the document)
- **Setting:** GUI field `r/R of this section`, Radial sections block, Airfoil tab; `.bemt` key `r_norm`
- **Current:** `A real blade rarely uses one aerofoil from root to tip.`
- **Proposed:** `<b>The physics.</b> A real blade rarely uses one airfoil from root to tip. The inboard part carries the structure and needs a thick section. The tip needs a thin one, because that is where the relative velocity and the Mach number are highest and where thickness costs the most drag. Defining sections at several radii lets the blade change profile along the span, and the radial position states where each section applies.`

### ¶13 "The position is given as a fraction..." (L4379)
- **Rules broken:** G31/G10 ("aerofoil")
- **Setting:** GUI field `r/R of this section`; `.bemt` key `r_norm`
- **Current:** `[…] two sections are not merged into an intermediate aerofoil, their polars are mixed.`
- **Proposed:** `[…] The consequence worth knowing is that the blend is in the <em>coefficients</em>, not in the shapes: two sections are not merged into an intermediate airfoil, their polars are mixed.`

### ¶14 "Use a value between the root cutout..." (L4387)
- **Rules broken:** P1 ("Place…, and remember…" merges instruction and advisory), G15 (dashes set off "root, mid-span and tip")
- **Setting:** GUI field `r/R of this section`; `.bemt` key `r_norm`
- **Current:** `Place sections where the profile actually changes, and remember that the interpolation is linear […] Three sections &mdash; root, mid-span and tip &mdash; describe most real blades.`
- **Proposed:** `<b>Configuration and valid range.</b> Use a value between the root cutout and $1.0$. Place sections where the profile actually changes. Remember that the interpolation is linear, so a sharp change of profile needs two sections close together rather than one in the middle. Three sections (root, mid-span and tip) describe most real blades. The name beside each section is a label for your own use and is never read by the solver.`

### ¶15 "the list in the Radial Sections block..." (L4394)
- **Rules broken:** G9 ("-ing" word used as a verb subject: "Clicking a row stores")
- **Setting:** GUI field `r/R of this section`, Radial sections block, Airfoil tab
- **Current:** `Clicking a row stores what is on screen into the section being edited and loads the clicked one, so nothing is lost when moving between them.`
- **Proposed:** `<span class="gui">GUI</span>: the list in the <i>Radial Sections</i> block, with the field <i>r/R of this section</i> beneath it. A click on a row stores what is on screen into the section being edited and loads the clicked section, so nothing is lost when moving between sections. The preview follows.`

### ¶16 "Removing the second of two would leave..." (L4414)
- **Rules broken:** G6 (final fragment "only the statement that…" has no verb)
- **Setting:** GUI button `- section`, Radial sections block, Airfoil tab
- **Current:** `Nothing about the aerodynamic model is lost in that step: only the statement that it applied at one particular radius.`
- **Proposed:** `[…] Nothing about the aerodynamic model is lost in that step. The collapse removes only the statement that the airfoil applied at one particular radius.`

### ¶17 "no flag, for the same reason as 8.1.2." (L4429)
- **Rules broken:** G6 (telegraphic), G29 (abbreviated cross-reference "8.1.2" without "Section")
- **Setting:** CLI (no flag), section removal
- **Current:** `<span class="cli">CLI</span>: no flag, for the same reason as 8.1.2.`
- **Proposed:** `<span class="cli">CLI</span>: there is no flag for this, for the same reason as in section 8.1.2.`

### ¶18 "Everything from 8.2 to 8.9 belongs..." (L4432)
- **Rules broken:** G18 ("which is what a blade…wants" — vague "which"), G30 ("a blade…usually wants" gives the blade human intent), G29 (plain "8.3.3", "8.8")
- **Setting:** per-section scope of all Airfoil tab settings
- **Current:** `That includes the dynamic-stall switch of 8.3.3, so one section can have the lag model active while its neighbor does not, which is what a blade with a thick root and a thin tip usually wants.`
- **Proposed:** `Everything from 8.2 to 8.9 belongs to <b>one section</b> when two or more sections are defined. That includes the dynamic-stall switch of section 8.3.3, so one section can have the lag model active while its neighbor does not. This is the arrangement a blade with a thick root and a thin tip usually needs. A generated polar is per section too: the external solver of section 8.8 runs on the section currently selected, and a multi-section blade needs it run once for each section.`

### ¶19 "The drag expression is a parabolic polar: minimum drag at zero lift..." (L4461, in 8.2.1 mathematics)
- **Rules broken:** G6 (after the colon only fragments, no verb)
- **Setting:** `.bemt` keys `cd0`, `k`; GUI fields `Cd0`, `k`
- **Current:** `The drag expression is a parabolic polar: minimum drag at zero lift, rising quadratically with the lift the section is asked to produce.`
- **Proposed:** `The drag expression is a parabolic polar: the drag reaches its minimum at zero lift and rises quadratically with the lift the section produces.`

### ¶20 "Increasing Cl_alpha increases lift..." (L4471)
- **Rules broken:** G9 ("-ing" words used as verb subjects: "Increasing", "Making" four times)
- **Setting:** `.bemt` keys `cl_alpha`, `alpha0_deg`, `cd0`, `k`; GUI fields `Cl_alpha`, `alpha0`, `Cd0`, `k`
- **Current:** `Increasing $C_{l_\alpha}$ increases lift at a given angle […] Increasing $k$ raises drag only where the section is working hard […]`
- **Proposed:** `<b>Physical effect.</b> A larger $C_{l_\alpha}$ gives more lift at a given angle and therefore more thrust at a given collective. A more negative $\alpha_0$ shifts the whole lift line towards lower angles, which is what camber does. A larger $C_{d0}$ raises profile drag at every angle and so raises torque and power without touching thrust. A larger $k$ raises drag only where the section is working hard, so it penalizes the highly loaded outboard stations and the retreating side more than it penalizes the rest of the disk.`

### ¶21 "Choose the analytical source when..." (L4487)
- **Rules broken:** G22 (first sentence about 42 words), G29 ("8.2.2")
- **Setting:** `.bemt` key `source`; GUI field `Data source`; CLI `--airfoil-source`
- **Current:** `Choose the analytical source when a compact attached-flow model is adequate and only four numbers are known about the section, and accept that everything beyond stall is then supplied by the stall model of 8.2.2 rather than measured.`
- **Proposed:** `<b>Applicability and limitations.</b> Choose the analytical source when a compact attached-flow model is adequate and only four numbers are known about the section. With that choice, everything beyond stall is supplied by the stall model of section 8.2.2 rather than by measurements. Choose the tabulated source when measured or externally computed data exist, which is the higher-fidelity option and the only one that reproduces an asymmetric or irregular real curve. Choose the generated source to produce such a table from a profile shape when no measured data exist.`

### ¶22 "A tabulated source may carry several slices..." (L4494)
- **Rules broken:** G22 (third sentence about 45 words)
- **Setting:** `.bemt` key `table_slices`
- **Current:** `[…] a table that stops at $M=0.4$ supplies its $M=0.4$ data to a tip running at $0.75$ and the run converges cleanly to an answer with no compressible drag rise in it.`
- **Proposed:** `[…] and nothing warns when the requested condition falls outside the tabulated range. A table that stops at $M=0.4$ supplies its $M=0.4$ data to a tip running at $0.75$. The run then converges cleanly to an answer with no compressible drag rise in it. The supplied condition grid must therefore bracket the operating envelope, root Reynolds to tip Mach.`

### ¶23 "the Aerodynamic model block, field Data source..." (L4545)
- **Rules broken:** G14 (semicolon joins sentences), G24 ("With analytical…" three times, "with" for "when")
- **Setting:** GUI field `Data source`, Aerodynamic model block, Airfoil tab
- **Current:** `With <code>analytical</code> the four fields […] are shown and editable. With <code>table</code> they are hidden […]. With <code>neuralfoil</code> or <code>xfoil</code> the profile and the operating points that generate the table are given in the blocks below; the choice between the two engines is made there […]`
- **Proposed:** `<span class="gui">GUI</span>: the <i>Aerodynamic model</i> block, field <i>Data source</i>. When <code>analytical</code> is selected, the four fields <i>Cl_alpha</i>, <i>alpha0</i>, <i>Cd0</i> and <i>k</i> are shown and editable. When <code>table</code> is selected, they are hidden and the imported polar is used instead. When <code>neuralfoil</code> or <code>xfoil</code> is selected, the profile and the operating points that generate the table are given in the blocks below. The choice between the two engines is made there. The XFOIL-only transition settings appear while <code>xfoil</code> is selected.`

### ¶24 "It exists for two purposes..." (L4603)
- **Rules broken:** G9 ("Selecting it…"), G18 ("it" is far from its antecedent), G24 ("with a residual that stays smooth" causal reading)
- **Setting:** `.bemt` key `stall_model` value `"linear"`; CLI `--airfoil-stall-model linear`
- **Current:** `Selecting it together with dynamic stall is rejected by validation, because the separation function of 8.3.2 is obtained by inverting a static polar that has stall in it, and this one has none.`
- **Proposed:** `It exists for two purposes. The first is numerical verification: because the residual stays smooth over the whole angle range, a convergence problem can be isolated from a stall effect. The second is as a theoretical reference limit, the ideal linear rotor against which a real one is compared. The linear option must not be used for performance prediction anywhere near the stall envelope. The combination of the linear option with dynamic stall is rejected by validation, because the separation function of section 8.3.2 is obtained by inverting a static polar that has stall in it, and the linear polar has none.`

### ¶25 "The cost is a corner at..." (L4618)
- **Rules broken:** G15 (em dash joins an explanatory clause)
- **Setting:** `.bemt` key `stall_model` value `"clip"`
- **Current:** `The cost is a <b>corner</b> at $\alpha=\alpha_{stall}^\pm$ &mdash; a discontinuity in the derivative, not in the value.`
- **Proposed:** `The cost is a <b>corner</b> at $\alpha=\alpha_{stall}^\pm$. The corner is a discontinuity in the derivative, not in the value. An element oscillating across that corner between iterations converges more slowly, since the slope a Newton step is built from changes abruptly there, though it rarely fails to converge outright.`

### ¶26 "It is a semi-empirical approximation..." (L4639)
- **Rules broken:** G15 (em-dash pair splits the sentence spine), G29 ("9.5.1")
- **Setting:** `.bemt` key `stall_model` value `"enhanced"`
- **Current:** `What it buys is a polar that is $C^1$-continuous everywhere &mdash; which is what the Newton and Aitken solvers of 9.5.1 need &mdash; from the same five parameters […]`
- **Proposed:** `It is a semi-empirical approximation, not measured data, and it is calibrated to reproduce flat-plate behavior qualitatively rather than any particular section quantitatively. What it buys is a polar that is $C^1$-continuous everywhere. That continuity is what the Newton and Aitken solvers of section 9.5.1 need. The enhanced option delivers it from the same five parameters the <code>linear</code> and <code>clip</code> options already use, with no extra experimental data.`

### ¶27 "computed with the same parameters — those of..." (L4647, figcaption)
- **Rules broken:** G15 (em dash joins the parameter list)
- **Setting:** none (figure caption for the three stall models)
- **Current:** `computed with the same parameters &mdash; those of the <code>starter_rotor</code> airfoil, […]`
- **Proposed:** `$C_l(\alpha)$ and $C_d(\alpha)$ for the three analytical stall models, computed with the same parameters. Those parameters are the ones of the <code>starter_rotor</code> airfoil: $C_{l_\alpha}=6.283$, $\alpha_0=-5^\circ$, $C_{d0}=0.01$, $k=0.01$, $\alpha_{stall}^+=16^\circ$ and $\alpha_{stall}^-=-10^\circ$. <code>linear</code> ignores stall and the lift line continues without bound. <code>clip</code> saturates abruptly at the stall value, leaving a corner. <code>enhanced</code> decays smoothly towards flat-plate behavior.`

### ¶28 "Read them off the measured polar..." (L4689)
- **Rules broken:** G8 (phrasal verb "read off"), G9 ("taking the peak angle"), G22 (sentence of about 50 words)
- **Setting:** GUI fields `alpha stall + [deg]`, `alpha stall - [deg]`; `.bemt` keys `alpha_stall_pos_deg`, `alpha_stall_neg_deg`
- **Current:** `Read them off the measured polar as the angles where the curve visibly leaves the straight line, not where it peaks: taking the peak angle instead pushes the stall several degrees too late and overstates thrust near the limit, while a value below the real one stalls the model early […]`
- **Proposed:** `<b>Applicability and configuration.</b> They do nothing when the source is a tabulated polar, because the table already contains the real shape, and the maximum and minimum lift and their angles are detected from the data itself. Read the two angles from the measured polar at the points where the curve visibly leaves the straight line, not where it peaks. A peak angle used instead pushes the stall several degrees too late and overstates thrust near the limit. A value below the real one stalls the model early and makes predicted thrust and power pessimistic. Typical values are $12^\circ$ to $16^\circ$ positive and $-6^\circ$ to $-12^\circ$ negative. The positive angle must be greater than the negative one.`

### ¶29 "Full-range extension supplies coefficients..." (L4712)
- **Rules broken:** G15 (em-dash pair "— analytical or tabulated —")
- **Setting:** `.bemt` key `extend_full_range`; GUI checkbox `Extrapolate table with Viterna-Corrigan`
- **Current:** `continuing the polar with the Viterna-Corrigan relations, which wrap any base model &mdash; analytical or tabulated &mdash; and extend it continuously to $\pm180^\circ$.`
- **Proposed:** `Full-range extension supplies coefficients over the rest of the circle by continuing the polar with the Viterna-Corrigan relations, which wrap any base model (analytical or tabulated) and extend it continuously to $\pm180^\circ$.`

### ¶30 "A wider blending window provides smoother..." (L4735)
- **Rules broken:** G13 ("impacting" used as an informal verb)
- **Setting:** `.bemt` key `viterna_blend_width_deg`; GUI field `Viterna blend width [deg]`
- **Current:** `A narrower window preserves base polar fidelity closer to stall but sharpens transitions, potentially impacting solver gradient evaluation.`
- **Proposed:** `<b>Transition window ($\Delta\alpha$).</b> A finite transition window $\Delta\alpha$ blends the base polar into the post-stall continuation. A wider blending window provides smoother gradient continuity at the cost of modifying base polar data over a broader angle range. A narrower window preserves base polar fidelity closer to stall but sharpens transitions, which can affect the gradient evaluation of the solver.`

### ¶31 "A tabulated polar in use: synthetic..." (L4838, figcaption)
- **Rules broken:** G8 (phrasal verb "stands in for")
- **Setting:** none (figure caption for tabulated interpolation)
- **Current:** `synthetic measured points, carrying Gaussian noise that stands in for experimental uncertainty, linearly interpolated between samples […]`
- **Proposed:** `A tabulated polar in use: synthetic measured points, carrying Gaussian noise that represents the experimental uncertainty, linearly interpolated between samples, against the analytical <code>enhanced</code> model that generated them. Interpolation reproduces any shape the real curve has, including asymmetries and irregularities no closed-form model would produce, at the cost of requiring the complete table as input and of inheriting whatever noise the measurement carried.`

### ¶32 "Ignoring it under-predicts the peak load..." (L4874)
- **Rules broken:** G9 ("-ing" subject "Ignoring it")
- **Setting:** none (prose; motivation for the dynamic stall model)
- **Current:** `Ignoring it under-predicts the peak load on the retreating side and mis-times where the blade recovers.`
- **Proposed:** `A model that omits the lag under-predicts the peak load on the retreating side and mis-times where the blade recovers. Whether it matters depends entirely on whether the blade reaches stall at all: in a lightly loaded rotor at low advance ratio the correction does nothing.`

### ¶33 "One deliberate limitation is worth stating..." (L4935)
- **Rules broken:** G9 ("Doing it properly would mean solving…")
- **Setting:** none (prose; limitation of the dynamic stall correction)
- **Current:** `Doing it properly would mean solving the inflow and the separation history at the same time, which is a substantially larger problem.`
- **Proposed:** `One deliberate limitation is worth stating. zBEMT applies the correction as post-processing on the converged solution. It recomputes the section loads from the final inflow field. It does not feed them back into the momentum balance. A fully coupled treatment would solve the inflow and the separation history at the same time, which is a substantially larger problem. The consequence is that dynamic stall changes the reported loads but not the inflow that produced them.`

### ¶34 "In REVERSE FLOW the attached lift line..." (L4949)
- **Rules broken:** G1 (all-caps emphasis "REVERSE FLOW" is casual), G15 (two em dashes), G31 (British "per cent")
- **Setting:** none (prose; branch of the separation-function inversion)
- **Current:** `That is not a corner case. In REVERSE FLOW the attached lift line is extrapolated far outside the range it was fitted over &mdash; at $\alpha=-148^\circ$ it reads about $-15.6$ &mdash; while the static polar, extended by Viterna, gives about $+0.96$. The ratio is negative there, and on a rotor at $\mu_x=0.3$ that is true over roughly forty per cent of the disk.`
- **Proposed:** `The low branch is not a corner case. In reverse flow the attached lift line is extrapolated far outside the range it was fitted over. At $\alpha=-148^\circ$ it reads about $-15.6$, while the static polar, extended by Viterna, gives about $+0.96$. The ratio is negative there, and on a rotor at $\mu_x=0.3$ that is true over roughly forty per cent of the disk.`

### ¶35 "the correction is proportional to how far..." (L4962)
- **Rules broken:** G14 (semicolon joins two sentences)
- **Setting:** none (prose; steady limit of the Øye model)
- **Current:** `The expression is the same as the blend above, rearranged; what it removes is a cancellation that had to be relied on for the static polar to come back.`
- **Proposed:** `Writing the blend this way makes the steady limit exact rather than approximate: the correction is proportional to how far the lagged separation state has fallen behind the static one, and in hover it is identically zero. The expression is the same as the blend above, only rearranged. What this form removes is a cancellation that the original form had to rely on for the static polar to come back.`

### ¶36 "a polar that rises linearly for ever has nothing..." (L4970)
- **Rules broken:** G31 (British "for ever")
- **Setting:** GUI checkbox `Enable dynamic stall`; `.bemt` key `use_dynamic_stall`; CLI `--dynamic-stall`
- **Current:** `the model works by inverting the static polar into the separation function, and a polar that rises linearly for ever has nothing to invert.`
- **Proposed:** `the model works by inverting the static polar into the separation function, and a polar that rises linearly forever has nothing to invert.`

### ¶37 "The grouping c/W is the time..." (L5001)
- **Rules broken:** G30 ("A says how many…" gives a parameter human speech)
- **Setting:** `.bemt` key `dynamic_stall_A`; GUI field `Constant A`
- **Current:** `The grouping $c/W$ is the time a particle of air takes to travel one chord, so $A$ says how many chord-lengths of travel the boundary layer needs before separation has caught up with the angle that provoked it.`
- **Proposed:** `The grouping $c/W$ is the time a particle of air takes to travel one chord, so $A$ gives the number of chord-lengths of travel the boundary layer needs before separation has caught up with the angle that provoked it.`

### ¶38 "Increasing A widens the loop..." (L5017)
- **Rules broken:** G9 ("Increasing", "Reducing" as verb subjects)
- **Setting:** `.bemt` key `dynamic_stall_A`; GUI field `Constant A`
- **Current:** `Increasing $A$ widens the loop: more lift than the static polar predicts […] Reducing $A$ towards zero collapses the loop […]`
- **Proposed:** `A larger $A$ widens the loop: the blade then produces more lift than the static polar predicts while the angle is rising past stall, less while the angle is falling back, and a larger difference between the two. A smaller $A$ collapses the loop. At zero, the model returns the static polar exactly, which is the check that the setting does what is expected.`

### ¶39 "It is not a per-airfoil constant to be tuned..." (L5022)
- **Rules broken:** G22 (single sentence of about 55 words after the colon)
- **Setting:** `.bemt` key `dynamic_stall_A`; GUI field `Constant A`
- **Current:** `It is not a per-airfoil constant to be tuned: treat a change to it as a sensitivity test, and read a result that depends strongly on it as a warning that the case is sitting deep enough in stall for the whole lag model to be near the edge of its usefulness.`
- **Proposed:** `The commonly used reference value is $8$, and it comes from fits to oscillating-airfoil measurements rather than from a derivation. It is not a per-airfoil constant to be tuned. Treat a change to it as a sensitivity test. A result that depends strongly on it is a warning: the case then sits deep enough in stall for the whole lag model to be near the edge of its usefulness. The value has no effect at all on a case in which the blade never reaches stall, because there is then no separation for the state to lag behind.`

### ¶40 "Positive, and in practice between about 4 and 12." (L5029)
- **Rules broken:** G6 (telegraphic, no verb)
- **Setting:** `.bemt` key `dynamic_stall_A`; GUI field `Constant A`
- **Current:** `<b>Configuration and valid range.</b> Positive, and in practice between about $4$ and $12$. Leave it at $8$ unless a specific reference for the section says otherwise.`
- **Proposed:** `<b>Configuration and valid range.</b> The value must be positive, and in practice it lies between about $4$ and $12$. Leave it at $8$ unless a specific reference for the section says otherwise.`

### ¶41 "The defaults, fading between 40° and 50°..." (L5055)
- **Rules broken:** G32 ("a sensible rotor" is vague, non-technical)
- **Setting:** GUI fields `Fade start [deg]`, `Fade end [deg]`; `.bemt` keys `dynamic_stall_fade_start_deg`, `dynamic_stall_fade_end_deg`
- **Current:** `The defaults, fading between $40^\circ$ and $50^\circ$, sit above any angle a sensible rotor operates at and below the region where the model stops meaning anything.`
- **Proposed:** `<b>Configuration.</b> The defaults, fading between $40^\circ$ and $50^\circ$, sit above any angle a rotor reaches in a flyable condition and below the region where the model stops meaning anything. The start angle must be below the end angle. The configuration is rejected otherwise.`

### ¶42 "The frequency-domain method is appropriate..." (L5082)
- **Rules broken:** G9 ("When marching, … must be run")
- **Setting:** `.bemt` keys `dynamic_stall_method`, `dynamic_stall_time_march_revolutions`, `dynamic_stall_time_march_avg_last`; GUI field `Method`
- **Current:** `When marching, enough revolutions must be run for the starting guess to be forgotten, and the answer is averaged over the last few so that what is reported is the settled cycle rather than one arbitrary revolution.`
- **Proposed:** `<b>Configuration and limitation.</b> The frequency-domain method is appropriate for a steady periodic analysis. For time marching, run enough revolutions for the starting guess to be forgotten. The answer is averaged over the last few revolutions, so that what is reported is the settled cycle rather than one arbitrary revolution. The number averaged must not exceed the number run.`

### ¶43 "Method in the Dynamic stall block..." (L5088)
- **Rules broken:** G15 (em-dash pair sets off a needed fact)
- **Setting:** GUI field `Method`, Dynamic stall block, Airfoil tab
- **Current:** `The fields that belong only to the march &mdash; the number of revolutions and how many of the last ones are averaged &mdash; appear only when <i>Time march</i> is selected.`
- **Proposed:** `The fields that belong only to the march (the number of revolutions and how many of the last ones are averaged) appear only when <i>Time march</i> is selected. A march reports how far the last revolution still differed from the one before it, and a value above one part in a thousand raises a finding: the cycle had not settled, so the averaged answer is not yet periodic.`

### ¶44 "The aerofoil is running in reverse..." (L5114)
- **Rules broken:** G31/G10 ("aerofoil")
- **Setting:** `.bemt` key `reverse_flow_model`; GUI dropdown `Reverse flow model`
- **Current:** `The aerofoil is running in reverse, and its measured polar, taken with the flow arriving at the leading edge, does not describe it.`
- **Proposed:** `The airfoil is running in reverse, and its measured polar, taken with the flow arriving at the leading edge, does not describe it.`

### ¶45 "Far outside its design range a section stops behaving like an aerofoil." (L5209)
- **Rules broken:** G31/G10 ("aerofoil")
- **Setting:** `.bemt` keys `thin_plate_blend_center_deg`, `thin_plate_blend_width_deg`; reverse flow model `thin_plate_blend`
- **Current:** `Far outside its design range a section stops behaving like an aerofoil.`
- **Proposed:** `<b>Thin-plate asymptote.</b> Far outside its design range a section stops behaving like an airfoil. Once the flow has separated from both edges, lift comes from the pressure difference across an inclined surface rather than from attached circulation, and camber and thickness stop mattering. What remains is the result any flat inclined surface obeys:`

### ¶46 "Blending towards that is not a convenience..." (L5216)
- **Rules broken:** G9 ("Blending" verb subject), G19 ("that" points at an equation, unclear)
- **Setting:** reverse flow model `thin_plate_blend`
- **Current:** `Blending towards that is not a convenience: it is the correct asymptote at large angle of attack […]`
- **Proposed:** `Blending the polar towards this limit is not a convenience: the limit is the correct asymptote at large angle of attack, and it needs no measured data beyond the range the polar actually covers.`

### ¶47 "Use thin_plate_blend when it has not..." (L5219)
- **Rules broken:** G8 ("the option to reach for" is a phrasal idiom)
- **Setting:** `.bemt` key `reverse_flow_model`; GUI dropdown `Reverse flow model`
- **Current:** `Use <code>thin_plate_blend</code> when it has not: it is continuous, needs no data past stall, and is the option to reach for if the solver struggles at the reverse boundary.`
- **Proposed:** `Use <code>thin_plate_blend</code> when the polar has not been extended: it is continuous, needs no data past stall, and is the option to choose if the solver struggles at the reverse boundary. The other three exist for comparison, and <code>flat_plate</code> is a reasonable crude choice when nothing is known about the section backwards. Below about $\mu_x=0.3$ all five give nearly the same integrated thrust and torque, so the choice is worth attention only in fast forward flight.`

### ¶48 "for a single element at r/R=0.30 and μx=0.55; the shaded band..." (L5231, figcaption)
- **Rules broken:** G14 (semicolon joins two sentences)
- **Setting:** none (figure caption comparing the five reverse-flow models)
- **Current:** `at $r/R=0.30$ and $\mu_x=0.55$; the shaded band is where $U_T<0$.`
- **Proposed:** `$C_l$, $C_d$ and $\alpha_{eff}$ around one revolution for a single element at $r/R=0.30$ and $\mu_x=0.55$. The shaded band is where $U_T<0$. <code>flat_plate</code> and <code>simple_flip</code> jump at the edges of the band, <code>alpha_blending</code> smooths the jump partly, and <code>thin_plate_blend</code> and <code>viterna_full_range</code> stay continuous right through it.`

### ¶49 "a steepness of 5 therefore smears the change over some forty per cent..." (L5261)
- **Rules broken:** G31 (British "per cent", twice)
- **Setting:** `.bemt` key `reverse_flow_blend_factor`; GUI field `Reverse flow blend factor`
- **Current:** `a steepness of $5$ therefore smears the change over some forty per cent of the radius, and a steepness of $50$ over four per cent.`
- **Proposed:** `<b>Physical effect.</b> This value controls the width of the artificial transition band on the disk. The hyperbolic tangent reaches about $96\%$ of its limit at $k\xi=2$, so the transition occupies roughly $|\xi|\lesssim2/k$, a band about $2R/k$ wide in radius where the boundary crosses. A steepness of $5$ therefore smears the change over some forty percent of the radius, and a steepness of $50$ over four percent.`

### ¶50 "A small value converges easily and pays for it..." (L5267)
- **Rules broken:** G22 (sentence of about 40 words, trailing participle)
- **Setting:** `.bemt` key `reverse_flow_blend_factor`; GUI field `Reverse flow blend factor`
- **Current:** `A small value converges easily and pays for it by applying a reduced angle of attack across a wide band where the flow is in fact ordinary forward flow, understating the load there.`
- **Proposed:** `A small value converges easily. It pays for this by applying a reduced angle of attack across a wide band where the flow is in fact ordinary forward flow, and it understates the load there. The default of $5$ sits deliberately on the forgiving side. If the answer visibly depends on this number, the reverse region is large enough that a continuous treatment is the better response than tuning the steepness.`

### ¶51 "Moving the center outward keeps the measured polar in charge..." (L5297)
- **Rules broken:** G9 ("Moving the center outward"), G13 (idiom "keeps the measured polar in charge"), G22 (sentence about 40 words)
- **Setting:** `.bemt` keys `thin_plate_blend_center_deg`, `thin_plate_blend_width_deg`; GUI fields `thin_plate_blend_center_deg`, `thin_plate_blend_width_deg`
- **Current:** `Moving the center outward keeps the measured polar in charge further into the stalled range, which is right when the data genuinely extend that far and wrong when they do not, because beyond the measured range the polar merely holds its last value.`
- **Proposed:** `<b>Physical interpretation.</b> Together these angles state where the real polar stops being trustworthy. If the center is set further out, the measured polar governs further into the stalled range. This is correct when the data genuinely extend that far and wrong when they do not, because beyond the measured range the polar merely holds its last value. Narrowing the width sharpens the changeover and, taken far enough, reintroduces the sharp feature the method exists to avoid.`

### ¶52 "The defaults, a center of 35° and a width of 20°, hand over..." (L5303)
- **Rules broken:** G8 (phrasal verb "hand over")
- **Setting:** `.bemt` keys `thin_plate_blend_center_deg`, `thin_plate_blend_width_deg`
- **Current:** `The defaults, a center of $35^\circ$ and a width of $20^\circ$, hand over across the range where most polars stop being reliable.`
- **Proposed:** `<b>Configuration and valid range.</b> The defaults, a center of $35^\circ$ and a width of $20^\circ$, place the changeover across the range where most polars stop being reliable. Because the weighting depends only on the angle of attack, it applies wherever large angles occur, including on the retreating side outside the reverse circle, so a center set too low inflates drag over a genuinely attached part of the disk.`

### ¶53 "An aerofoil works by setting up a pressure field..." (L5349)
- **Rules broken:** G31/G10 ("aerofoil")
- **Setting:** `.bemt` key `use_compressibility`; GUI checkbox `Compressibility`
- **Current:** `An aerofoil works by setting up a pressure field around itself, and that field is communicated through the air at the speed of sound.`
- **Proposed:** `An airfoil works by setting up a pressure field around itself, and that field is communicated through the air at the speed of sound. While the section moves slowly compared with that speed, the air has time to adjust and behaves as though it were incompressible. As the speed rises, the adjustment lags, the pressure disturbances crowd together, and the same geometric angle of attack produces a larger pressure difference. Both lift and drag rise for the same angle.`

### ¶54 "the advancing tip sees roughly ΩR+Vx..." (L5356)
- **Rules broken:** G30 ("the tip sees" gives the flow to a blade as human perception)
- **Setting:** none (prose; compressibility motivation)
- **Current:** `in forward flight the advancing tip sees roughly $\Omega R+V_x$ against the retreating tip's $\Omega R-V_x$.`
- **Proposed:** `On a rotor this matters because the blade speed is far from uniform. The tip moves at $\Omega R$ while the root barely moves at all, and in forward flight the advancing tip reaches roughly $\Omega R+V_x$ against the retreating tip's $\Omega R-V_x$. Compressibility is therefore felt very unevenly across the disk.`

### ¶55 "The factor is 1.005 at M=0.1... negligible below..." (L5368)
- **Rules broken:** G6 (after the colon only fragments, no verb)
- **Setting:** `.bemt` key `use_compressibility`; GUI checkbox `Compressibility`
- **Current:** `The factor is $1.005$ at $M=0.1$, $1.048$ at $M=0.3$, $1.25$ at $M=0.6$ and $1.67$ at $M=0.8$: negligible below about $M=0.3$, and steep beyond $M=0.6$.`
- **Proposed:** `The factor is $1.005$ at $M=0.1$, $1.048$ at $M=0.3$, $1.25$ at $M=0.6$ and $1.67$ at $M=0.8$. It is negligible below about $M=0.3$ and steep beyond $M=0.6$. It diverges formally as $M\to1$, where the linearized assumption stops describing the flow at all, because a shock forms and wave drag appears and neither is contained in this expression. The factor is therefore capped at its $M=0.9$ value, $1/\sqrt{1-0.9^2}\approx2.29$, rather than allowed to run away. Nothing below $M=0.9$ is altered by that cap. Above it, the coefficients reported are capped values and not a transonic prediction.`

### ¶56 "it steepens the advancing/retreating asymmetry..." (L5376)
- **Rules broken:** G26 (joining slash "advancing/retreating" in prose)
- **Setting:** `.bemt` key `use_compressibility`
- **Current:** `In forward flight it steepens the advancing/retreating asymmetry that already exists, adding load on the advancing side and increasing the rolling moment the disk must be trimmed against.`
- **Proposed:** `What it changes is the magnitude of the load, and it changes it unevenly. In forward flight it steepens the asymmetry between the advancing side and the retreating side that already exists, adding load on the advancing side and increasing the rolling moment the disk must be trimmed against. In hover, where the Mach number depends only on radius, the effect is a uniform shift of loading towards the tip.`

### ¶57 "Enable it when the tip Mach number is high enough to matter, which for most rotors..." (L5384)
- **Rules broken:** G2/G22 (one sentence carries a condition, a quantitative rule and a second case)
- **Setting:** `.bemt` key `use_compressibility`; GUI checkbox `Compressibility`
- **Current:** `Enable it when the tip Mach number is high enough to matter, which for most rotors means a tip speed above roughly $0.6a$, and always for a propeller, whose tip speeds are higher.`
- **Proposed:** `<b>Configuration and applicability.</b> Enable it when the tip Mach number is high enough to matter. For most rotors this means a tip speed above roughly $0.6a$. Enable it in every case for a propeller, whose tip speeds are higher. Leave it off when the polar is already resolved in Mach, because the table then carries the effect and applying the correction on top would count it twice. The speed of sound it uses is set in the Config/Engine tab and should match the altitude and temperature being modeled: a cold day raises the tip Mach number of an otherwise unchanged rotor.`

### ¶58 "the checkbox is cleared and greyed out..." (L5397)
- **Rules broken:** G31 (British "greyed")
- **Setting:** GUI checkbox `Compressibility`, Compressibility and Reverse Flow Effects block
- **Current:** `the checkbox is cleared and greyed out, and its tooltip says how many distinct Mach slices were found.`
- **Proposed:** `The <span class="gui">GUI</span> <b>freezes the field</b>. As soon as the airfoil source is <code>table</code>, <code>neuralfoil</code> or <code>xfoil</code> and the loaded polar carries more than one Mach value, the checkbox is cleared and grayed out, and its tooltip says how many distinct Mach slices were found. Because it is the source in use that decides, switching back to an analytical airfoil releases the field and restores whatever the setting was before it was frozen: the choice is suspended, not discarded.`

### ¶59 "Ticking a condition in that list overlays its curve..." (L5439)
- **Rules broken:** G9 ("Ticking a condition…" as verb subject), G29 ("8.9")
- **Setting:** GUI buttons `Import CSV`, `Export CSV`, Data import / tabulated polar block
- **Current:** `Ticking a condition in that list overlays its curve on the preview of 8.9, which is how several Reynolds numbers or several Mach numbers are compared against each other.`
- **Proposed:** `<span class="gui">GUI</span>: the <i>Data import / tabulated polar</i> block, with the <i>Import CSV</i> and <i>Export CSV</i> buttons and, below them, the list of conditions the loaded file turned out to contain. Tick a condition in that list to overlay its curve on the preview of section 8.9. This is how several Reynolds numbers or several Mach numbers are compared against each other.`

### ¶60 "Any column the list does not recognize is ignored..." (L5508)
- **Rules broken:** G19 ("Without this" has no clear antecedent)
- **Setting:** CSV import of a tabulated polar; CLI `--airfoil-table CSV`
- **Current:** `Without this, a file whose first column is $C_l$ would import as an angle sweep, with no warning.`
- **Proposed:** `Any column the list does not recognize is ignored, so a file carrying $C_m$, transition location or a comment column costs nothing. A missing <em>required</em> column is the one rejection at this stage. The importer raises an error. The error names the column it could not find and lists the headers it did see, instead of guessing by position. Without this error, a file whose first column is $C_l$ would import as an angle sweep, with no warning. A header no alias covers has to be renamed in the file before importing.`

### ¶61 "Using Export CSV… generates a properly formatted template..." (L5530)
- **Rules broken:** G9 ("Using Export CSV…"), G13 ("stratification" is jargon outside the project vocabulary)
- **Setting:** GUI button `Export CSV…`, Data import / tabulated polar block
- **Current:** `zBEMT ignores a column header it does not recognize (for example, <code>Reynolds_number</code> instead of <code>reynolds</code>), which produces a single polar with no stratification. Using <b>Export CSV&hellip;</b> generates a properly formatted template with canonical column headers […]`
- **Proposed:** `zBEMT ignores a column header it does not recognize (for example, <code>Reynolds_number</code> instead of <code>reynolds</code>), which produces a single polar with no condition labels. <b>Export CSV&hellip;</b> produces a template with the canonical column headers (<code>alpha_deg, Cl, Cd, r_norm, reynolds, mach</code>), already formatted for re-import.`

### ¶62 "A NACA code is the quickest..." (L5620)
- **Rules broken:** G31 (British "per cent", twice)
- **Setting:** `.bemt` key `naca_code`; CLI `--airfoil-geometry naca0012`-style
- **Current:** `so <code>2412</code> is a section with two per cent camber at forty per cent of the chord and twelve per cent thickness. […] the symmetric twelve-per-cent section.`
- **Proposed:** `<b>A NACA code</b> is the quickest, and covers most conventional sections. The four-digit family encodes the maximum camber, its position and the thickness, so <code>2412</code> is a section with two percent camber at forty percent of the chord and twelve percent thickness. The five-digit family encodes a different camber line. The code is a string, not a number, because the leading zeros carry meaning: <code>0012</code> is the symmetric twelve-percent section.`

### ¶63 "CST and Bézier are for shapes being designed rather than looked up..." (L5662)
- **Rules broken:** G22 (second sentence about 40 words)
- **Setting:** `.bemt` keys `cst_upper`, `cst_lower`, `bezier_control_points`; GUI `Source` dropdown, Profile 2D geometry block
- **Current:** `CST and Bézier are for shapes being designed rather than looked up, and both are stored exactly as typed, so a malformed list is reported when the geometry is generated rather than silently accepted.`
- **Proposed:** `<b>Configuration.</b> Use a NACA code unless there is a specific section to reproduce. CST and Bézier are for shapes being designed rather than looked up. Both are stored exactly as typed, so a malformed list is reported when the geometry is generated rather than silently accepted. The number of points controls how finely the contour is sampled. The default of $200$ resolves the leading edge adequately for polar generation.`

### ¶64 "One point per line, two numbers, x then y, both normalized..." (L5711)
- **Rules broken:** G6 (the lead sentence is a string of fragments without a verb)
- **Setting:** GUI button `Import .dat…`; coordinate file import
- **Current:** `<b>One point per line, two numbers, $x$ then $y$, both normalized by the chord</b>, separated by space, tab or comma. That is the entire contract:`
- **Proposed:** `<b>The importer reads one point per line, two numbers, $x$ then $y$, both normalized by the chord</b>, separated by space, tab or comma. That is the entire contract:`

### ¶65 "and a contour in millimetres would otherwise reach NeuralFoil..." (L5731)
- **Rules broken:** G31 (British "millimetres")
- **Setting:** coordinate file import; GUI `Import .dat…`
- **Current:** `a contour in millimetres would otherwise reach NeuralFoil as an airfoil of a thousand chords' extent.`
- **Proposed:** `What it <em>is</em> required to be is normalized ($x$ spanning $0$ to $1$), because the chord is the length scale everything downstream assumes, and a contour in millimeters would otherwise reach NeuralFoil as an airfoil of a thousand chords' extent.`

### ¶66 "The defaults 0.0158, 0.30, … reproduce a conventional section of about twelve per cent..." (L5783)
- **Rules broken:** G31 (British "per cent")
- **Setting:** `.bemt` key `generator_params` (PARSEC values); CLI `--airfoil-geometry parsec:...`
- **Current:** `The defaults 0.0158, 0.30, 0.0593, &minus;0.475, 0.35, &minus;0.047, 0.530, 0.0025 and 8.0 reproduce a conventional section of about twelve per cent thickness with slight camber.`
- **Proposed:** `The defaults 0.0158, 0.30, 0.0593, &minus;0.475, 0.35, &minus;0.047, 0.530, 0.0025 and 8.0 reproduce a conventional section of about twelve percent thickness with slight camber. If the surfaces of a parameter set would cross, generation stops with a message.`

### ¶67 "Type the nine numbers there, comma-separated, in the order given above, and press Generate geometry..." (L5795)
- **Rules broken:** P1 (two sequential instructions merged)
- **Setting:** GUI `Source` = `parsec`, field `PARSEC (9 values)`, Profile 2D geometry block
- **Current:** `Type the nine numbers there, comma-separated, in the order given above, and press <i>Generate geometry</i> to build and draw the contour.`
- **Proposed:** `<span class="gui">GUI</span>: choose <code>parsec</code> in the <i>Source</i> dropdown of the <i>Profile 2D geometry</i> block. One row appears, <i>PARSEC (9 values)</i>. Type the nine numbers there, comma-separated, in the order given above. Then press <i>Generate geometry</i> to build and draw the contour.`

### ¶68 "Type the two numbers there, comma-separated, and press Generate geometry." (L5842)
- **Rules broken:** P1 (two sequential instructions merged)
- **Setting:** GUI `Source` = `joukowski`, field `Joukowski (eps, camber)`
- **Current:** `Type the two numbers there, comma-separated, and press <i>Generate geometry</i>.`
- **Proposed:** `Type the two numbers there, comma-separated. Then press <i>Generate geometry</i>.`

### ¶69 "Type the thickness there and press Generate geometry." (L5877)
- **Rules broken:** P1 (two sequential instructions merged)
- **Setting:** GUI `Source` = `biconvex`, field `Biconvex (thickness)`
- **Current:** `Type the thickness there and press <i>Generate geometry</i>.`
- **Proposed:** `Type the thickness there. Then press <i>Generate geometry</i>.`

### ¶70 "Prerequisite: 2D geometry already generated/imported..." (L5923)
- **Rules broken:** G26 (joining slash "generated/imported" in prose)
- **Setting:** GUI button `Run polar generation`; CLI `--gen-neuralfoil`, `--gen-xfoil`
- **Current:** `Prerequisite: 2D geometry already generated/imported ([…]Section 8.7</a>).`
- **Proposed:** `Prerequisite: the 2D geometry is already generated or imported (<a class="xref" href="#cap-3-7" title="8.7 Profile 2D geometry">Section 8.7</a>). The "Run polar generation" button generates a polar for the <b>currently selected section</b> with the engine of the polar source selected in <a class="xref" href="#cap-3-2-1" title="8.2.1 Polar source and linear coefficients">Section 8.2.1</a>, <code>neuralfoil</code> or <code>xfoil</code> (<a class="xref" href="#cap-3-1-3" title="8.1.3 Radial position of a section">Section 8.1.3</a>). With multiple sections, repeat the run per section. The sweep covers Reynolds and Mach lists and an $\alpha$ range.`

### ¶71 "When that extension is active, the control follows it to Full range unless it was last set by hand." (L6122, list item)
- **Rules broken:** G18 ("it" twice with two different antecedents in one sentence)
- **Setting:** GUI control `Alpha` (drawing-aid strip, preview panels)
- **Current:** `When that extension is active, the control follows it to Full range unless it was last set by hand.`
- **Proposed:** `<i>Alpha</i> sets the angle-of-attack span the polar curves are computed over: Typical ($-30^\circ$ to $30^\circ$), Extended ($-90^\circ$ to $90^\circ$) or Full range ($-180^\circ$ to $180^\circ$). It recomputes the curves over the chosen span, which zooming the axes never does. Full range is therefore the only way to see what the full-range extension produced. When that extension is active, the control switches to Full range unless the span was last set by hand.`

### ¶72 "Below roughly Re∼10^5 the layer stays laminar... relative to the same profile at 10^6; stepping the Reynolds control..." (L6175)
- **Rules broken:** G14 (semicolon joins two sentences), G9 ("stepping… and watching…")
- **Setting:** GUI `Navigate` Reynolds selector, Airfoil tab preview
- **Current:** `[…] so minimum drag can double and maximum lift collapse relative to the same profile at $10^6$; stepping the Reynolds control down the tabulated list and watching the drag bucket fill in and $C_{\ell,max}$ fall is the fastest check that the table actually resolves the root.`
- **Proposed:** `Below roughly $Re \sim 10^5$ the layer stays laminar over much of the chord and separates without reattaching, so minimum drag can double and maximum lift collapse relative to the same profile at $10^6$. Move the Reynolds control down the tabulated list and watch the drag bucket fill in and $C_{\ell,max}$ fall: this is the fastest check that the table actually resolves the root. Mach number sets compressibility. In the linearized subsonic range the lift slope grows as`

### ¶73 "which is a modest 7 % at M = 0.35 but 25 % at M = 0.6 and unbounded as M → 1; the correction is capped..." (L6183)
- **Rules broken:** G14 (semicolon joins two sentences)
- **Setting:** GUI `Navigate` Mach selector; `.bemt` key `use_compressibility` (referenced model)
- **Current:** `which is a modest 7&nbsp;% at $M = 0.35$ but 25&nbsp;% at $M = 0.6$ and unbounded as $M \to 1$; the correction is capped at $M = 0.9$ because […]`
- **Proposed:** `which is a modest 7&nbsp;% at $M = 0.35$ but 25&nbsp;% at $M = 0.6$ and unbounded as $M \to 1$. The correction is capped at $M = 0.9$ because it is a linearized theory and means nothing beyond that (<a class="xref" href="#cap-3-5" title="8.5 Compressibility">Section 8.5</a>). Past the critical Mach number a shock forms on the upper surface, drag rises sharply, and the real polar departs from anything the linearized correction predicts. Only tabulated data at that Mach can show it.`

### ¶74 "Walk the axes to the extremes the case will actually produce (root Reynolds and tip Mach) and confirm a tabulated slice exists near each." (L6190)
- **Rules broken:** P1 (two sequential instructions merged), G12/G17 ("confirm a tabulated slice exists" drops "that")
- **Setting:** GUI `Navigate` controls (r/R, Reynolds, Mach)
- **Current:** `Walk the axes to the extremes the case will actually produce (root Reynolds and tip Mach) and confirm a tabulated slice exists near each.`
- **Proposed:** `<b>The practical use, and the trap.</b> Walk the axes to the extremes the case will actually produce: the root Reynolds and the tip Mach. Then confirm that a tabulated slice exists near each. Selection is nearest-neighbor, not interpolation, and nothing warns when the request falls outside the tabulated range: a table that stops at $M = 0.4$ quietly supplies its $M = 0.4$ data to a tip running at $0.75$, and the run converges cleanly to an answer with no compressible drag rise in it at all. A polar family that does not bracket the operating envelope is the most common single source of confidently wrong results.`

## Structural defects (appendix items)
- line 4309: plain-text span "the blocks of 8.2 to 8.9" — not a link and not written as "Sections 8.2 to 8.9" (documentation rule 11, G29)
- line 4402: plain-text reference "described in 8.2.1" — not a link (rule 11, G29)
- line 4415: plain-text reference "the reason given in 8.1.2" — not a link (rule 11, G29)
- line 4429: plain-text reference "for the same reason as 8.1.2" — not a link (rule 11, G29)
- line 4432: plain-text reference "Everything from

---

# Block F: chapters 9–10 (lines 6209–7480)

## Section 9 — Config/Engine (anchor: sec-93-configengine)
- Paragraphs reviewed: 131 | OK: 104 | Proposals: 27

### ¶1 "Three settings that might be expected here..." (L6228–6233)
- **Rules broken:** G22, G2
- **Setting:** none (prose)
- **Current:** The Config/Engine tab holds everything that decides how the problem is solved: how finely the disk is sampled, what the air is like, which inflow model and which corrections apply, and which solver runs. Three settings that might be expected here are elsewhere, because they belong to what is being modeled rather than to how it is solved: dynamic stall, reverse flow and compressibility are set in the Airfoil tab, and the rotor or propeller mode in the Project tab, which this tab shows only as a read-only label.
- **Proposed:** The Config/Engine tab holds everything that decides how the problem is solved. It covers how finely the disk is sampled, what the air is like, which inflow model and which corrections apply, and which solver runs. Three settings that might be expected here are elsewhere, because they belong to what is being modeled rather than to how it is solved. Dynamic stall, reverse flow and compressibility are set in the Airfoil tab. The rotor or propeller mode is set in the Project tab. This tab shows the mode only as a read-only label.

### ¶2 "Editing a field changes the project..." (L6235)
- **Rules broken:** G24 ("with the result shown" is an ambiguous with-absolute; an independent clause is clearer)
- **Setting:** GUI: Config/Engine tab
- **Current:** ... Validation runs again after every edit, and also whenever the geometry, the airfoil or the project itself changes, with the result shown in the panel above the buttons. There is no validate button because there is never a stale verdict waiting to be refreshed.
- **Proposed:** Editing a field changes the project held in memory and writes nothing to disk. <b>Save</b> commits the whole project and <b>Restore</b> discards the edits made since the last save. Validation runs again after every edit, and also whenever the geometry, the airfoil or the project itself changes. The result is shown in the panel above the buttons. There is no validate button because there is never a stale verdict waiting to be refreshed.

### ¶3 "Two unrelated groups of settings share this block..." (L6243)
- **Rules broken:** G18 ("it" could refer to the blade, the rotor or the disk)
- **Setting:** GUI: Config/Engine tab
- **Current:** Two unrelated groups of settings share this block on screen. The mesh decides how finely the disk is sampled. The air properties describe what it turns in. Two further settings, ...
- **Proposed:** Two unrelated groups of settings share this block on screen. The mesh decides how finely the disk is sampled. The air properties describe the medium the disk turns in. Two further settings, the kinematic viscosity and the convergence history, have no control on the tab and are documented at the end of the section because they belong to the same group in the project file.

### ¶4 "Both are integers of at least 1..." (L6271)
- **Rules broken:** G6 (second clause drops the verb)
- **Setting:** GUI: Config/Engine tab
- **Current:** Both are integers of at least $1$, the azimuthal count up to $720$. A purely axisymmetric case is hover, ...
- **Proposed:** Both are integers of at least $1$, and the azimuthal count can go up to $720$. A purely axisymmetric case is hover, or any climb or descent with no in-plane component. In such a case, every azimuthal station returns the same answer. Therefore, $N_\psi=1$ solves the problem exactly. Raising it costs time and changes nothing. In forward flight the azimuthal count is what resolves the once-per-revolution variation, and it must be raised accordingly. With dynamic stall active it also sets how many harmonics of the separation cycle can be represented, so it needs to be at least twice the highest harmonic that matters.

### ¶5 "Comparing a rotor at two altitudes..." (L6301)
- **Rules broken:** G9 ("Comparing" used as a verb form instead of an instruction)
- **Setting:** GUI: Config/Engine tab
- **Current:** ... The default $1.225$ is the standard sea-level value. Comparing a rotor at two altitudes means changing this field and nothing else.
- **Proposed:** Use the value for the altitude and temperature being studied, in kg/m³. The default $1.225$ is the standard sea-level value. To compare a rotor at two altitudes, change this field and nothing else.

### ¶6 "with $W$ the relative velocity..." (L6322)
- **Rules broken:** G24, G4 ("occurring" participle clause)
- **Setting:** none (prose)
- **Current:** with $W$ the relative velocity at that element, the largest value occurring at the advancing tip.
- **Proposed:** where $W$ is the relative velocity at that element. The largest value occurs at the advancing tip.

### ¶7 "That record is what the convergence plot..." (L6390)
- **Rules broken:** G8, G3 ("is told apart" is a passive phrasal verb)
- **Setting:** none (prose)
- **Current:** ... That record is what the convergence plot in the Results tab draws, and it is how a case that converged slowly is told apart from one that converged immediately. Keeping it costs memory ...
- **Proposed:** During a solve, the model can record the residual at every iteration. That record is what the convergence plot in the Results tab draws, and it distinguishes a case that converged slowly from one that converged immediately. Keeping it costs memory proportional to the number of iterations and conditions, which only matters for a very large batch.

### ¶8 "The Convergence view of the Results tab..." (L6399)
- **Rules broken:** P1 (two sequential instructions in one sentence)
- **Setting:** .bemt key collect_history in config.bemt
- **Current:** ... which writes <code>collect_history=true</code> into the open project; run the case again afterwards to record a history, and save the project to keep the setting. Nothing turns the switch on by itself ...
- **Proposed:** <span class="gui">GUI</span>: no field of this tab. The Convergence view of the Results tab carries an <i>Enable convergence history</i> button, which writes <code>collect_history=true</code> into the open project. Run the case again afterwards to record a history. Save the project to keep the setting. Nothing turns the switch on by itself for a run started from the <span class="gui">GUI</span>.

### ¶9 "In all three the mean..." (L6427)
- **Rules broken:** G4 ("has already been found" is a compound tense built into a passive)
- **Setting:** none (prose)
- **Current:** In all three the mean $\lambda_{i,0}$ has already been found by the annular momentum balance, and the harmonic is then applied to it in closed form, which is why they cost almost nothing.
- **Proposed:** In all three, the annular momentum balance supplies the mean $\lambda_{i,0}$, and the harmonic is then applied to it in closed form, which is why they cost almost nothing.

### ¶10 Table cell, glauert_local (L6481)
- **Rules broken:** G6 ("The textbook baseline." drops the verb; the cell is a prose sentence, not a label)
- **Setting:** .bemt key glauert_local in config.bemt
- **Current:** The classical first-harmonic tilt correction, with no separate longitudinal and lateral weights. The textbook baseline.
- **Proposed:** The classical first-harmonic tilt correction, with no separate longitudinal and lateral weights. It is the textbook baseline.

### ¶11 "Projects written before the coupling selector..." (L6527)
- **Rules broken:** G14
- **Setting:** .bemt key inflow_field_model in config.bemt
- **Current:** ... Projects written before the coupling selector was removed may still hold a value ending in <code>_global</code>; opening such a project reports it, and editing anything in the tab stores the supported value instead.
- **Proposed:** <span class="bemt">.bemt</span>: the key <code>inflow_field_model</code> in <code>config.bemt</code>, default <code>"coleman_local"</code>. Projects written before the coupling selector was removed may still hold a value ending in <code>_global</code>. Opening such a project reports the value, and editing anything in the tab stores the supported value instead.

### ¶12 "Transient Pitt-Peters" (L6541)
- **Rules broken:** P1 (two sequential actions in one imperative)
- **Setting:** GUI: Config/Engine tab (Inflow model control)
- **Current:** ... To march the Pitt-Peters states, open the Transient Simulation tool and define a maneuver. That tool carries the state from one time sample to the next ...
- **Proposed:** The Inflow model control configures a steady operating point. It does not start a time march. To march the Pitt-Peters states, open the Transient Simulation tool. In that tool, define a maneuver. The tool carries the state from one time sample to the next and reports a time history. It does not convert a transient trajectory into a steady result by averaging it.

### ¶13 "Leave all three at their defaults..." (L6562)
- **Rules broken:** P3 (condition buried after the command, twice); see also the structural defect below for the broken math that follows
- **Setting:** GUI: Config/Engine tab
- **Current:** Leave all three at their defaults. Raise the outer iteration count if a case reports that the states did not settle, and lower the relaxation if they oscillate instead of converging. The model solves the three states $u_0$, $u_s$ and $u_c$.
- **Proposed:** Leave all three at their defaults. If a case reports that the states did not settle, raise the outer iteration count. If the states oscillate instead of converging, lower the relaxation. The model solves the three states $\nu_0$, $\nu_s$ and $\nu_c$.

### ¶14 "This is one of the perturbation inputs..." (L6586)
- **Rules broken:** G14
- **Setting:** none (prose)
- **Current:** This is one of the perturbation inputs of a stability-derivative study; per condition, the angle travels inside the saved case instead (see Section 10.9). The default of zero leaves every solve untouched.
- **Proposed:** This is one of the perturbation inputs of a stability-derivative study. Per condition, the angle travels inside the saved case instead (see <a class="xref" href="#sec-perturbation-inputs" title="10.9 Perturbation inputs: sideslip and hub rates">Section 10.9</a>). The default of zero leaves every solve untouched.

### ¶15 "this engine field stays at zero on screen..." (L6595)
- **Rules broken:** G14
- **Setting:** GUI: Config/Engine tab
- **Current:** <span class="gui">GUI</span>: this engine field stays at zero on screen; a case-specific sideslip is a property of the saved case, which carries it through every surface a case reaches.
- **Proposed:** <span class="gui">GUI</span>: this engine field stays at zero on screen. A case-specific sideslip is a property of the saved case, which carries it through every surface a case reaches.

### ¶16 "The escaping flow rolls up into the tip vortex..." (L6611)
- **Rules broken:** G8
- **Setting:** none (prose)
- **Current:** ... The escaping flow rolls up into the tip vortex, and the lift the section actually produces is less than a two-dimensional calculation predicts.
- **Proposed:** The escaping flow concentrates into the tip vortex, and the lift the section actually produces is less than a two-dimensional calculation predicts.

### ¶17 "Both corrections here relax the same assumption..." (L6684)
- **Rules broken:** G31 ("aerofoil"; the document elsewhere uses "airfoil")
- **Setting:** GUI: Config/Engine tab
- **Current:** Both corrections here relax the same assumption: that each blade section behaves like an isolated two-dimensional aerofoil. They act on different coefficients ...
- **Proposed:** Both corrections here relax the same assumption: that each blade section behaves like an isolated two-dimensional airfoil. They act on different coefficients and do not overlap, so they are enabled separately. Rotational augmentation raises lift near the root. The radial-flow correction resolves the drag along the total relative wind, which raises the profile power and the hub force.

### ¶18 "Himmelskamp observed in 1945..." (L6690)
- **Rules broken:** G31 ("the same aerofoil"), G9 ("the same section not rotating")
- **Setting:** none (prose)
- **Current:** Himmelskamp observed in 1945 that a rotating blade sustains section lift coefficients higher than the same aerofoil ever reaches in a wind tunnel ... a pressure gradient that delays separation compared with the same section not rotating at the same angle.
- **Proposed:** Himmelskamp observed in 1945 that a rotating blade sustains section lift coefficients higher than the same airfoil ever reaches in a wind tunnel, and that the excess is concentrated near the root. The mechanism is centrifugal pumping. Rotation drives the boundary layer outwards along the span, and the Coriolis force acting on that outward flow sets up a pressure gradient that delays separation compared with the same section held stationary at the same angle. The blade therefore holds attached flow past the angle at which the static polar says it should have stalled.

### ¶19 "Every factor earns its place." (L6708)
- **Rules broken:** G1 (personifying, conversational); remainder of paragraph is compliant
- **Setting:** none (prose)
- **Current:** Every factor earns its place. The ratio $\lambda_r$ compares the local rotational speed with the inflow through the disk: ...
- **Proposed:** Each factor in the expression has a distinct role. The ratio $\lambda_r$ compares the local rotational speed with the inflow through the disk: where rotation dominates, as at the root in hover, the weight saturates at one. Where the inflow dominates, as at the tip or at high advance ratio, it vanishes and the two-dimensional value is recovered. The $(c/r)^{2}$ factor concentrates the effect inboard.

### ¶20 "The bracket is the important one..." (L6713)
- **Rules broken:** G4 ("has already taken away"), G8 ("taken away", "switches ... off")
- **Setting:** none (prose)
- **Current:** ... which is precisely the lift that separation has already taken away. ... Finally $g(\alpha)$ switches the term off above roughly $60^\circ$, where the semi-empirical fit stops being representative.
- **Proposed:** The bracket is the important one. It is the gap between the attached lift line and the actual static curve, which is precisely the lift that separation has removed. The correction is therefore <b>identically zero while the flow stays attached</b>, and grows only once the section has begun to stall. That is why enabling it changes nothing on a lightly loaded rotor: there is no deficit to restore. Finally $g(\alpha)$ disables the term above roughly $60^\circ$, where the semi-empirical fit stops being representative.

### ¶21 "It is a friction force..." (L6759–6764)
- **Rules broken:** G15 (em-dash joining two ideas)
- **Setting:** none (prose)
- **Current:** It is a friction force, generated in the boundary-layer, and it acts along the <i>total</i> relative wind &mdash; part of which runs along the blade, sweeping the boundary-layer spanwise as it goes.
- **Proposed:** It is a friction force, generated in the boundary-layer, and it acts along the <i>total</i> relative wind. Part of that wind runs along the blade, and sweeps the boundary layer spanwise as it goes.

### ¶22 "The spanwise part..." (L6769)
- **Rules broken:** G22 (final sentence runs to about 40 words with three clauses)
- **Setting:** none (prose)
- **Current:** The spanwise part, $\tfrac{1}{2}\rho c\,C_d\lvert\vec{U}\rvert U_R$, has no arm about the shaft, so it adds nothing at all to torque or to power, but it does push the rotor backwards and so enters the hub forces.
- **Proposed:** The spanwise part, $\tfrac{1}{2}\rho c\,C_d\lvert\vec{U}\rvert U_R$, has no arm about the shaft, so it adds nothing at all to torque or to power. However, it does push the rotor backwards, and so enters the hub forces.

### ¶23 "Adding back the work the free stream does..." (L6782)
- **Rules broken:** G14
- **Setting:** none (prose)
- **Current:** ... turns the second of these into a dissipated profile power of $(1+4.5\,\mu^{2})$, which is the classical $(1+4.65\,\mu^{2})$ of the helicopter literature; the small remainder is the root and reverse-flow region that the closed form ignores and this engine integrates directly. A correction that lowers the profile power ...
- **Proposed:** Adding back the work the free stream does on the rotor turns the second of these into a dissipated profile power of $(1+4.5\,\mu^{2})$, which is the classical $(1+4.65\,\mu^{2})$ of the helicopter literature. The small remainder is the root and reverse-flow region that the closed form ignores and this engine integrates directly. A correction that <i>lowers</i> the profile power is the signature of a model that rescales the drag coefficient instead of resolving the drag vector.

### ¶24 "It matters where $W$ collapses..." (L6795)
- **Rules broken:** G8 ("run away"), G31 ("the disc"; this page uses "disk" everywhere else)
- **Setting:** GUI: Config/Engine tab
- **Current:** It matters where $W$ collapses and that ratio would otherwise run away: near the blade root, and inside the reverse-flow region on the retreating side. Over the rest of the disc the local yaw angle stays well below any sensible ceiling and the value changes nothing.
- **Proposed:** It matters where $W$ collapses, because there the ratio would grow without bound: near the blade root, and inside the reverse-flow region on the retreating side. Over the rest of the disk the local yaw angle stays well below any sensible ceiling, and the value changes nothing. Leave it at $60$ degrees unless there is a specific reason to change it.

### ¶25 "a small $\omega$ is stable but slow..." (L6889)
- **Rules broken:** G6 ("a large one fast until it overshoots" drops the verb)
- **Setting:** none (prose)
- **Current:** ... which states the trade directly: a small $\omega$ is stable but slow, a large one fast until it overshoots and oscillates.
- **Proposed:** and its error shrinks by roughly $|1-\omega(1-g')|$ each iteration, which states the trade directly: a small $\omega$ is stable but slow, and a large one is fast until it overshoots and oscillates.

### ¶26 "Solver convergence troubleshooting" boxed note (L6909)
- **Rules broken:** G9 ("operating", "yielding"), G14 (semicolon-separated causes), G21 (three causes buried in a prose line), G32 ("typically stems from underlying formulation discontinuities" is vaguer than the mechanism list that follows)
- **Setting:** none (prose)
- **Current:** Numerical stagnation typically stems from underlying formulation discontinuities rather than the root-finding algorithm itself. Common causes include: (1) operating beyond the angle-of-attack bounds of a static polar (yielding zero gradient ...); (2) unmitigated reverse-flow discontinuities across the $U_T = 0$ boundary. Or (3) derivative discontinuities in non-smooth stall models. Recommended remedies are ...
- **Proposed:** Numerical stagnation usually comes from a discontinuity in the formulation, not from the root-finding algorithm itself. The common causes are three. Operating beyond the angle-of-attack bounds of a static polar gives a zero gradient, $g'(\lambda_{total}) = 0$. Reverse flow without blending is discontinuous across the $U_T = 0$ boundary. Non-smooth stall models carry derivative discontinuities. The corresponding remedies are to enable a 360&deg; polar extension (<a class="xref" href="#cap-3-2-4" title="8.2.4 Full-range extension and blend width">Section 8.2.4</a>), to apply continuous reverse-flow blending (<a class="xref" href="#cap-3-4" title="8.4 Reverse flow">Section 8.4</a>), or to select a smooth stall formulation. Increasing the maximum iteration limit is effective only when the residuals show steady, monotonic decay.

### ¶27 ".bemt" key lists and the CLI slash (L6573, L6984)
- **Rules broken:** G14 (semicolon-separated key lists read as joined sentences, L6573; the same pattern at L7009), G26 ("<code>--relax-schedule</code> / <code>--no-relax-schedule</code>", a joining slash in prose, L6984)
- **Setting:** CLI: --relax / --relax-schedule
- **Current (L6984):** <span class="cli">CLI</span>: <code>--relax X</code> and <code>--relax-schedule</code> / <code>--no-relax-schedule</code>. The five schedule parameters have no flags of their own. Set them with <code>--set</code>, for example <code>--set config.relax_root_factor=0.15</code>.
- **Proposed (L6984):** <span class="cli">CLI</span>: <code>--relax X</code>, and <code>--relax-schedule</code> or <code>--no-relax-schedule</code>. The five schedule parameters have no flags of their own. Set them with <code>--set</code>, for example <code>--set config.relax_root_factor=0.15</code>. (For L6573 and L7009, replacing the semicolons between key entries with periods, ending each at its default value, is sufficient; the equation, defaults and key names stay unchanged.)

## Section 10 — Run Case (anchor: sec-10-run-case)
- Paragraphs reviewed: 75 | OK: 63 | Proposals: 12

### ¶1 "Helicopter cruise falls roughly between..." (L7130)
- **Rules broken:** G22, G3 ("should be read")
- **Setting:** GUI: Run Case tab
- **Current:** Helicopter cruise falls roughly between $\mu_x=0.15$ and $\mu_x=0.35$. Above about $\mu_x=0.5$ a large part of the retreating side is in reverse flow, and the result should be read with that in mind rather than taken at face value.
- **Proposed:** Helicopter cruise falls roughly between $\mu_x=0.15$ and $\mu_x=0.35$. Above about $\mu_x=0.5$ a large part of the retreating side is in reverse flow. Read the result with that in mind, rather than taking it at face value. For a <b>propeller</b> in straight and level cruise, set this row to zero: $V_z=0$, or equivalently $\mu_z=0$ or $\alpha_{disk}=0^\circ$. Give it a non-zero value only to model a genuine cross-flow, such as a crosswind or a climb at an angle to the shaft.

### ¶2 "When editing a file by hand..." (L7147)
- **Rules broken:** G9 ("When editing" is "-ing" as a verb form)
- **Setting:** .bemt key J_x
- **Current:** ... a file containing <code>J_x</code> has that entry reported as an unknown key and ignored, and the field falls back to its default of $0.0$. When editing a file by hand, convert those to the ratio first.
- **Proposed:** ... a file containing <code>J_x</code> has that entry reported as an unknown key and ignored, and the field falls back to its default of $0.0$. When you edit a file by hand, convert those forms to the ratio first.

### ¶3 "The ANGLE is the exception..." (L7157)
- **Rules broken:** G1 ("ANGLE", "REFUSED" — all-caps shouting in prose), G3 ("is REFUSED ... rather than resolved by guessing")
- **Setting:** .bemt key alpha_disk_deg; CLI: --alpha-disk-deg
- **Current:** The ANGLE is the exception, and the only one. ... A condition that gives the angle together with a nonzero ratio, or that gives both angles at once, is REFUSED when the project is opened rather than resolved by guessing which of the two was meant.
- **Proposed:** The angle is the exception, and the only one. A condition may set <code>alpha_disk_deg</code> instead of the ratio, exactly as the command line accepts <code>--alpha-disk-deg</code>. It is measured from the shaft, so it is the along-shaft component that is the known one and the in-plane one that is derived from it: $\mu_x=\tan(\alpha_{disk})\,|V_z|/(\Omega R)$. The angle is an input form only: what the file keeps after the next save is still the ratio, so no component ever has two stored values that can disagree. Because the conversion needs the tip speed, a condition that gives the angle must also give an <code>rpm</code>, and the project's geometry must have a radius. On opening, the application refuses a condition that gives the angle together with a nonzero ratio, or that gives both angles at once; it does not guess which of the two was meant.

### ¶4 "Specifying multiple mutually exclusive flags..." (L7169)
- **Rules broken:** G9 ("Specifying"), G12 ("reference tip speed" without article)
- **Setting:** CLI: --mu-inplane / --j-inplane / --v-inplane / --alpha-disk-deg
- **Current:** ... Specifying multiple mutually exclusive flags raises an input error. Dimensional velocity (<code>--v-inplane</code>) and angle (<code>--alpha-disk-deg</code>) require <code>--rpm</code> to compute reference tip speed.
- **Proposed:** <span class="cli">CLI</span>: define in-plane flow using exactly one of <code>--mu-inplane X</code>, <code>--j-inplane X</code>, <code>--v-inplane X</code>, or <code>--alpha-disk-deg X</code>. More than one mutually exclusive flag raises an input error. The dimensional velocity (<code>--v-inplane</code>) and the angle (<code>--alpha-disk-deg</code>) require <code>--rpm</code>, because both need the tip speed for the conversion.

### ¶5 "The disk adds an induced velocity..." (L7200)
- **Rules broken:** G30 ("what the blade elements actually see" gives the elements a human sense; the rule's own counter-example is "the flow the airfoil sees")
- **Setting:** none (prose)
- **Current:** The disk adds an induced velocity $v_i$ to whatever is already flowing along the shaft, and the total is what the blade elements actually see:
- **Proposed:** <b>The mathematics.</b> The disk adds an induced velocity $v_i$ to whatever is already flowing along the shaft, and the total is the local flow at each blade element:

### ¶6 "where the leading minus sign is the convention..." (L7208)
- **Rules broken:** G1 ("POSITIVE" in caps), G22 (the parent sentence runs long), G3 ("is written")
- **Setting:** none (prose)
- **Current:** where the leading minus sign is the convention, not an accident of the algebra: the disk angle of attack is written the way a wing's is, POSITIVE when the free stream arrives from <b>below</b> the disk.
- **Proposed:** where the leading minus sign is the convention, not an accident of the algebra. The disk angle of attack follows the convention of a wing: it is positive when the free stream arrives from <b>below</b> the disk.

### ¶7 "Every along-shaft quantity of this row..." (L7219)
- **Rules broken:** G15 (em-dash parenthetical pair), G1 ("SAME", "NEGATIVE" in caps), G21 (three operating instructions in one sentence could stand as three sentences)
- **Setting:** GUI: Run Case tab (axial field)
- **Current:** Every along-shaft quantity of this row &mdash; $V_z$, $\lambda_z$, $\mu_z$ and $J_z$ &mdash; is positive in the SAME direction, ... For a <b>rotor</b>, leave it at zero for hover and for level forward flight, use a positive value in m/s to model a climb (equivalently a NEGATIVE $\alpha_{rotor}$), and a negative one to model a descent (a positive $\alpha_{rotor}$).
- **Proposed:** <b>Configuration and sign convention.</b> Every along-shaft quantity of this row ($V_z$, $\lambda_z$, $\mu_z$ and $J_z$) is positive in the same direction, the one the induced velocity acts in, which is why $\lambda_{total}=\lambda_z+\lambda_i$ above is a sum. The angle is the one entry written the other way round, for the reason given under the mathematics. For a <b>rotor</b>, leave it at zero for hover and for level forward flight. Use a positive value in m/s to model a climb, which is a negative $\alpha_{rotor}$. Use a negative value to model a descent, which is a positive $\alpha_{rotor}$. A descent in the band between roughly $-2v_h$ and zero, where $v_h$ is the hover induced velocity, falls in the region where momentum theory has no valid solution, and results there are unreliable no matter how fine the mesh or how tight the tolerance. For a <b>propeller</b> this is where the airspeed belongs, most naturally entered as $J_x$: zero represents the static case, and cruise typically falls between $J_x=0.6$ and $J_x=1.2$.

### ¶8 "If thrust stops rising..." (L7289)
- **Rules broken:** G9 ("the solver having failed" is an "-ing" verb form)
- **Setting:** GUI: Run Case tab (collective)
- **Current:** If thrust stops rising as the collective is increased, the blade has stalled rather than the solver having failed, and the polar and the stall settings are the place to look.
- **Proposed:** If thrust stops rising as the collective is increased, the cause is blade stall, not a solver failure. The polar and the stall settings are the place to look. In a trim run the collective is the quantity being solved for, so the value entered is only a starting guess.

### ¶9 "Collective pitch is the same at every azimuth..." (L7307)
- **Rules broken:** G14 (semicolon), G30 ("the pitch the blade sees"; per G30, a blade does not see)
- **Setting:** GUI: Run Case tab (cyclic pitch)
- **Current:** Collective pitch is the same at every azimuth; cyclic pitch varies once per revolution as $\theta_{1c}\cos\psi+\theta_{1s}\sin\psi$ on top of it. Because the pitch the blade sees now depends on where the blade is, cyclic pitch tilts the blade response: ...
- **Proposed:** Collective pitch is the same at every azimuth. Cyclic pitch varies once per revolution as $\theta_{1c}\cos\psi+\theta_{1s}\sin\psi$ on top of it. Because the local pitch now depends on where the blade is, cyclic pitch tilts the blade response: it is the control that holds the disk where it should be.

### ¶10 "The flap freedom itself is configured on another page..." (L7312)
- **Rules broken:** G14 (semicolon); G24 ("With flap freedom enabled" is a borderline with-absolute)
- **Setting:** GUI: Geometry tab (Blade Dynamics block)
- **Current:** ... On a fully rigid blade the angles still enter as azimuthal pitch, but no blade responds to them dynamically, so the fields stay disabled there. The flap freedom itself is configured on another page; see the Blade Dynamics block of this project's Geometry tab.
- **Proposed:** ... On a fully rigid blade the angles still enter as azimuthal pitch, but no blade responds to them dynamically, so the fields stay disabled there. The flap freedom itself is configured on another page. See the Blade Dynamics block of this project's Geometry tab.

### ¶11 "In the GUI: the Run Case tab carries all three..." (L7461)
- **Rules broken:** G15 (em-dash pair used as a parenthesis inside the sentence), G22 (the sentence runs to about 40 words)
- **Setting:** GUI: Run Case tab (sideslip, roll rate, pitch rate)
- **Current:** In the <span class="gui">GUI</span>: the Run Case tab carries all three beside the cyclic pitch of the condition block &mdash; <i>Sideslip ψ<sub>w</sub></i>, <i>Roll rate p</i> and <i>Pitch rate q</i> &mdash; and a saved case stores whatever is on screen, so the values travel into batches, comparisons and the derivative studies exactly like any other input.
- **Proposed:** In the <span class="gui">GUI</span>: the Run Case tab carries all three beside the cyclic pitch of the condition block, as the fields <i>Sideslip ψ<sub>w</sub></i>, <i>Roll rate p</i> and <i>Pitch rate q</i>. A saved case stores whatever is on screen, so the values travel into batches, comparisons and the derivative studies exactly like any other input.

### ¶12 "From the CLI: a saved case is data..." (L7473)
- **Rules broken:** G14 (semicolon), G30 adjacent ("a rotor ... still feels their aerodynamic effect" at L7457 — "feels" gives the rotor a human sense)
- **Setting:** CLI: --set config.inflow_sideslip_deg
- **Current:** From the <span class="cli">CLI</span>: a saved case is data, so the perturbation inputs travel with it wherever the case is used; the engine-side carrier accepts <code>--set config.inflow_sideslip_deg</code> directly, which sets the sideslip for every condition of the project at once.
- **Proposed:** From the <span class="cli">CLI</span>: a saved case is data, so the perturbation inputs travel with it wherever the case is used. The engine-side carrier accepts <code>--set config.inflow_sideslip_deg</code> directly, which sets the sideslip for every condition of the project at once. (At L7457, similarly: "a rotor with no flap freedom still shows their aerodynamic effect.")

## Structural defects (appendix items)
- **L6565–6568 (¶ in 9.2.1):** the math is mangled by hard line breaks — "the three states $\n u_0$, $\n u_s$ and $\n u_c$". The line breaks fall inside the math delimiters, and the symbols should be $\nu_0$, $\nu_s$, $\nu_c$ to match the states $\boldsymbol\nu=(\nu_0,\nu_s,\nu_c)$ defined one paragraph earlier (L6551). This is a rendering/correctness defect, not only style.
- **L6913–6916 (boxed note, 9.5.1):** the cause list is formatted as inline "(1) ... ; (2) ... . Or (3) ...", with a sentence-initial "Or" connecting a list item. The list should either be punctuated as a plain series with "and" before the last item or — given G21 — be broken out; see ¶26 in Section 9 above.
- **L6938 onwards to end of chapter 9:** the indentation of the source block shifts to a deeper level (extra leading spaces from L6938 to L7476). Cosmetic only in the render, but it makes the two halves of the chapter diverge in the source.
- **L6219 and L7049 (generated field-index boxes):** the sentence "The sections below are self-contained and use the same explanations as the field Help in the window." is compliant; no action.
- **L6485–6502 (option table):** the table cells in the remaining rows are sentence fragments ("Negligible", "The longitudinal harmonic in closed form: ..."). Fragments are tolerable inside tables, but the mixed pattern — full sentences in some cells, fragments in others of the same column (notably "The default." at L6859 and "An inner iteration per case" at L6501) — makes the tables inconsistent. Only the glauert_local cell (¶10 above) is flagged as a hard G6 violation, because it is a standalone statement, not row data.

---

# Block G: chapters 11–12 (lines 7481–8630)

## Section 11 — Run Batch (anchor: sec-11-run-batch)
- Paragraphs reviewed: 65 | OK: 33 | Proposals: 32

### ¶1 "The Run Batch tab solves..." (L7483)
- **Rules broken:** G3 (is held fixed, is entered by hand — actor known), G22 (third sentence two embedded relative clauses).
- **Setting:** none (prose)
- **Current:** The Run Batch tab solves a list of flight conditions one after another. Everything except the condition is held fixed, so the results are directly comparable and the list becomes a sweep. The tab builds that list in two ways, which can be combined: a factorial sweep, which generates the list from the values given on up to three axes, and an explicit list, in which each condition is entered by hand. Both fill the same queue, and the queue is what runs.
- **Proposed:** The Run Batch tab solves a list of flight conditions one after another. It holds everything except the condition fixed, so the results are directly comparable and the list becomes a sweep. The tab builds the list in two ways, which can be combined. A factorial sweep generates the list from the values given on up to three axes. An explicit list enters each condition by hand. Both fill the same queue, and the queue is what runs.

### ¶2 "The four quantities a batch sweeps..." (L7489)
- **Rules broken:** G22 (first sentence about 40 words with a long parenthesis), G27 (needed fact in a 17-word parenthesis).
- **Setting:** none (prose)
- **Current:** The four quantities a batch sweeps (the in-plane component of the flow, the along-shaft component, the collective and the rotational speed) are exactly the four that define a single case, and they mean the same thing here as there. …
- **Proposed:** The four quantities that a batch sweeps are the in-plane component of the flow, the along-shaft component, the collective and the rotational speed. They are exactly the four that define a single case, and they mean the same thing here as there. This chapter therefore documents what a batch does with them: how a queue is generated, what the unswept values do to the answer, and where the results go. Chapter 10 gives the physics of each of the four quantities, its units, its sign convention and its valid range once, and this chapter does not repeat them.

### ¶3 figcaption "The Run Batch tab. The sweep axes..." (L7499)
- **Rules broken:** G6 (second coordinate clause drops its verb).
- **Setting:** none (prose)
- **Current:** …The sweep axes and the fixed values are at the top, the resulting queue below them, and the export controls at the bottom.
- **Proposed:** The Run Batch tab. The sweep axes and the fixed values are at the top, the resulting queue is below them, and the export controls are at the bottom.

### ¶4 "Set the values on each axis..." (L7520, list item 2)
- **Rules broken:** P1 (two sequential steps merged).
- **Setting:** GUI: sweep axis fields, Total cases counter, Replace queue
- **Current:** Set the values on each axis and check the **Total cases** counter. …
- **Proposed:** Set the values on each axis. Then check the **Total cases** counter. Generating a list runs no physics, so it is immediate and can be repeated freely. **Replace queue** discards the current queue before generating. Leaving it unchecked adds to what is already there.

### ¶5 "Review the queue..." (L7529, list item 4)
- **Rules broken:** G3/G6 (can be removed, the whole queue cleared telegraphic passive, actors known).
- **Setting:** GUI: queue list, Remove/Clear
- **Current:** Review the **queue**. Individual rows can be removed and the whole queue cleared. A queue worth repeating can be saved under a name before it is run.
- **Proposed:** Review the **queue**. Remove individual rows or clear the whole queue. Save a queue worth repeating under a name before you run it.

### ¶6 "Press Run. Conditions are solved..." (L7531, list item 5)
- **Rules broken:** G3 (are solved — actor known).
- **Setting:** GUI: Run button, progress bar, Cancel
- **Current:** Press **Run**. Conditions are solved one at a time, with a progress bar and a status row per condition, and the GUI stays usable throughout. …
- **Proposed:** Press **Run**. The program solves the conditions one at a time, with a progress bar and a status row per condition, and the GUI stays usable throughout. **Cancel** stops the run after the condition in progress.

### ¶7 "A batch normally runs every generated condition..." (L7543)
- **Rules broken:** G3 (can be mistaken — actor known).
- **Setting:** none (prose)
- **Current:** …so when the load drifts during a sweep, the extra loading can be mistaken for a worse design.
- **Proposed:** …It also removes loading as a confounder between configurations: a rotor making more thrust always draws more power, so when the load drifts during a sweep, the user can mistake the extra loading for a worse design.

### ¶8 "Every condition in the queue is trimmed..." (L7561)
- **Rules broken:** G3 (is trimmed, is carried over — actor known).
- **Setting:** none (prose)
- **Current:** Every condition in the queue is trimmed independently against the same target, and no solution is carried over from one condition to the next, so the queue stays a set of well-defined operating points.
- **Proposed:** The trim loop trims every condition in the queue independently against the same target. It carries no solution over from one condition to the next. The queue therefore stays a set of well-defined operating points.

### ¶9 "With either solving mode..." (L7576)
- **Rules broken:** G22 (two sentences of about 40 words), G2.
- **Setting:** GUI: Target is / Target fields; .bemt trim
- **Current:** With either solving mode, Target is chooses whether the target is a dimensional thrust in newtons or the dimensionless $C_T$, and Target carries its value, from -1000000000 to 1000000000 with six decimals and a default of 0.1. While a solving mode is active, the quantity being solved stops being offered as an input: its fixed-value row hides, and an axis pointed at it returns to (none), because sweeping precisely the quantity the loop overwrites would produce a queue whose swept values are discarded. A solved condition costs several complete solves, because the loop bisects, so a trimmed batch multiplies the runtime by roughly ten.
- **Proposed:** With either solving mode, Target is chooses whether the target is a dimensional thrust in newtons or the dimensionless $C_T$. Target carries its value, from -1000000000 to 1000000000 with six decimals and a default of 0.1. While a solving mode is active, the quantity being solved stops being offered as an input. Its fixed-value row hides, and an axis pointed at it returns to (none): sweeping precisely the quantity the loop overwrites would produce a queue whose swept values are discarded. A solved condition costs several complete solves, because the loop bisects. A trimmed batch therefore multiplies the runtime by roughly ten.

### ¶10 "In the .bemt file, the setting rides..." (L7592)
- **Rules broken:** G8/G1 (rides with — informal phrasal verb).
- **Setting:** .bemt key trim in sweep_params of batches.bemt
- **Current:** In the .bemt file, the setting rides with the batch inside sweep_params of batches.bemt, under the key trim, …
- **Proposed:** In the .bemt file, the setting is stored with the batch inside sweep_params of batches.bemt, under the key trim, …

### ¶11 "A factorial sweep answers the question..." (L7609)
- **Rules broken:** G3 (can be swept — actor known).
- **Setting:** none (prose)
- **Current:** …Four quantities can be swept: the in-plane component of the flow, the along-shaft component, the collective, and the rotational speed. …
- **Proposed:** …A batch can sweep four quantities: the in-plane component of the flow, the along-shaft component, the collective, and the rotational speed. They are the same four quantities that define a single case, which is why a batch needs no settings of its own beyond the values to sweep.

### ¶12 "Each axis offers the same choice..." (L7623)
- **Rules broken:** G3 (are typed).
- **Setting:** GUI axis_unit
- **Current:** …and the choice affects only how the values are typed.
- **Proposed:** …and the choice affects only how the user types the values.

### ¶13 "Configuration and valid combinations..." (L7654)
- **Rules broken:** G3 (is swept, is ignored, can never be both swept and held), P1 (Start … then refine merged).
- **Setting:** .bemt axis_values / axes
- **Current:** …A quantity used as an axis is swept and its fixed field is ignored, so the same quantity can never be both swept and held. Start with a coarse sweep to see the shape of the answer, then refine the range that matters: a batch is cheap to define and expensive to run.
- **Proposed:** …When a quantity becomes an axis, the sweep sets it and ignores its fixed field, so the same quantity can never be both swept and held. Start with a coarse sweep to see the shape of the answer. Then refine the range that matters: a batch is cheap to define and expensive to run.

### ¶14 "In the GUI, the Factorial sweep block..." (L7660)
- **Rules broken:** G3 (is set to, is not offered), G22.
- **Setting:** GUI Factorial sweep / fill / axis_quantity / axis_unit / range_*
- **Current:** In the GUI, the Factorial sweep block shows one row per axis, each with a quantity dropdown that also switches the axis off with (none), a unit dropdown for the two flow quantities, and the list of values. Beside each list, three small fields (from, to, step) and a fill button generate an evenly spaced list into it: pressing fill replaces the list with every value from from to to, spaced by step, both bounds included. The three fields adapt to a default range for whichever quantity the row is set to, so a fill written for an advance ratio is not offered to a sweep in degrees or in rev/min.
- **Proposed:** In the GUI, the Factorial sweep block shows one row per axis. Each row holds a quantity dropdown that also switches the axis off with (none), a unit dropdown for the two flow quantities, and the list of values. Beside each list, three small fields (from, to, step) and a fill button generate an evenly spaced list: pressing fill replaces the list with every value from from to to, spaced by step, both bounds included. The three fields adapt to a default range for the quantity of the row, so a fill written for an advance ratio does not appear for a sweep in degrees or in rev/min.

### ¶15 "In the .bemt file, a generated queue is stored..." (L7671)
- **Rules broken:** G3 (is stored, How the list was produced is recorded).
- **Setting:** .bemt conditions / sweep_kind / sweep_params
- **Current:** In the .bemt file, a generated queue is stored as ordinary conditions, not as a formula. … How the list was produced is recorded alongside it in sweep_kind and sweep_params (…Section 11.5).
- **Proposed:** In the .bemt file, the batch stores a generated queue as ordinary conditions, not as a formula. Each entry of conditions in batches.bemt is a complete flight condition with the same keys as a saved case, so a batch introduces no new keys. The keys sweep_kind and sweep_params record alongside the list how the sweep produced it (Section 11.5).

### ¶16 "From the CLI, there are no flags..." (L7679)
- **Rules broken:** G14 (semicolon), G4 (has already been saved — compound tense).
- **Setting:** CLI --from-bemt-batch NAME, --list-batches
- **Current:** …A factorial sweep is generated in the GUI; from the command line, run a batch that has already been saved, with --from-bemt-batch NAME. …
- **Proposed:** …A factorial sweep is generated in the GUI. From the command line, run a batch saved earlier with --from-bemt-batch NAME. --list-batches prints the names available in the project and exits.

### ¶17 "The three controls of one axis..." (L7686)
- **Rules broken:** G14 (semicolon), G3 (are never read by the sweep).
- **Setting:** .bemt range_from / range_to / range_step / axis_values
- **Current:** …in steps of range_step; those three prepare what fill will write and are never read by the sweep themselves.
- **Proposed:** …in steps of range_step. Those three fields prepare what fill will write, and the sweep itself never reads them.

### ¶18 "A collective sweep at 600 rev/min..." (L7719)
- **Rules broken:** G14 (comma splice with erroneous capital: "divided by, It also doubles"), G3 (are divided by).
- **Setting:** none (prose)
- **Current:** Doubling $\Omega$ quadruples the dynamic pressure the loads are divided by, It also doubles the local Reynolds and Mach numbers. Therefore, zBEMT reads the section polars at a different place.
- **Proposed:** Doubling $\Omega$ quadruples the dynamic pressure that divides the loads. It also doubles the local Reynolds and Mach numbers. Therefore, zBEMT reads the section polars at a different place.

### ¶19 "The in-plane advance ratio is the most..." (L7727)
- **Rules broken:** G30 (the in-plane velocity seen by a section — the skill's own Don't example).
- **Setting:** none (prose)
- **Current:** With $\mu_x=V_x/(\Omega R)$, the in-plane velocity seen by a section at radius $r$ and azimuth $\psi$ is
- **Proposed:** With $\mu_x=V_x/(\Omega R)$, the in-plane velocity at a blade section at radius $r$ and azimuth $\psi$ is

### ¶20 "The queue is the list of conditions..." (L7767)
- **Rules broken:** G3 (will actually be solved, is solved, is run, can be inspected and edited).
- **Setting:** .bemt conditions (queue)
- **Current:** The queue is the list of conditions that will actually be solved, and it is the single record of what a batch is. … Nothing is solved until the queue is run, so it can be inspected and edited first.
- **Proposed:** The queue is the list of conditions that the batch will actually solve, and it is the single record of what a batch is. A factorial sweep fills it, the explicit list fills it, and both may contribute to the same queue. Nothing runs until the queue runs, so you can inspect and edit the queue first.

### ¶21 "How it behaves. Conditions are solved..." (L7774)
- **Rules broken:** G3 (are solved, is never carried over, is trimmed).
- **Setting:** .bemt trim_mode / queue
- **Current:** Conditions are solved independently and in order. A collective or a rotational speed found by trimming one condition is never carried over as the starting point of the next, so the queue is a set of well-defined operating points rather than a sweep whose result depends on the order it was run in. When a trim mode is active, every condition in the queue is trimmed separately against the same target.
- **Proposed:** The batch solves the conditions independently and in order. It never carries a collective or a rotational speed found by trimming one condition over as the starting point of the next. The queue therefore stays a set of well-defined operating points rather than a sweep whose result depends on its order. When a trim mode is active, the trim loop trims every condition in the queue separately against the same target.

### ¶22 "Configuration and verification. Review the queue before running it..." (L7783)
- **Rules broken:** G9 (before running it), G8 (filtering them out of), G3 (will be used … should be saved).
- **Setting:** GUI queue controls
- **Current:** Review the queue before running it. Remove conditions that were generated but are not wanted, rather than filtering them out of the results afterwards. A queue that will be used again should be saved as a named batch first.
- **Proposed:** Review the queue before you run it. Remove the conditions that the sweep generated but that are not wanted, rather than dropping them from the results afterwards. Save a queue that you will use again as a named batch first.

### ¶23 "Building the queue from more than one sweep..." (L7807)
- **Rules broken:** G25/G15 (— used twice in prose), G3 (are APPENDED), G6 (Checked, … Unchecked, … telegraphic conditions), G32 (all-caps emphasis).
- **Setting:** GUI replace_queue
- **Current:** …Checked, each generation starts a fresh queue. Unchecked, the generated cases are APPENDED, which is how a queue is assembled out of several sweeps — a hover point, then a forward-flight sweep, then a descent — and also how a second generation with the same axes silently doubles the queue.
- **Proposed:** **Building the queue from more than one sweep.** GUI: replace_queue decides what the generate button does with what is already there. When it is checked, each generation starts a fresh queue. When it is unchecked, the generation appends the generated cases. Appending is how a queue is assembled out of several sweeps: a hover point, then a forward-flight sweep, then a descent. It is also how a second generation with the same axes silently doubles the queue.

### ¶24 ".bemt: the control belongs to the builder..." (L7815)
- **Rules broken:** G14 (semicolon), G3 (is not stored).
- **Setting:** .bemt replace_queue (not stored)
- **Current:** .bemt: the control belongs to the builder and is not stored; what reaches batches.bemt is the queue it produced.
- **Proposed:** .bemt: the control belongs to the builder, and the batch does not store it. What reaches batches.bemt is the queue it produced.

### ¶25 "Review the queue, then save the batch..." (L7828)
- **Rules broken:** P1 (two sequential steps merged).
- **Setting:** GUI save batch
- **Current:** Review the queue, then save the batch. Give it a name that states the experiment, …
- **Proposed:** Review the queue. Then save the batch. Give it a name that states the experiment, since the name is what appears in the GUI and in the command line listing.

### ¶26 "In the .bemt project, batches are stored..." (L7836)
- **Rules broken:** G6 (And sweep_params, the values that were swept, kept so… — sentence fragment starting with "And"), G22.
- **Setting:** .bemt sweep_kind / sweep_params / batches.bemt
- **Current:** …which is "custom" for a hand-built list, "factorial" for a Cartesian product, or one of "mu_sweep", "alpha_sweep" and "collective_sweep" for a single-axis sweep. And sweep_params, the values that were swept, kept so the sweep can be reconstructed. …
- **Proposed:** In the .bemt project, the file batches.bemt stores a list of batches. Besides conditions, each batch carries sweep_kind, which records how the queue was produced: "custom" for a hand-built list, "factorial" for a Cartesian product, or one of "mu_sweep", "alpha_sweep" and "collective_sweep" for a single-axis sweep. Each batch also carries sweep_params, the values that were swept, kept so the sweep can be reconstructed. Both describe the queue rather than defining it: what runs is always conditions.

### ¶27 "The key name labels the batch..." (L7848)
- **Rules broken:** G3 (is what appears, is how a batch is selected).
- **Setting:** .bemt name
- **Current:** …It defaults to "batch 1", is what appears in the GUI and in the listing, and is how a batch is selected, so it must be unique within the file.
- **Proposed:** The key name labels the batch. Its default is "batch 1". The name appears in the GUI and in the listing, and the GUI and the command line select a batch by it, so it must be unique within the file.

### ¶28 "Configuration and output location..." (L7869)
- **Rules broken:** G3/G8 (that will be looked at).
- **Setting:** .bemt plots / outdir
- **Current:** …Ask only for the figures that will be looked at: disk_map draws twelve fields for every condition, …
- **Proposed:** …Ask only for the figures you will use: disk_map draws twelve fields for every condition, so a queue of fifty conditions produces several hundred images.

### ¶29 "From the CLI, --outdir PATH..." (L7885)
- **Rules broken:** G3 (are exported, suppressed).
- **Setting:** CLI --outdir, --plots, --no-csv, --export-layout
- **Current:** …Tabular summaries are exported to results.csv unless suppressed with --no-csv. …
- **Proposed:** …The program writes tabular summaries to results.csv unless you suppress them with --no-csv. For parametric batches, --export-layout per_case partitions figures into dedicated condition subdirectories.

### ¶30 ".bemt: the four switches are stored together..." (L7902)
- **Rules broken:** G14 (semicolon), G3 (are stored, is always written).
- **Setting:** .bemt plots / CLI save_csv
- **Current:** .bemt: the four switches are stored together as the plots list inside the batch in batches.bemt; the CSV is always written when the batch runs from the CLI, which has no flag to suppress it.
- **Proposed:** .bemt: the batch stores the four switches together as the plots list inside the batch in batches.bemt. The CLI always writes the CSV when it runs the batch, and it has no flag to suppress the file.

### ¶31 "The destination..." (L7906)
- **Rules broken:** G14 (semicolon), G6 (Left empty telegraphic condition).
- **Setting:** .bemt outdir
- **Current:** …Left empty it defaults to a folder inside the project, so the results travel with the project they belong to; an absolute path sends them anywhere.
- **Proposed:** …If the field is left empty, it defaults to a folder inside the project, so the results stay with the project they belong to. An absolute path sends them anywhere.

### ¶32 "A report gathers a batch into a single HTML file..." (L7917)
- **Rules broken:** G8 (send it on), G3 (that were used), G22.
- **Setting:** .bemt --report / report button
- **Current:** A report gathers a batch into a single HTML file: the summary table for every condition, the mesh, solver, rotor and polar that were used, and the figures embedded inside the file itself, so you can send it on with nothing alongside it. …
- **Proposed:** A report gathers a batch into a single HTML file: the summary table for every condition, the mesh, solver, rotor and polar behind the results, and the figures embedded inside the file itself. The file therefore needs nothing alongside it. The report button in the Results tab produces it, and so does --report on the command line, which writes report.html into the output folder unless given a file name. --report-notes TEXT embeds a note in it.

## Section 12 — Results (anchor: results-section)
- Paragraphs reviewed: 78 | OK: 33 | Proposals: 45

### ¶1 "The Results tab examines completed cases..." (L7951)
- **Rules broken:** G9 (allowing -ing verb form), G3 (is closed).
- **Setting:** none (prose)
- **Current:** …The session history retains entries from Run Case and Run Batch until the project is closed, allowing single-case inspection and comparison. …
- **Proposed:** …The session history retains entries from Run Case and Run Batch for as long as the project stays open, which allows single-case inspection and comparison. …

### ¶2 "Convergence answers whether..." (L7975, list item)
- **Rules broken:** P1 (two sequential steps merged), G8 (turn … on).
- **Setting:** GUI Convergence view
- **Current:** …If the run stored no history, turn recording on from the same strip and run the case again.
- **Proposed:** …If the run stored no history, enable recording from the same strip. Then run the case again.

### ¶3 "The summary table is the global integral..." (L7979)
- **Rules broken:** G14 (semicolon).
- **Setting:** none (prose)
- **Current:** …For a rotor, read $C_T$ together with $C_Q$ and $FM$; $C_P$ is the same number as $C_Q$, so it adds nothing beside it. …
- **Proposed:** …For a rotor, read $C_T$ together with $C_Q$ and $FM$. $C_P$ is the same number as $C_Q$, so it adds nothing beside it. …

### ¶4 "The Disk Map visualizes 2D spatial..." (L7990)
- **Rules broken:** G26 (linear/logarithmic joining slash).
- **Setting:** GUI Disk Map display controls
- **Current:** …Display controls include linear/logarithmic color scaling, manual range limits, and reverse-flow masking (…Section 8.4).
- **Proposed:** …Display controls include linear or logarithmic color scaling, manual range limits, and reverse-flow masking (Section 8.4).

### ¶5 "Size on screen..." (L8001)
- **Rules broken:** G14 (legible; shrinking does not), G31 (colour-bar — British spelling), G19 (This is deliberate — ambiguous "this"), G22.
- **Setting:** GUI Disk Map layout
- **Current:** …so a grid squeezed below about two hundred pixels a cell keeps all of its text at full size and the text begins to overlap the data. Scrolling keeps every panel legible; shrinking does not. …The labels, the azimuth names and the colour-bar numbers…
- **Proposed:** **Size on screen.** A single panel fills whatever area the window gives it, at any screen size. The multi-panel layout does not: each of its panels keeps a minimum readable size, and on a screen too small to hold the whole grid the drawing area scrolls over it instead of shrinking it. This scrolling behavior is deliberate. The labels, the azimuth names and the color-bar numbers are measured in points and do not shrink with the panel. A grid squeezed below about two hundred pixels a cell keeps all of its text at full size, and the text begins to overlap the data. Scrolling keeps every panel legible. Shrinking does not. The toolbar stays above the scrolling area, so the zoom and pan controls remain reachable exactly when the figure is larger than the window.

### ¶6 "Disk map physical interpretation..." (L8019)
- **Rules broken:** G9 (producing participle), word order (peaks typically).
- **Setting:** none (prose)
- **Current:** In hover, the solution is purely axisymmetric, producing concentric radial contours. The radial load $F_n(r)$ peaks typically between $0.75R$ and $0.90R$, …
- **Proposed:** In hover, the solution is purely axisymmetric, and the contours are concentric radial rings. The radial load $F_n(r)$ typically peaks between $0.75R$ and $0.90R$, …

### ¶7 "Nothing is drawn until a disk is chosen..." (L8039)
- **Rules broken:** G25/G15 (— in prose), G4 (the reader had said — compound tense), G10 (disc vs. disk used everywhere else).
- **Setting:** GUI Disk Map field dropdown
- **Current:** …The reason is cost: (grid with all fields) is one contoured disc per field, sixteen of them on one page, and it used to be the dropdown's first item and therefore its default — so merely selecting this view produced the most expensive figure the program makes, before the reader had said what they wanted to look at. …
- **Proposed:** **Nothing is drawn until a disk is chosen.** The dropdown above the canvas opens on (choose a field below), and that item draws nothing at all. The reason is cost. (grid with all fields) draws one contoured disk per field, sixteen of them on one page. It used to be the dropdown's first item and therefore its default, so merely selecting this view produced the most expensive figure the program makes, before the reader said what to look at. Opening the view is now immediate, a single field is drawn in about a tenth of a second, and the grid is one click away and is produced when the reader asks for it.

### ¶8 "The choice survives a switch..." (L8049)
- **Rules broken:** G31 (colour-scale), G10 (disc), G3 (is picked), G32 (all-caps ONE).
- **Setting:** GUI Disk Map field dropdown
- **Current:** …The colour-scale controls beside the dropdown act on ONE disc, so they stay visible and disabled both on the placeholder and on the grid, and become active as soon as a single field is picked.
- **Proposed:** The choice survives a switch to another view and back, so returning to the disk map does not silently re-run the grid. The color-scale controls beside the dropdown act on one disk. They therefore stay visible and disabled both on the placeholder and on the grid, and they become active as soon as the user picks a single field.

### ¶9 "GUI: the Field dropdown above the canvas..." (L8055)
- **Rules broken:** G3 (is decided), G32 (all-caps EXPORTS).
- **Setting:** GUI Field dropdown; .bemt not stored
- **Current:** …bemt: this is a view control and is not stored. Which figures a batch EXPORTS is decided on the Run Batch tab, independently of what is on screen here.
- **Proposed:** GUI: the Field dropdown above the canvas. .bemt: this is a view control, and the project does not store it. The Run Batch tab decides which figures a batch exports, independently of what is on screen here.

### ¶10 "This view accepts one run or several..." (L8060)
- **Rules broken:** G8 (throws that detail away), "2+" informal numeric shorthand in prose, P1 (Choose … and … toggle).
- **Setting:** GUI Flight Condition Sweeps view
- **Current:** …this view throws that detail away deliberately to show how the integrated behavior moves as one flight variable changes. Choose the X axis from $\mu_x$, $\alpha_{deg}$, collective, or RPM (…Section 12.3) and, with 2+ selections, toggle between combining everything into a single curve or overlaying one series per selection.
- **Proposed:** …this view discards that detail deliberately, to show how the integrated behavior moves as one flight variable changes. Choose the X axis from $\mu_x$, $\alpha_{deg}$, collective, or RPM (Section 12.3). With two or more selections, toggle between combining everything into a single curve or overlaying one series per selection.

### ¶11 "Choose the axis that actually varied..." (L8071)
- **Rules broken:** G12 (becomes meaningless zig-zag — missing article).
- **Setting:** GUI Flight Condition Sweeps X axis
- **Current:** …and the connecting line becomes meaningless zig-zag.
- **Proposed:** …and the connecting line becomes a meaningless zig-zag.

### ¶12 "What the classic shapes mean..." (L8084)
- **Rules broken:** G8 (bends over), G1 (twist-plus-collective coinage), G3 (is dominated).
- **Setting:** none (prose)
- **Current:** …It then bends over and flattens as stall arrives, and it arrives progressively, first at whichever stations combine high twist-plus-collective with lower local speed, spreading outboard as the collective climbs. … Low loading is dominated by profile drag, high loading by induced power and stall, …
- **Proposed:** **What the classic shapes mean.** Against collective, thrust first rises almost linearly, because each degree adds $\alpha$ over the whole blade at fixed dynamic pressure. Thrust then bends and flattens as stall arrives, and stall arrives progressively, first at the stations that combine high total pitch with lower local speed, then spreading outboard as the collective climbs. Power rises faster than thrust throughout, because the induced part scales roughly as a three-halves power, while the profile part is nearly independent of thrust and never goes away. The figure of merit is therefore a ratio of a growing numerator to a sum of a growing and a nearly constant term: it must peak at a finite loading. Profile drag dominates low loading, induced power and stall dominate high loading, and the maximum between them is the design point this plot exists to locate. Note that this measure is a hover definition. Away from hover the same formula can exceed one and stops meaning efficiency.

### ¶13 "Overlay versus combine..." (L8111)
- **Rules broken:** G1 (say as informal interjection), G3 (is read), G8 (averages away), G9 (being studied).
- **Setting:** GUI Flight Condition Sweeps overlay/combine
- **Current:** Overlay keeps one curve per selected case, which is how a family is read: one curve per rotational speed, say, against collective, so the vertical spread between curves is itself the result. … Combining a family produces a curve that folds back on itself and averages away the very effect being studied.
- **Proposed:** **Overlay versus combine.** Overlay keeps one curve per selected case. This is how the user examines a family: one curve per rotational speed against collective, so that the vertical spread between curves is itself the result. Combining merges all selected points into a single series, and that is legitimate only when the points truly form one monotone sweep of the chosen axis with every other condition held equal. Combining a family produces a curve that folds back on itself and removes the very effect under study.

### ¶14 "This view needs exactly one run selected. It gives a slice..." (L8128)
- **Rules broken:** G3 (lets magnitudes be read), G8 (read off).
- **Setting:** GUI radial/azimuthal cuts
- **Current:** …Both cuts read the same converged mesh as the disk map, but a curve lets magnitudes be read off an axis, which a color bar never does well.
- **Proposed:** …Both cuts read the same converged mesh as the disk map, but a curve gives magnitudes directly on an axis, which a color bar never does well.

### ¶15 "The radial cut answers..." (L8137)
- **Rules broken:** G4/G9 (has stopped following), G22.
- **Setting:** GUI radial cut
- **Current:** …Read the accompanying $\alpha$ or $C_l$ cut alongside it: a station where $C_l$ has stopped following $\alpha$, or where $C_d$ jumps by an order of magnitude, is stalled, and the radial position of that break says whether the cure is twist, chord, or simply less collective. …
- **Proposed:** …is the product of three competing radial trends: dynamic pressure rising as $r^2$, chord and twist set by the geometry, and the tip loss cutting the last few per cent of span to nothing. The resulting curve normally climbs through the mid-span, peaks outboard, and drops steeply at the tip. Read the accompanying $\alpha$ or $C_l$ cut alongside it. A station where $C_l$ no longer follows $\alpha$, or where $C_d$ jumps by an order of magnitude, is stalled. The radial position of that break says whether the cure is twist, chord, or simply less collective. The thrust carried by the blade, in these variables, is the area under the curve.

### ¶16 "The azimuthal cut answers..." (L8155)
- **Rules broken:** G30 (actually see — components given human senses; the skill bans "the flow the airfoil sees").
- **Setting:** GUI azimuthal cut
- **Current:** That once-per-revolution variation is what the blade root, the hub and the control linkages actually see as an alternating load, and it is the quantity that drives vibration and fatigue. …
- **Proposed:** The blade root, the hub and the control linkages carry that once-per-revolution variation as an alternating load, and it is the quantity that drives vibration and fatigue. …

### ¶17 "Hover is the built-in sanity check..." (L8169)
- **Rules broken:** G9 (is reporting).
- **Setting:** none (prose)
- **Current:** A hover case that produces a wavy azimuthal curve is reporting an error, either a non-zero advance or axial term left in the condition, or an unconverged solution. …
- **Proposed:** A hover case that produces a wavy azimuthal curve reports an error: either a non-zero advance or axial term left in the condition, or an unconverged solution. …

### ¶18 "This view needs exactly one run selected. The two-dimensional plan view..." (L8181)
- **Rules broken:** G3 (are produced, is not installed, is painted).
- **Setting:** GUI 3D view
- **Current:** …The rotor or blade in three dimensions and the 3D load distribution are produced through an optional rendering package, and those buttons stay disabled when it is not installed. Choose which field is painted on the surface: …
- **Proposed:** …An optional rendering package produces the rotor or blade in three dimensions and the 3D load distribution, and those buttons stay disabled when the package is not installed. Choose which field the view paints on the surface: $F_n$, $F_t$, $\alpha_{eff}$, $\lambda_i$, $C_l$, $C_d$, or Mach.

### ¶19 "Read twist together with angle of attack..." (L8199)
- **Rules broken:** G1 (is doing its job — colloquial).
- **Setting:** GUI 3D view
- **Current:** Painting $\alpha_{eff}$ on the twisted surface shows immediately whether the built-in twist is doing its job. …
- **Proposed:** Painting $\alpha_{eff}$ on the twisted surface shows immediately whether the built-in twist performs as intended. …

### ¶20 "Limits. This view re-colors results..." (L8207)
- **Rules broken:** G3 (was run, is loaded), G22.
- **Setting:** none (prose)
- **Current:** …and if the underlying case was run on a coarse mesh, the smooth surface interpolates over detail that was never computed. … It is also a single condition, like every spatial view: it shows where the blade is loaded now, not how that changes as the condition moves.
- **Proposed:** **Limits.** This view re-colors results that already exist. It never re-solves anything. Changing the painted field costs a redraw and changes no number. If the underlying case ran on a coarse mesh, the smooth surface interpolates over detail that the solver never computed. Smoothness here is a property of the rendering, not evidence of resolution. The view is also a single condition, like every spatial view: it shows where the blade carries load now, not how the loading changes as the condition moves.

### ¶21 "Drawing resolution..." (L8216)
- **Rules broken:** G31 (coloured), G3 (is set by).
- **Setting:** none (prose)
- **Current:** The surface is coloured face by face, and the drawing cost is set by the number of faces and by nothing else: a 150 by 360 grid is 53,640 of them, on a canvas about four hundred pixels across. …
- **Proposed:** **Drawing resolution.** The preview draws a thinned copy of the mesh, not the mesh the solver converged. The surface is colored face by face, and the number of faces alone sets the drawing cost: a 150 by 360 grid is 53,640 faces, on a canvas about four hundred pixels across. That is more than one face per pixel in both directions, so the extra faces cost time and cannot appear in the image.

### ¶22 "The first and last radial station..." (L8223)
- **Rules broken:** G3 (is thinned), G10 (disc).
- **Setting:** none (prose)
- **Current:** …so the disc still reaches the tip and still closes on itself. Only the drawing is thinned: the 2D disk map, the exported tables and the report all read the full grid, and the numbers behind the preview are unchanged.
- **Proposed:** The first and last radial station and the first and last azimuth are always kept, so the disk still reaches the tip and still closes on itself. The program thins only the drawing: the 2D disk map, the exported tables and the report all read the full grid, and the numbers behind the preview are unchanged.

### ¶23 "When any mesh element does not converge..." (L8237)
- **Rules broken:** P1 (inspect the map, then change — two sequential steps in one sentence).
- **Setting:** none (prose)
- **Current:** …Treat the case as incomplete: inspect the map, then change the solver or the operating condition before using its loads.
- **Proposed:** …Treat the case as incomplete. Inspect the map. Then change the solver or the operating condition before you use its loads.

### ¶24 "When the run recorded no per-iteration history..." (L8242)
- **Rules broken:** G8 (turns … on).
- **Setting:** GUI collect_history
- **Current:** …Pressing it turns the recording switch (collect_history) on in the open project. …
- **Proposed:** …Pressing it enables the recording switch (collect_history) in the open project. …

### ¶25 "Selecting a condition among many..." (L8290)
- **Rules broken:** G22 (second sentence about 40 words), G30 (an extra … selector appears and picks — the picker is the user).
- **Setting:** GUI Choose condition to plot selector
- **Current:** …Whenever the current selection spans more than one condition, whether it holds a single batch, several single cases, or a mix of both, an extra Choose condition to plot selector appears and picks which of those conditions the views display. …
- **Proposed:** **Selecting a condition among many.** The spatial views (the disk map, the azimuth and radius cuts, the three-dimensional view and the convergence view) each show one flight condition. Whenever the current selection holds more than one condition — be it a single batch, several single cases, or a mix of both — an extra Choose condition to plot selector appears. The selector chooses which of those conditions the views display. Each entry keeps the name it carries everywhere else, so choosing which batch condition to draw needs no re-running. The sweep view and the table are unaffected, since they show the whole selection by construction.

### ¶26 "The output the current view shows..." (L8314, table cell)
- **Rules broken:** G6 (noun phrase without a verb).
- **Setting:** GUI Export (plots mode)
- **Current:** The output the current view shows, under a folder or file chosen at the time. The disk map writes one image per selected field per condition, with the dialog offering which fields to draw and how to organize the files. …
- **Proposed:** Writes the output that the current view shows, to a folder or file chosen at the time. The disk map writes one image per selected field per condition, and the dialog offers which fields to draw and how to organize the files. The sweep view saves its whole panel grid as one image. The azimuth and radius cuts, the three-dimensional view and the convergence view write one file per selected condition. In Table mode the same button becomes Export table… and writes the displayed summary table as CSV or TSV, chosen by the extension in the save dialog.

### ¶27 "A single HTML file holding the summary table..." (L8327, table cell)
- **Rules broken:** G6 (fragment).
- **Setting:** GUI Export report
- **Current:** A single HTML file holding the summary table, the figures that apply to the current selection, and a record of the mesh, solver, rotor and polar that produced them. …
- **Proposed:** Writes a single HTML file holding the summary table, the figures that apply to the current selection, and a record of the mesh, solver, rotor and polar that produced them. It appends the disk maps of a selected batch at the end. A dialog first asks the figure groups to embed and their resolution, as described below.

### ¶28 "Puts what is on screen on the clipboard..." (L8336, table cell)
- **Rules broken:** G6 (no subject).
- **Setting:** GUI Copy to clipboard
- **Current:** Puts what is on screen on the clipboard. …
- **Proposed:** Copies what is on screen to the clipboard. In the plot modes this is the figure as an image, ready to paste into a document or a slide. In Table mode it is the summary table, tab-separated and ready to paste into a spreadsheet.

### ¶29 "The report settings dialog..." (L8345)
- **Rules broken:** G3 (is selected), G8 (add up).
- **Setting:** GUI report settings dialog
- **Current:** …Two defaults adapt to the size of the selection: the performance-coefficients box arrives checked when more than one case is selected, and the disk-maps box arrives unchecked when more than twelve are, because thirteen figures per case add up quickly. …
- **Proposed:** …Two defaults adapt to the size of the selection: the performance-coefficients box arrives checked when the selection holds more than one case, and the disk-maps box arrives unchecked when it holds more than twelve, because thirteen figures per case accumulate quickly. …

### ¶30 "The report and its format..." (L8357)
- **Rules broken:** G22 (first sentence about 40 words), G19 (this is what makes), G3 (is written).
- **Setting:** none (prose)
- **Current:** A report is one file with every figure embedded inside it, so it opens with no network access and nothing alongside it: this is what makes it the right thing to send to someone who does not have zBEMT. When a selection would carry a very large number of figures the report is written instead as a small main page with companion pages beside it, so the main page stays quick to open. Nothing is left out of it either way.
- **Proposed:** **The report and its format.** A report is one file with every figure embedded inside it. It opens with no network access and nothing alongside it, which makes it the right thing to send to someone who does not have zBEMT. When a selection would carry a very large number of figures, the program writes the report instead as a small main page with companion pages beside it, so the main page stays quick to open. Nothing is left out of it either way.

### ¶31 "In the .bemt file, a batch may carry its own output folder... described in 11.6" (L8387)
- **Rules broken:** G29 (plain-number cross-reference "11.6", not a link — also a structural defect).
- **Setting:** .bemt outdir / plots
- **Current:** In the .bemt file, a batch may carry its own output folder and its own list of figure kinds, described in 11.6. Nothing in this block is otherwise stored: a report is an output, not part of the project definition.
- **Proposed:** In the .bemt file, a batch may carry its own output folder and its own list of figure kinds, described in Section 11.6. Nothing in this block is otherwise stored: a report is an output, not part of the project definition.
### ¶32 "From the CLI, --report writes report.html..." (L8392)
- **Rules broken:** none.
- **Setting:** CLI flags `--report`, `--report FILE`, `--report-notes TEXT`, `--plots`, `--outdir PATH`
- **Current:** "From the <span class="cli">CLI</span>, <code>--report</code> writes <code>report.html</code> into the output folder, and <code>--report FILE</code> writes it to a given name. <code>--report-notes TEXT</code> embeds a note in it. <code>--plots</code> chooses which loose figures are written, and <code>--outdir PATH</code> where they go. The report produced this way is the same file the button produces from the same results."
- **Proposed:** (unchanged — OK)

### ¶33 "The Results tab integrates the two-dimensional fields..." (L8404)
- **Rules broken:** G3 (`is evaluated`).
- **Setting:** none (prose) — results aggregation
- **Current:** "The Results tab integrates the two-dimensional fields into one row of global results. For a field $f(r,\psi)$, the disk integral is evaluated numerically as [equation]. The integrated quantities include thrust, torque, power $P=Q\Omega$, rolling and pitching moments $M_x$ and $M_y$, and in-plane forces $H$ and $Y$."
- **Proposed:** "The Results tab integrates the two-dimensional fields into one row of global results. For a field $f(r,\psi)$, the program evaluates the disk integral numerically as [equation]. The integrated quantities include thrust, torque, power $P=Q\Omega$, rolling and pitching moments $M_x$ and $M_y$, and in-plane forces $H$ and $Y$."

### ¶34 "Both coefficient families are calculated..." (L8410)
- **Rules broken:** G3 (`is emphasized`).
- **Setting:** none (prose) — coefficient conventions
- **Current:** "…The selected mode determines which family is emphasized in labels, plots, and sweep defaults. …"
- **Proposed:** "…The selected mode determines which family the labels, the plots and the sweep defaults emphasize. …"

### ¶35 "$\eta_{prop}$ is built from the component along the shaft..." (L8416, note)
- **Rules broken:** G8 (`comes back`), G32/G1 (`positive and flattering` — non-technical judgment word that overstates/reads as an editorial claim).
- **Setting:** none (prose) — propeller efficiency definition
- **Current:** "…In the windmill regime, where thrust is negative, thrust and power both change sign and the raw ratio comes back positive and flattering. Propulsive efficiency has no meaning there, and $0$ is reported instead."
- **Proposed:** "…In the windmill regime, where thrust is negative, thrust and power both change sign, and the raw ratio returns a positive value that reads as a good efficiency. Propulsive efficiency has no meaning there, and the program reports $0$ instead."

### ¶36 figcaption "A sweep in advance ratio for the starter_rotor example..." (L8435)
- **Rules broken:** G14 (semicolon), G6 (`Left, …; right, …` telegraphic fragments).
- **Setting:** none (prose) — figure caption
- **Current:** "…so thrust is an output rather than a held constant. Left, $C_T$ and $C_Q$ against $\mu_x$; right, the resulting figure of merit. The abscissa is the in-plane advance ratio and all three ordinates are dimensionless."
- **Proposed:** "…so thrust is an output rather than a held constant. The left panel shows $C_T$ and $C_Q$ against $\mu_x$, and the right panel shows the resulting figure of merit. The abscissa is the in-plane advance ratio and all three ordinates are dimensionless."

### ¶37 "Reading that sweep. Three features of it..." (L8443)
- **Rules broken:** none.
- **Setting:** none (prose)
- **Current:** "Three features of it are general enough to be worth stating, and each has a named cause."
- **Proposed:** (unchanged — OK)

### ¶38 "$C_T$ rises monotonically with $\mu_x$..." (L8447)
- **Rules broken:** G22 (first sentence about 40 words with three clauses).
- **Setting:** none (prose) — physics of $C_T$ along a sweep
- **Current:** "At fixed pitch the advancing side gains more dynamic pressure than the retreating side loses, because the normal load goes with the square of the tangential velocity while the velocity itself is linear in $\mu_x$, and the gain and the loss therefore do not cancel. Stall and reverse flow on the retreating side deepen the imbalance rather than correcting it."
- **Proposed:** "At fixed pitch the advancing side gains more dynamic pressure than the retreating side loses. The normal load goes with the square of the tangential velocity, while the velocity itself is linear in $\mu_x$, so the gain and the loss do not cancel. Stall and reverse flow on the retreating side deepen the imbalance rather than correcting it."

### ¶39 "$C_Q$ is not monotonic..." (L8454)
- **Rules broken:** G22 (first sentence about 35 words).
- **Setting:** none (prose) — physics of $C_Q$ along a sweep
- **Current:** "It falls to a minimum near $\mu_x\approx0.25$ for this rotor and rises again beyond it, because the two parts of the torque move in opposite directions and trade places. …"
- **Proposed:** "It falls to a minimum near $\mu_x\approx0.25$ for this rotor, and it rises again beyond it. The two parts of the torque move in opposite directions and trade places. …" (remainder unchanged)

### ¶40 "The figure of merit grows past unity..." (L8466)
- **Rules broken:** G1 (`a hover one` — telegraphic pro-form), repetition.
- **Setting:** none (prose) — figure of merit interpretation
- **Current:** "The figure of merit grows past unity. It is the ratio of a rising numerator to a mostly falling denominator. Therefore, it must grow. A value above $1$ here signals the absence of collective trim, not a solver error: the definition is a hover one, as Section 12.3 sets out."
- **Proposed:** "The figure of merit grows past unity. It is the ratio of a rising numerator to a mostly falling denominator. Therefore, it must grow. A value above $1$ here signals the absence of collective trim, not a solver error: the definition applies to hover, as <a class="xref" href="#sec-123-flight-condition-sweeps" title="12.3 Flight Condition Sweeps">Section 12.3</a> sets out."

### ¶41 "What it is. The shaft power a main rotor needs..." (L8475)
- **Rules broken:** none.
- **Setting:** none (prose) — total power curve
- **Current:** "The shaft power a main rotor needs, plotted against flight speed, is the sum of three contributions that behave differently, and the shape of the total is what fixes the speeds for best endurance and best range. Two of the three are computed by zBEMT. The third belongs to the airframe and is added outside it."
- **Proposed:** (unchanged — OK)

### ¶42 "Induced power..." (L8483)
- **Rules broken:** G3 (`less induced velocity is then needed`).
- **Setting:** none (prose) — induced power $P_i$
- **Current:** "It <em>falls</em> with speed, because forward motion renews the mass flow through the disk and less induced velocity is then needed to sustain the same thrust. …"
- **Proposed:** "It <em>falls</em> with speed, because forward motion renews the mass flow through the disk, and the disk then needs less induced velocity for the same thrust. …"

### ¶43 "Profile power..." (L8491)
- **Rules broken:** none.
- **Setting:** none (prose) — profile power $P_0$
- **Current:** "It grows slowly with advance ratio, in the classical closed form as [equation], because profile drag on an element goes with the cube of its tangential velocity, and the tangential velocity gains $V_x\sin\psi$ over part of the disk. It never goes away, not even at zero thrust."
- **Proposed:** (unchanged — OK)

### ¶44 "Parasite power..." (L8501)
- **Rules broken:** none.
- **Setting:** none (prose) — parasite power $P_p$
- **Current:** "It grows with the cube of speed and dominates at the top end. It is external to the rotor and is not part of what this program solves: $f$ is a property of the fuselage, not of the blade."
- **Proposed:** (unchanged — OK)

### ¶45 "The sum..." (L8509)
- **Rules broken:** none.
- **Setting:** none (prose) — minimum-power bucket
- **Current:** "Falling induced power and rising parasite power give a curve with a minimum at an intermediate speed, the classical bucket. The bottom of the bucket is the speed of minimum power and therefore of maximum endurance. The speed for maximum range is where a line from the origin is tangent to the curve, which lies further right."
- **Proposed:** (unchanged — OK)

### ¶46 figcaption "Decomposition of total power into induced, profile, parasite..." (L8520)
- **Rules broken:** G26 (`tail rotor/accessories/transmission` joining slash).
- **Setting:** none (prose) — figure caption
- **Current:** "Decomposition of total power into induced, profile, parasite, plus tail rotor/accessories/transmission components, as a function of advance speed. …"
- **Proposed:** "Decomposition of total power into the induced, profile and parasite components, plus the tail rotor, the accessories and the transmission, as a function of advance speed. …"

### ¶47 "How to produce it here..." (L8526)
- **Rules broken:** none.
- **Setting:** none (prose) — producing the power curve via a trimmed sweep
- **Current:** "A sweep in $\mu_x$ at constant thrust (which means a trim run, since thrust is otherwise an output) gives the induced and profile parts directly, as the two components of torque multiplied by the rotational speed. The parasite part is added afterwards from the airframe's own flat-plate area. Nothing in the rotor geometry can supply it."
- **Proposed:** (unchanged — OK)

### ¶48 "What a sweep is..." (L8539)
- **Rules broken:** G3 (`so that a trend can be read`).
- **Setting:** none (prose) — definition of a sweep
- **Current:** "A sweep repeats the solution over a sequence of flight conditions and assembles one result row per condition, so that a trend can be read where a single case gives only a point. …"
- **Proposed:** "A sweep repeats the solution over a sequence of flight conditions and assembles one result row per condition, so that the reader sees a trend where a single case gives only a point. …"

### ¶49 "Choosing the independent variable..." (L8546)
- **Rules broken:** G3 (`Whichever is chosen`, `are held`), G22.
- **Setting:** none (prose) — independent variable choice
- **Current:** "The abscissa may be either component of the free stream, the collective, or the rotational speed. Whichever is chosen, the other three are held, and the held values are part of the answer: a curve from a sweep is a slice through a four-dimensional space of conditions, comparable with another curve only when the three unswept values agree. The exported table records both the swept quantity and the fixed settings, which is what makes that check possible after the fact."
- **Proposed:** "<b>Choosing the independent variable.</b> The abscissa may be either component of the free stream, the collective, or the rotational speed. The sweep holds the other three, and the held values are part of the answer: a curve from a sweep is a slice through a four-dimensional space of conditions, comparable with another curve only when the three unswept values agree. The exported table records both the swept quantity and the fixed settings, which makes that check possible after the fact."

### ¶50 figcaption "A sweep in advance ratio for the starter_rotor example..." (L8560)
- **Rules broken:** G14 (semicolon), G6 (`Left, …; right, …` telegraphic fragments).
- **Setting:** none (prose) — figure caption
- **Current:** "…so $C_T$ varies freely along the sweep instead of being held. Left, $C_T$ and $C_P$ against $\mu_x$; right, the resulting figure of merit. All three ordinates are dimensionless."
- **Proposed:** "…so $C_T$ varies freely along the sweep instead of being held. The left panel shows $C_T$ and $C_P$ against $\mu_x$, and the right panel shows the resulting figure of merit. All three ordinates are dimensionless."

### ¶51 "The distinction. The sweep above holds the pitch..." (L8571)
- **Rules broken:** none.
- **Setting:** none (prose) — direct mode
- **Current:** "The sweep above holds the pitch $\theta(r)$ fixed, so thrust is an <em>output</em> that varies from condition to condition. That is the direct mode, and it answers the question "what does this blade do at each of these conditions"."
- **Proposed:** (unchanged — OK)

### ¶52 "A performance polar... asks the opposite question..." (L8577)
- **Rules broken:** G3 (`thrust to be held`).
- **Setting:** none (prose) — performance polar
- **Current:** "That requires thrust to be held, which means solving for the collective that produces it at every condition. …"
- **Proposed:** "That requires the thrust to stay fixed, which means solving for the collective that produces it at every condition. …"

### ¶53 "Why it sits outside the solver..." (L8585)
- **Rules broken:** none.
- **Setting:** none (prose) — trim as an outer loop
- **Current:** "…A trim is therefore a loop <em>around</em> the solver, not a mode inside it, which is why a trimmed sweep costs several times an untrimmed one and why a trim that fails is a statement about the blade rather than about the solver."
- **Proposed:** (unchanged — OK)

### ¶54 "How to run each..." (L8595)
- **Rules broken:** G3 (`is then trimmed`), G29 (plain-number cross-reference "10.5" — also a structural defect; the target is 11.1, which documents the run modes).
- **Setting:** none (prose) — untrimmed vs trimmed sweep
- **Current:** "An untrimmed sweep is the default: define the axes, leave the run mode direct, and read thrust as a result. A trimmed sweep is the same batch with a trim mode selected, described in 10.5, and every condition of the queue is then trimmed independently against the same target."
- **Proposed:** "An untrimmed sweep is the default: define the axes, leave the run mode direct, and read thrust as a result. A trimmed sweep is the same batch with a trim mode selected, described in <a class="xref" href="#cap-6-trim" title="11.1 Run mode and trim target">Section 11.1</a>, and the trim loop then trims every condition of the queue independently against the same target."

### ¶55 "The definition is a hover one..." (L8605)
- **Rules broken:** none.
- **Setting:** none (prose) — figure of merit definition
- **Current:** "$FM$ compares the actual power against the ideal actuator-disk power of a rotor in still air. That reference stops applying the moment there is a free stream, so past hover the ratio can exceed $1$. A value above unity in a forward-flight sweep is not a solver error. It is the definition being read outside its domain."
- **Proposed:** (unchanged — OK)

### ¶56 "Why the column is produced anyway..." (L8612)
- **Rules broken:** none.
- **Setting:** none (prose) — $FM$ as a relative measure
- **Current:** "…a thrust-to-torque ratio that remains a usable <em>relative</em> measure along a sweep even where its hover interpretation does not hold. … Its absolute value carries no meaning outside hover."
- **Proposed:** (unchanged — OK)

### ¶57 "What to read instead..." (L8624)
- **Rules broken:** none.
- **Setting:** none (prose) — propeller $\eta_{prop}$ and trimmed power comparison
- **Current:** "For a propeller in cruise the quantity with a defined meaning is $\eta_{prop}$, which is zero at the static point by construction and peaks at a finite advance ratio. For a rotor away from hover, compare power at equal thrust, which is what a trimmed sweep produces."
- **Proposed:** (unchanged — OK)

## Structural defects (appendix items) — Section 12
- **line 8389:** plain-number cross-reference "described in 11.6" is not a link (breaks doc rule 11 and G29); the AGENTS convention requires an `a.xref` carrying the target's title. Fix shown in ¶31.
- **line 8599:** plain-number cross-reference "described in 10.5" is not a link and appears to point at the wrong section (run modes are documented in 11.1); breaks doc rule 11 and G29. Fix shown in ¶54.
- **line 7722:** comma splice with an erroneous capital after the comma: "the loads are divided by, It also doubles the local Reynolds and Mach numbers." (Section 11; fix in Section 11 ¶18.)
- **line 8427:** "$0$ is reported instead" — passive, actor known (the program); should read "the program reports $0$ instead" (fix folded into ¶35).
- **line 8469:** cross-reference "as Section 12.3 sets out" is in prose with the heading number written as plain text without a link; should be an `a.xref` (fix folded into ¶40).
- **lines 8042, 8051, 8224, 8265:** inconsistent spelling "disc" versus "disk" for the same concept (G10; fixes in Section 12 ¶7, ¶8, ¶22).
- **no other structural defects detected** in Section 12 within lines 7481–8630.

---

# Block H: chapters 13–16 (lines 8631–9984)

## Section 13 — Geometry Variation Studies (anchor: cap-designer)
- Paragraphs reviewed: 36 | OK: 14 | Proposals: 22

### ¶1 "The Geometry Designer is a separate window..."
- **Rules broken:** G24, G22
- **Setting:** none (prose)
- **Current:** Every variant runs with the airfoil polar, the mesh, the inflow model and the corrections of the open project, so a difference between two results has a geometric cause.
- **Proposed:** Every variant runs using the airfoil polar, the mesh, the inflow model and the corrections of the open project. A difference between two results therefore has a geometric cause. (Splits the long clause and removes the ambiguous "with".)

### ¶2 "Open the Geometry Designer like this:"
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** Open the Geometry Designer like this:
- **Proposed:** no change.

### ¶3 "The Designer opens as its own window..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The Designer opens as its own window over the main one. The main window stays usable while the Designer is open.
- **Proposed:** no change.

### ¶4 "The window holds three pages."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The window holds three pages. Variants defines the blade geometries to compare. Conditions decides what every variant runs. Run & results executes the solves and reads them. The window compares geometries. It does not search for one: design optimization lives in its own window, Chapter 14.
- **Proposed:** no change.

### ¶5 "Integrity and reuse. Every row is validated..."
- **Rules broken:** D3, G22, G15
- **Setting:** none (prose)
- **Current:** ...A base whose planform reads ONE chord quantity keeps the table honest too — a rectangular base renames the first column to Chord c/R and an elliptic one to Max chord c/R, disabling the tip cell in both cases instead of accepting a value that would be ignored. Two rows resolving to the same radial table warn with both labels before running (a deliberate repeat measures solver noise), the cost line states solves and a wall estimate timed from one real solve, a worker count spreads the variants over that many processes, and Save comparison…/Load comparison… persist the whole setup into inputs/comparisons.bemt (SC-7a).
- **Proposed:** Split the paragraph into one topic each. In particular split the third sentence (which packs validation, duplicate rows, cost line, worker count and save/load into one clause) and replace the em dash with a sentence break: "A base whose planform reads ONE chord quantity keeps the table honest too. A rectangular base renames the first column to Chord c/R and an elliptic one to Max chord c/R, disabling the tip cell in both cases instead of accepting a value that would be ignored."

### ¶6 "The physics. A variant is one blade planform..."
- **Rules broken:** D3, G22
- **Setting:** none (prose)
- **Current:** ...Most rows state a few overrides: each filled cell replaces one parameter of the session base planform, and an empty cell keeps its value, so a row can isolate a single parameter at a time. ... The first column holds the label that names the variant in the verdict strip, in the figures and in every export. Choose labels that state the difference the row carries.
- **Proposed:** Shorten sentence 3 ("Most rows state a few overrides: each filled cell replaces one parameter of the session base planform, and an empty cell keeps its value."), and drop the instruction "Choose labels that state the difference the row carries" (7 sentences, above the descriptive limit).

### ¶7 "The table columns. The table has eleven columns."
- **Rules broken:** G21, G22
- **Setting:** none (prose)
- **Current:** The first seven are editable and state overrides over the session base planform: the label; the root chord and the tip chord over the radius (the headers read c/R); the twist in degrees at the root and at the tip; the blade count; the root cutout (r/R); and the radius in meters.
- **Proposed:** Put the seven editable columns in a bulleted list, each item on its own line, instead of a semicolon-delimited run inside a long sentence.

### ¶8 "The derived columns. The next two columns..."
- **Rules broken:** G22 (borderline)
- **Setting:** none (prose)
- **Current:** With $c$ the chord distribution over $r/R$ and $N_b$ the blade count, they show the blade aspect ratio, $AR = 1/\int c\,\mathrm{d}(r/R)$, to two decimal places, and the rotor solidity, $\sigma = N_b\,\int c\,\mathrm{d}(r/R)/\pi$, to three.
- **Proposed:** Keep the mathematics, but split the two shown quantities into two sentences: "With $c$ the chord distribution over $r/R$ and $N_b$ the blade count, they show the blade aspect ratio, $AR = 1/\int c\,\mathrm{d}(r/R)$, to two decimal places. They show the rotor solidity, $\sigma = N_b\,\int c\,\mathrm{d}(r/R)/\pi$, to three."

### ¶9 "The Extra overrides column. The last column..."
- **Rules broken:** G14
- **Setting:** none (prose)
- **Current:** It lists every override of its row that has no dedicated column, written as a param=value fragment; an em dash means the row carries none of them.
- **Proposed:** It lists every override of its row that has no dedicated column, written as a param=value fragment. An em dash means the row carries none of them.

### ¶10 "The variation sweep builder. The panel beside the table..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The panel beside the table turns one geometry parameter into several rows at once. The Parameter dropdown lists the parameters the generators accept: ...
- **Proposed:** no change.

### ¶11 "A count of 1 produces the start value alone."
- **Rules broken:** G22
- **Setting:** none (prose)
- **Current:** Build variants validates every value against the session base planform before it appends the row, so the builder rejects an unacceptable value with a message instead of leaving rows that fail only at run time.
- **Proposed:** Build variants validates every value against the session base planform before it appends the row. The builder rejects an unacceptable value with a message instead of leaving rows that fail only at run time.

### ¶12 "Planform values on a base without a generator."
- **Rules broken:** D3, G18
- **Setting:** none (prose)
- **Current:** (9 sentences, mixing several topics.) ... Every geometry is a radial table, so it reads each parameter as a target on that table. ...
- **Proposed:** Split into smaller paragraphs, one topic each (the parametric case, the table-space case, the chord handling, the twist handling). Replace "it reads each parameter" with "the window reads each parameter" to remove the ambiguous pronoun.

### ¶13 "The row buttons and the preview."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** Add copies the base row under an automatic label of the form variant N. ...
- **Proposed:** no change.

### ¶14 "The Generate variant block."
- **Rules broken:** D3
- **Setting:** none (prose)
- **Current:** (10 sentences, one paragraph.) The second builder panel beside the table builds one blade from scratch... When a project opens, the window seeds the radius, the blade count, the root cutout and the station count from that project's own blade.
- **Proposed:** Split into two paragraphs: one for the family dropdown and its chord fields, one for the shared settings (twist, radius, blades, cutout, stations).

### ¶15 "Built rows. Add as variant builds..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** Add as variant builds the blade from these fields and appends it as one row that carries the generated geometry itself, not overrides over the base. ...
- **Proposed:** no change.

### ¶16 "In the GUI: pick the family in the Generate variant panel..."
- **Rules broken:** P1, P3
- **Setting:** Generate variant panel (Geometry Designer window)
- **Current:** In the GUI: pick the family in the Generate variant panel and fill the fields it reveals. Adjust the shared radius, blade count, root cutout, twist and station count if the defaults do not match the study. Then press Add as variant.
- **Proposed:** In the GUI: pick the family in the Generate variant panel. Fill the fields it reveals. If the defaults do not match the study, adjust the shared radius, blade count, root cutout, twist and station count. Then press Add as variant.

### ¶17 "In the .bemt file: none. A generated variant..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** In the .bemt file: none. A generated variant is a row of the session table, not a project field, and it is gone when another project opens.
- **Proposed:** no change.

### ¶18 "From the CLI: no flag builds a single blade..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** From the CLI: no flag builds a single blade from a family. The command-line form of this comparison is --compare PATHS, whose variants are whole project folders rather than single generated rows.
- **Proposed:** no change.

### ¶19 "Import from project… The button beside Add as variant..."
- **Rules broken:** D3, G2
- **Setting:** Import from project… button (Geometry Designer window)
- **Current:** Every override row now builds on it, the base row reseeds from it, and it is the reference the run ranks the others against. The substitution lives in the window only.
- **Proposed:** Split the paragraph into two (import mechanics, then replace-base behavior). Split "Every override row now builds on it, the base row reseeds from it, and it is the reference the run ranks the others against" into separate sentences.

### ¶20 "In the GUI: press Import from project…, pick the project folder..."
- **Rules broken:** P1
- **Setting:** Import from project… dialog (Geometry Designer window)
- **Current:** In the GUI: press Import from project…, pick the project folder, then choose Add as variant or Replace base in the dialog.
- **Proposed:** In the GUI: press Import from project…. Pick the project folder. Then choose Add as variant or Replace base in the dialog.

### ¶21 "In the .bemt file: none. An imported blade..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** In the .bemt file: none. An imported blade exists in the session only, whichever button added it, and nothing is ever written back to the folder it came from.
- **Proposed:** no change.

### ¶22 "From the CLI: --compare PATHS accepts project folders..."
- **Rules broken:** none
- **Setting:** --compare PATHS (CLI)
- **Current:** From the CLI: --compare PATHS accepts project folders as variants. Each comma-separated folder contributes its blade as one variant named after the project it holds, beside the variant base that carries the geometry of --project. This automates the import flow. The command always adds the folders as extra variants and never replaces its own base.
- **Proposed:** no change.

### ¶23 "In the GUI: pick the parameter in the Variation sweep panel."
- **Rules broken:** P1
- **Setting:** Variation sweep panel (Geometry Designer window)
- **Current:** In the GUI: pick the parameter in the Variation sweep panel. Set Start, End and Count, or type explicit numbers in Values. Then press Build variants. Edit any cell of any row afterwards. Manage rows with Add, Duplicate and Remove, and watch the preview to confirm what each variant looks like.
- **Proposed:** Split the last sentence: "Manage rows with Add, Duplicate and Remove. Watch the preview to confirm what each variant looks like."

### ¶24 "In the .bemt file: comparison variants are not persisted."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** In the .bemt file: comparison variants are not persisted. The table rebuilds itself from the project's own geometry every time the project opens, and the labels live only in the session. A comparison worth repeating persists only through its exports, which are written into the outputs folder of the project.
- **Proposed:** no change.

### ¶25 "From the CLI: --compare PATHS compares whole projects..."
- **Rules broken:** none
- **Setting:** --compare PATHS (CLI)
- **Current:** From the CLI: --compare PATHS compares whole projects instead of table rows. The value is a comma-separated list of other project folders. Each folder becomes one variant named after the project it holds, and the geometry of --project joins the comparison as the variant named base. The command writes comparison.html and comparison.csv into the outputs folder of --project and exits. It refuses to share one call with --optimize, --gen-neuralfoil or --gen-xfoil.
- **Proposed:** no change.

### ¶26 "The generated sweep, control by control."
- **Rules broken:** G22, G30
- **Setting:** vsweep_param / vsweep_start / vsweep_end / vsweep_count / vsweep_values (.bemt keys; GUI fields)
- **Current:** vsweep_param chooses which property of the blade varies across the generated rows, and every row differs from the base geometry in that property alone, so any difference in the result belongs to it. ... vsweep_values overrides all three when it is not empty: an even sweep spends the same effort everywhere, and a real study usually wants points clustered where the answer changes fastest.
- **Proposed:** Split the first sentence. Replace the study-intent clause: "and a real study usually wants points clustered where the answer changes fastest" with "and points are usually clustered where the answer changes fastest".

### ¶27 "gen_family sets the planform of the generated blade."
- **Rules broken:** none
- **Setting:** gen_family (.bemt key; Generate variant family dropdown)
- **Current:** gen_family sets the planform of the generated blade. Rectangular keeps one chord throughout and is the reference case. ...
- **Proposed:** no change.

### ¶28 ".bemt: the generated variants are geometries..."
- **Rules broken:** none
- **Setting:** geom.bemt (.bemt file)
- **Current:** .bemt: the generated variants are geometries, so what is stored is a geom.bemt per variant, not the sweep that produced them. The sweep itself lives in the window.
- **Proposed:** no change.

### ¶29 "The physics. Every variant must run something..."
- **Rules broken:** D3, G22
- **Setting:** none (prose)
- **Current:** (7 sentences.) ... A gray estimate line at the bottom states the resulting count, for example single condition: 4 variants × 1 case = 4 solves, or names the reason a run cannot start.
- **Proposed:** Split the final sentence: "A gray estimate line at the bottom states the resulting count, for example single condition: 4 variants × 1 case = 4 solves. It also names the reason a run cannot start." Keep to 6 sentences.

### ¶30 "Saved cases. The panel shows how many cases..."
- **Rules broken:** none
- **Setting:** Saved cases panel (Conditions page)
- **Current:** Saved cases. The panel shows how many cases the project stores. The run refuses to start when none are stored. It also refuses to start when a stored case lacks a rotational speed, and the message names the cases without one. Cases are created and stored on the Run Case tab of the main window.
- **Proposed:** no change.

### ¶31 "The single condition fields."
- **Rules broken:** D3
- **Setting:** Single condition fields (Conditions page)
- **Current:** (13 sentences in one paragraph, four fields described.) The first field carries the advance ratio μx = Vx/(ΩR) along the vehicle longitudinal axis. ... The fourth field is the rotational speed in rev/min. It fixes the tip speed ΩR, and through it every dimensionless scale of the run: the advance ratios, the Reynolds number and the Mach number of each blade element. It accepts whole numbers from 1 to 20000 and comes prefilled with 1500.
- **Proposed:** Split into four paragraphs, one per field, or into a structured list with one item per field.

### ¶32 "The sweep fields."
- **Rules broken:** G22
- **Setting:** Sweep fields (Conditions page)
- **Current:** Start and Stop bound the sweep, both included, anywhere from -1000 to 1000, and Count sets how many evenly spaced values fall between them, from 1 to 200 with a default of 5.
- **Proposed:** Start and Stop bound the sweep, both included, anywhere from -1000 to 1000. Count sets how many evenly spaced values fall between them, from 1 to 200 with a default of 5.

### ¶33 "The swept condition. GUI: sweep_axis chooses..."
- **Rules broken:** G18 (borderline)
- **Setting:** sweep_axis / sweep_start / sweep_stop / sweep_count (.bemt keys; Sweep axis dropdown)
- **Current:** GUI: sweep_axis chooses the flight quantity carried through evenly spaced values, and it becomes the horizontal axis of every curve the comparison draws.
- **Proposed:** GUI: sweep_axis chooses the flight quantity carried through evenly spaced values. That quantity becomes the horizontal axis of every curve the comparison draws.

### ¶34 "The count multiplies with the number of variants..."
- **Rules broken:** none (borderline G6 "numbers but not answers")
- **Setting:** none (prose)
- **Current:** The count multiplies with the number of variants: five variants over twenty conditions is a hundred solves. Push the upper bound past the point where the blade stalls, or where momentum theory loses its solution, and the sweep still produces numbers but not answers.
- **Proposed:** no change (edge cases acceptable).

### ¶35 ".bemt: the conditions are expanded when the comparison runs..."
- **Rules broken:** none
- **Setting:** comparisons.bemt (.bemt file); --compare NAME (CLI)
- **Current:** .bemt: the conditions are expanded when the comparison runs, so what a saved comparison holds in comparisons.bemt is the resulting list of conditions rather than the sweep. CLI: --compare NAME.
- **Proposed:** no change.

### ¶36 (13.2.1) "The physics. A comparison at equal controls..."
- **Rules broken:** G22
- **Setting:** Thrust matching dropdown (Conditions page)
- **Current:** A comparison at equal controls does not, by itself, hold the loading constant: a planform that happens to make more thrust also draws more power, so an ordinary ranking favors whichever variant loads its blade most heavily.
- **Proposed:** A comparison at equal controls does not, by itself, hold the loading constant. A planform that happens to make more thrust also draws more power, so an ordinary ranking favors whichever variant loads its blade most heavily.

### ¶37 (13.2.1) "The mathematics. The target comes from the reference..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The target comes from the reference, which is the first row of the variant table, the base row of Section 13.1. The reference runs untrimmed, and its own result at each condition fixes the target of that condition:
- **Proposed:** no change.

### ¶38 (13.2.1) "Every other variant then re-solves one control..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** Every other variant then re-solves one control until it reaches the target. Which control is solved follows automatically from the project convention: a propeller solves RPM, because a fixed-pitch machine throttles with rotational speed, while a rotor solves the collective, because a rotor's rotational speed stays governed.
- **Proposed:** no change.

### ¶39 (13.2.1) "Options, cost, and failure."
- **Rules broken:** G22
- **Setting:** Thrust matching dropdown (Conditions page)
- **Current:** A trimmed case bisects its control instead of solving once, so each case outside the base row costs roughly ten direct solves, about 10 to 20 engine solves in practice.
- **Proposed:** A trimmed case bisects its control instead of solving once. Each case outside the base row costs roughly ten direct solves, about 10 to 20 engine solves in practice.

### ¶40 (13.2.1) "In the GUI: choose (off), Thrust or CT..."
- **Rules broken:** none
- **Setting:** Thrust matching dropdown (Conditions page)
- **Current:** In the GUI: choose (off), Thrust or CT in the Thrust matching dropdown below the three conditions panels. It applies to all three modes at once, because it changes what one case solves, never which cases run.
- **Proposed:** no change.

### ¶41 (13.2.1) "In the .bemt file: none. Thrust matching..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** In the .bemt file: none. Thrust matching is a choice of the run, like the variant table itself, and stores nothing in the project.
- **Proposed:** no change.

### ¶42 (13.2.1) "From the CLI: --trim {none,thrust,CT}..."
- **Rules broken:** none
- **Setting:** --trim {none,thrust,CT} (CLI)
- **Current:** From the CLI: --trim {none,thrust,CT} on the --compare flow selects the same behavior, with none as the default.
- **Proposed:** no change.

### ¶43 (13.2.1) "In the GUI: check one of the three radio buttons..."
- **Rules broken:** P1, P3
- **Setting:** radio buttons (Conditions page)
- **Current:** In the GUI: check one of the three radio buttons at the top of the page and fill the panel that appears below it. Choose the Thrust matching option if the variants must be compared at equal loading. Read the estimate line to confirm the number of solves before moving on.
- **Proposed:** In the GUI: check one of the three radio buttons at the top of the page. Fill the panel that appears below it. If the variants must be compared at equal loading, choose the Thrust matching option. Read the estimate line to confirm the number of solves before moving on.

### ¶44 (13.2.1) "In the .bemt file: the saved cases are real..."
- **Rules broken:** none
- **Setting:** inputs/saved_cases.bemt (.bemt file)
- **Current:** In the .bemt file: the saved cases are real project data and live in inputs/saved_cases.bemt. The single and sweep settings belong to the window alone and store nothing.
- **Proposed:** no change.

### ¶45 (13.2.1) "From the CLI: --compare PATHS runs the saved cases..."
- **Rules broken:** none
- **Setting:** --compare PATHS, --rpm R (CLI)
- **Current:** From the CLI: --compare PATHS runs the saved cases of the --project folder over the variants. When that project stores no cases, the command builds one hover-like condition instead, with 8 degrees of collective and the speed given by --rpm R. Without saved cases and without --rpm, it stops with an instruction rather than guessing a speed.
- **Proposed:** no change.

### ¶46 (13.3) "The physics. One solve covers one variant..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** One solve covers one variant at one condition, so a comparison costs one complete solve per pair of variant and condition. Nothing is interpolated between them and no result stands in for another: every number shown after a run comes from a full solution. The results live in memory for the rest of the session.
- **Proposed:** no change.

### ¶47 (13.3) "Run comparison. The button solves every condition..."
- **Rules broken:** none
- **Setting:** Run comparison button (Run & results page)
- **Current:** Run comparison. The button solves every condition of every variant in the table. A progress bar counts the pairs as they finish, a status line reports the same count, and Cancel stays clickable and stops the run cleanly. All of it happens off the main thread, so the window keeps responding while the solver works. When the run ends, the verdict strip, the ranking figure, the delta figure and the overlay figure fill in.
- **Proposed:** no change.

### ¶48 (13.3) "The verdict strip."
- **Rules broken:** G21, G22
- **Setting:** verdict strip (Run & results page)
- **Current:** Best thrust goes to the largest thrust coefficient or force, best figure of merit to the largest FM, lowest power to the smallest power coefficient or power, and best propeller efficiency to the largest ηprop computed by the formula above.
- **Proposed:** Put the four badge rules in a bulleted list, one per item, instead of a long comma-run sentence.

### ¶49 (13.3) "The ranking figure."
- **Rules broken:** D3
- **Setting:** Rank by and Condition dropdowns (Run & results page)
- **Current:** (10 sentences in one paragraph.) ... The winning bar takes the highlight color, every bar carries its numeric annotation, and the title states the condition the bars were read at.
- **Proposed:** Split into two paragraphs: one for the Rank by dropdown, one for the Condition dropdown and the bar figure.

### ¶50 (13.3) "The delta figure."
- **Rules broken:** G22 (borderline G31 "per cent")
- **Setting:** Delta vs base (%) panel (Run & results page)
- **Current:** For the same metric and the same condition as the ranking figure, each variant is drawn as its percent change against the base planform, 100*(v-v_base)/|v_base|, with an emphasized line at zero marking "equal to base". It states directly how many per cent a variant gains or loses against the project's own geometry.
- **Proposed:** Split the long first sentence; use "percent" for the American spelling. "For the same metric and the same condition as the ranking figure, each variant is drawn as its percent change against the base planform. The emphasized line at zero marks "equal to base". It states directly how many percent a variant gains or loses against the project's own geometry."

### ¶51 (13.3) "The overlay figure."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The lower canvas draws one panel per summary quantity among CT, FM, CP, ηprop, AR and σ, whichever ones the run produced. ...
- **Proposed:** no change.

### ¶52 (13.3) "The exports."
- **Rules broken:** G22
- **Setting:** Export report / Export CSV buttons (Run & results page)
- **Current:** Export CSV writes one row per geometry and condition beside it, and every row carries the aspect ratio and the solidity of its geometry next to the performance columns, so shape and results can be compared in one place.
- **Proposed:** Export CSV writes one row per geometry and condition beside it. Every row carries the aspect ratio and the solidity of its geometry next to the performance columns, so shape and results can be compared in one place.

### ¶53 (13.3) "In the GUI: press Run comparison and wait..."
- **Rules broken:** P1
- **Setting:** Run comparison button (Run & results page)
- **Current:** In the GUI: press Run comparison and wait for the finished message on the status line. Read the verdict chips at the reference condition. Choose a quantity in Rank by and a case in Condition. Read how far each variant departs from the base in the delta panel, and compare the curves of the overlay figure across the conditions. Press Export report or Export CSV to keep the run.
- **Proposed:** In the GUI: press Run comparison. Wait for the finished message on the status line. Read the verdict chips at the reference condition. Choose a quantity in Rank by and a case in Condition. Read how far each variant departs from the base in the delta panel. Compare the curves of the overlay figure across the conditions. Press Export report or Export CSV to keep the run.

### ¶54 (13.3) "In the .bemt file: nothing about the run..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** In the .bemt file: nothing about the run or the results persists. The exports are the record on disk, written into the outputs folder of the project.
- **Proposed:** no change.

### ¶55 (13.3) "From the CLI: --compare PATHS produces the same pair..."
- **Rules broken:** none
- **Setting:** --compare PATHS (CLI)
- **Current:** From the CLI: --compare PATHS produces the same pair of files the window exports, named comparison.html and comparison.csv, and prints one line per variant with its thrust coefficient and figure of merit at the first condition.
- **Proposed:** no change.

### ¶56 (13.3) "Ordering the variants."
- **Rules broken:** none
- **Setting:** ranking_field / ranking_condition (.bemt keys; Rank by dropdown)
- **Current:** GUI: ranking_field is the summary quantity the table is ordered by, and ranking_condition is which of the swept conditions that ordering reads. Both change the view alone: every variant was already solved at every condition, so re-ordering runs nothing.
- **Proposed:** no change.

### ¶57 (13.3) "The ordering is on ONE quantity at ONE condition."
- **Rules broken:** G14
- **Setting:** none (prose)
- **Current:** A variant that wins on the figure of merit may lose on torque, and a blade that is best in hover is frequently not the one that is best in cruise; that reversal is usually the finding, which is why the full table stays beside the ranking.
- **Proposed:** Split the semicolon: "A variant that wins on the figure of merit may lose on torque. A blade that is best in hover is frequently not the one that is best in cruise. That reversal is usually the finding, which is why the full table stays beside the ranking."

### ¶58 (13.4) "What it answers. The ranking above compares..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The ranking above compares variants on performance: thrust, torque, efficiency. A rotor that wins on performance can still be the worse aircraft, because how strongly it RESISTS a disturbance is a separate property from how much it lifts. This table puts the two side by side, so a planform is not chosen on hover figure of merit alone.
- **Proposed:** no change.

### ¶59 (13.4) "The physics. Four quantities are reported..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** Four quantities are reported per variant, each the slope of a hub load with respect to one disturbance, held at the ranking condition:
- **Proposed:** no change.

### ¶60 (13.4) "The first two are the rate dampings..."
- **Rules broken:** G2, G30
- **Setting:** none (prose)
- **Current:** The first two are the rate dampings: a rotor pitching nose-up meets a larger incidence at the front of the disk, the extra lift there opposes the motion, and the resulting moment is negative. ... The third is speed stability, the moment produced by flying faster, whose positive sign is what makes a helicopter want to pitch up as it accelerates.
- **Proposed:** Split the first sentence's comma-run: "The first two are the rate dampings. A rotor pitching nose-up meets a larger incidence at the front of the disk. The extra lift there opposes the motion, and the resulting moment is negative." Replace the intent: "whose positive sign is what makes a helicopter pitch up as it accelerates".

### ¶61 (13.4) "How it is computed."
- **Rules broken:** G15, G22
- **Setting:** Compare damping button (Run & results page)
- **Current:** Each variant is trimmed at the chosen condition and then perturbed by a central difference, exactly as in chapter 16 — that chapter is where the step size, the Richardson check and the sign conventions are set out. Four solves are needed per variant, one variable at a time, so the button is separate from the run: it costs about as much again as the comparison itself, and it is only worth paying when the ranking is already settled.
- **Proposed:** Replace the em dash with a sentence break: "exactly as in chapter 16. That chapter is where the step size, the Richardson check and the sign conventions are set out." Split the second sentence.

### ¶62 (13.4) "GUI: Compare damping on the Run & results page..."
- **Rules broken:** none
- **Setting:** Compare damping button (Run & results page)
- **Current:** GUI: Compare damping on the Run & results page fills the Damping comparison table beside the ranking. It is enabled once a comparison has been run, because the trim point comes from it.
- **Proposed:** no change.

### ¶63 (13.4) ".bemt: nothing to set..."
- **Rules broken:** none
- **Setting:** inputs/comparisons.bemt (.bemt file)
- **Current:** .bemt: nothing to set. The table is a view of the comparison already defined in inputs/comparisons.bemt.
- **Proposed:** no change.

### ¶64 (13.4) "CLI: not offered as one step."
- **Rules broken:** none
- **Setting:** --compare NAME, --derivatives NAME (CLI)
- **Current:** CLI: not offered as one step. Run --compare NAME for the ranking and --derivatives NAME for the derivatives of a saved study.
- **Proposed:** no change.

## Section 14 — Design Optimization (anchor: cap-optimization)
- Paragraphs reviewed: 38 | OK: 17 | Proposals: 21

### ¶1 "The Design Optimization window searches for the blade geometry..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The Design Optimization window searches for the blade geometry that best satisfies two goals at once. ...
- **Proposed:** no change.

### ¶2 "The search varies bounded planform parameters..."
- **Rules broken:** G14
- **Setting:** none (prose)
- **Current:** The flight condition itself comes from a saved case of the project; its definition lives on the Run Case tab, and this window never edits it.
- **Proposed:** The flight condition itself comes from a saved case of the project. Its definition lives on the Run Case tab, and this window never edits it.

### ¶3 "The mathematics that orders candidates is the domination rule."
- **Rules broken:** G21, G22
- **Setting:** none (prose)
- **Current:** When a constraint exists, the rule extends: any feasible design beats any infeasible one, two infeasible designs compare by how far they break the constraint, and two feasible designs compare by plain domination.
- **Proposed:** Put the three cases in a bulleted list: "any feasible design beats any infeasible one", "two infeasible designs compare by how far they break the constraint", "two feasible designs compare by plain domination".

### ¶4 "The Design Optimization window, opened from the Tools button..."
- **Rules broken:** G14 (borderline)
- **Setting:** none (prose; figure caption)
- **Current:** The Study page is open: the study list, the two objective rows and the constraint table on the left; the variables, the search settings and the cost estimate on the right.
- **Proposed:** The Study page is open: the study list, the two objective rows and the constraint table on the left. The variables, the search settings and the cost estimate are on the right.

### ¶5 "The study. GUI: optimization at the top of the window..."
- **Rules broken:** none
- **Setting:** optimization (.bemt key; Study selector at top of window)
- **Current:** GUI: optimization at the top of the window selects the named study, which fixes the objectives, the constraints, the design variables, the condition and the algorithm together, so a search can be repeated instead of re-entered.
- **Proposed:** no change.

### ¶6 ".bemt: the studies are stored..."
- **Rules broken:** none
- **Setting:** inputs/optimizations.bemt (.bemt file); --optimize NAME (CLI)
- **Current:** .bemt: the studies are stored in inputs/optimizations.bemt. CLI: --optimize NAME runs one of them.
- **Proposed:** no change.

### ¶7 (14.1) "An objective names one quantity..."
- **Rules broken:** none
- **Setting:** Objective 1 / Objective 2 rows (Study page)
- **Current:** An objective names one quantity of the results summary and states which direction is better. ...
- **Proposed:** no change.

### ¶8 (14.1) "In the GUI: type the summary key, for example FM..."
- **Rules broken:** P1
- **Setting:** Objective key box (Study page)
- **Current:** In the GUI: type the summary key, for example FM, into the key box of Objective 1, and choose Maximize or Minimize beside it. Fill Objective 2 the same way to request the front.
- **Proposed:** In the GUI: type the summary key, for example FM, into the key box of Objective 1. Choose Maximize or Minimize beside it. Fill Objective 2 the same way to request the front.

### ¶9 (14.1) "In the .bemt file: the study carries an objectives list..."
- **Rules broken:** G14
- **Setting:** objectives list, inputs/optimizations.bemt (.bemt file)
- **Current:** One entry runs the single-result search; two entries run the Pareto search.
- **Proposed:** One entry runs the single-result search. Two entries run the Pareto search.

### ¶10 (14.1) "From the CLI: the objectives come from the saved study; --optimize NAME..."
- **Rules broken:** G14
- **Setting:** --optimize NAME (CLI)
- **Current:** From the CLI: the objectives come from the saved study; --optimize NAME reads them from inputs/optimizations.bemt exactly as the window does.
- **Proposed:** From the CLI: the objectives come from the saved study. --optimize NAME reads them from inputs/optimizations.bemt exactly as the window does.

### ¶11 (14.2) "A constraint discards part of the design space."
- **Rules broken:** G8, G15, G22
- **Setting:** Add constraint row (Study page)
- **Current:** This keeps thresholds honest — a thrust floor of 0.008 either holds or it does not. ... When nothing satisfied the constraints, the outcome says so instead of dressing the least-bad design up as a success.
- **Proposed:** Replace the em dash with a sentence break: "This keeps thresholds honest. A thrust floor of 0.008 either holds or it does not." Replace the phrasal verb: "instead of presenting the least-bad design as a success". Split the long sentence 3.

### ¶12 (14.2) "In the GUI: press Add constraint..."
- **Rules broken:** P1
- **Setting:** Add constraint / Remove selected (Study page)
- **Current:** In the GUI: press Add constraint, type the summary key into the row, pick the operator from its dropdown and enter the value. Select a row and press Remove selected to drop it.
- **Proposed:** In the GUI: press Add constraint. Type the summary key into the row. Pick the operator from its dropdown. Enter the value. Select a row. Press Remove selected to drop it.

### ¶13 (14.2) "In the .bemt file: the study carries a constraints list..."
- **Rules broken:** none
- **Setting:** constraints list, inputs/optimizations.bemt (.bemt file)
- **Current:** In the .bemt file: the study carries a constraints list with one entry per row, holding key, operator (">=", "<=" or "==") and value. An empty list constrains nothing.
- **Proposed:** no change.

### ¶14 (14.2) "From the CLI: constraints also come..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** From the CLI: constraints also come from the saved study, with no separate flag.
- **Proposed:** no change.

### ¶15 (14.3) "A design variable is one degree of freedom..."
- **Rules broken:** G14, G8 (borderline)
- **Setting:** Add variable row (Study page)
- **Current:** A design variable is one degree of freedom the search may turn, together with the range it may turn it over. ... Bounds need a finite lower below a finite upper; the search respects them throughout, and the stratified first population already spreads across the whole box before evolution begins.
- **Proposed:** Split the semicolon: "Bounds need a finite lower below a finite upper. The search respects them throughout, and the stratified first population already spreads across the whole box before evolution begins." Consider rewording "the range it may turn it over" to "the range over which it may turn it".

### ¶16 (14.3) "In the GUI: press Add variable..."
- **Rules broken:** P1
- **Setting:** Add variable / Remove selected (Study page)
- **Current:** In the GUI: press Add variable, type the parameter name into the row and fill the lower and upper bounds. Select a row and press Remove selected to drop it.
- **Proposed:** In the GUI: press Add variable. Type the parameter name into the row. Fill the lower and upper bounds. Select a row. Press Remove selected to drop it.

### ¶17 (14.3) "In the .bemt file: the study carries a variables list..."
- **Rules broken:** none
- **Setting:** variables list, inputs/optimizations.bemt (.bemt file)
- **Current:** In the .bemt file: the study carries a variables list with one entry per row, holding param, lower and upper.
- **Proposed:** no change.

### ¶18 (14.3) "From the CLI: variables also come..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** From the CLI: variables also come from the saved study, with no separate flag.
- **Proposed:** no change.

### ¶19 (14.4) "Every candidate is solved at one flight condition."
- **Rules broken:** G13 (borderline "adimensionalizes")
- **Setting:** Condition dropdown (Study page)
- **Current:** Rotation is not optional: the solver adimensionalizes by ΩR, so a case without an RPM cannot take part, and the window refuses to start without one.
- **Proposed:** Rotation is not optional: the solver non-dimensionalizes by ΩR, so a case without an RPM cannot take part, and the window refuses to start without one. (if "non-dimensionalize" is the project's approved word; otherwise keep the project term.)

### ¶20 (14.4) "In the GUI: pick the saved case..."
- **Rules broken:** none
- **Setting:** Condition dropdown (Study page)
- **Current:** In the GUI: pick the saved case in the Condition dropdown of the search settings.
- **Proposed:** no change.

### ¶21 (14.4) "In the .bemt file: the study carries a condition block..."
- **Rules broken:** none
- **Setting:** condition block, inputs/optimizations.bemt (.bemt file)
- **Current:** In the .bemt file: the study carries a condition block equal to a saved case, RPM included. Without it the first saved case of the project runs.
- **Proposed:** no change.

### ¶22 (14.4) "From the CLI: the condition comes..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** From the CLI: the condition comes from the saved study, exactly as stored.
- **Proposed:** no change.

### ¶23 (14.5) "The algorithm decides how the next generation..."
- **Rules broken:** G22 (borderline)
- **Setting:** Algorithm dropdown (Study page)
- **Current:** NSGA-II is the Pareto search: it keeps a whole population, ranks it by the domination rules above, preserves variety along the front with a crowding measure, and breeds the next generation from the winners.
- **Proposed:** Split into two sentences: "NSGA-II is the Pareto search. It keeps a whole population, ranks it by the domination rules above, preserves variety along the front with a crowding measure, and breeds the next generation from the winners."

### ¶24 (14.5) "In the GUI: choose the algorithm..."
- **Rules broken:** G14, G30, G31
- **Setting:** Algorithm dropdown (Study page)
- **Current:** Choosing differential evolution disables the crossover and mutation controls of Section 14.7, which have nothing to say about it; they stay on screen, greyed out.
- **Proposed:** Choosing differential evolution disables the crossover and mutation controls of Section 14.7, because they do not apply to it. They stay on screen, grayed out.

### ¶25 (14.5) "In the .bemt file: the study carries algorithm..."
- **Rules broken:** none
- **Setting:** algorithm key, inputs/optimizations.bemt (.bemt file)
- **Current:** In the .bemt file: the study carries algorithm, with "nsga2" or "de". An older study without the field falls back to its legacy method.
- **Proposed:** no change.

### ¶26 (14.5) "From the CLI: --algorithm..."
- **Rules broken:** none
- **Setting:** --algorithm {nsga2,de,powell,nelder-mead} (CLI)
- **Current:** From the CLI: --algorithm {nsga2,de,powell,nelder-mead} overrides the stored value for one run.
- **Proposed:** no change.

### ¶27 (14.6) "The population is the number of designs alive..."
- **Rules broken:** G14
- **Setting:** Population / Generations / Seed fields (Study page)
- **Current:** A small population with many generations walks further but explores less; a large population with few generations maps the front more evenly but converges less.
- **Proposed:** A small population with many generations walks further but explores less. A large population with few generations maps the front more evenly but converges less.

### ¶28 (14.6) "In the GUI: set Population, Generations and Seed..."
- **Rules broken:** none
- **Setting:** Population / Generations / Seed fields (Study page)
- **Current:** In the GUI: set Population, Generations and Seed in the search settings. Population accepts 4 to 400, generations 1 to 500, the seed 0 to 999999.
- **Proposed:** no change.

### ¶29 (14.6) "In the .bemt file: the fields are population..."
- **Rules broken:** none
- **Setting:** population / generations / seed keys, inputs/optimizations.bemt (.bemt file)
- **Current:** In the .bemt file: the fields are population, generations and seed on the study.
- **Proposed:** no change.

### ¶30 (14.6) "From the CLI: --population N..."
- **Rules broken:** none
- **Setting:** --population N, --generations N, --seed N (CLI)
- **Current:** From the CLI: --population N, --generations N and --seed N override the stored values for one run.
- **Proposed:** no change.

### ¶31 (14.7) "NSGA-II breeds children with two operators."
- **Rules broken:** G14, G15, G30 (borderline)
- **Setting:** Crossover eta / Mutation eta / Mutation rate fields (Study page)
- **Current:** Simulated binary crossover blends two parents; its distribution index ηc says how close children stay to them — large values keep the family together, small values scatter it. Polynomial mutation then perturbs individual genes; its index ηm plays the same role for single genes, and the mutation rate is the fraction of genes touched per child. The defaults ηc = 15, ηm = 20 suit smooth aerodynamic landscapes; lower both when the search stalls in a narrow region.
- **Proposed:** Split the semicolons and the em dash: "Simulated binary crossover blends two parents. Its distribution index ηc sets how close children stay to them. Large values keep the family together, and small values scatter it. Polynomial mutation then perturbs individual genes. Its index ηm plays the same role for single genes, and the mutation rate is the fraction of genes touched per child. The defaults ηc = 15 and ηm = 20 suit smooth aerodynamic landscapes. Lower both when the search stalls in a narrow region."

### ¶32 (14.7) "In the GUI: set Crossover eta..."
- **Rules broken:** none
- **Setting:** Crossover eta / Mutation eta / Mutation rate fields (Study page)
- **Current:** In the GUI: set Crossover eta, Mutation eta and Mutation rate in the search settings. The indices accept 1 to 40 and 1 to 100, the rate 0 to 1. The controls disable under differential evolution.
- **Proposed:** no change.

### ¶33 (14.7) "In the .bemt file: the fields are crossover_eta..."
- **Rules broken:** none
- **Setting:** crossover_eta / mutation_eta / mutation_rate keys, inputs/optimizations.bemt (.bemt file)
- **Current:** In the .bemt file: the fields are crossover_eta, mutation_eta and mutation_rate on the study.
- **Proposed:** no change.

### ¶34 (14.7) "From the CLI: these three come..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** From the CLI: these three come from the saved study, with no separate flag.
- **Proposed:** no change.

### ¶35 (14.8) "Pressing Run optimization first checks the study..."
- **Rules broken:** G14, G22
- **Setting:** Run optimization button (Run page)
- **Current:** Pressing Run optimization first checks the study and names every problem it finds — an unknown summary key, bounds that do not increase, a genetic algorithm with too few designs, two objectives given to a single-result method. Errors block the start, warnings only inform; nothing pays solver time to learn about a bad definition. ... The front table lists one non-dominated design per row — its variables first, then its raw objective values, then the constraint values of Section 14.2. No row dominates another; that is what makes them the front.
- **Proposed:** Split the semicolons and shorten the first sentence. "Errors block the start, warnings only inform. Nothing pays solver time to learn about a bad definition." and "No row dominates another. That is what makes them the front."

### ¶36 (14.8) "The figures."
- **Rules broken:** G15, G22, G31
- **Setting:** Pareto / parallel-coordinates views (Run page)
- **Current:** In the Pareto view the shape to look for is a falling curve — each step right along the first objective buys a step down on the second, and the engineer's job is choosing the point along it worth having. ... The parallel-coordinates view draws one polyline per member across every variable and objective, each axis normalized over the front so quantities with different units share the picture: a member reads high where it wins and low where it pays, and crossings between neighbouring axes are the visible trade-off.
- **Proposed:** Replace the em dash with a sentence break. Split the long parallel-coordinates sentence. Replace "neighbouring" with "neighboring" and "grey" with "gray".

### ¶37 (14.8) "The exports."
- **Rules broken:** G22
- **Setting:** Export CSV / Export report (Run page)
- **Current:** Export report writes a self-contained HTML report with the metadata of the run, the front table, the trade-off figure and the planforms of three spread members, plus an evaluations CSV beside it holding every solve of the search.
- **Proposed:** Export report writes a self-contained HTML report with the metadata of the run, the front table, the trade-off figure and the planforms of three spread members. It also writes an evaluations CSV beside it holding every solve of the search.

### ¶38 (14.8) "In the GUI: press Run optimization, watch the progress line..."
- **Rules broken:** P1
- **Setting:** Run optimization / Cancel buttons (Run page)
- **Current:** In the GUI: press Run optimization, watch the progress line, press Cancel to stop early. Read the front table, pick a member against the trade-off figure, then export.
- **Proposed:** In the GUI: press Run optimization. Watch the progress line. Press Cancel to stop early. Read the front table. Pick a member against the trade-off figure. Then export.

### ¶39 (14.8) "In the .bemt file: nothing about a run persists."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** In the .bemt file: nothing about a run persists. The exports and the report are the record on disk.
- **Proposed:** no change.

### ¶40 (14.8) "From the CLI: --optimize NAME runs the saved study..."
- **Rules broken:** none
- **Setting:** --optimize NAME, --pareto-csv PATH (CLI)
- **Current:** From the CLI: --optimize NAME runs the saved study and produces the same three artifacts — <study>_pareto.html, <study>_pareto_front.csv and <study>_pareto_evaluations.csv in the outputs folder — and prints the front as a table. --pareto-csv PATH chooses another destination for the front CSV.
- **Proposed:** no change.

### ¶41 (14.9) "What it is. How many designs are solved..."
- **Rules broken:** none
- **Setting:** Parallel workers field (Study page)
- **Current:** How many designs are solved at the same time. Every design in a generation is an independent solve — a variant geometry evaluated at one flight condition, reading nothing the other designs write — so the generation can be spread over several processes and reassembled afterwards.
- **Proposed:** no change.

### ¶42 (14.9) "The mathematics. There is none to speak of..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** There is none to speak of, and that is the point: the answer must not depend on this setting. ...
- **Proposed:** no change.

### ¶43 (14.9) "The wall time falls close to proportionally..."
- **Rules broken:** G1 (borderline)
- **Setting:** none (prose)
- **Current:** The wall time falls close to proportionally until there are more workers than the machine has cores, after which the processes compete and the gain stops.
- **Proposed:** The wall time falls almost proportionally until there are more workers than the machine has cores. After that, the processes compete and the gain stops.

### ¶44 (14.9) "GUI: Parallel workers in the Search block..."
- **Rules broken:** none
- **Setting:** Parallel workers field (Study page)
- **Current:** GUI: Parallel workers in the Search block of the Study page.
- **Proposed:** no change.

### ¶45 (14.9) ".bemt: the key parallel_workers..."
- **Rules broken:** none
- **Setting:** parallel_workers key, inputs/optimizations.bemt (.bemt file)
- **Current:** .bemt: the key parallel_workers, default 1, in inputs/optimizations.bemt.
- **Proposed:** no change.

### ¶46 (14.9) "CLI: --workers 8..."
- **Rules broken:** none
- **Setting:** --workers 8 (CLI)
- **Current:** CLI: --workers 8 alongside --optimize NAME, which overrides what the study stores.
- **Proposed:** no change.

### ¶47 (14.10) "What it is. A single number saying..."
- **Rules broken:** G14, G30
- **Setting:** none (prose)
- **Current:** A single number saying how good a whole Pareto front is. Comparing two fronts by eye works only when one clearly dominates the other; when they cross, a measure is needed, and the hypervolume is the standard one.
- **Proposed:** A single number that states how good a whole Pareto front is. Comparing two fronts by eye works only when one clearly dominates the other. When they cross, a measure is needed, and the hypervolume is the standard one.

### ¶48 (14.10) "The mathematics. Fix a reference point..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** Fix a reference point r worse than every member of the front in every objective. Each front member f^(i) then spans a box between itself and r, and the hypervolume is the AREA of the union of those boxes (the volume, for more than two objectives):
- **Proposed:** no change.

### ¶49 (14.10) "where Λ is the ordinary area."
- **Rules broken:** G30, G22
- **Setting:** none (prose)
- **Current:** A union, not a sum: overlapping boxes are counted once, which is what makes the measure reward a front that is both close to the ideal corner and spread along it, rather than one that piles many members onto the same spot. It grows as the search improves and never falls, so its history is a convergence trace: a curve that has flattened says further generations are buying nothing.
- **Proposed:** Replace the curve intent: "a curve that has flattened says further generations are buying nothing" with "a curve that has flattened shows that further generations are buying nothing". Split the long first sentence.

### ¶50 (14.10) "The reference point is taken as the worst value..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The reference point is taken as the worst value seen on the current front in each objective, moved ten percent further out. It is therefore recomputed each generation, which is worth knowing when reading the trace: the number is a fair comparison BETWEEN generations of one run, and not between two runs with different objectives or scales.
- **Proposed:** no change.

### ¶51 (14.10) "GUI: computed on every generation..."
- **Rules broken:** G14
- **Setting:** none (prose)
- **Current:** GUI: computed on every generation of an nsga2 run with two objectives; a single-objective run records the best value instead, since an area needs two axes.
- **Proposed:** GUI: computed on every generation of an nsga2 run with two objectives. A single-objective run records the best value instead, since an area needs two axes.

### ¶52 (14.10) ".bemt: nothing to set..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** .bemt: nothing to set. It is a diagnostic of the run, not an input.
- **Proposed:** no change.

### ¶53 (14.10) "CLI: written into <study>_pareto_evaluations.csv..."
- **Rules broken:** none
- **Setting:** <study>_pareto_evaluations.csv (CLI)
- **Current:** CLI: written into <study>_pareto_evaluations.csv alongside the evaluation ledger.
- **Proposed:** no change.

## Section 15 — Transient Simulation (anchor: cap-transiente)
- Paragraphs reviewed: 28 | OK: 16 | Proposals: 12

### ¶1 "Every other chapter of this manual computes a rotor..."
- **Rules broken:** G3, G15 (borderline)
- **Setting:** none (prose)
- **Current:** A flight condition is given, the inflow is solved until it stops changing, and the loads are read off the converged field. ... which covers hover, steady climb and steady forward flight — most of what a rotor does.
- **Proposed:** Use the active voice: "The solver is given a flight condition. It solves the inflow until it stops changing, and it reads the loads off the converged field." Replace the em dash with a sentence break: "which covers hover, steady climb and steady forward flight. That is most of what a rotor does."

### ¶2 "It is the wrong answer when the condition itself..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The wake carries memory: the induced velocity at one instant is the response to what the rotor was doing a moment ago, not to what it is doing now. Pull collective quickly and the thrust overshoots, because the inflow that would oppose it has not arrived yet.
- **Proposed:** no change.

### ¶3 "Scope, stated before the physics: the state that is marched..."
- **Rules broken:** G3 (borderline)
- **Setting:** none (prose)
- **Current:** The blade motion and the separation state can be carried along with it, but the aerodynamics inside each sample stay quasi-steady.
- **Proposed:** The march can carry the blade motion and the separation state along with it, but the aerodynamics inside each sample stay quasi-steady.

### ¶4 "The maneuver. GUI: maneuver at the top of the window..."
- **Rules broken:** none
- **Setting:** maneuver selector (.bemt key; top of window)
- **Current:** A maneuver is not a batch: each sample inherits the inflow state of the sample before it, which is the whole reason a transient differs from a sequence of steady solves.
- **Proposed:** no change.

### ¶5 ".bemt: stored in inputs/maneuvers.bemt..."
- **Rules broken:** none
- **Setting:** inputs/maneuvers.bemt (.bemt file); --maneuver NAME (CLI)
- **Current:** .bemt: stored in inputs/maneuvers.bemt. CLI: --maneuver NAME.
- **Proposed:** no change.

### ¶6 (15.1) "The physics. A rotor's induced inflow..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** Pitt and Peters wrote the delay as a first-order system in three states — a uniform component and two harmonics — driven by the hub loads:
- **Proposed:** no change.

### ¶7 (15.1) "M is the apparent-mass matrix..."
- **Rules broken:** G14
- **Setting:** none (prose)
- **Current:** M is the apparent-mass matrix, the air the disk has to accelerate before its own inflow changes; L is the static gain that relates a load to the inflow it eventually produces; and V is a mass-flow parameter that grows with the speed through the disk.
- **Proposed:** Put the three matrix definitions as a bulleted list or separate sentences: "M is the apparent-mass matrix, the air the disk has to accelerate before its own inflow changes. L is the static gain that relates a load to the inflow it eventually produces. V is a mass-flow parameter that grows with the speed through the disk."

### ¶8 (15.1) "How it is marched. Inside one sub-step..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** Inside one sub-step the matrices are frozen and the resulting linear system is solved EXACTLY, not stepped:
- **Proposed:** no change.

### ¶9 (15.1) "This matters more than it may look."
- **Rules broken:** G22, G31
- **Setting:** none (prose)
- **Current:** The exponential form has no such limit: it is the exact solution of the frozen system, so a single sub-step already relaxes smoothly toward equilibrium when the sample is long compared with the delay, which is the physically correct behaviour and not an approximation of it.
- **Proposed:** Split the sentence and replace "behaviour" with "behavior": "The exponential form has no such limit. It is the exact solution of the frozen system, so a single sub-step already relaxes smoothly toward equilibrium when the sample is long compared with the delay. This is the physically correct behavior, not an approximation of it."

### ¶10 (15.2) "What it is. A manoeuvre is a list of points..."
- **Rules broken:** G22
- **Setting:** none (prose)
- **Current:** It is not a batch: a batch solves each case from scratch and the order of the cases is irrelevant, whereas here every sample inherits the inflow state of the sample before it, and reversing the order gives a different answer.
- **Proposed:** Split into two sentences: "It is not a batch. A batch solves each case from scratch and the order of the cases is irrelevant. Here every sample inherits the inflow state of the sample before it, and reversing the order gives a different answer."

### ¶11 (15.2) "The letters follow the mode..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The letters follow the mode, exactly as they do for a saved case: in propeller mode the in-plane column is the cross-flow and the axial one is the flight speed (Chapter 4).
- **Proposed:** no change.

### ¶12 (15.2) "Between the points. Two readings are offered."
- **Rules broken:** G31
- **Setting:** Interpolation combo (Trajectory points table)
- **Current:** Linear blends each quantity between the two neighbouring points, which is what a control input that is moved smoothly looks like.
- **Proposed:** Replace "neighbouring" with "neighboring".

### ¶13 (15.2) "GUI: the Trajectory points table..."
- **Rules broken:** none
- **Setting:** Trajectory points table / Add / Build from two saved cases / Interpolation (GUI)
- **Current:** GUI: the Trajectory points table, one row per point, with Add appending a row one interval after the last. Build from two saved cases fills the table from two conditions already stored in the project and a duration, which is the quickest way to state "go from this to that in so many seconds". The Interpolation combo chooses between the two readings.
- **Proposed:** no change.

### ¶14 (15.2) ".bemt: the key points, a list whose entries carry..."
- **Rules broken:** G14
- **Setting:** points / interpolation keys, inputs/maneuvers.bemt (.bemt file)
- **Current:** .bemt: the key points, a list whose entries carry t_s, mu_x, Vz, collective_deg, cyclic_c_deg, cyclic_s_deg and an optional rpm; and the key interpolation, either linear (the default) or hold.
- **Proposed:** Split the semicolon: "...an optional rpm. The key interpolation is either linear (the default) or hold."

### ¶15 (15.2) "CLI: --maneuver NAME runs a manoeuvre..."
- **Rules broken:** none
- **Setting:** --maneuver NAME, --list-maneuvers, --maneuver-file PATH (CLI)
- **Current:** CLI: --maneuver NAME runs a manoeuvre saved in the project, and a bare --maneuver runs the first one. --list-maneuvers prints the saved names. --maneuver-file PATH runs a definition held in a .bemt file outside the project, which is how a trajectory is shared without copying it into every project that needs it.
- **Proposed:** no change.

### ¶16 (15.2) "The two-case builder. GUI: instead of typing the nodes..."
- **Rules broken:** G14
- **Setting:** build_case_a / build_case_b (.bemt keys; Build from two saved cases)
- **Current:** build_case_a is the case the ramp starts at and becomes the first node; build_case_b is the case it ends at and becomes the last.
- **Proposed:** build_case_a is the case the ramp starts at and becomes the first node. build_case_b is the case it ends at and becomes the last.

### ¶17 (15.2) "build_duration is what makes the trajectory..."
- **Rules broken:** none
- **Setting:** build_duration (.bemt key)
- **Current:** build_duration is what makes the trajectory a transient rather than a step: the shorter it is, the further the inflow lags behind the condition. A long ramp approaches a sequence of steady states, and a short one is where the dynamic inflow, and any dynamic stall carried along with it, actually show themselves.
- **Proposed:** no change.

### ¶18 (15.3) "The physics. Two intervals decide the run..."
- **Rules broken:** G14
- **Setting:** none (prose)
- **Current:** Refining the sample interval makes the recorded curve smoother; refining the sub-steps makes the marched state more accurate without adding a single row to the table.
- **Proposed:** Refining the sample interval makes the recorded curve smoother. Refining the sub-steps makes the marched state more accurate without adding a single row to the table.

### ¶19 (15.3) "A useful reading of the pair..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** A useful reading of the pair: choose the sample interval from what you want to SEE, and the sub-steps from what the PHYSICS needs. If halving the sub-steps changes the curve, the march was not resolved.
- **Proposed:** no change.

### ¶20 (15.3) "Ranges. The sample interval accepts..."
- **Rules broken:** G14
- **Setting:** Sample interval [s] / Sub-steps per sample fields (Sampling and march block)
- **Current:** The sample interval accepts $0.001$ to $5$ seconds and defaults to $0.05$; the sub-step count accepts $1$ to $200$ and defaults to $8$.
- **Proposed:** The sample interval accepts $0.001$ to $5$ seconds and defaults to $0.05$. The sub-step count accepts $1$ to $200$ and defaults to $8$.

### ¶21 (15.3) "GUI: Sample interval [s] and Sub-steps per sample..."
- **Rules broken:** none
- **Setting:** Sample interval [s] / Sub-steps per sample / Cost estimate (GUI)
- **Current:** GUI: Sample interval [s] and Sub-steps per sample in the Sampling and march block, with the Cost estimate block turning the two into a number of solver calls before anything is run.
- **Proposed:** no change.

### ¶22 (15.3) ".bemt: the keys dt_s, default 0.02..."
- **Rules broken:** none
- **Setting:** dt_s / substeps_per_step keys (.bemt file)
- **Current:** .bemt: the keys dt_s, default $0.02$, and substeps_per_step, default $8$.
- **Proposed:** no change.

### ¶23 (15.3) "CLI: --maneuver-dt FLOAT..."
- **Rules broken:** none
- **Setting:** --maneuver-dt FLOAT, --maneuver-substeps INT (CLI)
- **Current:** CLI: --maneuver-dt FLOAT and --maneuver-substeps INT override the values stored with the manoeuvre without editing it.
- **Proposed:** no change.

### ¶24 (15.4) "The physics. A differential equation needs..."
- **Rules broken:** G31
- **Setting:** Initial state combo
- **Current:** A differential equation needs an initial condition, and here the choice is a modelling statement rather than a numerical one.
- **Proposed:** Replace "modelling" with "modeling": "A differential equation needs an initial condition, and here the choice is a modeling statement rather than a numerical one."

### ¶25 (15.4) "Equilibrium is what a manoeuvre flown..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** Equilibrium is what a manoeuvre flown from steady flight needs. Zero is a diagnostic: it makes the inflow time constant visible directly, because the decay it produces IS that time constant. Reading a start-up transient as if it were part of the manoeuvre is the mistake this control exists to prevent.
- **Proposed:** no change.

### ¶26 (15.4) "GUI: the Initial state combo."
- **Rules broken:** none
- **Setting:** Initial state combo
- **Current:** GUI: the Initial state combo.
- **Proposed:** no change.

### ¶27 (15.4) ".bemt: the key initial_state..."
- **Rules broken:** none
- **Setting:** initial_state key (.bemt file)
- **Current:** .bemt: the key initial_state, either equilibrium (the default) or zero.
- **Proposed:** no change.

### ¶28 (15.4) "CLI: no flag of its own..."
- **Rules broken:** G14
- **Setting:** --set initial_state=zero (CLI)
- **Current:** CLI: no flag of its own; it is set with --set initial_state=zero on the manoeuvre, or stored with the definition.
- **Proposed:** CLI: no flag of its own. It is set with --set initial_state=zero on the manoeuvre, or stored with the definition.

### ¶29 (15.5) "The physics. The inflow is not the only quantity..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The inflow is not the only quantity with memory, and two more can be threaded through the march. Each is off by default, because each costs time and neither is meaningful unless the corresponding model is enabled elsewhere.
- **Proposed:** no change.

### ¶30 (15.5) "Dynamic stall carries the Øye separation state..."
- **Rules broken:** G31
- **Setting:** March dynamic stall check box
- **Current:** It needs dynamic stall switched on for the aerofoil.
- **Proposed:** Replace "aerofoil" with "airfoil": "It needs dynamic stall switched on for the airfoil."

### ¶31 (15.5) "Flapping solves the periodic flap response..."
- **Rules broken:** none
- **Setting:** March flapping (quasi-steady) check box
- **Current:** Flapping solves the periodic flap response at every sample and feeds the resulting blade motion into the loads. It is QUASI-STEADY within a sample: the blade is assumed to have reached its periodic response at the condition of that sample, which is a good assumption while the manoeuvre is slow compared with one revolution and a poor one when it is not. It is not a flap transient, and the window says so on the control itself.
- **Proposed:** no change.

### ¶32 (15.5) "GUI: the March dynamic stall..."
- **Rules broken:** none
- **Setting:** March dynamic stall / March flapping (quasi-steady) check boxes
- **Current:** GUI: the March dynamic stall and March flapping (quasi-steady) check boxes.
- **Proposed:** no change.

### ¶33 (15.5) ".bemt: the keys march_dynamic_stall..."
- **Rules broken:** none
- **Setting:** march_dynamic_stall / march_flapping keys (.bemt file)
- **Current:** .bemt: the keys march_dynamic_stall and march_flapping, both false by default.
- **Proposed:** no change.

### ¶34 (15.5) "CLI: both travel with the saved manoeuvre..."
- **Rules broken:** none
- **Setting:** --set march_dynamic_stall=true (CLI)
- **Current:** CLI: both travel with the saved manoeuvre; a run that needs them switched on for one execution uses --set march_dynamic_stall=true.
- **Proposed:** no change.

### ¶35 (15.6) "The run produces one row per sample."
- **Rules broken:** none
- **Setting:** Time history / Disk map at sample blocks
- **Current:** The run produces one row per sample. Besides the loads, each row carries the marched interval, the number of sub-steps taken and the state the march started from, so a stored history says how it was produced and not only what it produced. The Time history block plots any column against time; the Disk map at sample block draws the disk at a chosen sample index, which is how a transient is inspected where a steady run would be inspected in the Results tab.
- **Proposed:** no change.

### ¶36 (15.6) "What to check first."
- **Rules broken:** none
- **Setting:** Validation block
- **Current:** A transient that did not settle must not be read as a settled one. The Validation block reports the findings of the same checks the rest of the program uses, and a manoeuvre whose last revolutions are still changing is reported rather than quietly averaged. Where the answer is meant to end in equilibrium, comparing the last sample against a steady run of the same condition is the cheapest check there is: the two must agree, and a difference is either a manoeuvre that has not finished settling or a sample interval too coarse to have followed it.
- **Proposed:** no change.

## Section 16 — Stability Derivatives (anchor: cap-stability)
- Paragraphs reviewed: 24 | OK: 14 | Proposals: 10

### ¶1 "A stability derivative answers one question..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** A stability derivative answers one question: if the rotor flies a little faster, rolls a little quicker, or its collective moves a little, how much does one hub load change? The answer is a number — newtons per metre per second, newton-metres per radian per second — and a whole flight-dynamics model is nothing more than a table of such numbers about one trim point.
- **Proposed:** no change.

### ¶2 "The Stability Derivatives window, opened from the Tools button..."
- **Rules broken:** none
- **Setting:** none (prose; figure caption)
- **Current:** The Stability Derivatives window, opened from the Tools button in the main window's top bar. The Trim point page is open: the study list and trim mode on the left; the trim-only check and the project's validation findings on the right.
- **Proposed:** no change.

### ¶3 "The study. GUI: derivatives at the top of the window..."
- **Rules broken:** none
- **Setting:** derivatives selector (.bemt key; top of window)
- **Current:** GUI: derivatives at the top of the window selects the named study, which fixes what is perturbed, what is measured, how big each step is and at which flight condition, so that a set of derivatives can be reproduced rather than re-typed.
- **Proposed:** no change.

### ¶4 ".bemt: the studies are stored..."
- **Rules broken:** none
- **Setting:** inputs/derivatives.bemt (.bemt file); --derivatives NAME (CLI)
- **Current:** .bemt: the studies are stored in inputs/derivatives.bemt. CLI: --derivatives NAME.
- **Proposed:** no change.

### ¶5 (16.1) "A derivative about a bad trim describes..."
- **Rules broken:** none
- **Setting:** trim mode (zero flapping / thrust / none) on Trim point page
- **Current:** A derivative about a bad trim describes a rotor nobody flies. The trim fixes the reference controls first: zero flapping solves both cyclic harmonics so the tip-path plane sits level at the reference state (the usual choice, and the default), thrust solves collective until a target thrust is hit, and none keeps the saved controls exactly as they are. Run the trim alone before any sweep: every number in chapter inherits from this point.
- **Proposed:** no change.

### ¶6 (16.1) "Setting the point. GUI: trim_target_thrust..."
- **Rules broken:** none
- **Setting:** trim_target_thrust key (.bemt key; Trim point page)
- **Current:** GUI: trim_target_thrust is the thrust the collective is driven to before any perturbation is applied. A derivative is a slope AT A POINT, so the point has to be defined: comparing two rotors at the same collective compares them at different thrusts, and comparing them at the same thrust is almost always the question actually being asked. Zero leaves the condition untrimmed and uses its collective as written.
- **Proposed:** no change.

### ¶7 (16.1) ".bemt: the key trim_target_thrust..."
- **Rules broken:** none
- **Setting:** trim_target_thrust / trim keys, inputs/derivatives.bemt (.bemt file)
- **Current:** .bemt: the key trim_target_thrust inside the study in inputs/derivatives.bemt, alongside trim, which chooses between no trim, a thrust trim and a cyclic flapback trim.
- **Proposed:** no change.

### ¶8 (16.2) "The perturbation set is nine quantities..."
- **Rules broken:** none
- **Setting:** Perturbations page check boxes and steps table
- **Current:** The perturbation set is nine quantities: longitudinal, lateral and axial speed (u, v, w), roll and pitch rate (p, q), rotor speed Ω, and the three pitch controls θ0, θ1c, θ1s. Each derivative is a central difference, ... with a step stated PER QUANTITY in its own unit — 0.5 m/s for speeds, 0.02 rad/s for rates, 0.1° for pitch controls, half a percent of the trim rpm for Ω — because truncation error grows as h^2 while round-off shrinks as 1/h: too small a step drowns the answer in solver noise, too large a step averages over real curvature.
- **Proposed:** no change.

### ¶9 (16.2) "In the GUI: tick states and controls..."
- **Rules broken:** none
- **Setting:** Perturbations page check boxes and steps table
- **Current:** In the GUI: tick states and controls on the Perturbations page, adjust any step in its table, and read the solve count before running. With no flap freedom the rate and cyclic boxes stay visible but disabled: a rigid blade cannot feel them.
- **Proposed:** no change.

### ¶10 (16.2) "In the .bemt file: a study lives..."
- **Rules broken:** none
- **Setting:** states / controls / outputs / steps / trim / richardson_check keys, inputs/derivatives.bemt (.bemt file)
- **Current:** In the .bemt file: a study lives in inputs/derivatives.bemt with its states, controls, outputs, steps, trim ("none", "thrust", "cyclic_flapback") and richardson_check.
- **Proposed:** no change.

### ¶11 (16.2) "From the CLI: --derivatives NAME runs a saved study..."
- **Rules broken:** none
- **Setting:** --derivatives NAME, --list-derivatives, --derivatives-csv PATH (CLI)
- **Current:** From the CLI: --derivatives NAME runs a saved study and prints the matrix; given no name it runs the first one in the file. --list-derivatives names what the project holds, and --derivatives-csv PATH writes the matrix to a chosen file instead of the outputs folder. The persisted inputs/derivatives.bemt remains the interface of record: the flags select and run a study, they do not define one.
- **Proposed:** no change.

### ¶12 (16.2) "The states and the controls, one by one."
- **Rules broken:** none
- **Setting:** Perturbations page check boxes
- **Current:** GUI: the check boxes name the perturbations. The speeds are u along the longitudinal axis, v along the lateral one and w along the shaft; the rates are p in roll and q in pitch; Omega perturbs the rotational speed itself. The controls are the collective theta_0 and the two cyclic harmonics theta_1c and theta_1s.
- **Proposed:** no change.

### ¶13 (16.2) "w gives the heave damping..."
- **Rules broken:** none
- **Setting:** w, Omega, theta_1c, theta_1s (Perturbations page)
- **Current:** w gives the heave damping, the strongest and most reliable derivative of a rotor: it is negative in every normal state, because climbing into the flow lowers the thrust. Omega is unlike the others in that it rescales the reference quantities as well, so the coefficients move even when the dimensional forces barely do. theta_1c and theta_1s need a blade with flap freedom: on a rigid blade a cyclic input produces no disk tilt, and the control is shown disabled rather than hidden.
- **Proposed:** no change.

### ¶14 (16.2) "richardson_check repeats every derivative..."
- **Rules broken:** none
- **Setting:** richardson_check key (.bemt file)
- **Current:** richardson_check repeats every derivative at half the step. A central difference carries truncation error, which falls as the square of the step, against round-off, which grows as the step shrinks; one step size cannot say which of the two dominates, and two can.
- **Proposed:** no change.

### ¶15 (16.3) "An isolated rotor with a vertical shaft feels..."
- **Rules broken:** G30 (borderline)
- **Setting:** none (prose)
- **Current:** An isolated rotor with a vertical shaft feels no first-order moment from yawing: rotating about its own shaft changes no blade incidence. The yaw rate therefore stays out of the perturbation set on purpose. What remains is the yaw DAMPING (∂Q/∂Ω): torque does change with rotor speed. The vehicle model below keeps a yaw row so the bookkeeping closes, fed by that damping alone.
- **Proposed:** no change (metaphorical "feels" acceptable; borderline G30).

### ¶16 (16.4) "The tilting moments computed from the pressure field..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The tilting moments computed from the pressure field alone miss a second path into the hub: with a hinge offset or a root spring, the flapping blade carries structural moment, M_hub = ..., and for a hingeless rotor that path is the larger one. The totals reported here always include it when flap freedom exists; a rigid blade's total is simply the aerodynamic moment. These are the numbers whose derivatives make the pitch and roll damping.
- **Proposed:** no change.

### ¶17 (16.4) "The two moments this path produces."
- **Rules broken:** none
- **Setting:** Mx_total / My_total keys (.bemt file; outputs list)
- **Current:** GUI: Mx_total is the total moment about the reference in-plane axis and My_total its companion about the other, both INCLUDING the structural part carried through the hinge offset or the root spring. On an articulated blade with no offset that part vanishes and only the aerodynamic tilt remains.
- **Proposed:** no change.

### ¶18 (16.4) ".bemt: both are names in the study's outputs list..."
- **Rules broken:** none
- **Setting:** outputs list, inputs/derivatives.bemt (.bemt file)
- **Current:** .bemt: both are names in the study's outputs list in inputs/derivatives.bemt, and both are column headings of the exported table.
- **Proposed:** no change.

### ¶19 (16.5) "The matrix lists outputs down the rows..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** The matrix lists outputs down the rows and variables across the columns, switchable between dimensional and non-dimensional form without rerunning: forces divided by ρA(ΩR)^2, moments by ρA(ΩR)^2 R, speeds by ΩR and rates by Ω. The bar chart draws one output across all variables so the dominant term is visible at a glance. The SIGN CHECKS panel is the window's conscience: heave damping must be negative, pitch damping must be negative, thrust must rise with collective. A FAIL there means a sign flipped somewhere in the engine chain — do not fly the numbers.
- **Proposed:** no change.

### ¶20 (16.5) "The optional vehicle block turns the table..."
- **Rules broken:** none
- **Setting:** Vehicle model (optional) block on Run page
- **Current:** The optional vehicle block turns the table into a rigid-body linear model ([u v w p q r φ θ] against the three pitch controls), draws its eigenvalues on the complex plane and marks unstable poles in red. Its limits are stated where the checkbox lives and repeated here: ONE rotor, NO fuselage, NO tail, NO engine dynamics. A classic mode (phugoid, subsidence, Dutch roll) is named only when its damping and frequency fall inside the expected band; an unnamed pole is not a discovery, it is the tool refusing to guess.
- **Proposed:** no change.

### ¶21 (16.5) "The outputs. GUI: Thrust is the force..."
- **Rules broken:** none
- **Setting:** Thrust / H / Y / Torque outputs (.bemt file; outputs list)
- **Current:** GUI: Thrust is the force along the shaft and the output most derivatives are read against. H is the in-plane drag force: small beside the thrust and decisive anyway, because with a hub above the centre of gravity it is the force whose arm pitches the aircraft. Y is its lateral companion, near zero in hover by symmetry. Torque is the moment about the shaft, which is what an engine or a governor model needs.
- **Proposed:** no change.

### ¶22 (16.5) ".bemt: the study's outputs list..."
- **Rules broken:** none
- **Setting:** outputs list, inputs/derivatives.bemt (.bemt file)
- **Current:** .bemt: the study's outputs list in inputs/derivatives.bemt holds these names, and they are the column headings of the exported table.
- **Proposed:** no change.

### ¶23 (16.6) "What these are. The derivatives above belong to the ROTOR."
- **Rules broken:** none
- **Setting:** Vehicle model (optional) block on Run page
- **Current:** The derivatives above belong to the ROTOR. Turning them into aircraft motion needs the aircraft, and the aircraft is not derivable from the blade: its mass, its three moments of inertia and where the hub sits relative to the centre of gravity have to be stated. That is what this block asks for, and why it is optional — a rotor study that stops at the derivative matrix never needs it.
- **Proposed:** no change.

### ¶24 (16.6) "The mathematics. The linearised rigid-body model..."
- **Rules broken:** G31 (borderline "linearised")
- **Setting:** none (prose)
- **Current:** The linearised rigid-body model is x-dot=Ax+Bu with the state x=[u,v,w,p,q,r,φ,θ] and the controls u=[θ0,θ1c,θ1s]. A rotor force enters divided by the mass and a rotor moment divided by the inertia about its own axis:
- **Proposed:** Replace "linearised" with "linearized".

### ¶25 (16.6) "The hub arm is what makes a FORCE produce a moment."
- **Rules broken:** none
- **Setting:** Hub ahead of the CG / Hub above the CG fields (Run page)
- **Current:** With the hub a height z_h above the centre of gravity, a rearward hub force pitches the aircraft, so the pitching row gains the arm term A_q,u = (1/I_y)(∂M_x/∂u + z_h ∂H/∂u).
- **Proposed:** no change.

### ¶26 (16.6) "A zero arm is therefore a modelling choice..."
- **Rules broken:** G31
- **Setting:** Hub ahead of the CG / Hub above the CG fields (Run page)
- **Current:** A zero arm is therefore a modelling choice and not a neutral default: it removes the term that couples thrust and drag changes into the pitching and rolling equations, which for a helicopter is most of the coupling there is.
- **Proposed:** Replace "modelling" with "modeling".

### ¶27 (16.6) "What it does not model. One rotor and nothing else..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** One rotor and nothing else: no fuselage drag, no tail rotor, no horizontal stabiliser, no engine or governor dynamics. The eigenvalues drawn beside the block are those of a rotor-and-mass system, useful for comparing designs against each other, and not a flight-dynamics model of an aircraft.
- **Proposed:** no change.

### ¶28 (16.6) "GUI: Vehicle model (optional) on the Run page..."
- **Rules broken:** none
- **Setting:** Vehicle model (optional), Build the rigid-body A/B matrices, Mass, inertias, Hub ahead of the CG, Hub above the CG, g (Run page)
- **Current:** GUI: Vehicle model (optional) on the Run page. Build the rigid-body A/B matrices enables it; Mass, the three inertias, Hub ahead of the CG, Hub above the CG and g are the inputs.
- **Proposed:** no change.

### ¶29 (16.6) ".bemt: the keys vehicle_enabled..."
- **Rules broken:** none
- **Setting:** vehicle_enabled / vehicle_mass_kg / vehicle_Ix_kg_m2 / vehicle_Iy_kg_m2 / vehicle_Iz_kg_m2 / hub_offset_x_m / hub_offset_z_m / gravity_m_s2 keys, inputs/derivatives.bemt (.bemt file)
- **Current:** .bemt: the keys vehicle_enabled, vehicle_mass_kg, vehicle_Ix_kg_m2, vehicle_Iy_kg_m2, vehicle_Iz_kg_m2, hub_offset_x_m, hub_offset_z_m and gravity_m_s2 in inputs/derivatives.bemt. They used to live only in the window, which put the whole block outside the file and outside the CLI.
- **Proposed:** no change.

### ¶30 (16.6) "CLI: set in the persisted study and run..."
- **Rules broken:** none
- **Setting:** --derivatives NAME (CLI)
- **Current:** CLI: set in the persisted study and run with --derivatives NAME; there is no flag that overrides them, because they describe the aircraft rather than the run.
- **Proposed:** no change.

## Structural defects (appendix items)
- line 8675: em dash joining an explanation to its topic ("keeps the table honest too — a rectangular base renames the first column..."), G15 (already raised as ¶5).
- line 9205: em dash joining two sentences ("chapter 16 — that chapter is where the step size..."), G15 (already raised as ¶61).
- line 9295: em dash joining two sentences ("keeps thresholds honest — a thrust floor of 0.008..."), G15 (already raised as ¶11 in section 14).
- line 9409: em dash joining two ideas ("how close children stay to them — large values keep the family together"), G15 (already raised as ¶31 in section 14).
- line 9455: em dash joining an idea ("is a falling curve — each step right along the first objective..."), G15 (already raised as ¶36 in section 14).
- line 9559: em dash joining an apposition ("steady forward flight — most of what a rotor does"), G15 (already raised as ¶1 in section 15).
- line 9893: no dash; the sign panel sentence "A FAIL there means a sign flipped somewhere in the engine chain — do not fly the numbers." uses an em dash joining two ideas, G15 (already raised as ¶19 in section 16).
- line 9496: em dash delimiters around an aside ("collected as they finish — so that one slow design does not hold up the reading of the rest — and each is written back..."), G15 (borderline, parenthetical aside; noted in ¶42 of section 14).
- British spelling occurrences flagged under G31: line 9369 "greyed out" (¶24 s14), line 9451 "grey" and line 9455 "neighbouring" (¶36 s14), line 9618 "behaviour" (¶9 s15), line 9636 "neighbouring" (¶12 s15), line 9708 "modelling" (¶24 s15), line 9738 "aerofoil" (¶30 s15), line 9910 "linearised" (¶24 s16), line 9955 "modelling" (¶26 s16), line 9116 "per cent" (¶50 s13).
- Semicolon splices flagged under G14 are listed with their paragraph entries above (lines 8727, 9175, 9237, 9279, 9286, 9317, 9369, 9389, 9409, 9436/9445, 9517, 9543, 9595, 9648, 9661, 9679, 9690, 9725).

All line numbers refer to docs/documentation.html. Facts, physics, equations, hedges and HTML structure are preserved in every proposal. The fixed per-field pattern (physics, equation, options, then GUI / .bemt / CLI) is structure, not a violation.

---

# Block I: chapters 17–18 and References (lines 9985–end)

## Section 17 — Command-line reference (anchor: sec-15-outside-the-gui)
- Paragraphs reviewed: 19 | OK: 6 | Proposals: 13

### ¶1 "This chapter is the concise reference..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "This chapter is the concise reference for automation. It lists the supported <span class="cli">CLI</span> commands and flags, the corresponding <code>.bemt</code> files, validation rules, and common option combinations. Every editable project field remains reachable through the serialized project representation, including fields without a dedicated <span class="gui">GUI</span> control."
- **Proposed:** (no change)

### ¶2 "The CLI points at a project folder..."
- **Rules broken:** G2, G22
- **Setting:** `zbemt --project`
- **Current:** "The <span class="cli">CLI</span> points at a project folder, runs the condition or the sweep asked for, and writes the results. It goes through the same code as the <span class="gui">GUI</span> and applies the same validation, so a project run either way gives the same numbers."
- **Proposed:** "The <span class="cli">CLI</span> points at a project folder, runs the requested condition or sweep, and writes the results. It goes through the same code as the <span class="gui">GUI</span> and applies the same validation. Therefore, a project run either way gives the same numbers."

### ¶3 "Every flag sets a field the GUI can also edit..."
- **Rules broken:** G2, G3
- **Setting:** none (prose)
- **Current:** "Every flag sets a field the <span class="gui">GUI</span> can also edit, and a <span class="bemt">.bemt</span> written by any of the three is read back identically by the other two. After installing, the command <code>zbemt</code> is available. Without installing, <code>python -m zbemt.cli</code> is the equivalent."
- **Proposed:** "Every flag sets a field the <span class="gui">GUI</span> can also edit. The other two interfaces read a <span class="bemt">.bemt</span> written by any of the three back identically. After installing, the command <code>zbemt</code> is available. Without installing, <code>python -m zbemt.cli</code> is the equivalent."

### ¶4 "Complete table of flags..."
- **Rules broken:** G6, G12, G27
- **Setting:** none (prose)
- **Current:** "Complete table of flags (grouped by corresponding tab. See each linked section for the physical meaning of each field):"
- **Proposed:** "The table below lists the complete set of flags, grouped by their corresponding tab. See each linked section for the physical meaning of each field."

### ¶5 "reaches any configuration or airfoil field..."
- **Rules broken:** none
- **Setting:** `--set`
- **Current:** "<code>--set NAMESPACE.FIELD=VALUE</code> (for example, <code>--set config.Ne=90 --set config.Npsi=144</code>) reaches any configuration or airfoil field, with or without a dedicated flag. The name is checked against the project schema, so a typo becomes an error message rather than silence"
- **Proposed:** (no change)

### ¶6 "A field with no dedicated flag is still reachable..."
- **Rules broken:** G2, G22, G27
- **Setting:** `--set`
- **Current:** "A field with no dedicated flag is still reachable, with <code>--set</code>. The field sections of the earlier chapters say so one by one, and they are mostly fine-grained numerical settings (the analytical polar coefficients, the blend widths of the reverse-flow and full-range models, and the five relaxation-schedule parameters) for which a value given on the command line is rarely the natural way to work. Setting one of those permanently means editing the project file, or setting it in the window and saving."
- **Proposed:** "A field with no dedicated flag is still reachable with <code>--set</code>. The field sections of the earlier chapters state this one by one. These are mostly fine-grained numerical settings, such as the analytical polar coefficients, the blend widths of the reverse-flow and full-range models, and the five relaxation-schedule parameters. A value given on the command line is rarely the natural way to set them. Setting one permanently means editing the project file, or setting it in the window and saving."

### ¶7 "Every configuration is checked before the solver is called..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "Every configuration is checked before the solver is called, and the same checks apply to the <span class="gui">GUI</span>, the <span class="cli">CLI</span> and a project run from a saved file. They flag combinations that are physically inconsistent or not implemented. A finding either reports only, as <code>info</code> or <code>warning</code>, or blocks execution, as <code>error</code>."
- **Proposed:** (no change)

### ¶8 "Øye interpolates between $C_{l,att}$..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "Øye interpolates between $C_{l,att}$ and the separated $C_l$ from the <i>static</i> polar. Without stall in the base polar there is no separation to model."
- **Proposed:** (no change)

### ¶9 "Field has no effect in that combination."
- **Rules broken:** G6, G12
- **Setting:** none (prose)
- **Current:** "Field has no effect in that combination."
- **Proposed:** "The field has no effect in that combination."

### ¶10 "No polar for the solver to consume."
- **Rules broken:** G6, G12
- **Setting:** none (prose)
- **Current:** "No polar for the solver to consume."
- **Proposed:** "No polar exists for the solver to consume."

### ¶11 "Needs the profile shape to generate the polar..."
- **Rules broken:** G6, G12
- **Setting:** none (prose)
- **Current:** "Needs the profile shape to generate the polar (<a class="xref" href="#cap-3-8" title="8.8 External polar generation">Section 8.8</a>)."
- **Proposed:** "It needs the profile shape to generate the polar (<a class="xref" href="#cap-3-8" title="8.8 External polar generation">Section 8.8</a>)."

### ¶12 "Fading window ... is invalid."
- **Rules broken:** G6, G12
- **Setting:** none (prose)
- **Current:** "Fading window (<a class="xref" href="#cap-3-3-4" title="8.3.5 Fade window">Section 8.3.5</a>) is invalid."
- **Proposed:** "The fading window (<a class="xref" href="#cap-3-3-4" title="8.3.5 Fade window">Section 8.3.5</a>) is invalid."

### ¶13 "Positive/negative stall signals probably swapped."
- **Rules broken:** G26, G6, G12
- **Setting:** none (prose)
- **Current:** "Positive/negative stall signals probably swapped."
- **Proposed:** "The positive and negative stall signals are probably swapped." (hedge "probably" preserved)

### ¶14 "Heuristic: the table was probably truncated before saturation."
- **Rules broken:** G6, G12
- **Setting:** none (prose)
- **Current:** "Heuristic: the table was probably truncated before saturation."
- **Proposed:** "This is a heuristic: the table was probably truncated before saturation." (hedge "probably" preserved)

### ¶15 "Without the extension ... the reverse-flow region..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "Without the extension (<a class="xref" href="#cap-3-2-4" title="8.2.4 Full-range extension and blend width">Section 8.2.4</a>), the reverse-flow region has no physically defined polar."
- **Proposed:** (no change)

### ¶16 "Only the classical three-state formulation is available."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "Only the classical three-state formulation is available."
- **Proposed:** (no change)

### ¶17 "Double-counting compressibility ..."
- **Rules broken:** G6, G12
- **Setting:** none (prose)
- **Current:** "Double-counting compressibility (<a class="xref" href="#cap-3-5" title="8.5 Compressibility">Section 8.5</a>)."
- **Proposed:** "Enabling the correction double-counts the compressibility effects (<a class="xref" href="#cap-3-5" title="8.5 Compressibility">Section 8.5</a>)."

### ¶18 "zBEMT solves steady and quasi-steady conditions only..."
- **Rules broken:** G24
- **Setting:** none (prose)
- **Current:** "zBEMT solves steady and quasi-steady conditions only. A value naming a time-marching inflow variant is rejected before the solver runs, with the message naming <code>pitt_peters_steady</code> as the supported choice."
- **Proposed:** "zBEMT solves steady and quasi-steady conditions only. A value naming a time-marching inflow variant is rejected before the solver runs. The message names <code>pitt_peters_steady</code> as the supported choice."

### ¶19 "The window enforces most of these rules..."
- **Rules broken:** G22, G2
- **Setting:** none (prose)
- **Current:** "The window enforces most of these rules before they can be broken, by disabling a field or hiding an option that does not apply. Validation is the safety net behind that, and it applies equally to a run started from the command line, where there are no widgets to disable."
- **Proposed:** "The window enforces most of these rules before they can be broken, by disabling a field or hiding an option that does not apply. Validation is the safety net behind this. It applies equally to a run started from the command line, where there are no widgets to disable."

## Section 18 — Limitations (anchor: limitations)
- Paragraphs reviewed: 10 | OK: 6 | Proposals: 4

### ¶1 "The following limitations bound the interpretation..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "The following limitations bound the interpretation of every result. Mesh refinement and tighter numerical tolerances reduce numerical error, but they do not remove the modeling limitations listed below."
- **Proposed:** (no change)

### ¶2 "zBEMT models the blade as RIGID in bending..."
- **Rules broken:** G14, G2, G3, G22
- **Setting:** none (prose)
- **Current:** "zBEMT models the blade as RIGID in bending and torsion. Rigid-body flap and lead-lag about a hinge are solved (SC-11), and the hub pitching and rolling moments they carry are reported; what is neglected is elastic deflection of the blade itself, so a blade soft enough to bend appreciably is outside the model."
- **Proposed:** "zBEMT models the blade as RIGID in bending and torsion. It solves rigid-body flap and lead-lag about a hinge (SC-11) and reports the hub pitching and rolling moments they carry. What is neglected is elastic deflection of the blade itself. Therefore, a blade soft enough to bend appreciably is outside the model."

### ¶3 "zBEMT solves each radial annulus..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "zBEMT solves each radial annulus with isolated 1D momentum conservation. Therefore, empirical tip and root loss models approximate the turbulent mixing between annuli and the full 3D wake roll-up."
- **Proposed:** (no change)

### ¶4 "Classical momentum theory has no unique real roots..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "Classical momentum theory has no unique real roots in steep axial descent. Therefore, empirical momentum extensions give approximate trends only."
- **Proposed:** (no change)

### ¶5 "Trim solves the collective alone..."
- **Rules broken:** G2, G22
- **Setting:** none (prose)
- **Current:** "Trim solves the collective alone, or the collective together with both cyclic angles against the two hub flapping moments (a 3&times;3 Newton). It is not a vehicle trim: the fuselage, the tail rotor and the 6-DOF force and moment balance of the aircraft are outside it, so the rotor is trimmed, not the helicopter."
- **Proposed:** "Trim solves the collective alone, or the collective together with both cyclic angles against the two hub flapping moments (a 3&times;3 Newton). It is not a vehicle trim. The fuselage, the tail rotor and the 6-DOF force and moment balance of the aircraft are outside it. Therefore, the rotor is trimmed, not the helicopter."

### ¶6 "External solvers (for example, NeuralFoil) execute offline..."
- **Rules broken:** G7
- **Setting:** none (prose)
- **Current:** "External solvers (for example, NeuralFoil) execute offline to produce polar tables. Coupled on-the-fly aerodynamic calls during solver iterations are not supported (<a class="xref" href="#cap-3-8" title="8.8 External polar generation">Section 8.8</a>)."
- **Proposed:** "External solvers (for example, NeuralFoil) execute offline to produce polar tables. Calling an external aerodynamics model during solver iterations is not supported (<a class="xref" href="#cap-3-8" title="8.8 External polar generation">Section 8.8</a>)."

### ¶7 "Linearized Prandtl-Glauert scaling applies up to..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "Linearized Prandtl-Glauert scaling applies up to $M_{\max} = 0.9$, which bounds the amplification factor at $2.29$. However, transonic shock formation and drag divergence above $M \approx 0.75$ need specialized CFD polar data (<a class="xref" href="#cap-3-5" title="8.5 Compressibility">Section 8.5</a>)."
- **Proposed:** (no change)

### ¶8 "Enabling analytical compressibility corrections on polars..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "Enabling analytical compressibility corrections on polars that already incorporate Mach variation double-counts compressibility effects (<a class="xref" href="#cap-3-5" title="8.5 Compressibility">Section 8.5</a>)."
- **Proposed:** (no change)

### ¶9 "Formulation targets preliminary aeromechanical sizing..."
- **Rules broken:** G6, G12, G2
- **Setting:** none (prose)
- **Current:** "Formulation targets preliminary aeromechanical sizing and performance diagnosis, excluding unsteady free-wake vortex dynamics and high-frequency maneuver acoustics (<a class="xref" href="#sec-01-scope" title="0.1 Scope">Section 0.1</a>)."
- **Proposed:** "The formulation targets preliminary aeromechanical sizing and performance diagnosis. It excludes unsteady free-wake vortex dynamics and high-frequency maneuver acoustics (<a class="xref" href="#sec-01-scope" title="0.1 Scope">Section 0.1</a>)."

### ¶10 "None of these invalidate a result on their own."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "None of these invalidate a result on their own. They define when you can trust a result at face value, and when you must treat it as an estimate. An estimate needs outside corroboration, such as a trim loop, a wake model, or a reference dataset."
- **Proposed:** (no change)

## References (anchor: sec-references)
- Paragraphs reviewed: 6 | OK: 4 | Proposals: 2

### ¶1 "Kumar ... open course (Jupyter Book). Schematic figures..."
- **Rules broken:** G6, G12
- **Setting:** none (prose)
- **Current:** "...open course (Jupyter Book). Schematic figures of actuator disk, velocity triangle, reverse flow, lift asymmetry, and power curve."
- **Proposed:** "...open course (Jupyter Book). It provides schematic figures of the actuator disk, the velocity triangle, reverse flow, lift asymmetry, and power curve." (citation data unchanged)

### ¶2 "Øye ... 1991. See QBlade documentation..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "Øye, S. "Dynamic stall simulated as time lag of separation", 1991. See <a href="https://docs.qblade.org/src/theory/aerodynamics/dynamic_stall/OYE_stall.html" target="_blank">QBlade documentation</a> for the formulation of Bergami dynamic $C_d$."
- **Proposed:** (no change)

### ¶3 "The figures in this document divide into two sources..."
- **Rules broken:** G2
- **Setting:** none (prose)
- **Current:** "The figures in this document divide into two sources, and the distinction matters for anyone redistributing:"
- **Proposed:** "The figures in this document divide into two sources. The distinction matters for anyone redistributing:"

### ¶4 "docs/img/*.png: generated by zBEMT itself..."
- **Rules broken:** G6, G3
- **Setting:** none (prose)
- **Current:** "<b><code>docs/img/*.png</code></b>: generated by zBEMT itself (sweeps, disk maps, polars). They are project material, under the same license."
- **Proposed:** "The figures in <b><code>docs/img/*.png</code></b> are generated by zBEMT itself (sweeps, disk maps, polars). They are project material under the same license."

### ¶5 "docs/img/externas/: eleven schematic figures by S. Kumar..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "<b><code>docs/img/externas/</code></b>: eleven schematic figures by S. Kumar, <a href="https://kumar-sumeet.github.io/HeliAeroNotes/" target="_blank"><i>Fundamentals of Helicopter Aerodynamics</i></a>. They are bundled here, not loaded from the original site, so that this documentation works without connectivity. It is the built-in Help documentation (also opened with F1) and must work in an offline lab. Each caption maintains the credit and link to the original page. <b>The license belongs to the original author. Before publicly redistributing zBEMT, confirm the terms with him.</b>"
- **Proposed:** (no change)

### ¶6 "End of document. Figures without explicit credit..."
- **Rules broken:** none
- **Setting:** none (prose)
- **Current:** "End of document. Figures without explicit credit are graphs generated from the equations of the zBEMT solver. Figures with credit are reproduced from open sources cited in each caption."
- **Proposed:** (no change)

## Structural defects (appendix items)
- line 9985: the heading number is "17" but the anchor id is "sec-15-outside-the-gui"; left unchanged because linked cross-references resolve against it.
- none

---

# GUI popup review - help_blocks.py (BLOCK_HELP)


Note: several "OK" blocks carry one long or math-heavy descriptive string; those were judged compliant once math entities and LaTeX were set aside per the exemption. Proposals below are the items that genuinely break a rule in the surrounding prose.

## Block "global_geometry"
### Item 1 "Two numbers on this block fix the size of the problem before any aerodynamics happens..."
- **Rules broken:** G2, G14, G22, G1 (all-caps "BUILT")
- **Setting:** GUI: Config/Engine tab, Global Geometry block
- **Current:** Two numbers on this block fix the size of the problem before any aerodynamics happens: the number of blades and the radius. The root cutout and the reference chord belong to the same set and are set where the radial table is BUILT, in the Generate Table dialog, because they describe how that table is laid out; the table below then carries them as its first station and as the c/R it is normalized against.
- **Proposed:** Two numbers on this block fix the size of the problem before any aerodynamics happens: the number of blades and the radius. The root cutout and the reference chord belong to the same set. You set them in the Generate Table dialog, where the radial table is built, because they describe how that table is laid out. The table below then carries them as its first station and as the c/R value it is normalized against.

## Block "blade_dynamics"
### Item 2 "Flapping answers thrust with a coning angle β0, tilts the disk in edgewise flight..."
- **Rules broken:** G2, G15 (dashes joining ideas)
- **Setting:** GUI: Config/Engine tab, Blade Dynamics block
- **Current:** Flapping answers thrust with a coning angle &beta;<sub>0</sub>, tilts the disk in edgewise flight through its 1/rev harmonics, and - when the hinge carries an offset or a spring - feeds a structural moment back into the hub: M<sub>hub</sub> = (N<sub>b</sub>/2)&middot;I<sub>&beta;</sub>&Omega;<sup>2</sup>(&nu;<sub>&beta;</sub><sup>2</sup>&minus;1)&beta;<sub>1</sub>. Lead-lag follows the same scheme in the disk plane, with a damper instead of thrust restoring.
- **Proposed:** Flapping answers thrust with a coning angle &beta;<sub>0</sub> and tilts the disk in edgewise flight through its 1/rev harmonics. When the hinge carries an offset or a spring, it also feeds a structural moment back into the hub: M<sub>hub</sub> = (N<sub>b</sub>/2)&middot;I<sub>&beta;</sub>&Omega;<sup>2</sup>(&nu;<sub>&beta;</sub><sup>2</sup>&minus;1)&beta;<sub>1</sub>. Lead-lag follows the same scheme in the disk plane, with a damper instead of thrust restoring.

## Block "radial_table"
### Item 3 "Twist is the built-in pitch variation... it is the single most effective way..."
- **Rules broken:** G32 (superlative "single most effective")
- **Setting:** GUI: Geometry tab, Radial Distribution Table block
- **Current:** ...and it is the single most effective way to flatten the spanwise loading and raise the figure of merit.
- **Proposed:** ...and it is an effective way to flatten the spanwise loading and raise the figure of merit.

### Item 4 "In forward flight twist interacts with the advancing/retreating asymmetry..."
- **Rules broken:** G26 (joining slash)
- **Setting:** GUI: Geometry tab, Radial Distribution Table block
- **Current:** In forward flight twist interacts with the advancing/retreating asymmetry: the same washout that balances hover leaves the advancing tip at low or negative angle of attack and the retreating blade closer to stall.
- **Proposed:** In forward flight twist interacts with the advancing and retreating asymmetry: the same washout that balances hover leaves the advancing tip at low or negative angle of attack and the retreating blade closer to stall.

## Block "reverse_flow"
### Item 5 "flat_plate — Cl = 0, Cd ≈ 1.9 inside the region. The most abrupt jump in Cl..."
- **Rules broken:** G32 (superlative "most abrupt")
- **Setting:** GUI: Config/Engine tab, Reverse Flow block (model options)
- **Current:** <b>flat_plate</b> — Cl = 0, Cd ≈ 1.9 inside the region. The most abrupt jump in Cl of the five, but physically defensible as a crude bound.
- **Proposed:** <b>flat_plate</b> — Cl = 0, Cd ≈ 1.9 inside the region. It gives the largest jump in Cl of the five, but it is physically defensible as a crude bound.

### Item 6 "Rule of thumb: below μ ≈ 0.2–0.3 the region is small..."
- **Rules broken:** G28 (hyphenated range), G1 (casual "Rule of thumb")
- **Setting:** GUI: Config/Engine tab, Reverse Flow block
- **Current:** Rule of thumb: below μ ≈ 0.2–0.3 the region is small (often inside the root cutout) and all five agree. Above that, the choice is worth a sensitivity run. Masking in disk plots is a drawing option only: forces and CSV always contain the region.
- **Proposed:** As a rule of thumb, below μ of about 0.2 to 0.3 the region is small, often inside the root cutout, and all five models agree. Above that, the choice is worth a sensitivity run. Masking in disk plots is a drawing option only: forces and CSV always contain the region.

## Block "compressibility"
### Item 7 "The factor is 1.005 at M = 0.1... instead of letting it blow up. Above M ≈ 0.75–0.8..."
- **Rules broken:** G8 (phrasal verb "blow up"), G28 (hyphenated range), G1 (casual "blow up")
- **Setting:** GUI: Config/Engine tab, Compressibility block
- **Current:** The factor is 1.005 at M = 0.1, 1.048 at M = 0.3, 1.25 at M = 0.6 and formally diverges at M → 1, which is why the engine floors β instead of letting it blow up. Above M ≈ 0.75–0.8 the linearization is void anyway: shocks and wave drag are not modeled.
- **Proposed:** The factor is 1.005 at M = 0.1, 1.048 at M = 0.3, 1.25 at M = 0.6 and formally diverges at M → 1, which is why the engine floors β instead of letting it diverge. Above M from approximately 0.75 to 0.8 the linearization is void anyway: shocks and wave drag are not modeled.

## Block "inflow"
### Item 8 "Drees for helicopter cruise 0.1 < μ < 0.4... around μ ≈ 0.16–0.19."
- **Rules broken:** G28 (hyphenated range)
- **Setting:** GUI: Config/Engine tab, Inflow Model block
- **Current:** ...and with the linear-theory caveat that unrelieved hub moments can push it out of its validity range around μ ≈ 0.16–0.19.
- **Proposed:** ...and with the linear-theory caveat that unrelieved hub moments can push it out of its validity range around μ of about 0.16 to 0.19.

## Block "mesh_atmosphere"
### Item 9 "Resolving advancing and retreating asymmetry needs enough harmonics: 24 is a minimum, 72–144..."
- **Rules broken:** G28 (hyphenated ranges)
- **Setting:** GUI: Config/Engine tab, Mesh and Atmosphere block
- **Current:** Resolving advancing and retreating asymmetry needs enough harmonics: 24 is a minimum, 72–144 for high μ or cyclic pitch. Radially, 30–50 is usually converged. The reference production mesh is 120×180.
- **Proposed:** Resolving advancing and retreating asymmetry needs enough harmonics: 24 is a minimum, and 72 to 144 for high μ or cyclic pitch. Radially, 30 to 50 is usually converged. The reference production mesh is 120×180.

## Block "induction_solver"
### Item 10 "fixed_point — Picard with relaxation: ...newton (default) — ...bisection — ...aitken — ..."
- **Rules broken:** G21 (4-option set buried in prose), G14 (semicolons), G15 (dashes), G32 ("very robust", "slowest")
- **Setting:** GUI: Config/Engine tab, Induction Solver block (solver options)
- **Current:** <b>fixed_point</b> — Picard with relaxation: \n\n λ<sub>n+1</sub> = λ<sub>n</sub> + ω[g(λ<sub>n</sub>) − λ<sub>n</sub>] \n\n Linear convergence, very robust.<br><b>newton</b> (default) — Newton-Raphson on r(λ) = g(λ) − λ. Quadratic near the root, but the finite-difference Jacobian degrades on derivative corners (a reason to avoid stall_model="clip" with it).<br><b>bisection</b> — derivative-free and slowest. It expands a bracket from the physical initial estimate, then converges to the nearest bracketed root.<br><b>aitken</b> — Δ² extrapolation over two Picard iterates: superlinear, no derivative needed.
- **Proposed:** <b>fixed_point</b> — Picard with relaxation: \n\n λ<sub>n+1</sub> = λ<sub>n</sub> + ω[g(λ<sub>n</sub>) − λ<sub>n</sub>] \n\n It has linear convergence and is robust.<br>• <b>newton</b> (default) — Newton-Raphson on r(λ) = g(λ) − λ. It is quadratic near the root, but the finite-difference Jacobian degrades on derivative corners, a reason to avoid stall_model="clip" with it.<br>• <b>bisection</b> — derivative-free and slow. It expands a bracket from the physical initial estimate, then converges to the nearest bracketed root.<br>• <b>aitken</b> — Δ² extrapolation over two Picard iterates. It is superlinear and needs no derivative.

## Block "aerodynamic_model"
### Item 11 "BEMT never solves the flow around the section. It looks the coefficients up and projects them..."
- **Rules broken:** G8 (phrasal verb "looks up")
- **Setting:** GUI: Airfoil tab, Aerodynamic Model block
- **Current:** BEMT never solves the flow around the section. It looks the coefficients up and projects them onto the disk:
- **Proposed:** BEMT never solves the flow around the section. It reads the coefficients and projects them onto the disk:

### Item 12 "Static stall models extend the linear curve... • linear — ... • clip — ... • enhanced ..."
- **Rules broken:** G21 (3+ options should be a list; some items inline), G32 (no limit claim hedged only by "(solver-verification / theoretical reference only)")
- **Setting:** GUI: Airfoil tab, Aerodynamic Model block, stall models
- **Current:** <b>Static stall models</b> extend the linear curve past α<sub>stall</sub>, where C<sub>l,s</sub> = C<sub>lα</sub>(α<sub>stall</sub> − α<sub>0</sub>):<br>• <b>linear</b> — no limit; the line is used for every α (solver-verification / theoretical reference only).<br>• <b>clip</b> — C<sub>l</sub> saturates at C<sub>l,s</sub>; value-continuous but with a derivative corner.<br>• <b>enhanced</b> (default) — C¹-continuous cosine roll-off past stall over Δ = 30°: [math] • <b>viterna</b> — Viterna-Corrigan full-range closure (see below).
- **Proposed:** <b>Static stall models</b> extend the linear curve past α<sub>stall</sub>, where C<sub>l,s</sub> = C<sub>lα</sub>(α<sub>stall</sub> − α<sub>0</sub>):<br>• <b>linear</b> — no limit; the line is used for every α. This is for solver verification and theoretical reference only.<br>• <b>clip</b> — C<sub>l</sub> saturates at C<sub>l,s</sub>. It is value-continuous but has a derivative corner.<br>• <b>enhanced</b> (default) — C¹-continuous cosine roll-off past stall over Δ = 30°: [math]<br>• <b>viterna</b> — Viterna-Corrigan full-range closure (see below).

### Item 13 "Highest fidelity where data exist. Outside the measured α range the edge value is held..."
- **Rules broken:** G32 (superlative "Highest"), G6 (telegraphic fragment "Highest fidelity where data exist.")
- **Setting:** GUI: Airfoil tab, Aerodynamic Model block, tabulated source
- **Current:** Outside the measured α range the edge value is held, which is exactly why the Viterna closure exists. Highest fidelity where data exist.
- **Proposed:** Outside the measured α range the edge value is held, which is exactly why the Viterna closure exists. It is accurate where the data exist.

## Block "table_import"
### Item 14 "That last point is the one that bites. Outside the tabulated angle-of-attack range..."
- **Rules broken:** G1 (casual "is the one that bites"), G19 ("That" points at the previous paragraph's conclusion)
- **Setting:** GUI: Airfoil tab, Data import block
- **Current:** That last point is the one that bites. Outside the tabulated angle-of-attack range the interpolation holds the edge value: a table swept from −10° to 20° evaluated at 40° returns the 20° coefficients, which understates drag by a large factor.
- **Proposed:** The edge behavior is the important consequence. Outside the tabulated angle-of-attack range the interpolation holds the edge value: a table swept from −10° to 20° evaluated at 40° returns the 20° coefficients, which understates drag by a large factor.

## Block "batch_fixed_values"
### Item 15 "The most consequential fixed value is usually the advance ratio... the advancing/retreating asymmetry..."
- **Rules broken:** G26 (joining slash), G32 (superlative "most consequential")
- **Setting:** GUI: Run Batch tab, Fixed values block
- **Current:** The most consequential fixed value is usually the advance ratio, because it alone decides how much of the disk is in reverse flow and how strong the advancing/retreating asymmetry is.
- **Proposed:** The most consequential fixed value is usually the advance ratio, because it alone decides how much of the disk is in reverse flow and how strong the advancing and retreating asymmetry is.

## Block "run_case"
### Item 16 "rotor convention C_T = ...; propeller convention C_T = ..."
- **Rules broken:** G14 (semicolon joining two alternatives)
- **Setting:** GUI: Run Case tab, Run Case block
- **Current:** ...rotor convention C<sub>T</sub> = T/(ρAΩ²R²), C<sub>Q</sub>, C<sub>P</sub> with figure of merit FM = C<sub>T</sub><sup>3/2</sup>/(√2·C<sub>P</sub>); propeller convention C<sub>T</sub> = T/(ρn²D⁴), C<sub>P</sub> = P/(ρn³D⁵), η = J<sub>x</sub>·C<sub>T</sub>/C<sub>P</sub>. Which set you get is decided by the project mode, not by the case.
- **Proposed:** ...rotor convention C<sub>T</sub> = T/(ρAΩ²R²), C<sub>Q</sub>, C<sub>P</sub> with figure of merit FM = C<sub>T</sub><sup>3/2</sup>/(√2·C<sub>P</sub>). The propeller convention is C<sub>T</sub> = T/(ρn²D⁴), C<sub>P</sub> = P/(ρn³D⁵), η = J<sub>x</sub>·C<sub>T</sub>/C<sub>P</sub>. Which set you get is decided by the project mode, not by the case.

## Block "polar_generation"
### Item 17 "Accuracy is best for conventional sections at −5° < α < 25°..."
- **Rules broken:** G32 (superlative "best")
- **Setting:** GUI: Airfoil tab, Polar Generation block
- **Current:** Accuracy is best for conventional sections at −5° &lt; α &lt; 25°; it degrades at extreme α, very thin sections and unusual shapes.
- **Proposed:** Accuracy is highest for conventional sections at −5° &lt; α &lt; 25°; it degrades at extreme α, very thin sections and unusual shapes.

## Block "batch_export"
### Item 18 "That echo is what makes a result file interpretable months later. A table of coefficients without it is not."
- **Rules broken:** G6 (telegraphic "is not"), G16 (implied link needs "therefore" or restatement)
- **Setting:** GUI: Run Batch tab, Export block
- **Current:** That echo is what makes a result file interpretable months later. A table of coefficients without it is not.
- **Proposed:** That echo is what makes a result file interpretable months later. A table of coefficients without it is not interpretable.

## Block "stability_export"
### Item 19 "The HTML report adds ... A matrix without its trim point and its steps is not."
- **Rules broken:** G6 (telegraphic "is not")
- **Setting:** GUI: Stability window, Export block
- **Current:** The HTML report adds the trim point, the perturbation steps, the sign checks and the step-size error of every entry, which is what makes the numbers interpretable later. A matrix without its trim point and its steps is not.
- **Proposed:** The HTML report adds the trim point, the perturbation steps, the sign checks and the step-size error of every entry, which is what makes the numbers interpretable later. A matrix without its trim point and its steps is not interpretable.

# Structural notes
- Encoding: none observed. All Greek letters and math symbols appear as HTML entities (`&beta;`, `&Omega;`, `&le;`, `&ge;`) or as Unicode characters (`≈`, `β`, `²`); the `\u00b0`-style artifacts the brief warned about were not present.
- The block titles (and the dash separators in several titles, e.g. "Operation Mode — rotor or propeller", "Blade Dynamics - the rigid blade's flap and lead-lag freedoms") use a dash or hyphen as a subtitle separator. This is a label format, not prose joining two ideas, so it was not flagged under G15; note the hyphen in the "Blade Dynamics" title is inconsistent with the em-dash used everywhere else.
- Duplicated/overlapping text: none within `BLOCK_HELP`. Several blocks share the same `anchor` (e.g. all maneuver blocks use `cap-transiente`; flap_plots and blade_dynamics both use `sec-blade-dynamics`; stability_results and stability_export both use `cap-stability-run`). This is by design (same documentation chapter) and was not treated as duplication.
- Several blocks (reverse_flow models, inflow models, induction_solver solvers, aerodynamic_model stall models) present 3+ named options as prose; G21 was applied to the induction_solver and stall-model strings and is the same latent issue in reverse_flow/inflow, left as-is because their em-dash label format already reads as a de facto list.

---

# GUI popup review - help_content.py (FIELD_HELP and other help)


## Field "axis_unit"
- **Rules broken:** G14 (semicolon joining two clauses); G19 (ambiguous "this")
- **Setting:** Axis Unit dropdown, Run Batch tab (factorial builder)
- **Current:** "The form the values on this axis are written in.\n\nThe same physical condition can be stated as a ratio, a speed or an angle; this says which one the list below uses."
- **Proposed:** "The form the values on this axis are written in.\n\nThe same physical condition can be stated as a ratio, a speed, or an angle. This field says which one the list below uses."

## Field "axis_values"
- **Rules broken:** G14 (semicolon joining two clauses)
- **Setting:** Axis Values list, Run Batch tab (factorial builder)
- **Current:** "The values this axis takes, separated by commas.\n\nThis list is what the factorial actually uses. The range controls beside it are a convenience that WRITES into this list; they are not read directly."
- **Proposed:** "The values this axis takes, separated by commas.\n\nThis list is what the factorial actually uses. The range controls beside it are a convenience that WRITES into this list. They are not read directly."

## Field "plots"
- **Rules broken:** G32 (superlative "by far the most expensive")
- **Setting:** Exported Plots checkboxes, Run Batch tab
- **Current:** "The disk maps are by far the most expensive, because they are one image per field per condition. On a long queue, switching them off is the difference between a quick batch and a slow one."
- **Proposed:** "The disk maps cost the most time, because they are one image per field per condition. On a long queue, switching them off is the difference between a quick batch and a slow one."

## Field "save_csv"
- **Rules broken:** G14 (semicolon joining two clauses)
- **Setting:** Save CSV checkbox, Run Batch tab
- **Current:** "It is the export the results are usually read from outside the program. The figures are a view of the same numbers; the CSV is the numbers."
- **Proposed:** "It is the export the results are usually read from outside the program. The figures are a view of the same numbers. The CSV is the numbers."

## Field "trim_mode"
- **Rules broken:** G14 (semicolon joining two clauses)
- **Setting:** Trim Mode dropdown, Run Case / Run Batch tab
- **Current:** "It changes what a comparison MEANS. Two rotors at the same collective are being compared at two different thrusts; at the same thrust they are being compared at two different collectives, which is nearly always the intended question."
- **Proposed:** "It changes what a comparison MEANS. Two rotors at the same collective are compared at two different thrusts. At the same thrust they are compared at two different collectives, which is nearly always the intended question."

## Field "v"
- **Rules broken:** G14 (semicolon joining two clauses)
- **Setting:** v — lateral speed step, Stability Derivatives window (state perturbations)
- **Current:** "Gives the lateral force and rolling-moment derivatives. In hover they are near zero by symmetry; in forward flight they are not, and that asymmetry is what couples roll to sideslip."
- **Proposed:** "Gives the lateral force and rolling-moment derivatives. In hover they are near zero by symmetry. In forward flight they are not, and that asymmetry is what couples roll to sideslip."

## Field "parallel_workers"
- **Rules broken:** G14 (semicolon joining two clauses)
- **Setting:** Parallel Workers spinbox, Optimization window and Stability Derivatives window
- **Current:** "Only the wall-clock time changes: results are collected in submission order, so one worker and eight workers produce the same front, member for member. In the derivative study the value is stored but not yet used; that run is serial."
- **Proposed:** "Only the wall-clock time changes. Results are collected in submission order, so one worker and eight workers produce the same front, member for member. In the derivative study the value is stored but not yet used. That run is serial."

## Field "generations"
- **Rules broken:** G14 (semicolon joining two clauses)
- **Setting:** Generations spinbox, Optimization window
- **Current:** "How many rounds of selection and variation run after the initial sample.\n\nThe population converges over generations; the hypervolume curve on the Convergence view is what says whether it already has."
- **Proposed:** "How many rounds of selection and variation run after the initial sample.\n\nThe population converges over generations. The hypervolume curve on the Convergence view is what says whether it already has."

## Field "interpolation"
- **Rules broken:** G14 (semicolon); G19 (ambiguous "this")
- **Setting:** Interpolation dropdown, Transient window (builder)
- **Current:** "How the condition moves between two nodes of the trajectory.\n\nThe nodes state where the vehicle is at given instants; this states what it does in between."
- **Proposed:** "How the condition moves between two nodes of the trajectory.\n\nThe nodes state where the vehicle is at given instants. This field states what it does in between."

## Field "trim_target_thrust"
- **Rules broken:** G14 (semicolon joining two clauses)
- **Setting:** Thrust Target of the Trim field, Stability Derivatives window
- **Current:** "A derivative is a slope AT A POINT, so the point has to be defined. Comparing two rotors at the same collective compares them at different thrusts; comparing them at the same thrust is almost always the question actually being asked."
- **Proposed:** "A derivative is a slope AT A POINT, so the point has to be defined. Comparing two rotors at the same collective compares them at different thrusts. Comparing them at the same thrust is almost always the question actually being asked."

## Field "richardson_check"
- **Rules broken:** G14 (semicolon joining two clauses)
- **Setting:** Richardson Half-Step Check, Stability Derivatives window
- **Current:** "A central difference carries two errors that move in opposite directions: truncation, which falls as the square of the step, and round-off, which grows as the step shrinks. A single step size cannot tell you which one you are dominated by; two can."
- **Proposed:** "A central difference carries two errors that move in opposite directions: truncation, which falls as the square of the step, and round-off, which grows as the step shrinks. A single step size cannot tell you which one you are dominated by. Two can."

## Field "vehicle_Iy_kg_m2"
- **Rules broken:** G31 (British spelling "centre")
- **Setting:** Pitch Inertia field, Stability Derivatives window (vehicle block)
- **Current:** "It is the inertia the hub arm acts through, because a hub force at a height above the centre of gravity pitches the aircraft."
- **Proposed:** "It is the inertia the hub arm acts through, because a hub force at a height above the center of gravity pitches the aircraft."

## Field "hub_offset_x_m"
- **Rules broken:** G31 (British spelling "centre")
- **Setting:** Hub Ahead of the CG field, Stability Derivatives window (vehicle block)
- **Current:** "Longitudinal distance from the centre of gravity to the hub, positive forward."
- **Proposed:** "Longitudinal distance from the center of gravity to the hub, positive forward."

## Field "hub_offset_z_m"
- **Rules broken:** G31 (British spelling "centre")
- **Setting:** Hub Above the CG field, Stability Derivatives window (vehicle block)
- **Current:** "Vertical distance from the centre of gravity to the hub, positive up."
- **Proposed:** "Vertical distance from the center of gravity to the hub, positive up."

## Field "source"
- **Rules broken:** G32 ("best" superlative)
- **Setting:** Polar Source option "analytical", Airfoil tab
- **Current:** "Polynomial analytical model with stall transition. Fast and smooth, best for preliminary design."
- **Proposed:** "Polynomial analytical model with stall transition. Fast and smooth, and suitable for preliminary design."

## Field "stall_model"
- **Rules broken:** G32 (superlative "the most physically grounded")
- **Setting:** Stall Model option "viterna", Airfoil tab
- **Current:** "Viterna-Corrigan model with curvature. It extends to ±90° if enabled and is the most physically grounded choice for high α and reverse flow."
- **Proposed:** "Viterna-Corrigan model with curvature. It extends to ±90° if enabled and is a physically grounded choice for high α and reverse flow."

## Field "reverse_flow_model"
- **Rules broken:** G32 (non-technical vague word "Robust"); G14 (semicolon)
- **Setting:** Reverse-Flow Polar option "flat_plate", Airfoil tab
- **Current:** "Inside the reverse region the section is treated as a flat plate: Cl = 0 and Cd = 1.9, with α_eff = −α_geom and the Mach number taken from |Ut|.\n\nRobust and idealized; discards the airfoil's own polar where it applies."
- **Proposed:** "Inside the reverse region the section is treated as a flat plate: Cl = 0 and Cd = 1.9, with α_eff = −α_geom and the Mach number taken from |Ut|.\n\nIt is an idealized treatment. It discards the airfoil's own polar where it applies."

## Field "kind"
- **Rules broken:** G21 (3-item sequence buried in one sentence); G14 (semicolons)
- **Setting:** Chord Distribution Type dropdown, Geometry tab (radial table generator)
- **Current:** "Shape of the chord distribution along the radius used by the radial table generator.\n\n'rectangular' keeps a single constant chord; 'tapered' interpolates linearly between a root and a tip chord; 'elliptic' follows an elliptic planform, which minimizes induced drag for a given lift in fixed-wing theory."
- **Proposed:** "Shape of the chord distribution along the radius used by the radial table generator.\n\n- 'rectangular' keeps a single constant chord.\n- 'tapered' interpolates linearly between a root chord and a tip chord.\n- 'elliptic' follows an elliptic planform, which minimizes induced drag for a given lift in fixed-wing theory."

## Field "relax"
- **Rules broken:** G28 (hyphenated range in prose "0-1"); G14 (semicolon)
- **Setting:** Global Relaxation Factor, Config/Engine tab
- **Current:** "Global relaxation factor ω applied to the induced-inflow update: λi,new = λi,old + ω·Δλi.\n\nTypically 0-1; stabilizes oscillatory convergence."
- **Proposed:** "Global relaxation factor ω applied to the induced-inflow update: λi,new = λi,old + ω·Δλi.\n\nIt typically falls between 0 and 1. It stabilizes oscillatory convergence."

# Structural notes
- Encoding artifacts: many math strings in the range fields of the solver/free-stream families (e.g. "1e-8–1e-4", "1e-6–1e-3") and in fields such as `relax`, `xfoil_xtr_top`, `xfoil_xtr_bot` render replacement characters (`�`, `?`, `p`) in place of Greek letters (λ, μ, π, Ω, α, °, ·) and `=`. These affect math notation and were treated as artifacts; surrounding prose was reviewed as-is. Notable files/lines: `use_radial_flow_correction` (lines 2064-2069, `&sigma;C<sub>d0</sub>�/4`), `solver` (2135-2136, `g(?<sub>i</sub>)`), `is_propeller` (2293-2329), `mu_x`, `Vz`, `rpm`, `sideslip_deg`, `p_rate_deg_s`, `q_rate_deg_s`, `hinge_offset_norm`.
- Duplicated/overlapping text: `xfoil_xtr_top` and `xfoil_xtr_bot` carry identical definition and effect bodies, differing only in "upper" vs "lower"; `use_dynamic_stall`, `dynamic_stall_method` and the `stall_model`/`reverse_flow_model` option lists overlap in subject matter but are not verbatim duplicates.
- Range-field values such as "off/on", "on / off", "0.1–1.0" and "8 to 500; 40 to 100 for two objectives" were treated as option/value enumerations rather than prose sentences, so the joining slashes and semicolons there were not proposed for change.
