"""A `.bemt` file speaks the axis letters the GUI shows.

A propeller project's flight conditions are written under the keys the
propeller user reads -- `Vx` for the airspeed along the shaft, `mu_z` for the
cross-flow -- not under the engine's disk-axes names. In memory nothing
changes: `FlightCondition` still carries `mu_x`/`Vz`, and the engine is never
told about any of this.

The rotation is a SWAP, so these tests care most about the two ways a swap
can go wrong: collapsing both components onto one value, and not surviving a
round trip.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from zbemt import models
from zbemt.models import FlightCondition, BatchDefinition


def _escrever_e_ler_bruto(obj, is_propeller):
    """Saves `obj` and returns the raw JSON, as it sits on disk."""
    with tempfile.TemporaryDirectory() as d:
        caminho = os.path.join(d, "cond.bemt")
        models.save_bemt(obj, caminho, is_propeller=is_propeller)
        return json.loads(Path(caminho).read_text(encoding="utf-8"))


class TestRotorFilesAreUnchanged(unittest.TestCase):
    """Rotor letters ARE the engine letters, so a rotor project's files must
    be byte-identical to what they always were."""

    def test_rotor_keys_stay_engine_keys(self):
        bruto = _escrever_e_ler_bruto(
            FlightCondition(name="hover", mu_x=0.0, Vz=0.0, collective_deg=8.0,
                            rpm=600.0), is_propeller=False)
        self.assertIn("mu_x", bruto)
        self.assertIn("Vz", bruto)
        self.assertNotIn("Vx", bruto)


class TestPropellerFilesUseVehicleLetters(unittest.TestCase):

    def setUp(self):
        self.condicao = FlightCondition(name="cruise 65 m/s", mu_x=0.02,
                                        Vz=65.0, collective_deg=0.0, rpm=2500.0)

    def test_axial_airspeed_is_written_as_Vx(self):
        bruto = _escrever_e_ler_bruto(self.condicao, is_propeller=True)
        self.assertEqual(bruto["Vx"], 65.0)
        self.assertNotIn("Vz", bruto)

    def test_cross_flow_is_written_as_mu_z(self):
        bruto = _escrever_e_ler_bruto(self.condicao, is_propeller=True)
        self.assertEqual(bruto["mu_z"], 0.02)
        self.assertNotIn("mu_x", bruto)

    def test_non_axis_fields_are_untouched(self):
        bruto = _escrever_e_ler_bruto(self.condicao, is_propeller=True)
        self.assertEqual(bruto["name"], "cruise 65 m/s")
        self.assertEqual(bruto["collective_deg"], 0.0)
        self.assertEqual(bruto["rpm"], 2500.0)

    def test_round_trip_gives_back_the_engine_fields(self):
        """What comes back is a `FlightCondition` in DISK axes -- the
        rotation exists only on disk."""
        with tempfile.TemporaryDirectory() as d:
            caminho = os.path.join(d, "cond.bemt")
            models.save_bemt(self.condicao, caminho, is_propeller=True)
            lida = models.load_bemt(FlightCondition, caminho, is_propeller=True)
        self.assertEqual(lida.mu_x, 0.02)
        self.assertEqual(lida.Vz, 65.0)
        self.assertEqual(lida.name, "cruise 65 m/s")

    def test_both_components_survive_the_swap(self):
        """The collision case: `mu_x` -> `mu_z` and `Vz` -> `Vx` at once. A
        key-by-key rename would lose one of them."""
        bruto = _escrever_e_ler_bruto(
            FlightCondition(name="climbing turn", mu_x=0.05, Vz=40.0,
                            collective_deg=3.0, rpm=2400.0), is_propeller=True)
        self.assertEqual(bruto["mu_z"], 0.05)
        self.assertEqual(bruto["Vx"], 40.0)


class TestBatchesRotateToo(unittest.TestCase):
    """`batches.bemt` holds `FlightCondition`s nested inside a
    `BatchDefinition` -- the rotation has to reach them there as well."""

    def test_nested_conditions_are_rotated(self):
        lote = BatchDefinition(
            name="cruise sweep",
            conditions=[FlightCondition(name="c1", mu_x=0.0, Vz=50.0, rpm=2500.0),
                        FlightCondition(name="c2", mu_x=0.0, Vz=70.0, rpm=2500.0)])
        bruto = _escrever_e_ler_bruto(lote, is_propeller=True)
        for c in bruto["conditions"]:
            self.assertIn("Vx", c)
            self.assertNotIn("Vz", c)

    def test_list_of_conditions_round_trips(self):
        condicoes = [FlightCondition(name="c1", mu_x=0.0, Vz=50.0, rpm=2500.0),
                     FlightCondition(name="c2", mu_x=0.01, Vz=70.0, rpm=2500.0)]
        with tempfile.TemporaryDirectory() as d:
            caminho = os.path.join(d, "saved_cases.bemt")
            models.save_bemt_list(condicoes, caminho, is_propeller=True)
            lidas = models.load_bemt_list(FlightCondition, caminho,
                                          is_propeller=True)
        self.assertEqual([c.Vz for c in lidas], [50.0, 70.0])
        self.assertEqual([c.mu_x for c in lidas], [0.0, 0.01])


class TestAFileFromTheOldSchemaIsRefused(unittest.TestCase):
    """There is no back-compat by decision -- but a SILENT misread is a wrong
    answer, not a missing feature. An old propeller file carries `Vz` for its
    airspeed, which under the new schema means the cross-flow: loading it
    quietly would turn 65 m/s of cruise into 65 m/s of cross-flow."""

    def test_rotor_keys_in_a_propeller_file_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            caminho = Path(d) / "saved_cases.bemt"
            caminho.write_text(json.dumps(
                [{"name": "cruise", "mu_x": 0.0, "Vz": 65.0, "rpm": 2500.0}]),
                encoding="utf-8")
            with self.assertWarns(UserWarning) as capturado:
                models.load_bemt_list(FlightCondition, str(caminho),
                                      is_propeller=True)
        self.assertIn("nomenclature", str(capturado.warning).lower())


if __name__ == "__main__":
    unittest.main()
