"""Apply the airfoil pitching-moment and geometry clipboard patch.

This helper exists only to prepare one reviewed branch. The helper removes
itself after it applies the patch so it does not become part of zBEMT.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _path(relative: str) -> Path:
    return ROOT / relative


def _replace_once(relative: str, old: str, new: str) -> None:
    path = _path(relative)
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{relative}: expected one replacement target, found {count}."
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _replace_block(relative: str, start: str, end: str, replacement: str) -> None:
    path = _path(relative)
    text = path.read_text(encoding="utf-8")
    start_index = text.find(start)
    if start_index < 0:
        raise RuntimeError(f"{relative}: start marker not found: {start!r}")
    end_index = text.find(end, start_index + len(start))
    if end_index < 0:
        raise RuntimeError(f"{relative}: end marker not found: {end!r}")
    if text.find(start, start_index + len(start)) >= 0:
        raise RuntimeError(f"{relative}: start marker is not unique: {start!r}")
    path.write_text(
        text[:start_index] + replacement + text[end_index:], encoding="utf-8"
    )


def _write(relative: str, content: str) -> None:
    path = _path(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Data model: preserve the optional section pitching-moment coefficient.
# ---------------------------------------------------------------------------
_replace_once(
    "zbemt/models.py",
    '''@dataclass
class PolarSlice:
    """A polar (alpha_deg, Cl, Cd), optionally labeled by radial section
    (r_norm), Reynolds and/or Mach. The combination of which labels are
    present (None = absent) across the whole slice list of an
    ``AirfoilDef`` determines, in ``airfoils.to_airfoil()``, whether the
    result is a single polar, multi-section, and/or interpolated in
    Re/Mach."""
    alpha_deg: list[float] = field(default_factory=list)
    cl: list[float] = field(default_factory=list)
    cd: list[float] = field(default_factory=list)
    r_norm: Optional[float] = None
''',
    '''@dataclass
class PolarSlice:
    """A polar with angle, lift, drag, and optional pitching moment.

    ``r_norm``, Reynolds, and Mach label the condition of a slice. ``cm``
    stores the section pitching-moment coefficient when the source supplies
    it. The current BEMT force and performance solution does not use ``cm``.
    It is retained in the project and in exported polar data.
    """
    alpha_deg: list[float] = field(default_factory=list)
    cl: list[float] = field(default_factory=list)
    cd: list[float] = field(default_factory=list)
    cm: list[float] = field(default_factory=list)
    r_norm: Optional[float] = None
''',
)


# ---------------------------------------------------------------------------
# CSV import and export: optional Cm, including multi-radial files.
# ---------------------------------------------------------------------------
_replace_once(
    "zbemt/airfoils.py",
    '''    "cd": ["cd", "Cd", "CD"],
    "r_norm": ["r_norm", "r/R", "rR", "radial_station"],
''',
    '''    "cd": ["cd", "Cd", "CD"],
    "cm": ["cm", "Cm", "CM"],
    "r_norm": ["r_norm", "r/R", "rR", "radial_station"],
''',
)
_replace_once(
    "zbemt/airfoils.py",
    '''                cd=group[cols["cd"]].tolist(),
                r_norm=_val(cols["r_norm"]),
''',
    '''                cd=group[cols["cd"]].tolist(),
                cm=(group[cols["cm"]].tolist()
                    if cols["cm"] is not None else []),
                r_norm=_val(cols["r_norm"]),
''',
)
_replace_once(
    "zbemt/airfoils.py",
    '''            cd=df[cols["cd"]].tolist(),
            label=Path(path).stem,
''',
    '''            cd=df[cols["cd"]].tolist(),
            cm=(df[cols["cm"]].tolist() if cols["cm"] is not None else []),
            label=Path(path).stem,
''',
)
_replace_block(
    "zbemt/airfoils.py",
    "def export_polar_slices_csv(slices: list[PolarSlice], path: str) -> Path:\n",
    "def export_polar_csv(airfoil_def: AirfoilDef, path: str) -> Path:\n",
    '''def export_polar_slices_csv(slices: list[PolarSlice], path: str) -> Path:
    """Write polar slices in the format accepted by ``import_polar_csv``.

    The required aerodynamic columns are ``alpha_deg``, ``Cl``, and ``Cd``.
    ``Cm`` is written when at least one slice contains pitching-moment data.
    Radial position, Reynolds number, and Mach number remain conditioning
    columns and can identify many slices in one file.
    """
    rows = []
    has_cm = any(bool(s.cm) for s in slices)
    for s in slices:
        n_points = min(len(s.alpha_deg), len(s.cl), len(s.cd))
        cm_aligned = len(s.cm) == n_points
        for index in range(n_points):
            row = {
                "alpha_deg": s.alpha_deg[index],
                "Cl": s.cl[index],
                "Cd": s.cd[index],
                "r_norm": s.r_norm,
                "reynolds": s.reynolds,
                "mach": s.mach,
            }
            if has_cm:
                row["Cm"] = s.cm[index] if cm_aligned else np.nan
            rows.append(row)
    df = pd.DataFrame(rows)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return out


''',
)
_replace_once(
    "zbemt/airfoils.py",
    '''    """Imports a polar CSV, automatically detecting which axes (r_norm,
    reynolds, mach) are present, and returns a list of `PolarSlice`, one
    per unique combination of (r_norm, reynolds, mach) found in the file.
''',
    '''    """Import a polar CSV and preserve an optional ``Cm`` column.

    The function detects the conditioning axes ``r_norm``, Reynolds, and
    Mach. It returns one ``PolarSlice`` for each unique axis combination.
''',
)


# ---------------------------------------------------------------------------
# External polar engines: preserve CM when the source supplies it.
# ---------------------------------------------------------------------------
_replace_block(
    "zbemt/external_solvers.py",
    "def _parse_xfoil_polar(",
    "def _mach_corrected_slices(",
    '''def _parse_xfoil_polar(text: str, *, include_cm: bool = False) -> tuple:
    """Parse a standard XFOIL accumulated polar dump.

    The default return stays ``(alpha_deg, cl, cd)`` for compatibility.
    Set ``include_cm=True`` to also return the XFOIL ``CM`` column when the
    header supplies it. A missing ``CM`` column then returns an empty list.
    """
    if not text or not text.strip():
        raise ValueError("XFOIL polar dump is empty.")
    lines = text.splitlines()
    header_index = None
    header_tokens: list[str] = []
    for position, line in enumerate(lines):
        tokens = line.split()
        if tokens and tokens[0].lower().startswith("alpha"):
            header_index = position
            header_tokens = tokens
    if header_index is None:
        raise ValueError(
            "XFOIL polar dump has no column-header line starting with "
            "'alpha'. The content is not a recognizable polar output."
        )

    columns = {name.lower(): index for index, name in enumerate(header_tokens)}
    alpha_index = columns.get("alpha", 0)
    cl_index = columns.get("cl", 1)
    cd_index = columns.get("cd", 2)
    cm_index = columns.get("cm")

    alpha_deg: list[float] = []
    cl: list[float] = []
    cd: list[float] = []
    cm: list[float] = []
    required_last = max(alpha_index, cl_index, cd_index)
    for line in lines[header_index + 1:]:
        tokens = line.split()
        if len(tokens) <= required_last:
            continue
        try:
            alpha = float(tokens[alpha_index])
            lift = float(tokens[cl_index])
            drag = float(tokens[cd_index])
        except ValueError:
            continue
        if not (np.isfinite(alpha) and np.isfinite(lift) and np.isfinite(drag)):
            continue

        moment = None
        if cm_index is not None:
            if len(tokens) <= cm_index:
                moment = float("nan")
            else:
                try:
                    moment = float(tokens[cm_index])
                except ValueError:
                    moment = float("nan")

        alpha_deg.append(alpha)
        cl.append(lift)
        cd.append(drag)
        if cm_index is not None:
            cm.append(moment)

    if not alpha_deg:
        raise ValueError(
            "XFOIL polar dump contains a column header but no usable data row."
        )
    if include_cm:
        return alpha_deg, cl, cd, cm
    return alpha_deg, cl, cd


''',
)
_replace_block(
    "zbemt/external_solvers.py",
    "def _mach_corrected_slices(",
    "def _validate_xfoil_adjustments(",
    '''def _mach_corrected_slices(engine_name: str, alpha_valid_deg: np.ndarray,
                           cl_inc: np.ndarray, cd_inc: np.ndarray,
                           mach_list: list[float], reynolds: float,
                           label: str, cm_inc: Optional[np.ndarray] = None) -> list[PolarSlice]:
    """Apply the Prandtl-Glauert correction and build polar slices.

    Lift, drag, and pitching-moment coefficients use the same ``1 / beta``
    pressure-coefficient scaling when pitching-moment data are available.
    A sonic or supersonic Mach value contributes no slice.
    """
    slices: list[PolarSlice] = []
    for mach in mach_list:
        beta = float(np.sqrt(max(0.0, 1.0 - mach ** 2)))
        if beta < 1e-3:
            warnings.warn(
                f"{engine_name}: Mach={mach:.2f} is sonic or supersonic. "
                f"Prandtl-Glauert diverges, so the slice is ignored."
            )
            continue
        slices.append(PolarSlice(
            alpha_deg=alpha_valid_deg.tolist(),
            cl=(cl_inc / beta).tolist(),
            cd=(cd_inc / beta).tolist(),
            cm=((cm_inc / beta).tolist() if cm_inc is not None else []),
            reynolds=float(reynolds),
            mach=float(mach),
            label=label,
        ))
    return slices


''',
)
_replace_once(
    "zbemt/external_solvers.py",
    '''                alpha_vals, cl_vals, cd_vals = _parse_xfoil_polar(text)
''',
    '''                alpha_vals, cl_vals, cd_vals, cm_vals = _parse_xfoil_polar(
                    text, include_cm=True)
''',
)
_replace_once(
    "zbemt/external_solvers.py",
    '''                cd_inc=np.asarray(cd_vals, dtype=float),
                mach_list=mach_list,
''',
    '''                cd_inc=np.asarray(cd_vals, dtype=float),
                cm_inc=(np.asarray(cm_vals, dtype=float) if cm_vals else None),
                mach_list=mach_list,
''',
)
_replace_once(
    "zbemt/external_solvers.py",
    '''        cl_inc = np.asarray(aero["CL"], dtype=float)
        cd_inc = np.asarray(aero["CD"], dtype=float)
        confidence = np.asarray(
''',
    '''        cl_inc = np.asarray(aero["CL"], dtype=float)
        cd_inc = np.asarray(aero["CD"], dtype=float)
        cm_raw = aero.get("CM")
        cm_inc = np.asarray(cm_raw, dtype=float) if cm_raw is not None else None
        confidence = np.asarray(
''',
)
_replace_once(
    "zbemt/external_solvers.py",
    '''            cd_inc=cd_inc[valid_base],
            mach_list=mach_list,
''',
    '''            cd_inc=cd_inc[valid_base],
            cm_inc=(cm_inc[valid_base] if cm_inc is not None else None),
            mach_list=mach_list,
''',
)


# ---------------------------------------------------------------------------
# Airfoil GUI: no inline format instructions. Use a tooltip and help popup.
# ---------------------------------------------------------------------------
_replace_once(
    "zbemt/gui/tabs/airfoil.py",
    '''        btn_export.setToolTip(
            "Writes the current polar in the same CSV format the importer "
            "reads — one row per angle of attack, with a column for each of "
            "r/R, Reynolds and Mach that this polar actually uses. Exporting "
            "once is the quickest way to get a template to fill in.")
''',
    '''        btn_export.setToolTip(
            "Write the current polar in the CSV format accepted by the importer. "
            "The export preserves the optional pitching-moment coefficient and "
            "the radial, Reynolds, and Mach conditioning columns when present.")
''',
)
_replace_once(
    "zbemt/gui/tabs/airfoil.py",
    '''        row.addWidget(btn_import)
        row.addWidget(btn_export)
        row.addStretch(1)
''',
    '''        row.addWidget(btn_import)
        row.addWidget(btn_export)
        btn_csv_help = QPushButton("?")
        btn_csv_help.setFixedWidth(28)
        btn_csv_help.setToolTip("Show the polar CSV format help.")
        btn_csv_help.clicked.connect(self._show_csv_import_help)
        row.addWidget(btn_csv_help)
        row.addStretch(1)
''',
)
_replace_block(
    "zbemt/gui/tabs/airfoil.py",
    "        # The same text as the button, visible without having to discover\n",
    "        self.detected_axes_label = QLabel(\"No data imported yet.\")\n",
    '''        self.detected_axes_label = QLabel("No data imported yet.")
''',
)
_replace_block(
    "zbemt/gui/tabs/airfoil.py",
    "    #: Help text for the tabulated polar IMPORTER.",
    "    #: Help text for the contour import button.",
    '''    def _show_csv_import_help(self):
        QMessageBox.information(
            self, "Polar CSV format", self._CSV_IMPORT_TOOLTIP)

    #: Help for the tabulated polar importer. The same text is available as
    #: the Import CSV button tooltip and through the adjacent help button.
    _CSV_IMPORT_TOOLTIP = (
        "Import one or more airfoil polar slices from one CSV file.\n\n"
        "Required columns are alpha_deg, Cl, and Cd. Common aliases are "
        "accepted without regard to case. The pitching-moment coefficient "
        "Cm is optional. If Cm is present, zBEMT stores it in the project and "
        "writes it on export. The current BEMT force and performance solution "
        "does not use the pitching-moment coefficient.\n\n"
        "Use r_norm to put several radial polar stations of the same airfoil "
        "in one file. Do not import one file for each radial station. Repeat "
        "the r_norm value on every angle-of-attack row that belongs to that "
        "station. Reynolds and Mach work the same way and can appear in the "
        "same file.\n\n"
        "Example:\n"
        "    r_norm,alpha_deg,Cl,Cd,Cm\n"
        "    0.20,-5,-0.32,0.0121,-0.040\n"
        "    0.20,0,0.21,0.0098,-0.043\n"
        "    0.80,-5,-0.30,0.0114,-0.036\n"
        "    0.80,0,0.24,0.0092,-0.039\n\n"
        "Use the Radial Sections control when the blade uses different airfoil "
        "definitions or different profile geometries along the span. A radial "
        "polar table for one airfoil does not require separate Airfoil Sections.\n\n"
        "Without r_norm, Reynolds, or Mach, the CSV defines one polar for the "
        "whole blade. Export CSV writes a compatible template."
    )

''',
)
_replace_once(
    "zbemt/gui/tabs/airfoil.py",
    '''if v and k not in ("alpha_deg", "cl", "cd"))
''',
    '''if v and k not in ("alpha_deg", "cl", "cd", "cm"))
''',
)


# ---------------------------------------------------------------------------
# Geometry GUI: spreadsheet-style clipboard paste with one final update.
# ---------------------------------------------------------------------------
_replace_once(
    "zbemt/gui/tabs/geometry_tab.py",
    '''    QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem, QMessageBox,
    QScrollArea, QSplitter, QHeaderView, QDialog, QCheckBox, QLabel,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
''',
    '''    QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem, QMessageBox,
    QScrollArea, QSplitter, QHeaderView, QDialog, QCheckBox, QLabel, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QKeySequence
''',
)
_replace_once(
    "zbemt/gui/tabs/geometry_tab.py",
    '''

class GeometryTab(QWidget):
''',
    '''

def _parse_clipboard_number(value: str) -> float:
    """Parse one spreadsheet number and accept a decimal comma."""
    token = value.strip().replace("\u00a0", "").replace(" ", "")
    if not token:
        raise ValueError("The pasted geometry table contains an empty cell.")
    if "," in token and "." not in token:
        token = token.replace(",", ".")
    try:
        number = float(token)
    except ValueError as exc:
        raise ValueError(
            f"The pasted geometry value {value!r} is not a number."
        ) from exc
    if not np.isfinite(number):
        raise ValueError(
            f"The pasted geometry value {value!r} is not finite."
        )
    return number


def _parse_geometry_clipboard(text: str) -> list[list[float]]:
    """Parse a rectangular table copied from a spreadsheet or text file."""
    lines = [
        line for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]
    if not lines:
        return []

    if any("\t" in line for line in lines):
        rows = [line.split("\t") for line in lines]
    elif any(";" in line for line in lines):
        rows = [line.split(";") for line in lines]
    elif all(line.count(",") == 2 for line in lines):
        # Three-column CSV with dot decimals. A single value such as "0,2"
        # remains one decimal-comma cell instead of becoming two columns.
        rows = [line.split(",") for line in lines]
    else:
        rows = [line.split() for line in lines]

    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError("The pasted geometry table must be rectangular.")
    return [[_parse_clipboard_number(cell) for cell in row] for row in rows]


def _format_clipboard_number(value: float) -> str:
    return f"{value:.12g}"


class GeometryTableWidget(QTableWidget):
    """QTableWidget that accepts a rectangular spreadsheet paste."""

    paste_completed = pyqtSignal()

    def paste_text(self, text: str) -> None:
        matrix = _parse_geometry_clipboard(text)
        if not matrix:
            return
        start_row = max(0, self.currentRow())
        start_column = max(0, self.currentColumn())
        width = len(matrix[0])
        if start_column + width > self.columnCount():
            raise ValueError(
                "The pasted geometry block extends past the last table column."
            )

        needed_rows = start_row + len(matrix)
        previous_blocked = self.blockSignals(True)
        try:
            if needed_rows > self.rowCount():
                self.setRowCount(needed_rows)
            for row_offset, row in enumerate(matrix):
                for column_offset, value in enumerate(row):
                    self.setItem(
                        start_row + row_offset,
                        start_column + column_offset,
                        QTableWidgetItem(_format_clipboard_number(value)),
                    )
        finally:
            self.blockSignals(previous_blocked)
        if not previous_blocked:
            self.paste_completed.emit()

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Paste):
            try:
                self.paste_text(QApplication.clipboard().text())
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid geometry table", str(exc))
            event.accept()
            return
        super().keyPressEvent(event)


class GeometryTab(QWidget):
''',
)
_replace_once(
    "zbemt/gui/tabs/geometry_tab.py",
    '''    dirty_changed = pyqtSignal(bool)   # asterisk for "not saved to disk" (same mechanism as config.py/airfoil.py)

    def __init__(self, state: AppState):
''',
    '''    dirty_changed = pyqtSignal(bool)   # asterisk for "not saved to disk" (same mechanism as config.py/airfoil.py)

    _GEOMETRY_TABLE_HELP = (
        "Edit one cell at a time, or paste a rectangular block from a spreadsheet.\n\n"
        "Select the first destination cell and press Ctrl+V. The first pasted "
        "value goes into that cell. Following rows and columns fill consecutive "
        "cells. The table grows when the pasted block needs more rows.\n\n"
        "Tab-delimited clipboard data from Excel and Google Sheets is accepted. "
        "Semicolon-delimited text and simple three-column CSV text are also "
        "accepted. A decimal comma is accepted in spreadsheet and semicolon "
        "data.\n\n"
        "zBEMT validates the complete pasted block before it changes any cell. "
        "The geometry and preview update once after the full paste."
    )

    def __init__(self, state: AppState):
''',
)
_replace_once(
    "zbemt/gui/tabs/geometry_tab.py",
    '''        table_box = QGroupBox("Radial Distribution Table")
        tbox_layout = QVBoxLayout(table_box)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["r/R", "chord c/R", "twist [deg]"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._schedule_preview_refresh)
        self.table.itemChanged.connect(self._apply_table_edits)
        tbox_layout.addWidget(self.table)
''',
    '''        table_box = QGroupBox("Radial Distribution Table")
        tbox_layout = QVBoxLayout(table_box)
        help_row = QHBoxLayout()
        help_row.addStretch(1)
        btn_table_help = QPushButton("?")
        btn_table_help.setFixedWidth(28)
        btn_table_help.setToolTip("Show the geometry table help.")
        btn_table_help.clicked.connect(
            lambda: QMessageBox.information(
                self, "Geometry table", self._GEOMETRY_TABLE_HELP))
        help_row.addWidget(btn_table_help)
        tbox_layout.addLayout(help_row)

        self.table = GeometryTableWidget(0, 3)
        self.table.setToolTip(self._GEOMETRY_TABLE_HELP)
        self.table.setHorizontalHeaderLabels(["r/R", "chord c/R", "twist [deg]"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._schedule_preview_refresh)
        self.table.itemChanged.connect(self._apply_table_edits)
        self.table.paste_completed.connect(self._schedule_preview_refresh)
        self.table.paste_completed.connect(self._apply_table_edits)
        tbox_layout.addWidget(self.table)
''',
)


# ---------------------------------------------------------------------------
# Binding requirements.
# ---------------------------------------------------------------------------
_replace_once(
    "docs/software_requirements.md",
    '''### 1.2 The software must not support
''',
    '''- **SC-16** — A tabulated airfoil polar may contain an optional pitching-moment
  coefficient $C_m$ beside $C_l$ and $C_d$. CSV import, external polar
  generation when the source supplies the coefficient, `.bemt` persistence,
  and CSV export preserve $C_m$. The current BEMT force and performance
  solution does not use $C_m$. A single polar CSV may contain several radial
  stations through the `r_norm` conditioning column. Therefore, one file may
  define all radial polar stations of one airfoil.

### 1.2 The software must not support
''',
)
_replace_once(
    "docs/software_requirements.md",
    '''---

## 4. Quality Requirements
''',
    '''- **TB-5** — The Geometry radial table accepts a rectangular clipboard block.
  A paste starts at the selected cell and fills consecutive rows and columns.
  The table grows when more rows are required. The parser accepts tab-delimited
  spreadsheet data, semicolon-delimited text, and simple three-column CSV text.
  It accepts a decimal comma in spreadsheet and semicolon data. The GUI validates
  the complete pasted block before it changes cells and applies one project update
  after the complete paste.

---

## 4. Quality Requirements
''',
)


# ---------------------------------------------------------------------------
# Main HTML documentation.
# ---------------------------------------------------------------------------
_replace_once(
    "docs/documentation.html",
    '''    <p><span class="gui">GUI</span>: the <i>Radial Distribution Table</i>, with the columns
      <i>r/R</i>, <i>chord c/R</i> and <i>twist [deg]</i>, editable cell by cell. Confirming a cell
      rebuilds the blade immediately, keeping the current number of blades and radius.
    </p>
''',
    '''    <p><span class="gui">GUI</span>: the <i>Radial Distribution Table</i> has the columns
      <i>r/R</i>, <i>chord c/R</i> and <i>twist [deg]</i>. Edit one cell at a time, or select the
      first destination cell and paste a rectangular spreadsheet block. A paste fills consecutive cells
      and adds rows when necessary. Tab-delimited spreadsheet data accepts a dot or comma decimal separator.
      Semicolon-delimited text and simple three-column CSV text are also accepted. zBEMT validates the full
      pasted block before it changes the table and rebuilds the geometry once after the paste.
    </p>
''',
)
_replace_once(
    "docs/documentation.html",
    '''                <p><b>One row is one angle of attack.</b> The three required columns are the angle in degrees and
                  the two coefficients at that angle:</p>
                <pre>alpha_deg,Cl,Cd
-5,-0.32,0.0121
0,0.21,0.0098
5,0.74,0.0115</pre>
''',
    '''                <p><b>One row is one angle of attack.</b> The required columns are the angle in degrees,
                  lift coefficient, and drag coefficient. The pitching-moment coefficient $C_m$ is optional:</p>
                <pre>alpha_deg,Cl,Cd,Cm
-5,-0.32,0.0121,-0.040
0,0.21,0.0098,-0.043
5,0.74,0.0115,-0.046</pre>
                <p>If the source supplies $C_m$, zBEMT stores it in the polar slice and preserves it in
                  <code>.bemt</code> files and CSV exports. The current BEMT force and performance solution does
                  not use the section pitching-moment coefficient.</p>
''',
)
_replace_once(
    "docs/documentation.html",
    '''                    <tr>
                      <td>Drag coefficient</td>
                      <td>required</td>
                      <td><code>cd</code>, <code>Cd</code>, <code>CD</code></td>
                    </tr>
''',
    '''                    <tr>
                      <td>Drag coefficient</td>
                      <td>required</td>
                      <td><code>cd</code>, <code>Cd</code>, <code>CD</code></td>
                    </tr>
                    <tr>
                      <td>Pitching-moment coefficient</td>
                      <td>optional</td>
                      <td><code>cm</code>, <code>Cm</code>, <code>CM</code></td>
                    </tr>
''',
)
_replace_once(
    "docs/documentation.html",
    '''                  $(r/R, Re, M)$ without requiring sorted or contiguous rows. A single CSV may span multiple radial
                  stations, Reynolds numbers, and Mach numbers. The solver interpolates across all supplied dimensions
                  during execution. Omitting parametric columns defines a single global static polar.</p>
''',
    '''                  $(r/R, Re, M)$ without requiring sorted or contiguous rows. A single CSV may span multiple radial
                  stations, Reynolds numbers, and Mach numbers. Therefore, do not import one file for each radial polar
                  station of the same airfoil. Use the separate Airfoil Sections control only when the blade uses different
                  airfoil definitions or different profile geometries along the span. The solver interpolates across all
                  supplied dimensions during execution. Omitting parametric columns defines a single global static polar.</p>
''',
)
_replace_once(
    "docs/documentation.html",
    '''                  <code>alpha_deg</code>, <code>Cl</code>, <code>Cd</code>, <code>r_norm</code>,
                  <code>reynolds</code> and <code>mach</code>. Exporting and re-importing is therefore exact.
''',
    '''                  <code>alpha_deg</code>, <code>Cl</code>, <code>Cd</code>, optional <code>Cm</code>,
                  <code>r_norm</code>, <code>reynolds</code> and <code>mach</code>. Exporting and re-importing
                  therefore preserves the available polar data.
''',
)


# ---------------------------------------------------------------------------
# Regression tests. Engine tests do not import Qt until the GUI-specific test.
# ---------------------------------------------------------------------------
_write(
    "tests/regression/test_airfoil_cm_clipboard.py",
    '''"""Regression coverage for optional airfoil Cm and geometry table paste."""

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
        "r_norm,alpha_deg,Cl,Cd,Cm\\n"
        "0.2,-5,-0.32,0.0121,-0.040\\n"
        "0.2,0,0.21,0.0098,-0.043\\n"
        "0.8,-5,-0.30,0.0114,-0.036\\n"
        "0.8,0,0.24,0.0092,-0.039\\n",
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
        "alpha_deg,Cl,Cd\\n-5,-0.3,0.02\\n0,0.2,0.01\\n",
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
        "0,20\\t0,080\\t12\\n0,40\\t0,075\\t9\\n"
    )
    assert matrix == [[0.2, 0.08, 12.0], [0.4, 0.075, 9.0]]

    app = QApplication.instance() or QApplication([])
    table = GeometryTableWidget(1, 3)
    table.setCurrentCell(0, 0)
    emissions = []
    table.paste_completed.connect(lambda: emissions.append(True))
    table.paste_text("0.2\\t0.08\\t12\\n0.4\\t0.075\\t9")

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
        _parse_geometry_clipboard("0.2\\t0.08\\t12\\n0.4\\t0.075")
''',
)


# Remove the temporary automation from the final branch.
for temporary in (
    _path("tools/apply_airfoil_cm_geometry_paste.py"),
    _path(".github/workflows/apply_airfoil_cm_geometry_paste.yml"),
):
    if temporary.exists():
        temporary.unlink()
