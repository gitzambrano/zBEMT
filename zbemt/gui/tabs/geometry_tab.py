"""Tab 2 -- Geometry: the radial table is the source of truth; the
parametric generator is just a convenience to fill it."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QPushButton,
    QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem, QMessageBox,
    QScrollArea, QSplitter, QHeaderView, QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from ... import geometry
from ...viz import plots

from ..common import AppState, CanvasHost
from ..dialogs import GeometryGeneratorDialog


class GeometryTab(QWidget):
    """Geometry = radial table (r/R, chord, twist). The parametric
    generator is just a convenience to fill it (popup); number of
    blades and radius are constants always visible, outside the popup
    (docs/plano.md Section 3).

    Embedded canvas (docs/plano_v3.md Part 6.1): same rationale as the
    Airfoil tab (Part 5) -- horizontal `QSplitter`, form on the left,
    "Top View"/"Chord-Twist" preview on the right, always visible, live
    with debounce (~300ms). Replaces the old "Geometry" mode of
    ResultsTab, removed in this Part."""

    dirty_changed = pyqtSignal(bool)   # asterisk for "not saved to disk" (same mechanism as config.py/airfoil.py)

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self._dirty = False
        # True while this tab is writing its own edit back into
        # `state.project.geometry` -- prevents `_refresh_from_project`
        # (connected to `geometry_changed`, which the write itself
        # triggers) from rebuilding the table from what just came out of
        # it and clearing the asterisk before the user saves to disk.
        self._applying_locally = False

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._refresh_preview)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        left_widget = QWidget()
        layout = QVBoxLayout(left_widget)
        scroll.setWidget(left_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(scroll)
        splitter.addWidget(self._build_preview_panel())
        # All extra space goes to the CANVAS (stretch 0 x 1), not to the
        # form: the window opens maximized (`app.main` calls
        # showMaximized), and with the form growing along with it a wide
        # screen turned into half an empty field panel and a squeezed
        # plot. `setSizes` fixes only the INITIAL width of each side.
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([460, 900])
        outer = QVBoxLayout(self)
        outer.addWidget(splitter)

        const_box = QGroupBox("Global Geometry")
        const_form = QFormLayout(const_box)
        self.n_blades = QSpinBox(); self.n_blades.setRange(1, 12); self.n_blades.setValue(2)
        self.n_blades.setToolTip('"n_blades"<br><br>Number of blades in the rotor or propeller.')
        self.radius_m = QDoubleSpinBox(); self.radius_m.setRange(0.01, 100); self.radius_m.setValue(1.0)
        self.radius_m.setSingleStep(0.1)
        self.radius_m.setToolTip('"radius_m"<br><br>Rotor or propeller radius in metres.<br><br>Chord values in the table are normalized by this radius.')
        const_form.addRow("Number of Blades:", self.n_blades)
        const_form.addRow("Rotor Radius [m]:", self.radius_m)
        self.n_blades.valueChanged.connect(self._apply_constants)
        self.radius_m.valueChanged.connect(self._apply_constants)
        layout.addWidget(const_box)

        btn_gen = QPushButton("Generate Table…")
        btn_gen.setToolTip(
            "Generate the radial blade table from a parametric chord distribution.<br><br>"
            "The available shapes are rectangular, tapered, and elliptical.")
        btn_gen.clicked.connect(self._open_generator)
        layout.addWidget(btn_gen)

        table_box = QGroupBox("Radial Distribution Table")
        tbox_layout = QVBoxLayout(table_box)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["r/R", "chord c/R", "twist [deg]"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._schedule_preview_refresh)
        self.table.itemChanged.connect(self._apply_table_edits)
        tbox_layout.addWidget(self.table)
        layout.addWidget(table_box, stretch=1)

        save_row = QHBoxLayout()
        # One-word labels -- see the same change in `tabs/config.py`.
        btn_save = QPushButton("Save")
        btn_save.setToolTip("Save the current geometry and project settings to disk.")
        btn_save.clicked.connect(self._save_project)
        save_row.addWidget(btn_save)
        btn_restore = QPushButton("Restore")
        btn_restore.setToolTip("Discard unsaved geometry changes and reload the project from disk.")
        btn_restore.clicked.connect(self._restore_project)
        save_row.addWidget(btn_restore)
        # The slack goes to the end of the row, not to the buttons (see
        # `tests/test_gui_layout.py`: without this they stretch to the
        # QSS width ceiling, and `setSizePolicy(Fixed)` doesn't hold).
        save_row.addStretch(1)
        layout.addLayout(save_row)

        self.state.geometry_changed.connect(self._refresh_from_project)
        self._refresh_preview()

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)

        self.preview_tabs = QTabWidget()
        self.planform_canvas = CanvasHost()
        self.chord_twist_canvas = CanvasHost()
        self.rotor_3d_canvas = CanvasHost()
        self.preview_tabs.addTab(self.planform_canvas, "Plan View")
        self.preview_tabs.addTab(self.chord_twist_canvas, "Chord/Twist")
        self.preview_tabs.addTab(self.rotor_3d_canvas, "Rotor 3D")
        self.preview_tabs.currentChanged.connect(lambda _i: self._refresh_preview())
        panel_layout.addWidget(self.preview_tabs, stretch=1)
        return panel

    def _schedule_preview_refresh(self, *_args):
        if hasattr(self, "_preview_timer"):
            self._preview_timer.start()

    def _mark_dirty(self, *_args):
        if not self._dirty:
            self._dirty = True
            self.dirty_changed.emit(True)

    def _clear_dirty(self):
        if self._dirty:
            self._dirty = False
            self.dirty_changed.emit(False)

    def _current_geometry(self):
        """Geometry to draw in the preview: reflects the table/constants
        exactly as they are in the form RIGHT NOW, even before "Apply
        table edits" -- this is the whole reason the live canvas exists
        (see the same principle in Part 5, `_collect_airfoil_def`)."""
        r, c, t = [], [], []
        for i in range(self.table.rowCount()):
            item_r, item_c, item_t = self.table.item(i, 0), self.table.item(i, 1), self.table.item(i, 2)
            if item_r is None or item_c is None or item_t is None:
                continue
            r.append(float(item_r.text())); c.append(float(item_c.text())); t.append(float(item_t.text()))
        if len(r) < 2:
            if self.state.project is not None:
                return self.state.project.geometry
            return None
        airfoil_name = self.state.project.geometry.airfoil_name if self.state.project else ""
        return geometry.generate_custom(r, c, t, radius_m=self.radius_m.value(),
                                          n_blades=self.n_blades.value(), airfoil_name=airfoil_name)

    def _refresh_preview(self):
        if not hasattr(self, "preview_tabs"):
            return
        try:
            geom = self._current_geometry()
        except Exception as exc:
            self.planform_canvas.show_message(f"Error reading geometry: {exc}")
            return
        if geom is None:
            self.planform_canvas.show_message("No project/geometry yet.")
            self.chord_twist_canvas.show_message("No project/geometry yet.")
            self.rotor_3d_canvas.show_message("No project/geometry yet.")
            return
        if self.preview_tabs.currentIndex() == 0:
            canvas = self.planform_canvas.use_simple()
            canvas.clear()
            try:
                plots.plot_planform(geom, ax=canvas.ax)
            except Exception as exc:
                canvas.clear()
                canvas.ax.text(0.5, 0.5, f"Error drawing planform: {exc}", ha="center",
                                va="center", wrap=True, transform=canvas.ax.transAxes)
            canvas.draw()
        elif self.preview_tabs.currentIndex() == 1:
            canvas = self.chord_twist_canvas.use_simple()
            canvas.clear()
            try:
                plots.plot_chord_twist_distribution(geom, ax=canvas.ax)
            except Exception as exc:
                canvas.clear()
                canvas.ax.text(0.5, 0.5, f"Error drawing chord/twist: {exc}", ha="center",
                                va="center", wrap=True, transform=canvas.ax.transAxes)
            canvas.draw()
        else:
            canvas = self.rotor_3d_canvas.use_simple()
            canvas.fig.clear()
            canvas.ax = canvas.fig.add_subplot(111, projection="3d")
            try:
                plots.plot_rotor_3d(geom, ax=canvas.ax)
            except Exception as exc:
                canvas.clear()
                canvas.ax.text(0.5, 0.5, f"Error drawing rotor: {exc}", ha="center",
                               va="center", wrap=True, transform=canvas.ax.transAxes)
            canvas.draw()

    def _open_generator(self):
        airfoil_name = self.state.project.airfoil.name if self.state.project else ""
        dlg = GeometryGeneratorDialog(self, self.n_blades.value(), self.radius_m.value(), airfoil_name)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.generated_geom is not None:
            if self.state.project is not None:
                self.state.project.geometry = dlg.generated_geom
                # Round-trip from item 2: number of blades and radius
                # are now EDITABLE inside the popup, so the "Global
                # Geometry" box here has to start showing what was
                # actually generated -- otherwise the two places diverge
                # and the next `_apply_table_edits` would overwrite the
                # geometry with this tab's stale values.
                self._sync_constants_from_geometry(dlg.generated_geom)
                self._mark_dirty()
                self.state.notify_geometry()
            else:
                QMessageBox.warning(self, "No Project", "Create or open a project first.")

    def _sync_constants_from_geometry(self, geom):
        """Mirrors `n_blades`/`radius_m` from the geometry into the
        spinboxes, without triggering `_apply_constants` (which would
        overwrite the geometry that just arrived)."""
        self.n_blades.blockSignals(True)
        self.radius_m.blockSignals(True)
        self.n_blades.setValue(int(geom.n_blades))
        self.radius_m.setValue(float(geom.radius_m))
        self.n_blades.blockSignals(False)
        self.radius_m.blockSignals(False)

    def _apply_constants(self, _value=None):
        """Number of blades/radius are editable at any time, including
        after pasting a custom table — write directly into
        geom.n_blades/geom.radius_m without reopening the generation
        popup (docs/plano.md Section 3, engineering note)."""
        self._schedule_preview_refresh()
        if self.state.project is None:
            return
        self._mark_dirty()
        geom = self.state.project.geometry
        geom.n_blades = self.n_blades.value()
        geom.radius_m = self.radius_m.value()
        self._applying_locally = True
        try:
            self.state.notify_geometry()
        finally:
            self._applying_locally = False

    def _save_project(self):
        from ..common import save_project_from_tab
        save_project_from_tab(self, self.state)
        self._clear_dirty()

    def _restore_project(self):
        from ..common import restore_project_from_disk
        restore_project_from_disk(self, self.state)

    def _refresh_from_project(self):
        if self.state.project is None:
            return
        if self._applying_locally:
            return
        geom = self.state.project.geometry
        self._sync_constants_from_geometry(geom)

        self.table.blockSignals(True)
        self.table.setRowCount(len(geom.r_norm))
        for i, (r, c, t) in enumerate(zip(geom.r_norm, geom.chord_norm, geom.twist_deg)):
            self.table.setItem(i, 0, QTableWidgetItem(f"{r:.4f}"))
            self.table.setItem(i, 1, QTableWidgetItem(f"{c:.4f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{t:.3f}"))
        self.table.blockSignals(False)
        self._clear_dirty()
        self._refresh_preview()

    def _apply_table_edits(self, *_args):
        if self.state.project is None:
            return
        try:
            r, c, t = [], [], []
            for i in range(self.table.rowCount()):
                r.append(float(self.table.item(i, 0).text()))
                c.append(float(self.table.item(i, 1).text()))
                t.append(float(self.table.item(i, 2).text()))
            geom = self.state.project.geometry
            new_geom = geometry.generate_custom(r, c, t, radius_m=self.radius_m.value(),
                                                  n_blades=self.n_blades.value(),
                                                  airfoil_name=geom.airfoil_name)
        except Exception:
            # Live: a temporarily invalid cell while the user is typing
            # (empty, a lone "-") should not interrupt with a dialog on
            # every keystroke -- the preview already shows the error
            # (`_refresh_preview`), and nothing is written to the project
            # until the row becomes a valid number again.
            return
        self._mark_dirty()
        self.state.project.geometry = new_geom
        self._applying_locally = True
        try:
            self.state.notify_geometry()
        finally:
            self._applying_locally = False


