from pathlib import Path
import re

# Repair the temporary primary patcher's validation docstring output. The
# primary script was authored against the pre-change docstring and does not
# include the closing triple quotes in its replacement text.
p = Path('tools/_patch_pitt_periodic_case.py')
t = p.read_text(encoding='utf-8')
repairs = [
    (
        "    '    marches.\\n',\n    '    ``inflow_path`` selects which execution path the config serves:",
        "    '    marches.\\\"\\\"\\\"\\n',\n    '    ``inflow_path`` selects which execution path the config serves:",
    ),
    (
        "    '    formulation transports the inflow state along a changing trajectory.\\n',\n)",
        "    '    formulation transports the inflow state along a changing trajectory.\\\"\\\"\\\"\\n',\n)",
    ),
]
for old, new in repairs:
    if old not in t:
        raise SystemExit(f'primary patcher repair pattern not found: {old[:90]}')
    t = t.replace(old, new, 1)
p.write_text(t, encoding='utf-8')

# Run the primary product patch now that its docstring replacement is sound.
exec(compile(p.read_text(encoding='utf-8'), str(p), 'exec'), {'__name__': '__main__'})

# The fixed periodic path can march Oye's separation state with Pitt-Peters,
# so the post-SC12 blanket incompatibility is obsolete.
p = Path('zbemt/validation.py')
t = p.read_text(encoding='utf-8')
pattern = (
    r'    # --- dynamic stall x UNSTEADY Pitt-Peters outside maneuvers ----------\n'
    r'.*?\n    # --- is_propeller changes the default of advance_kind'
)
replacement = '''    # --- dynamic stall + dynamic Pitt-Peters -----------------------------
    # The fixed periodic case path can march both states together. Oye
    # time_march is threaded from revolution to revolution; its frequency
    # formulation remains the algebraic periodic correction at each sample.

    # --- is_propeller changes the default of advance_kind'''
t2, n = re.subn(pattern, replacement, t, count=1, flags=re.S)
if n != 1:
    raise SystemExit(f'expected one obsolete dynamic-stall compatibility block, got {n}')
p.write_text(t2, encoding='utf-8')

# Update the two regression tests whose purpose was to enforce the old ban.
p = Path('tests/regression/test_validation.py')
t = p.read_text(encoding='utf-8')
old1 = '''    def test_dynamic_stall_with_pitt_peters_unsteady_is_error(self):
        """Narrowed by SC-12: the rejection holds on the CASE path."""
        cfg = asdict(BEMTConfig(inflow_field_model="pitt_peters_unsteady"))
        a = AirfoilDef(use_dynamic_stall=True, stall_model="clip")
        issues = validation.validate_config(cfg, a)
        self.assertIn("error", levels(issues))
'''
new1 = '''    def test_dynamic_stall_with_pitt_peters_unsteady_is_allowed_on_case_path(self):
        """A fixed periodic case can march Oye and Pitt-Peters together."""
        cfg = asdict(BEMTConfig(inflow_field_model="pitt_peters_unsteady"))
        a = AirfoilDef(use_dynamic_stall=True, dynamic_stall_method="time_march")
        issues = validation.validate_config(cfg, a)
        self.assertNotIn("error", levels(issues))
'''
old2 = '''    def test_unsteady_inflow_stays_rejected_on_the_case_path(self):
        """SC-12 narrowed the old blanket ban: the unsteady inflow is
        still an error for an isolated case, with the maneuver as the
        named remedy."""
        cfg = asdict(BEMTConfig(inflow_field_model="pitt_peters_unsteady"))
        issues = validation.validate_config(cfg, AirfoilDef())
        errors = [i.message for i in issues if i.level == "error"]
        self.assertTrue(any("maneuver" in m.lower() for m in errors),
                        str(errors))
'''
new2 = '''    def test_unsteady_inflow_is_allowed_on_the_case_path(self):
        """An isolated case runs a constant-condition periodic time march."""
        cfg = asdict(BEMTConfig(inflow_field_model="pitt_peters_unsteady"))
        issues = validation.validate_config(cfg, AirfoilDef())
        self.assertNotIn("error", levels(issues))
        self.assertTrue(any("fixed case" in i.message.lower() for i in issues),
                        str([i.message for i in issues]))
'''
for old, new in ((old1, new1), (old2, new2)):
    if old not in t:
        raise SystemExit('legacy validation test pattern not found')
    t = t.replace(old, new, 1)
p.write_text(t, encoding='utf-8')

print('Pitt-Peters periodic contract patch applied')
