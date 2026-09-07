from pathlib import Path
import re


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise SystemExit(f'marker not found in {path}: {old[:100]!r}')
    text = text.replace(old, new, 1)
    p.write_text(text, encoding='utf-8')


def regex_once(path, pattern, replacement, flags=0):
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    new, n = re.subn(pattern, lambda m: replacement, text, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f'expected one regex replacement in {path}, got {n}')
    p.write_text(new, encoding='utf-8')


# ---------------------------------------------------------------------------
# Engine: Glauert has no first-harmonic wake law, so there is no distinct
# physical "global Glauert" model. Keep legacy project compatibility by
# migrating old glauert_global values to glauert_local at the project layer.
# ---------------------------------------------------------------------------
replace_once(
    'zbemt/bemt.py',
    '# Valid values: glauert_local | glauert_global | coleman_local |\n'
    '    # coleman_global | coleman_feingold_global | drees_local | drees_global |\n',
    '# Valid values: glauert_local | coleman_local | coleman_global |\n'
    '    # coleman_feingold_global | drees_local | drees_global |\n'
)
replace_once(
    'zbemt/bemt.py',
    '    "glauert_local":        dict(harmonic="glauert", coupling="local",       unsteady=False),\n'
    '    "glauert_global":       dict(harmonic="glauert", coupling="global",      unsteady=False),\n',
    '    "glauert_local":        dict(harmonic="glauert", coupling="local",       unsteady=False),\n'
)

# Existing old-schema (glauert, global) projects and any briefly-written
# inflow_field_model="glauert_global" project both migrate to the single
# physical Glauert model.
replace_once(
    'zbemt/studies.py',
    '    ("glauert", "local"): "glauert_local", ("glauert", "global"): "glauert_global",\n',
    '    ("glauert", "local"): "glauert_local", ("glauert", "global"): "glauert_local",\n'
)
replace_once(
    'zbemt/studies.py',
    '    if "inflow_field_model" in migrated:\n        return migrated\n',
    '    if "inflow_field_model" in migrated:\n'
    '        # Legacy compatibility: Glauert has no distinct global harmonic\n'
    '        # formulation. A short-lived GUI exposed ``glauert_global``; map\n'
    '        # it to the single physical axisymmetric Glauert model.\n'
    '        if migrated["inflow_field_model"] == "glauert_global":\n'
    '            migrated["inflow_field_model"] = "glauert_local"\n'
    '        return migrated\n'
)

# ---------------------------------------------------------------------------
# GUI: only the empirical skewed-wake families expose Global.
# ---------------------------------------------------------------------------
replace_once(
    'zbemt/gui/tabs/config.py',
    '    # Empirical inflow families may be solved either with their local\n'
    '    # element/ring coupling or with a disk-wide GLOBAL first-harmonic field.\n'
    '    # Coleman-Feingold exists only as a global empirical model. Pitt-Peters\n'
    '    # keeps its own finite-state formulation and is steady on the case path.\n'
    '    _AVAILABLE_COUPLINGS = {\n'
    '        "glauert": ("local", "global"),\n',
    '    # Skewed-wake empirical families may use either local coupling or a\n'
    '    # disk-wide GLOBAL first-harmonic field. Glauert is the axisymmetric\n'
    '    # annular-momentum reference and has no distinct global harmonic law.\n'
    '    # Coleman-Feingold exists only as a global empirical model. Pitt-Peters\n'
    '    # keeps its own finite-state formulation and is steady on the case path.\n'
    '    _AVAILABLE_COUPLINGS = {\n'
    '        "glauert": ("local",),\n'
)

# ---------------------------------------------------------------------------
# Layer-3 field popup helper.
# ---------------------------------------------------------------------------
replace_once(
    'zbemt/gui/help_content.py',
    '            "Local empirical variants couple the wake law to the local BEMT inflow. Global variants use one disk-wide wake-skew condition and close the radial mean inflow against the full two-dimensional disk loading."\n',
    '            "Glauert is the axisymmetric annular-momentum reference. Coleman and Drees may couple their skewed-wake law locally or use one disk-wide wake condition; Coleman-Feingold is global only. Global variants close the radial mean inflow against the full two-dimensional disk loading."\n'
)
replace_once(
    'zbemt/gui/help_content.py',
    '            "glauert_local": "Axisymmetric Glauert/annular BEMT with local coupling.",\n'
    '            "glauert_global": "Axisymmetric Glauert law evaluated through the global radial closure.",\n',
    '            "glauert_local": "Axisymmetric Glauert/annular BEMT reference. There is no separate global Glauert wake model because Kx=Ky=0.",\n'
)

# ---------------------------------------------------------------------------
# Block popup helper: explain WHY Glauert has no Global choice.
# ---------------------------------------------------------------------------
replace_once(
    'zbemt/gui/help_blocks.py',
    '            "<b>Glauert.</b> K<sub>x</sub>=K<sub>y</sub>=0. Local and global forms are available; with no harmonic gradient they provide the axisymmetric reference coupling.",\n',
    '            "<b>Glauert.</b> K<sub>x</sub>=K<sub>y</sub>=0. It is the axisymmetric annular-momentum reference and therefore has no separate Global choice: without a first-harmonic wake gradient, a second global wake model would only rename a numerical closure, not add new physics.",\n'
)

# ---------------------------------------------------------------------------
# GUI discoverability regression: global means actual skewed-wake global
# models; also assert Glauert offers only Local and legacy values migrate.
# ---------------------------------------------------------------------------
replace_once(
    'tests/regression/test_option_discoverability.py',
    '        cases = {\n'
    '            "glauert_global": ("glauert", "global"),\n'
    '            "coleman_global": ("coleman", "global"),\n',
    '        cases = {\n'
    '            "coleman_global": ("coleman", "global"),\n'
)
insert_marker = '    def test_coleman_feingold_does_not_offer_a_fictitious_local_variant(self):\n'
insert_text = '''    def test_glauert_does_not_offer_a_fictitious_global_variant(self):\n        config = self._tab("Config")\n        config.cfg_inflow_family.setCurrentText("glauert")\n        self.app.processEvents()\n        values = [config.cfg_inflow_coupling.itemData(i)\n                  for i in range(config.cfg_inflow_coupling.count())]\n        self.assertEqual(values, ["local"])\n        self.assertEqual(config._inflow_field_model_from_widgets(), "glauert_local")\n\n'''
p = Path('tests/regression/test_option_discoverability.py')
t = p.read_text(encoding='utf-8')
if insert_marker not in t:
    raise SystemExit('GUI test insertion marker missing')
t = t.replace(insert_marker, insert_text + insert_marker, 1)
p.write_text(t, encoding='utf-8')

# Add explicit migration regression to the global-model regression module.
p = Path('tests/regression/test_global_inflow_models.py')
t = p.read_text(encoding='utf-8')
marker = '    def test_coleman_feingold_gradient_matches_johnson_ndarc_form(self):\n'
addition = '''    def test_legacy_glauert_global_migrates_to_axisymmetric_glauert(self):\n        from zbemt.studies import _migrate_config_dict\n        self.assertEqual(\n            _migrate_config_dict({"inflow_field_model": "glauert_global"})["inflow_field_model"],\n            "glauert_local",\n        )\n        self.assertEqual(\n            _migrate_config_dict({"inflow_model": "glauert", "inflow_coupling": "global"})["inflow_field_model"],\n            "glauert_local",\n        )\n\n'''
if marker not in t:
    raise SystemExit('global test insertion marker missing')
t = t.replace(marker, addition + marker, 1)
p.write_text(t, encoding='utf-8')

# ---------------------------------------------------------------------------
# Main documentation.html: it was stale and still claimed GLOBAL variants
# were superseded/hidden. Replace that interface text, add the actual global
# closure and Coleman-Feingold definition, and explicitly state why Glauert
# has only the axisymmetric Local entry.
# ---------------------------------------------------------------------------
doc = Path('docs/documentation.html')
text = doc.read_text(encoding='utf-8')

stale = '''                <p><span class="bemt">.bemt</span>: the key <code>inflow_field_model</code> in
                  <code>config.bemt</code>, default <code>"coleman_local"</code>. Projects written before the coupling
                  selector was removed may still hold a value ending in <code>_global</code>. Opening such a project
                  reports the value, and editing anything in the tab stores the supported value instead.
                </p>

                <p><span class="cli">CLI</span>: <code>--inflow coleman_local</code>, or any of
                  <code>glauert_local</code>, <code>drees_local</code> and <code>pitt_peters_steady</code>. The flag
                  also still accepts the superseded names ending in <code>_global</code>, so that an older script
                  keeps running. They are not offered in the window and are not a supported choice for new work.
                  A value naming a time-marching variant is accepted by the parser and then rejected by validation,
                  so that the run stops with an explanation rather than with a bare usage error.
                </p>'''
replacement = '''                <p><span class="bemt">.bemt</span>: the key <code>inflow_field_model</code> in
                  <code>config.bemt</code>, default <code>"coleman_local"</code>. Supported steady values are
                  <code>glauert_local</code>, <code>coleman_local</code>, <code>coleman_global</code>,
                  <code>coleman_feingold_global</code>, <code>drees_local</code>, <code>drees_global</code> and
                  <code>pitt_peters_steady</code>. A legacy <code>glauert_global</code> value is migrated to
                  <code>glauert_local</code>, because Glauert has no distinct first-harmonic global wake model.
                </p>

                <p><span class="cli">CLI</span>: use <code>--inflow</code> with the same supported steady values.
                  Coleman and Drees expose Local and Global formulations; Coleman-Feingold is Global only;
                  Glauert is the single axisymmetric reference. A value naming a time-marching variant is accepted
                  by the parser and then rejected by single-case validation, because unsteady Pitt-Peters belongs
                  to the transient path rather than to an isolated steady case.
                </p>'''
if stale not in text:
    raise SystemExit('stale documentation interface block not found')
text = text.replace(stale, replacement, 1)

# Replace the old GUI paragraph immediately before the .bemt paragraph. The
# exact wording varied historically, so anchor on its ending sentence.
pattern = re.compile(
    r'\s*<p><span class="gui">GUI</span>:(?:(?!<p><span class="bemt">).)*?fixed by the family and is not offered as a separate choice, because only one coupling is\s+implemented for each\.</p>',
    re.S,
)
gui_repl = '''
                <p><span class="gui">GUI</span>: choose the inflow <i>Family</i> and, where the physics has a
                  meaningful alternative, its <i>Formulation</i>. Glauert offers <code>Local</code> only. Coleman
                  offers <code>Local</code> and <code>Global</code>. Coleman-Feingold offers <code>Global</code> only.
                  Drees offers <code>Local</code> and <code>Global</code>. Pitt-Peters keeps its finite-state
                  <code>Steady</code> formulation. The interface never fabricates a Glauert Global option merely
                  to make the dropdowns symmetric.</p>'''
text, n = pattern.subn(lambda m: gui_repl, text, count=1)
if n != 1:
    raise SystemExit(f'GUI documentation paragraph replacement count={n}')

# Insert the global closure explanation after the Drees formula paragraph if
# the new material is not already present.
if 'coleman_feingold_global' not in text[:text.find(replacement)+len(replacement)+5000] or 'disk-wide wake-skew' not in text:
    needle = '''                <div class="eqn">$$K_x=\\frac{4}{3}\\left[(1-1.8\\mu_x^{2})\\sqrt{1+\\chi^{2}}-\\chi\\right],
                  \\qquad K_y=-2\\mu_x.$$</div>'''
    if needle not in text:
        raise SystemExit('Drees documentation equation marker not found')
    extra = needle + '''

                <h4>Local and Global empirical wake formulations</h4>
                <p><b>Glauert is not a Global wake model.</b> For Glauert, $K_x=K_y=0$: there is no first-harmonic
                  skew field to make disk-wide. zBEMT therefore exposes one Glauert formulation, the axisymmetric
                  annular-momentum reference. A historical <code>glauert_global</code> project value is read as
                  <code>glauert_local</code>.</p>

                <p><b>Local Coleman/Drees.</b> The empirical coefficient is evaluated through the local BEMT coupling.
                  This is a useful hybrid closure, but its harmonic coefficient can inherit local variation and is not
                  the strict classical interpretation of one wake-skew angle for the entire disk.</p>

                <p><b>Global Coleman/Drees/Coleman-Feingold.</b> One disk-wide wake condition produces one pair
                  $(K_x,K_y)$. The induced field is
                  $$\\lambda_i(r,\\psi)=\\lambda_0(r)\\left[1+K_x(r/R)\\cos\\psi+K_y(r/R)\\sin\\psi\\right].$$
                  zBEMT closes the radial mean $\\lambda_0(r)$ iteratively against the blade-element loads evaluated
                  over the complete two-dimensional $(r,\\psi)$ disk. The wake gradient is therefore global while the
                  aerodynamic loading remains fully two-dimensional.</p>

                <p><b>Coleman-Feingold global.</b> The implemented Johnson/NDARC convention is
                  $$K_x=\\frac{15\\pi}{32}\\frac{\\mu_x}{\\sqrt{\\mu_x^2+\\lambda^2}+|\\lambda|},
                  \\qquad K_y=-2\\mu_x.$$
                  It is kept as a distinct named model because literature uses more than one convention under the
                  label “Coleman”. Naming the formula prevents a validation from silently comparing different laws.</p>

                <p>All three skewed-wake Global variants collapse to the axisymmetric solution in hover, where the
                  wake-skew gradients vanish. In forward flight, the global closure is iterated until the configured
                  residual tolerance is met or the configured iteration limit is reached.</p>'''
    text = text.replace(needle, extra, 1)

doc.write_text(text, encoding='utf-8')

print('patched Glauert semantics, GUI, popup helpers, documentation.html, and tests')
