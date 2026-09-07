from pathlib import Path

# Apply the already-tested engine/GUI/validation patch and the updated contract.
contract = Path('tools/_patch_pitt_periodic_contract.py')
exec(compile(contract.read_text(encoding='utf-8'), str(contract), 'exec'),
     {'__name__': '__main__'})


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected exactly one match, got {count}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


# -----------------------------------------------------------------------------
# CLI: these are primary user-facing Pitt-Peters controls, so expose dedicated
# flags in addition to the generic --set parity mechanism.
# -----------------------------------------------------------------------------
replace_once(
    'zbemt/cli.py',
    '    p.add_argument("--pitt-peters-tol", type=float, default=None,\n'
    '                    help="Set the convergence tolerance for Pitt-Peters (BEMTConfig.pitt_peters_tol).")\n',
    '    p.add_argument("--pitt-peters-tol", type=float, default=None,\n'
    '                    help="Set the convergence tolerance for Pitt-Peters (BEMTConfig.pitt_peters_tol).")\n'
    '    p.add_argument("--pitt-peters-time-march-revolutions", type=int, default=None, metavar="N",\n'
    '                    help="Dynamic fixed case: number of constant-condition rotor revolutions to march (BEMTConfig.pitt_peters_time_march_revolutions).")\n'
    '    p.add_argument("--pitt-peters-time-march-avg-last", type=int, default=None, metavar="N",\n'
    '                    help="Dynamic fixed case: average the last N marched revolutions into reported coefficients and azimuthal maps (BEMTConfig.pitt_peters_time_march_avg_last).")\n'
    '    p.add_argument("--pitt-peters-time-march-substeps-per-revolution", type=int, default=None, metavar="N",\n'
    '                    help="Dynamic fixed case: Pitt-Peters state-integration substeps inside each rotor revolution (BEMTConfig.pitt_peters_time_march_substeps_per_revolution).")\n'
    '    p.add_argument("--pitt-peters-time-march-initial-state", choices=["zero", "equilibrium"], default=None,\n'
    '                    help="Dynamic fixed case: initialize the three inflow states at zero or at the steady Pitt-Peters equilibrium (BEMTConfig.pitt_peters_time_march_initial_state).")\n',
)
replace_once(
    'zbemt/cli.py',
    '        "pitt_peters_tol": "pitt_peters_tol",\n'
    '        "solver": "solver",\n',
    '        "pitt_peters_tol": "pitt_peters_tol",\n'
    '        "pitt_peters_time_march_revolutions": "pitt_peters_time_march_revolutions",\n'
    '        "pitt_peters_time_march_avg_last": "pitt_peters_time_march_avg_last",\n'
    '        "pitt_peters_time_march_substeps_per_revolution": "pitt_peters_time_march_substeps_per_revolution",\n'
    '        "pitt_peters_time_march_initial_state": "pitt_peters_time_march_initial_state",\n'
    '        "solver": "solver",\n',
)

# -----------------------------------------------------------------------------
# Documentation: keep the four new fields inside the existing Pitt-Peters
# parameter section. One self-contained block states GUI, .bemt and CLI forms,
# satisfying the manual's field-parity contract without adding another heading.
# -----------------------------------------------------------------------------
replace_once(
    'docs/documentation.html',
    '                <p><span class="cli">CLI</span>:\n'
    '                  <code>--pitt-peters-outer-iter N</code>, <code>--pitt-peters-relax X</code> and\n'
    '                  <code>--pitt-peters-tol X</code>.\n'
    '                </p>\n',
    '                <p><span class="cli">CLI</span>:\n'
    '                  <code>--pitt-peters-outer-iter N</code>, <code>--pitt-peters-relax X</code> and\n'
    '                  <code>--pitt-peters-tol X</code>.\n'
    '                </p>\n\n'
    '                <p><b>Dynamic fixed-case time march.</b> These controls appear only when the Pitt-Peters\n'
    '                  formulation is <i>Dynamic (time march)</i>. They do not create a maneuver: the operating\n'
    '                  point, controls and rpm remain constant while the three inflow states are advanced. The\n'
    '                  start-up is then excluded by reporting averages over the configured final revolutions.\n'
    '                  The result keeps the time history and the averaged radial/azimuthal disk map.</p>\n\n'
    '                <p><span class="gui">GUI</span>: <i>Dynamic march revolutions</i> sets\n'
    '                  <code>pitt_peters_time_march_revolutions</code>; <i>Average final revolutions</i> sets\n'
    '                  <code>pitt_peters_time_march_avg_last</code>; <i>State sub-steps / revolution</i> sets\n'
    '                  <code>pitt_peters_time_march_substeps_per_revolution</code>; and <i>Dynamic initial state</i>\n'
    '                  sets <code>pitt_peters_time_march_initial_state</code> to <code>zero</code> or\n'
    '                  <code>equilibrium</code>.</p>\n\n'
    '                <p><span class="bemt">.bemt</span>, in <code>config.bemt</code>:\n'
    '                  <code>pitt_peters_time_march_revolutions</code>, default <code>8</code>;\n'
    '                  <code>pitt_peters_time_march_avg_last</code>, default <code>3</code>;\n'
    '                  <code>pitt_peters_time_march_substeps_per_revolution</code>, default <code>16</code>;\n'
    '                  <code>pitt_peters_time_march_initial_state</code>, default <code>zero</code>.\n'
    '                  The number averaged must not exceed the number marched.</p>\n\n'
    '                <p><span class="cli">CLI</span>:\n'
    '                  <code>--pitt-peters-time-march-revolutions N</code>,\n'
    '                  <code>--pitt-peters-time-march-avg-last N</code>,\n'
    '                  <code>--pitt-peters-time-march-substeps-per-revolution N</code> and\n'
    '                  <code>--pitt-peters-time-march-initial-state {zero,equilibrium}</code>.\n'
    '                  The generic form remains equivalent, for example\n'
    '                  <code>--set config.pitt_peters_time_march_revolutions=8</code>.</p>\n',
)
replace_once(
    'docs/documentation.html',
    '                                <code>--pitt-peters-relax X</code> | <code>--pitt-peters-tol X</code> |\n',
    '                                <code>--pitt-peters-relax X</code> | <code>--pitt-peters-tol X</code> |\n'
    '                                <code>--pitt-peters-time-march-revolutions N</code> |\n'
    '                                <code>--pitt-peters-time-march-avg-last N</code> |\n'
    '                                <code>--pitt-peters-time-march-substeps-per-revolution N</code> |\n'
    '                                <code>--pitt-peters-time-march-initial-state {zero,equilibrium}</code> |\n',
)

print('Pitt-Peters periodic finish patch applied')
