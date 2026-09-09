"""Regression coverage for optional airfoil Cm and geometry table paste."""

from __future__ import annotations

import math

import numpy as np
import pytest

from zbemt import airfoils
from zbemt.external_solvers import _mach_corrected_slices, _parse_xfoil_polar
from zbemt.models import AirfoilDef, PolarSlice, load_bemt, save_bemt


def test_csv_import_and_export_preserve_cm_and_radial_stations(tmp_path):
    source = tmp_path / "polar.csv"
    source.write_text(
        "r_norm,alpha_deg,Cl,Cd,Cm\n"
        "0.2,-5,-0.32,0.0121,-0.040\n"
        "0.2,0,0.21,0.0098,-0.043\n"
        "0.8,-5,-0.30,0.0114,-0.036\n"
        "0.8,0,0.24,0.0092,-0.039\n",
        encoding="utf-8",
    )

    axes = airfoils.detect_csv_axes(str(source))
    assert axes["cm"] == "Cm"

    slices = airfoils.import_polar_csv(str(source))
    assert [s.r_norm for s in slices] == [0.2, 0.8]
    assert slices[0].cm == [-0.040, -0.043]
    assert slices[1].cm == [-0.036, -0.039]

    exported = tmp_path / "exported.csv"
    airfoils.export_polar_slices_csv(slices, str(exported))
    roundtrip = airfoils.import_polar_csv(str(exported))
    assert [s.r_norm for s in roundtrip] == [0.2, 0.8]
    assert roundtrip[0].cm == pytest.approx(slices[0].cm)
    assert roundtrip[1].cm == pytest.approx(slices[1].cm)


def test_old_csv_without_cm_remains_compatible(tmp_path):
    source = tmp_path / "legacy.csv"
    source.write_text(
        "alpha_deg,Cl,Cd\n-5,-0.3,0.02\n0,0.2,0.01\n",
        encoding="utf-8",
    )
    slices = airfoils.import_polar_csv(str(source))
    assert len(slices) == 1
    assert slices[0].cm == []


def test_cm_survives_bemt_serialization(tmp_path):
    path = tmp_path / "airfoil.bemt"
    airfoil = AirfoilDef(
        name="table",
        source="table",
        table_slices=[PolarSlice(
            alpha_deg=[-2.0, 2.0],
            cl=[-0.2, 0.2],
            cd=[0.01, 0.01],
            cm=[-0.04, -0.05],
            r_norm=0.6,
        )],
    )
    save_bemt(airfoil, str(path))
    loaded = load_bemt(AirfoilDef, str(path))
    assert loaded.table_slices[0].cm == [-0.04, -0.05]
    assert loaded.table_slices[0].r_norm == 0.6


def test_xfoil_parser_can_return_cm_without_breaking_default_shape():
    text = """
 XFOIL polar
 alpha    CL       CD       CDp      CM
 ----- -------- -------- -------- --------
 -2.0   -0.20    0.0120   0.0080  -0.041
  2.0    0.24    0.0110   0.0070  -0.047
"""
    alpha, cl, cd = _parse_xfoil_polar(text)
    assert alpha == [-2.0, 2.0]
    assert cl == [-0.20, 0.24]
    assert cd == [0.0120, 0.0110]

    alpha, cl, cd, cm = _parse_xfoil_polar(text, include_cm=True)
    assert cm == [-0.041, -0.047]


def test_prandtl_glauert_preserves_and_scales_cm():
    slices = _mach_corrected_slices(
        engine_name="test",
        alpha_valid_deg=np.array([0.0]),
        cl_inc=np.array([0.4]),
        cd_inc=np.array([0.02]),
        cm_inc=np.array([-0.04]),
        mach_list=[0.6],
        reynolds=500000.0,
        label="test",
    )
    beta = math.sqrt(1.0 - 0.6 ** 2)
    assert slices[0].cm == pytest.approx([-0.04 / beta])


def test_geometry_clipboard_accepts_excel_tsv_decimal_comma_and_updates_once():
    pytest.importorskip("PyQt6")
    from PyQt6.QtWidgets import QApplication
    from zbemt.gui.tabs.geometry_tab import GeometryTableWidget, _parse_geometry_clipboard

    matrix = _parse_geometry_clipboard(
        "0,20\t0,080\t12\n0,40\t0,075\t9\n"
    )
    assert matrix == [[0.2, 0.08, 12.0], [0.4, 0.075, 9.0]]

    app = QApplication.instance() or QApplication([])
    table = GeometryTableWidget(1, 3)
    table.setCurrentCell(0, 0)
    emissions = []
    table.paste_completed.connect(lambda: emissions.append(True))
    table.paste_text("0.2\t0.08\t12\n0.4\t0.075\t9")

    assert table.rowCount() == 2
    assert table.item(0, 0).text() == "0.2"
    assert table.item(1, 1).text() == "0.075"
    assert table.item(1, 2).text() == "9"
    assert emissions == [True]
    app.processEvents()


def test_geometry_clipboard_rejects_non_rectangular_data_before_editing():
    pytest.importorskip("PyQt6")
    from zbemt.gui.tabs.geometry_tab import _parse_geometry_clipboard

    with pytest.raises(ValueError, match="rectangular"):
        _parse_geometry_clipboard("0.2\t0.08\t12\n0.4\t0.075")
