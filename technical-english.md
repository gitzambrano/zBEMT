# Technical English

This file adapts ASD-STE100 (Simplified Technical English), the aerospace
controlled-language standard, for this project. It governs every piece of
prose in the repository: docstrings, comments, commit messages, helper and
tooltip text, dialog and error messages, `docs/*.md`, and
`docs/documentation.html`.

ASD-STE100 was built so a maintenance technician can never misread an
instruction. The same discipline keeps this project's documentation short,
unambiguous, and easy to translate or parse, by a human reader or by an
agent.

## Rules

| # | Do | Don't |
|---|----|----|
| 1 | Give each sentence one topic or one instruction. "Set the tip loss factor. Then run the solver." | Chain unrelated ideas into one sentence. "Set the tip loss factor and run the solver, which then writes the report." |
| 2 | Use active voice. "The solver computes the induced velocity." | Use passive voice when the actor is known. "The induced velocity is computed by the solver." |
| 3 | Use only simple verb forms: infinitive, imperative, simple present, simple past, simple future, or past participle as an adjective. "The airfoil table failed to load." | Build a compound tense with an auxiliary verb. "The airfoil table has failed to load." |
| 4 | Write every part of the sentence, including subject, verb, and article. "If a custom geometry table is used, validate it first." | Drop words or use a contraction to save space. "If custom table, validate first." / "Don't skip validation." |
| 5 | Keep a multi-word noun to 3 words or fewer. "Convergence tolerance for induced velocity." | Stack four or more nouns together. "Induced velocity convergence tolerance check." |
| 6 | Use a single plain verb. "Remove the batch entry." | Build a phrasal verb from two words. "Take out the batch entry." |
| 7 | Use the same term for the same thing every time. Always "airfoil polar," never switch to "aero table" mid-document. | Rotate synonyms for the same concept. "Airfoil polar" in one line, "aero table" in the next. |
| 8 | Use an approved verb to name an action. "Check the residual." | Turn the action into a noun. "Do a check of the residual." |
| 9 | Use an article before a noun. "Open the results tab." | Drop the article for a telegraphic style. "Open results tab." |
| 10 | Use plain, well-known words. "The batch run failed." | Use slang or jargon outside the project's own vocabulary. "The batch run bombed." |
| 11 | Split related facts into separate sentences. "The residual did not converge. Increase the iteration limit." | Join them with a semicolon. "The residual did not converge; increase the iteration limit." |
| 12 | Use a plain sentence break or a new sentence instead of a dash. "The blade twist changes the local angle of attack. This shifts the lift distribution." | Use a dash to join two ideas. "The blade twist changes the local angle of attack — this shifts the lift distribution." |
| 13 | Add a connector when one sentence follows logically from the one before it: *however*, *therefore*, *thus*, *then*, *nevertheless*. "The polar has no post-stall data. Therefore, the solver falls back to Viterna extrapolation." | Leave the logical link implicit between two related sentences. "The polar has no post-stall data. The solver falls back to Viterna extrapolation." |
| 14 | Write one instruction per sentence, unless two actions happen at the same time. "Open the Geometry tab. Select the blade station." | Merge two sequential steps into one sentence. "Open the Geometry tab and select the blade station." |
| 15 | Write instructions in the imperative form. "Set the collective pitch." | Describe the instruction instead of giving it. "The collective pitch can be set." |
| 16 | State a condition first, then the command, separated by a comma. "If the airfoil table is missing, load a default polar." | Bury the condition after the command. "Load a default polar if the airfoil table is missing." |
| 17 | Give descriptive information gradually, one subject per sentence. "BEMT couples blade element theory with momentum theory. It solves for the induced velocity at each station." | Front-load several facts into one dense sentence. "BEMT, which couples blade element and momentum theory, solves for induced velocity at each station using an iterative residual." |
| 18 | Keep one topic per paragraph, and keep each paragraph to 6 sentences or fewer. | Mix two topics, or let a paragraph run past 6 sentences. |
| 19 | Use a numbered or bulleted list for a sequence or a set of conditions with 3 or more items. | Bury a 3-step sequence inside one paragraph of prose. |
| 20 | Use a note only to give information. "Note: the tip loss factor also affects the root region." | Put an instruction or a requirement inside a note. "Note: set the tip loss factor before running the case." |
| 21 | Keep sentences short: about 20 words for an instruction, about 25 words for a description. | Write a long sentence with several clauses. |

All documentation in this project, including docstrings, helper text,
tooltips, and GUI strings, must follow this table.

## How to review a text

1. Read the text once, for meaning only. Do not edit yet.
2. Check it sentence by sentence against the rules table above.
3. Split any sentence that has a semicolon, a dash, or more than one
   instruction.
4. Replace vague words, noun clusters, and phrasal verbs with plain,
   specific ones.
5. Add a connector where one sentence's meaning depends on the sentence
   before it.
6. Reread the paragraph. Confirm it has one topic, 6 sentences or fewer,
   and that no fact or hedge was lost in the edit.

## Scope

This file governs prose and user-facing strings. It does not govern code
identifiers, which follow the project's existing naming conventions. It
complements, and does not override, the structural rules for
`docs/documentation.html` in `CLAUDE.md`.
