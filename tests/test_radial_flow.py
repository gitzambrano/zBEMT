"""The spanwise (radial) flow correction, checked against closed form.

`EN-10`. In forward flight part of the free stream runs ALONG the blade,
``U_R = V_inf*cos(psi - psi_w)``. The swept-wing independence principle
keeps lift on the normal-flow pair (Up, Ut), but drag is a friction force
and lies along the TOTAL relative wind, so it gains a spanwise component.
That component produces no torque -- it has no arm about the shaft -- and
does push the rotor backward, so it belongs in the H-force and in the
side force, not in the power.

For a constant drag coefficient the closed form is exact and, better,
CHORD-INDEPENDENT: both the tangential and the spanwise contributions
integrate a term proportional to r, so their ratio is one half whatever
the taper and whatever the root cutout. That is what makes the ratios
below a real check on the engine rather than a check on one blade.

    C_H,profile : sigma*Cd0*mu/4  ->  3*sigma*Cd0*mu/8      (ratio 3/2)
    C_Hr/C_Hp   : 1/2
    C_P,profile : (1 + mu^2)      ->  (1 + 1.5*mu^2)

The last one is the classical (1 + 4.65*mu^2) of the helicopter
literature once the free stream's own contribution (-mu*C_H) is added
back to the shaft power, which is the identity the third test uses.
"""
import unittest
from dataclasses import asdict

import numpy as np

from zbemt import api, geometry
from zbemt.bemt import BEMTConfig
from zbemt.models import AirfoilDef, FlightCondition, Project


def _constant_drag_project(**cfg_overrides) -> Project:
    """A blade that produces NO lift and a drag coefficient that does not
    vary with anything.

    ``cl_alpha = 0`` removes lift, and with it the induced inflow, the
    tip loss and every other effect that would blur the comparison. What
    is left on the disk is exactly the profile drag the closed form
    describes."""
    geom = geometry.generate_tapered(root_chord_norm=0.08, tip_chord_norm=0.08,
                                      twist_root_deg=0.0, twist_tip_deg=0.0,
                                      root_cutout_norm=0.15, radius_m=1.0,
                                      n_stations=40)
    airfoil = AirfoilDef(source="analytical", stall_model="linear",
                          cl_alpha=0.0, alpha0_deg=0.0, cd0=0.02, k=0.0)
    cfg = asdict(BEMTConfig(Ne=40, Npsi=180, solver="fixed_point", max_iter=200))
    cfg.update(reverse_flow_model="simple_flip", use_compressibility=False,
                use_dynamic_stall=False, use_himmelskamp=False,
                prandtl_loss_mode="off")
    cfg.update(cfg_overrides)
    return Project(name="constant drag", geometry=geom, airfoil=airfoil, config=cfg)


def _summaries(mu: float, **cfg_overrides) -> tuple:
    """``(correction off, correction on)`` for the same condition."""
    out = []
    for flag in (False, True):
        project = _constant_drag_project(use_radial_flow_correction=flag,
                                          **cfg_overrides)
        condition = FlightCondition(mu_x=mu, Vz=0.0, collective_deg=0.0, rpm=600.0)
        out.append(api.run_case(project, condition).summary)
    return tuple(out)


class TestSpanwiseDragAgainstClosedForm(unittest.TestCase):
    """The three ratios above. Read at a small advance ratio, where the
    closed form's own first-order truncation is negligible."""

    MU = 0.05

    @classmethod
    def setUpClass(cls):
        cls.off, cls.on = _summaries(cls.MU)

    def test_spanwise_part_is_half_the_tangential_part(self):
        self.assertAlmostEqual(self.on["CHr"] / self.on["CHp"], 0.5, delta=0.01)

    def test_hub_force_grows_by_one_half(self):
        self.assertAlmostEqual(self.on["CH"] / self.off["CH"], 1.5, delta=0.01)

    def test_profile_power_grows_as_the_closed_form_says(self):
        """(1 + 1.5*mu^2)/(1 + mu^2) -- an INCREASE. The spanwise flow
        raises the total relative speed and with it the drag the blade
        has to be dragged through, so profile power going DOWN when the
        correction is switched on is the signature of a model that
        reduces the drag coefficient instead of resolving the drag
        vector."""
        expected = (1.0 + 1.5 * self.MU ** 2) / (1.0 + self.MU ** 2)
        self.assertAlmostEqual(self.on["CPp"] / self.off["CPp"], expected,
                                delta=0.002)
        self.assertGreater(self.on["CPp"], self.off["CPp"])

    def test_the_spanwise_force_adds_no_torque(self):
        """It has no arm about the shaft, so the INDUCED torque and the
        thrust must be untouched; only the profile side may move."""
        self.assertAlmostEqual(self.on["CT"], self.off["CT"], delta=1e-6)
        self.assertAlmostEqual(self.on["CPi"], self.off["CPi"], delta=1e-9)


class TestRatiosHoldForAnyBlade(unittest.TestCase):
    """The one-half ratio is chord-independent by construction. A tapered
    blade must therefore report the same ratio as the constant-chord one
    -- if it does not, the spanwise force is being built from something
    other than the section drag."""

    def test_taper_does_not_change_the_ratio(self):
        geom = geometry.generate_tapered(root_chord_norm=0.14, tip_chord_norm=0.04,
                                          twist_root_deg=0.0, twist_tip_deg=0.0,
                                          root_cutout_norm=0.25, radius_m=1.0,
                                          n_stations=40)
        project = _constant_drag_project(use_radial_flow_correction=True)
        project.geometry = geom
        summary = api.run_case(project, FlightCondition(
            mu_x=0.05, Vz=0.0, collective_deg=0.0, rpm=600.0)).summary
        self.assertAlmostEqual(summary["CHr"] / summary["CHp"], 0.5, delta=0.01)


class TestTheCorrectionIsGated(unittest.TestCase):
    """Switching the option off must reproduce the engine as it was
    before the spanwise drag existed -- that is what keeps every stored
    golden number valid (`tests/data/golden_results.json`)."""

    def test_off_reports_exactly_zero_spanwise_force(self):
        off, _on = _summaries(0.20)
        self.assertEqual(off["CHr"], 0.0)
        self.assertEqual(off["Hr"], 0.0)
        self.assertAlmostEqual(off["CH"], off["CHi"] + off["CHp"], delta=1e-12)

    def test_off_leaves_the_disk_field_at_zero(self):
        project = _constant_drag_project(use_radial_flow_correction=False)
        maps = api.run_case(project, FlightCondition(
            mu_x=0.20, Vz=0.0, collective_deg=0.0, rpm=600.0)).maps
        self.assertTrue(np.all(np.asarray(maps["Fr"]) == 0.0))

    def test_the_three_parts_reconstruct_the_total(self):
        _off, on = _summaries(0.20)
        self.assertAlmostEqual(on["CH"], on["CHi"] + on["CHp"] + on["CHr"],
                                delta=1e-12)


class TestTheSkewCapLimitsTheEffect(unittest.TestCase):
    """`radial_flow_max_skew_deg` caps the local yaw angle, and with it
    the share of the drag the model sends along the span. A tighter cap
    must produce a smaller spanwise force, never a larger one."""

    def test_a_tighter_cap_gives_a_smaller_spanwise_force(self):
        values = []
        for cap in (5.0, 20.0, 60.0):
            project = _constant_drag_project(use_radial_flow_correction=True,
                                              radial_flow_max_skew_deg=cap)
            summary = api.run_case(project, FlightCondition(
                mu_x=0.30, Vz=0.0, collective_deg=0.0, rpm=600.0)).summary
            values.append(summary["CHr"])
        self.assertEqual(values, sorted(values))
        self.assertGreater(values[-1], values[0])


if __name__ == "__main__":
    unittest.main()
