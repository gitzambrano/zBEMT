"""The FIVE reverse flow models: effective angle formula, real effect on the
engine and fidelity of the Airfoil tab's polar preview.

Reason for this file: the models act in TWO places --
`bemt.reverse_flow_alpha_eff` (angle at which the polar is queried) and
`bemt.apply_reverse_flow_to_polar` (Cl/Cd post-processing) -- and the
preview only called the second. Consequence: choosing `viterna_full_range`
or `alpha_blending` changed NOTHING in the plot, even though it changed what
the engine calculated -- exactly the "some do not modify the plot, but modify
the modeling?" from the report.
"""
import unittest

import numpy as np

from zbemt import airfoils
from zbemt.bemt import (BEMTConfig, reverse_flow_alpha_eff,
                         apply_reverse_flow_to_polar, UT_NORMALIZADO_DE_PREVIA)
from zbemt.models import AirfoilDef

_MODELS = ("simple_flip", "flat_plate", "alpha_blending",
           "thin_plate_blend", "viterna_full_range")


class TestEffectiveAlphaPerModel(unittest.TestCase):
    """Formula by model, written here independently of the code -- it is the
    contract that the refactoring (extract the function from inside
    `element_state`) had to preserve."""

    def setUp(self):
        self.alpha = np.deg2rad(np.array([-20.0, -5.0, 0.0, 5.0, 20.0]))
        self.reverse = np.array([True, True, True, True, True])
        self.forward = np.zeros(self.alpha.shape, dtype=bool)

    def _cfg(self, model, **kw):
        return BEMTConfig(reverse_flow_model=model, **kw)

    def test_simple_flip_and_flat_plate_mirror_the_incidence(self):
        for model in ("simple_flip", "flat_plate"):
            with self.subTest(model=model):
                got = reverse_flow_alpha_eff(self.alpha, self.reverse, self._cfg(model))
                np.testing.assert_allclose(got, -self.alpha)

    def test_viterna_full_range_mirrors_nothing(self):
        got = reverse_flow_alpha_eff(self.alpha, self.reverse,
                                     self._cfg("viterna_full_range"))
        np.testing.assert_allclose(got, self.alpha)

    def test_viterna_full_range_wraps_back_inside_180(self):
        alpha = np.deg2rad(np.array([200.0, -200.0]))
        got = np.rad2deg(reverse_flow_alpha_eff(
            alpha, np.array([False, False]), self._cfg("viterna_full_range")))
        np.testing.assert_allclose(got, [-160.0, 160.0], atol=1e-9)

    def test_thin_plate_blend_does_not_touch_the_angle(self):
        got = reverse_flow_alpha_eff(self.alpha, self.reverse,
                                     self._cfg("thin_plate_blend"))
        np.testing.assert_allclose(got, self.alpha)

    def test_alpha_blending_uses_the_tanh_of_normalized_ut(self):
        k = 5.0
        ut_norm = np.full(self.alpha.shape, -0.3)
        got = reverse_flow_alpha_eff(self.alpha, self.reverse,
                                     self._cfg("alpha_blending", reverse_flow_blend_factor=k),
                                     ut_norm=ut_norm)
        np.testing.assert_allclose(got, self.alpha * np.tanh(k * -0.3))

    def test_alpha_blending_without_ut_assumes_the_preview_limit(self):
        k = 5.0
        got = reverse_flow_alpha_eff(
            self.alpha, self.reverse,
            self._cfg("alpha_blending", reverse_flow_blend_factor=k))
        np.testing.assert_allclose(
            got, self.alpha * np.tanh(k * UT_NORMALIZADO_DE_PREVIA))

    def test_outside_the_reverse_region_no_model_touches_the_angle(self):
        for model in _MODELS:
            with self.subTest(model=model):
                got = reverse_flow_alpha_eff(self.alpha, self.forward, self._cfg(model))
                np.testing.assert_allclose(got, self.alpha, atol=1e-12)

    def test_unknown_model_fails_loudly(self):
        with self.assertRaises(ValueError):
            reverse_flow_alpha_eff(self.alpha, self.reverse, self._cfg("nonexistent"))


class TestPolarPostProcessing(unittest.TestCase):
    """The other half: what each model does with already-queried Cl/Cd."""

    def setUp(self):
        self.alpha = np.deg2rad(np.array([5.0, 10.0]))
        self.cl = np.array([0.5, 1.0])
        self.cd = np.array([0.01, 0.02])
        self.reverse = np.array([True, True])

    def test_flat_plate_zeroes_cl_and_imposes_a_flat_plate(self):
        cl, cd = apply_reverse_flow_to_polar(
            self.cl, self.cd, self.alpha, self.reverse,
            BEMTConfig(reverse_flow_model="flat_plate"))
        np.testing.assert_allclose(cl, 0.0)
        np.testing.assert_allclose(cd, 1.9)

    def test_viterna_and_alpha_blending_do_not_post_process(self):
        for model in ("viterna_full_range", "alpha_blending"):
            with self.subTest(model=model):
                cl, cd = apply_reverse_flow_to_polar(
                    self.cl, self.cd, self.alpha, self.reverse,
                    BEMTConfig(reverse_flow_model=model))
                np.testing.assert_allclose(cl, self.cl)
                np.testing.assert_allclose(cd, self.cd)


class TestPreviewReflectsTheModel(unittest.TestCase):
    """The Airfoil tab's preview draws what the engine consumes -- for all
    FIVE models, not just the three that post-process Cl/Cd."""

    #: full range: it is where the models separate (extrapolation and flat
    #: plate blending live above stall)
    _RANGE = (-180.0, 180.0, 1.0)

    def _airfoil(self):
        return AirfoilDef(name="p", source="analytical", stall_model="viterna")

    def _reverse_branch(self, model):
        _a, cl, cd = airfoils.preview_polar(
            self._airfoil(), alpha_deg_range=self._RANGE,
            config={"reverse_flow_model": model}, reverse=True)
        return np.asarray(cl), np.asarray(cd)

    def test_every_model_changes_the_reverse_branch_relative_to_the_forward_one(self):
        """`thin_plate_blend` is the DELIBERATE exception: its blend is a
        function of |alpha| only, so both branches coincide -- it is the
        model's point (no discontinuity at Ut=0)."""
        _a, cl_forward, _cd = airfoils.preview_polar(
            self._airfoil(), alpha_deg_range=self._RANGE,
            config={"reverse_flow_model": "simple_flip"}, reverse=False)
        for model in ("simple_flip", "flat_plate", "alpha_blending"):
            with self.subTest(model=model):
                cl_rev, _cd_rev = self._reverse_branch(model)
                self.assertFalse(np.allclose(cl_rev, cl_forward),
                                 f"'{model}' did not change the preview's reverse branch")

    def test_viterna_full_range_distinguishes_itself_from_thin_plate_blend(self):
        """Both leave alpha_eff = alpha_geom; what separates them is the flat
        plate post-processing -- and the preview shows it."""
        cl_v, cd_v = self._reverse_branch("viterna_full_range")
        cl_t, cd_t = self._reverse_branch("thin_plate_blend")
        self.assertFalse(np.allclose(cl_v, cl_t))

    def test_the_five_produce_curves_distinct_pairwise(self):
        """No pair of models draws the SAME curve in the reverse branch --
        which was the reported defect ("some do not modify the plot").

        The pair that comes closest is `simple_flip`/`alpha_blending`: the
        preview draws `alpha_blending` at the saturated limit of the reverse
        region (`bemt.UT_NORMALIZADO_DE_PREVIA`), where tanh -> -1 and it
        tends toward the mirroring of `simple_flip`. Still distinct, because
        tanh(-k) is not exactly -1."""
        curves = {m: self._reverse_branch(m)[0] for m in _MODELS}
        for i, a in enumerate(_MODELS):
            for b in _MODELS[i + 1:]:
                with self.subTest(pair=(a, b)):
                    self.assertFalse(np.allclose(curves[a], curves[b], atol=1e-3),
                                      f"'{a}' and '{b}' draw the same curve")

    def test_without_config_the_preview_is_the_raw_polar(self):
        """Compatibility: without `config` no reverse flow is applied."""
        _a, cl, _cd = airfoils.preview_polar(self._airfoil(), alpha_deg_range=self._RANGE,
                                              reverse=True)
        _a2, cl2, _cd2 = airfoils.preview_polar(self._airfoil(), alpha_deg_range=self._RANGE,
                                                 reverse=False)
        np.testing.assert_allclose(cl, cl2)


class TestModelChangesTheEngineResult(unittest.TestCase):
    """The question from the report -- "do they modify the modeling?" --
    answered in the engine: at high advance (large reverse region) the five
    give different CT values."""

    def _ct(self, model):
        from tests.helpers import make_studies_project
        from zbemt import studies
        from zbemt.models import FlightCondition

        project = make_studies_project(reverse_flow_model=model, Ne=10, Npsi=16)
        project.airfoil = AirfoilDef(source="analytical", stall_model="viterna")
        result = studies.run_single_case(
            project, FlightCondition(name="rev", mu_x=0.45, Vz=0.0,
                                      collective_deg=8.0, rpm=600.0))
        return float(result.summary["CT"])

    def test_ct_depends_on_the_model(self):
        cts = {m: self._ct(m) for m in _MODELS}
        self.assertGreater(len(set(round(v, 6) for v in cts.values())), 1,
                            f"no model changed the CT: {cts}")


if __name__ == "__main__":
    unittest.main()
