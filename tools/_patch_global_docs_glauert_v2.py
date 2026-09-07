from pathlib import Path

p = Path('docs/documentation.html')
text = p.read_text(encoding='utf-8')

# Keep the whole inflow-field explanation inside the canonical cap-4-2
# section. An id-less h4 splits the documentation parser's section body and
# makes F1 resolve inflow_field_model to a later incidental mention.
text = text.replace(
    '                <h4>Local and Global empirical wake formulations</h4>\n',
    '                <p><b>Local and Global empirical wake formulations.</b> The distinction below is part of the same inflow-model setting.</p>\n',
    1,
)

# Glauert in zBEMT is the axisymmetric annular-momentum reference. Do not
# describe a harmonic that the implementation deliberately sets to zero.
old = '''                <p><b>Glauert</b> (1926) is the original ring momentum theory with a first-harmonic tilt correction
                  and no separate decomposition. <b>Coleman</b> (1945) adds a single longitudinal harmonic,</p>'''
new = '''                <p><b>Glauert</b> is the axisymmetric annular-momentum reference used by zBEMT. It has
                  $K_x=K_y=0$, so it carries no first-harmonic wake-skew field and there is no distinct physical
                  “Glauert Global” formulation. <b>Coleman</b> adds a longitudinal harmonic,</p>'''
if old not in text:
    raise SystemExit('Glauert physics paragraph not found')
text = text.replace(old, new, 1)

# The selector table must be the authoritative inventory, not the old four
# local choices. Preserve old option anchors where possible so existing links
# keep working.
start = text.find('                <p><b>What can be entered.</b> Four families are available.</p>')
end = text.find('                <p class="boxed note"><b>A note on the word "dynamic".</b>', start)
if start < 0 or end < 0:
    raise SystemExit('inflow option table/configuration block not found')
replacement = '''                <p><b>What can be entered.</b> The steady selector exposes one axisymmetric reference,
                  five empirical skewed-wake formulations, and Pitt-Peters steady:</p>

                <div class="tablewrap">
                  <table>
                    <tr>
                      <th>Option</th>
                      <th>Physical representation</th>
                      <th>Coupling</th>
                    </tr>
                    <tr>
                      <td id="cap-4-2-1-1"><code>glauert_local</code></td>
                      <td>Axisymmetric annular-momentum reference, $K_x=K_y=0$.</td>
                      <td>Local annular BEMT</td>
                    </tr>
                    <tr>
                      <td id="cap-4-2-1-2"><code>coleman_local</code></td>
                      <td>Coleman longitudinal wake-skew law evaluated through the local BEMT coupling.</td>
                      <td>Local</td>
                    </tr>
                    <tr>
                      <td><code>coleman_global</code></td>
                      <td>The same Coleman harmonic law with one disk-wide wake condition and a radial mean inflow closed against the full 2D loading.</td>
                      <td>Global</td>
                    </tr>
                    <tr>
                      <td><code>coleman_feingold_global</code></td>
                      <td>Coleman-Feingold/Johnson-NDARC coefficient law, kept separately to make the $15\pi/32$ convention explicit.</td>
                      <td>Global only</td>
                    </tr>
                    <tr>
                      <td id="cap-4-2-1-3"><code>drees_local</code></td>
                      <td>Drees longitudinal and lateral gradients evaluated through local coupling.</td>
                      <td>Local</td>
                    </tr>
                    <tr>
                      <td><code>drees_global</code></td>
                      <td>Drees longitudinal and lateral gradients from one disk-wide wake condition, with full 2D blade-element loading in the closure.</td>
                      <td>Global</td>
                    </tr>
                    <tr>
                      <td id="cap-4-2-1-4"><code>pitt_peters_steady</code></td>
                      <td>Three finite-state disk-level inflow states solved to equilibrium.</td>
                      <td>Finite-state steady</td>
                    </tr>
                  </table>
                </div>

                <p><b>Configuration and applicability.</b> Use <code>glauert_local</code> when the purpose is an
                  axisymmetric annular-momentum baseline. Coleman and Drees offer both Local and Global formulations.
                  The Local forms retain the element/ring coupling and are useful BEMT hybrids. The Global forms are
                  closer to the classical interpretation of a single skewed wake for the whole disk: one pair
                  $(K_x,K_y)$ shapes the field while the radial mean inflow is iterated against the complete 2D
                  aerodynamic loading. <code>coleman_feingold_global</code> is Global only because its published
                  coefficient law is a disk-level empirical wake model, not a separate local closure. Choose
                  <code>pitt_peters_steady</code> when a finite-state disk model is desired instead of an empirical
                  harmonic law. In hover, all skewed-wake gradients vanish and the Global empirical variants collapse
                  to the axisymmetric solution.</p>

'''
text = text[:start] + replacement + text[end:]

p.write_text(text, encoding='utf-8')
print('normalized canonical inflow documentation section')
