# Writing and naming refactor: completion report

This file replaces the plan that preceded it. The full pass described there
is applied and verified. What follows records what was done, the defects
found on the way, the exceptions kept on purpose, and the verification
evidence.

---

## 1. Result

| Gate | Outcome |
|---|---|
| Full suite (`tests/run_all_tests.py`, one process per file) | **43/43 files OK, 0 failed**, 6 skips (optional dependencies only, same set as baseline) |
| Example projects (`tools/check_project_configs.py`) | 14/14 load, validate, solve |
| Golden engine numbers (`tests/test_golden_results.py`) | byte-identical, 10 passed / 792 subtests |
| Nomenclature snapshot (`tools/nomenclature_snapshot.py`) | byte-identical output |
| Generated index (`tools/build_toc.py`) | "index already up to date" (no heading moved) |
| Portuguese-identifier scan (`zbemt/`, `tools/`, `tests/`) | 1 hit = the HTML id `uso-resultados` in a test (an address, exempt) |
| Accent scan | only rendered notation (Greek, subscripts, math symbols), box-drawing banner art, degree/middle-dot symbols, Bézier, Øye |
| LaTeX/font diff gate | `viz/style.py` untouched; `styles.py` diff is one comment translation plus `_seta`→`_arrow` with identical px values; `katex_inline.py` marker renames only |

The baseline before any edit was also green (43/43), so every number above
compares against a proven starting point.

---

## 2. What was executed

### Prose (`docs/documentation.html`)

- All 281 prose `&mdash;` entities converted per class: sentence splits,
  real parentheses for asides, colons after interface markers, recast table
  cells. No blanket replace; every instance was an individual edit.
- **11 entities remain, all inside `<h3>`/`<h4>` heading titles**
  ("Rotor &mdash; vertical shaft", section titles). A title has no sentence
  break available, so `G15` does not reach it; renaming headings would
  cascade into the generated index and every link `title`. Kept on purpose.
- Latin abbreviations, contractions, British spelling: zero in prose (the
  KaTeX bundle inside lines 1-633 stays excluded by rule).

### Code prose (`zbemt/` docstrings, comments, help text)

- Roughly 530 style fixes across the core modules, GUI help modules,
  viz modules, `api.py` and the tab files (`G14` semicolons, `G15`/`G25`
  dashes, `G20` Latin abbreviations, `G22` length, `G29` `Sec.`→
  `Section`, `G26` slashes, contractions, spelling).
- `bemt.py` (edited directly, per repository rule): module docstring and
  solver sections rewritten; 26 Latin abbreviations to zero; 41 comment and
  26 docstring semicolon joins to zero; 212 dash joins converted to
  sentence breaks; `Sec.N`→`Section N` throughout.
- The `__main__` demo block (lines 3694-4097): every print, plot label,
  title and assert message translated; demo output filename
  `convergencia_solvers.png`→`solver_convergence.png`; then executed end to
  end (all 11 blocks `[OK]`).
- Plot titles in `viz/plots.py` de-dashed; tool figure strings in
  `regenerate_documentation_plots.py` likewise.

### Names (QR-9, now a standing requirement)

Every Portuguese identifier found was renamed to an English name stating
its purpose, repo-wide in the same change, with zero behavior change.
Representative map (full detail in the commit history):

| Old | New |
|---|---|
| `modo_helice`, `_modo_helice` | `propeller_mode`, `_propeller_mode` |
| `rotulos_de_condicao`, `rotulo_e_dica_de_condicao` | `condition_labels`, `condition_label_and_tooltip` |
| `definir_linha_visivel` / `mostrar_todas_as_opcoes` (named in AGENTS.md) | `set_row_visible` / `show_all_options` |
| `azrad_*` (`_AZRAD_X_RAIO`, `_refresh_azrad`) | sweep (`_SWEEP_VS_RADIUS`, `_refresh_sweep`) |
| `fila_*`, `trabalho_nao_salvo`, `janela_pai`, `pasta_de_saida_padrao` | queue/`unsaved_work`/`parent_window`/`default_output_dir` |
| `avisar_chaves_desconhecidas`, `nome_de_condicao` | `warn_unknown_keys`, `condition_name` |
| `uniformizar_largura_de_botoes`, `ESPACO_DE_CONDICAO`, `UNIDADES_DE_CONDICAO` | `equalize_button_widths`, `CONDITION_ROW_SPACING`, `CONDITION_UNITS` |
| api report internals (`celulas`, `posicao`, `_pagina_satelite`, `_legenda_de_figura`, ...) | `cells`, `section_position`, `_satellite_page`, `_figure_caption`, ... |
| tools/tests helpers (`patch_em_toda_gui`) | `patch_message_box_everywhere` |

Developer-facing CLI and outputs: `--escrever`→`--write`,
`--lista`→`--list`, `resultado_testes.txt`→`test_results.txt`; AGENTS.md,
CLAUDE.md and README.md updated in step (mirror parity enforced by
`test_agent_instructions`, green).

Documentation figure assets: all 18 files under `docs/img/` carried
Portuguese names; renamed in three coordinated places at once (tool string,
file on disk, HTML reference). During this pass, collateral damage from a
parallel rename (hybrid names such as `fluxo-reversed_mask-cinco-models`
inside tool strings) was found and repaired.

### Requirements

`docs/software_requirements.md` gained **QR-9 — English internal
identifiers**, so the standard outlives this pass. Its own prose dashes were
cleaned in the same change.

---

## 3. Defects found and repaired along the way

1. **`tests/test_notation.py` had a corrupt regex since before this work.**
   At HEAD, `GREEK_IN_TEXT` contained literal backspace bytes (`0x08`)
   where word boundaries belonged. A pattern of backspace characters matches
   nothing in prose, so four PR-4 checks passed vacuously at baseline. The
   repair restores the evident intent:
   `\b(?:rho|Omega|...)\b|\^\d`. This is a repair, not a weakening: the
   negative check shows it still catches real violations (`'rho'`, `'^3'`)
   while ignoring English words that merely contain these letter pairs
   ("number", "pitch") and identifiers (`alpha_blending`). A stray docstring
   appended after `unittest.main()` was removed.
2. **Interrupted-agent damage**: an empty stub `def` left in
   `tests/test_help_content.py`; hybrid PNG names inside tool strings;
   stale comment references to renamed constants
   (`common._ROTULOS_DE_CONDICAO` → `nomenclature._SLOT_LABELS` in three
   files); an orphan caller `api.nomes_de_arquivo_de_condicao` in
   `results.py`. All repaired and re-verified.
3. **Latent leftovers surfaced by the final sweeps**: `_AXIS_SLOTS_HELICE`,
   Portuguese test-method names, `# já rodando`, `§8.3.3`-style
   cross-references, Portuguese assertion messages. All converted.

---

## 4. Exceptions kept on purpose

| Exception | Where | Why |
|---|---|---|
| `&mdash;` inside heading tags (11) | `documentation.html` h3/h4 titles | Titles have no sentence break; index/link-title cascade |
| `BLOCK N -- TITLE` headers (11) | `bemt.py` `__main__` | Title separators, same class as headings |
| Field-label dashes (`# Section 11.5 -- near-hover`, leading-dash labels) | `bemt.py` RunPlan, axes note | Label annotations, not sentences |
| Portuguese HTML ids (`cap-projeto`, `uso-resultados`, ...) | documentation.html, tests | Addresses, not text (standing project rule) |
| Rendered Unicode notation | everywhere | Required by PR-4: Greek letters, subscripts, `≈ ≤ ∈ ∝ ∞ ‖ √`, en dashes in numeric ranges ("2–4") |
| Accented quoted examples | `api.py` mojibake warning ("Î¼=0.1", "Caso Padrão"); `sanitize_filename("condição ok")` test input | They exist to prove non-ASCII passes through intact; translating them would defeat their purpose |
| Python statement separators | plotting one-liners (`ax.set_xlabel(...); ax.grid(...)`) | Code, exempt from prose rules |
| CSS classes `.blocos`, `.satelites` | generated report HTML | Output-format stability; renaming would churn every previously produced report |

---

## 5. Verification trail

- Full suite green twice: once at Phase 0 baseline, once after the last
  edit. Single-file reruns were used between batches, per the runner rule.
- `python zbemt/bemt.py` self-demo executed once after translation: all 11
  blocks completed with `[OK]` markers in English.
- Snapshot regenerations run and compared: golden results and nomenclature
  snapshots byte-identical; documentation index unchanged.
- Whole-tree `compileall`: clean (catches any syntax damage from scripted
  edits).

Nothing in this pass changed physics, engine outputs, file formats, keys,
flags or rendering. The next person can enforce QR-9 the way the other
codes are enforced: by naming it.
