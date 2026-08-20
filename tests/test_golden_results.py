"""
test_golden_results.py
======================

The engine's OUTPUT had no regression net. A handful of tests lock a
hand-written value; everything else was covered only by "it ran without
raising", which a solver can do while returning numbers that are five
percent wrong in every case.

Two things happen here, both driven by one solve of every saved case of
every project under `projects/`:

  * `TestValoresConferem` compares the run against
    `tests/data/golden_results.json`, written by
    `tools/golden_snapshot.py`. A deliberate change to the physics is made
    visible by regenerating that file and reading its diff; an accidental
    one fails here, naming the project, the case and the quantity that
    moved.
  * `TestResultadosSaoFisicamentePlausiveis` asks the questions the golden
    file cannot: a recorded number is "correct" by construction, even if it
    is a NaN or a figure of merit of 4. These checks are independent of the
    record and would have caught a bad snapshot at the moment it was taken.

The two are deliberately not merged. The first says "this changed"; the
second says "this is wrong". A change that trips both is a regression; a
change that trips only the first is a decision to review.
"""
from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tools import golden_snapshot

GOLDEN_PATH = RAIZ / "tests" / "data" / "golden_results.json"

#: Relative tolerance of the comparison. The snapshot keeps six decimals, so
#: this is loose enough to absorb a different BLAS or a different platform's
#: last-bit reduction order, and far tighter than any change to a model, a
#: mesh rule or an integration scheme.
TOLERANCIA_RELATIVA = 1e-6

#: Below this the relative comparison is meaningless -- a coefficient that is
#: zero by symmetry oscillates in the last digits around zero -- so an
#: absolute floor takes over.
PISO_ABSOLUTO = 1e-9


class _RodadaUnica(unittest.TestCase):
    """Both suites need the same solve of every project, and that solve is
    the expensive part. Running it once in the `setUpClass` of a shared base
    keeps the file at about twenty seconds instead of forty."""

    @classmethod
    def setUpClass(cls):
        cls.atual = golden_snapshot.coletar()
        cls.esperado = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


class TestValoresConferem(_RodadaUnica):

    def test_o_arquivo_de_referencia_existe(self):
        self.assertTrue(
            GOLDEN_PATH.is_file(),
            f"{GOLDEN_PATH} is missing -- run `python tools/golden_snapshot.py`")

    def test_todo_projeto_e_todo_caso_esta_registrado(self):
        """A new example project, or a new saved case inside one, has to
        enter the record. Otherwise it is exercised by the run and checked
        by nothing -- the one failure mode a snapshot cannot detect on its
        own."""
        faltando = []
        for projeto, casos in self.atual.items():
            if projeto not in self.esperado:
                faltando.append(projeto)
                continue
            for caso in casos:
                if caso not in self.esperado[projeto]:
                    faltando.append(f"{projeto}/{caso}")
        self.assertEqual(
            faltando, [],
            "not in the golden record (run `python tools/golden_snapshot.py`): "
            + str(faltando))

    def test_nenhum_projeto_saiu_do_registro(self):
        """The converse: a project deleted from `projects/` but left in the
        record would keep passing forever without ever running."""
        sobrando = [p for p in self.esperado if p not in self.atual]
        self.assertEqual(
            sobrando, [],
            "in the golden record but no longer on disk: " + str(sobrando))

    def test_os_numeros_nao_mudaram(self):
        divergencias = []
        for projeto, casos in sorted(self.esperado.items()):
            if projeto not in self.atual:
                continue
            for caso, valores in sorted(casos.items()):
                if caso not in self.atual[projeto]:
                    continue
                obtido = self.atual[projeto][caso]
                for chave, referencia in sorted(valores.items()):
                    with self.subTest(projeto=projeto, caso=caso, chave=chave):
                        self.assertIn(
                            chave, obtido,
                            f"{projeto}/{caso}: '{chave}' is no longer produced")
                        agora = obtido[chave]
                        if isinstance(referencia, str) or isinstance(agora, str):
                            self.assertEqual(referencia, agora)
                            continue
                        escala = max(abs(referencia), PISO_ABSOLUTO)
                        if abs(agora - referencia) > TOLERANCIA_RELATIVA * escala:
                            divergencias.append(
                                f"{projeto}/{caso}/{chave}: {referencia} -> {agora}")
        self.assertEqual(
            divergencias, [],
            "the engine's numbers changed. If deliberate, regenerate with "
            "`python tools/golden_snapshot.py` and review the diff:\n  "
            + "\n  ".join(divergencias))


class TestResultadosSaoFisicamentePlausiveis(_RodadaUnica):
    """Checks that hold whatever the numbers happen to be. Each one
    corresponds to a way a solve can fail while still returning a result."""

    def test_nenhum_valor_e_nan_ou_infinito(self):
        """A NaN in the summary reaches the results table, the report and
        the CSV as an empty cell, and reads as "this column does not apply
        here" rather than as a failure."""
        ruins = []
        for projeto, casos in sorted(self.atual.items()):
            for caso, valores in sorted(casos.items()):
                for chave, valor in sorted(valores.items()):
                    if valor == "nan" or (isinstance(valor, float)
                                          and not math.isfinite(valor)):
                        ruins.append(f"{projeto}/{caso}/{chave}")
        self.assertEqual(ruins, [], "non-finite value in the summary: " + str(ruins))

    #: Convergence floor. Hover reaches 100%; forward flight does not, and
    #: is not expected to: a few elements per solve sit in the reverse-flow
    #: region or at the root, where the inflow equation is close to
    #: singular and the fixed point stalls at the tolerance. Those elements
    #: carry almost no area weight. Measured worst case across the example
    #: projects today is 99.91%, so the floor is set well below that and
    #: still catches a solve that has genuinely fallen apart.
    CONVERGENCIA_MINIMA_PCT = 99.0

    def test_toda_solucao_converge_quase_por_completo(self):
        """`convergence_pct` is the fraction of mesh elements that reached
        their fixed point. A case well below the floor means the leftover
        error is spread over enough of the disk to contaminate every
        integrated quantity, and an example project is a reference: it must
        not ship in that state."""
        ruins = []
        for projeto, casos in sorted(self.atual.items()):
            for caso, valores in sorted(casos.items()):
                pct = valores.get("convergence_pct")
                if pct is not None and pct < self.CONVERGENCIA_MINIMA_PCT:
                    ruins.append(f"{projeto}/{caso}: {pct}%")
        self.assertEqual(
            ruins, [],
            f"case converged below {self.CONVERGENCIA_MINIMA_PCT}%: " + str(ruins))

    def test_potencia_total_e_a_soma_das_suas_partes(self):
        """Induced plus profile is the whole of the shaft power. If the
        identity breaks, one of the two integrations is being done over a
        different mesh, or with a different weighting, than the total."""
        for projeto, casos in sorted(self.atual.items()):
            for caso, v in sorted(casos.items()):
                if not {"Power", "Power_i", "Power_p"} <= set(v):
                    continue
                with self.subTest(projeto=projeto, caso=caso):
                    self.assertAlmostEqual(
                        v["Power"], v["Power_i"] + v["Power_p"],
                        delta=1e-6 * max(abs(v["Power"]), 1.0),
                        msg=f"{projeto}/{caso}: P is not P_i + P_p")

    def test_as_partes_da_potencia_nao_sao_negativas(self):
        """Induced and profile power are both dissipative. Negative means
        either that the sign of a force was flipped somewhere, or that a
        section is driving the shaft -- which a BEMT solve of a powered
        rotor must not produce."""
        ruins = []
        for projeto, casos in sorted(self.atual.items()):
            for caso, v in sorted(casos.items()):
                for chave in ("Power_i", "Power_p"):
                    if v.get(chave, 0.0) < 0.0:
                        ruins.append(f"{projeto}/{caso}/{chave} = {v[chave]}")
        self.assertEqual(ruins, [], "negative power component: " + str(ruins))

    def test_a_eficiencia_propulsiva_fica_abaixo_de_um(self):
        """The propulsive efficiency is thrust power over shaft power. Above
        1 the propeller would be returning more than it is given."""
        ruins = []
        for projeto, casos in sorted(self.atual.items()):
            for caso, v in sorted(casos.items()):
                eta = v.get("eta_prop")
                if eta is not None and eta > 1.0:
                    ruins.append(f"{projeto}/{caso}: eta = {eta}")
        self.assertEqual(ruins, [], "propulsive efficiency above 1: " + str(ruins))

    def test_o_torque_acompanha_o_sinal_da_potencia(self):
        """Shaft power is torque times angular speed, and the angular speed
        is positive by convention. The two must therefore carry the same
        sign; opposite signs mean one of them was integrated with a flipped
        moment arm."""
        ruins = []
        for projeto, casos in sorted(self.atual.items()):
            for caso, v in sorted(casos.items()):
                if "Torque" not in v or "Power" not in v:
                    continue
                if v["Torque"] * v["Power"] < 0.0:
                    ruins.append(f"{projeto}/{caso}: Q={v['Torque']}, P={v['Power']}")
        self.assertEqual(ruins, [], "torque and power disagree in sign: " + str(ruins))


if __name__ == "__main__":
    unittest.main()
