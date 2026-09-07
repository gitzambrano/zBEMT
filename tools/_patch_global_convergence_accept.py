#!/usr/bin/env python3
"""Fix empirical-global convergence acceptance.

The outer fixed point previously detected ``||g(x)-x|| <= tol`` and then
replaced the already-converged ``x`` by the full unrelaxed target ``g(x)``
before leaving the loop. For a mildly oscillatory fixed point, the new point
can have a larger residual than the one that satisfied the tolerance.

Accept the current iterate instead. This is the standard fixed-point stopping
condition and preserves the configured tolerance in the final rebuilt field.
"""

from pathlib import Path

p = Path("zbemt/bemt.py")
text = p.read_text(encoding="utf-8")
old = '''        if residual <= tol_outer:
            lam0_r = target_r
            converged = True
            break
'''
new = '''        if residual <= tol_outer:
            # `lam0_r` itself already satisfies ||g(x)-x|| <= tol. Do NOT
            # replace it by the full unrelaxed target here: for an oscillatory
            # fixed point that final jump can move the residual back above the
            # tolerance immediately after convergence was detected.
            converged = True
            break
'''
if text.count(old) != 1:
    raise RuntimeError(f"expected one convergence-acceptance block, found {text.count(old)}")
text = text.replace(old, new, 1)
p.write_text(text, encoding="utf-8")
print("fixed empirical-global convergence acceptance")
