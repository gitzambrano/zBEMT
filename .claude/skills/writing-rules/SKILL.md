---
name: writing-rules
description: "Use when writing or reviewing any prose in this project: docstrings, comments, commit messages, helper text, tooltips, dialog and error messages, docs/*.md, or docs/documentation.html. Adapts ASD-STE100 (Simplified Technical English) into a concise rules table and a review checklist. Triggers: writing documentation, writing a docstring, writing GUI or CLI help text, reviewing text for clarity, technical writing style."
---

# Writing rules

This skill adapts ASD-STE100 (Simplified Technical English), the aerospace
controlled-language standard, for this project. It governs every piece of
prose in the repository: docstrings, comments, commit messages, helper and
tooltip text, dialog and error messages, `docs/*.md`, and
`docs/documentation.html`.

ASD-STE100 was built so a maintenance technician can never misread an
instruction. The same discipline keeps this project's documentation short,
unambiguous, and easy to translate or parse, by a human reader or by an
agent.

Text is either **procedural** (steps, CLI usage, GUI instructions, a
tutorial) or **descriptive** (an explanation, a docstring, a module
overview, prose in `docs/`). The General rules apply to both. The
Procedural and Descriptive rules apply only to their own kind of text.

## General rules

| # | Do | Don't |
|---|----|----|
| G1 | Write in formal, technical English. "The solver did not converge within the iteration limit." | Write in a casual or conversational tone. "Looks like the solver just couldn't converge in time." |
| G2 | Give each sentence one topic or one instruction. "Set the tip loss factor. Then run the solver." | Chain unrelated ideas into one sentence. "Set the tip loss factor and run the solver, which then writes the report." |
| G3 | Use active voice. "The solver computes the induced velocity." | Use passive voice when the actor is known. "The induced velocity is computed by the solver." |
| G4 | Use only simple verb forms: infinitive, imperative, simple present, simple past, simple future, or past participle as an adjective. "The airfoil table failed to load." | Build a compound tense with an auxiliary verb. "The airfoil table has failed to load." |
| G5 | Use a past participle as an adjective to show a state. "Examine the damaged blade." | Use it to build a passive construction. "The blade was damaged by the impact." |
| G6 | Write the full sentence: its verb, its articles, and any connector it needs. Don't use contractions. "If a custom geometry table is used, validate it first." | Write telegraphic text that drops the verb, the articles, or an adverbial connector to save space. "Custom table: validate first." |
| G7 | Keep a multi-word noun to 3 words or fewer. "Convergence tolerance for induced velocity." | Stack four or more nouns together. "Induced velocity convergence tolerance check." |
| G8 | Use a single plain verb. "Remove the batch entry." | Build a phrasal verb from two words. "Take out the batch entry." |
| G9 | Use an "-ing" word only as a technical noun or as a modifier in one. "Open the Troubleshooting tab." | Use "-ing" as a verb form. "While troubleshooting the case, check the log." |
| G10 | Use the same term for the same thing every time. Always "airfoil polar," never switch to "aero table" mid-document. | Rotate synonyms for the same concept. "Airfoil polar" in one line, "aero table" in the next. |
| G11 | Use an approved verb to name an action. "Check the residual." | Turn the action into a noun. "Do a check of the residual." |
| G12 | Use an article before a noun. "Open the results tab." | Drop the article for a telegraphic style. "Open results tab." |
| G13 | Use plain, well-known words. "The batch run failed." | Use slang or jargon outside the project's own vocabulary. "The batch run bombed." |
| G14 | Split related facts into separate sentences. "The residual did not converge. Increase the iteration limit." | Join them with a semicolon. "The residual did not converge; increase the iteration limit." |
| G15 | Use a plain sentence break instead of a dash. "The blade twist changes the local angle of attack. This shifts the lift distribution." | Use a dash to join two ideas. "The blade twist changes the local angle of attack — this shifts the lift distribution." |
| G16 | Add a connector when one sentence follows logically from the one before it: *however*, *therefore*, *thus*, *then*, *nevertheless*. "The polar has no post-stall data. Therefore, the solver falls back to Viterna extrapolation." | Leave the logical link implicit. "The polar has no post-stall data. The solver falls back to Viterna extrapolation." |
| G17 | Use "that" after verbs like "make sure," "confirm," or "show." "Make sure that the airfoil table is loaded." | Drop "that" and risk a misread clause. "Make sure the airfoil table is loaded." |
| G18 | Replace a pronoun with the noun it refers to, if more than one noun could fit. "If the pins are damaged, replace the pins." | Leave an ambiguous pronoun. "If the pins are damaged, replace them." |
| G19 | State what "this" refers to when more than one reading is possible. "If the tab is locked, this lock blocks editing." | Leave "this" to point at an unclear antecedent. "If the tab is locked, this blocks editing." |
| G20 | Spell out "for example," "that is," "and so on." | Use a Latin abbreviation. "e.g.," "i.e.," "etc." |
| G21 | Use a numbered or bulleted list for a sequence or a set of conditions with 3 or more items. | Bury a 3-step sequence inside one paragraph of prose. |
| G22 | Keep sentence length in check: about 20 words for an instruction, about 25 words for a description. | Write a long sentence with several clauses. |
| G23 | When an approved word does not fit, restructure the sentence around a word that does. "Make sure that you can see the oil level." | Force a word-for-word swap that reads as nonsense. "Make sure that the oil level is visible." (when "visible" is not an approved word here) |
| G24 | Re-read every sentence that uses "with." Confirm the reader cannot mistake it for association, means, or an instrument. "Seal the opening with sealant PN 4471." | Leave "with" open to more than one reading. "Install the panel with the fasteners." (unclear whether "with" means "using" or "together with") |

All documentation in this project, including docstrings, helper text,
tooltips, and GUI strings, must follow this table.

## Procedural rules (steps, CLI usage, GUI instructions)

| # | Do | Don't |
|---|----|----|
| P1 | Write one instruction per sentence, unless two actions happen at the same time. "Open the Geometry tab. Select the blade station." | Merge two sequential steps into one sentence. "Open the Geometry tab and select the blade station." |
| P2 | Write instructions in the imperative form. "Set the collective pitch." | Describe the instruction instead of giving it. "The collective pitch can be set." |
| P3 | State a condition first, then the command, separated by a comma. "If the airfoil table is missing, load a default polar." | Bury the condition after the command. "Load a default polar if the airfoil table is missing." |
| P4 | Use a note only to give information. "Note: the tip loss factor also affects the root region." | Put an instruction or a requirement inside a note. "Note: set the tip loss factor before running the case." |
| P5 | Name the concrete risk in a warning or an error message. "This deletes the project folder and its results." | State an abstract risk. "This action is not recommended." |

## Descriptive rules (explanations, docstrings, module overviews, prose)

| # | Do | Don't |
|---|----|----|
| D1 | Give information gradually, one subject per sentence. "BEMT couples blade element theory with momentum theory. It solves for the induced velocity at each station." | Front-load several facts into one dense sentence. "BEMT, which couples blade element and momentum theory, solves for induced velocity at each station using an iterative residual." |
| D2 | Open a paragraph with a topic sentence that states its subject. | Start a paragraph mid-detail, with the topic implied. |
| D3 | Keep one topic per paragraph, and keep each paragraph to 6 sentences or fewer. | Mix two topics, or let a paragraph run past 6 sentences. |

## How to review a text

1. Read the text once, for meaning only. Do not edit yet.
2. Decide whether it is procedural or descriptive, and pull in that
   section's rules (`P1`-`P5` or `D1`-`D3`) along with the General rules.
3. Go through every applicable rule, one at a time, from `G1` to the last
   rule in each table. For each one, check whether the text complies. This
   step is mandatory: do not skip straight to a general impression.
4. `G1`: confirm the tone is formal and technical, not casual or
   conversational.
5. `G2` and `P1`: split any sentence that holds more than one topic or
   instruction, unless the actions happen at the same time.
6. `G14`: split any sentence joined by a semicolon.
7. `G15`: replace any dash with a plain sentence break.
8. `G10`: look for synonym rotation, the same thing named two different
   ways. Pick one name and use it everywhere.
9. `G11`: look for a nominalization ("perform a check of"). Replace it
   with the verb ("check").
10. `G1`: look for a hedge stacked past the point of meaning ("it may
    potentially help to improve"), or a vague or marketing adjective
    (robust, powerful, seamless). State the claim, or delete the word,
    without changing the strength of the original claim.
11. `G7` and `G8`: replace any remaining noun cluster over 3 words, or any
    phrasal verb, with a plain, specific one.
12. `G16`: add a connector where one sentence's meaning depends on the
    sentence before it.
13. `G23` and `G24`: confirm any reworded sentence keeps its original
    meaning, and that every "with" reads without ambiguity.
14. `D3` (descriptive text only): confirm each paragraph has one topic and
    6 sentences or fewer.
15. Reread the whole text start to finish. Confirm every rule from step 3
    is satisfied, and that no fact or hedge was lost in the edit.

## Scope

This skill governs prose and user-facing strings. It does not govern code
identifiers, which follow the project's existing naming conventions. It
complements, and does not override, the structural rules for
`docs/documentation.html` in `CLAUDE.md`.
