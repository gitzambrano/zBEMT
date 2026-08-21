"""Implement the Project GUI tab.

The tab creates, opens, saves, and validates projects; selects rotor or propeller
mode; and edits project metadata. Inputs are project paths, names, mode settings,
and shared project definitions. Outputs are updated application state and persisted
``.bemt`` projects. Solver execution and file-format interpretation remain owned by
the application boundary.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QListWidget, QListWidgetItem,
    QRadioButton, QButtonGroup,
)

from ... import api

from ..common import PROJECTS_ROOT, AppState, show_error


# =============================================================================
# Tab 1 — Project
# =============================================================================

class ProjectTab(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        layout = QHBoxLayout(self)

        # --- left column: list of existing projects ---
        left = QVBoxLayout()
        left.addWidget(QLabel("<b>Existing Projects</b>"))
        self.project_list = QListWidget()
        self.project_list.itemDoubleClicked.connect(self._open_selected)
        left.addWidget(self.project_list)
        btn_refresh = QPushButton("Refresh List")
        btn_refresh.clicked.connect(self._refresh_list)
        left.addWidget(btn_refresh)
        layout.addLayout(left, stretch=1)

        # --- right column: mode (Rotor/Propeller) + actions ---
        right = QVBoxLayout()

        mode_box = QGroupBox("Operation Mode")
        mode_layout = QVBoxLayout(mode_box)
        self.radio_rotor = QRadioButton("Rotor")
        self.radio_propeller = QRadioButton("Propeller")
        self.radio_rotor.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_rotor)
        self.mode_group.addButton(self.radio_propeller)
        mode_layout.addWidget(self.radio_rotor)
        mode_layout.addWidget(self.radio_propeller)
        self.radio_rotor.toggled.connect(self._on_mode_toggled)
        right.addWidget(mode_box)

        right.addWidget(QLabel("<b>New / Open / Save</b>"))

        form = QFormLayout()
        self.name_edit = QLineEdit("new_project")
        self.name_edit.setToolTip(
            '"name"<br><br>Name used for the project folder, generated report, '
            'and Results history.<br><br>It does not change the physical calculation.')
        form.addRow("Project Name:", self.name_edit)
        right.addLayout(form)

        btn_new = QPushButton("New Project")
        btn_new.clicked.connect(self._new_project)
        right.addWidget(btn_new)

        btn_open_dialog = QPushButton("Open from another folder…")
        btn_open_dialog.clicked.connect(self._open_dialog)
        right.addWidget(btn_open_dialog)

        # "Save", same as the other tabs -- the Save/Restore pair appears
        # in Geometry, Airfoil, and Config/Engine with this label, and a
        # fourth spelling ("Save Project") would only make the user
        # wonder if the button does something different.
        btn_save = QPushButton("Save")
        btn_save.setToolTip("Save the current project to disk.")
        btn_save.clicked.connect(self._save_project)
        right.addWidget(btn_save)

        right.addSpacing(20)
        self.status_label = QLabel("No project open.")
        self.status_label.setWordWrap(True)
        right.addWidget(self.status_label)
        right.addStretch(1)

        layout.addLayout(right, stretch=1)

        self._refresh_list()
        self.state.project_changed.connect(self._refresh_status)
        self.state.project_changed.connect(self._refresh_mode_from_project)

    def _refresh_list(self):
        self.project_list.clear()
        for name in api.list_projects(PROJECTS_ROOT):
            self.project_list.addItem(QListWidgetItem(name))

    def _new_project(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a project name.")
            return
        path = str(Path(PROJECTS_ROOT) / name)
        try:
            project = api.new_project(path, name=name)
            self.state.set_project(project)
            self._refresh_list()
        except Exception as exc:
            show_error(self, "Error creating project", exc)

    def _open_selected(self, item: QListWidgetItem):
        path = str(Path(PROJECTS_ROOT) / item.text())
        self._open_path(path)

    def _open_dialog(self):
        path = QFileDialog.getExistingDirectory(self, "Open Project")
        if path:
            self._open_path(path)

    def _open_path(self, path: str):
        try:
            project = api.open_project(path)
            self.state.set_project(project)
            self.name_edit.setText(project.name)
        except Exception as exc:
            show_error(self, "Error opening project", exc)

    def _save_project(self):
        if self.state.project is None:
            QMessageBox.warning(self, "No Project", "Create or open a project first.")
            return
        try:
            api.save_project(self.state.project)
            self.state.mark_saved()
            QMessageBox.information(self, "Saved", f"Project saved at {self.state.project.path}")
            self._refresh_list()
        except Exception as exc:
            show_error(self, "Error saving project", exc)

    def _refresh_status(self):
        p = self.state.project
        if p is None:
            self.status_label.setText("No project open.")
        else:
            self.status_label.setText(f"Active project: <b>{p.name}</b><br>Folder: {p.path}")

    # --- Rotor/Propeller mode (docs/plano.md Section 2) --------------------

    def _refresh_mode_from_project(self):
        if self.state.project is None:
            return
        is_prop = self.state.is_propeller()
        self.radio_rotor.blockSignals(True)
        self.radio_propeller.blockSignals(True)
        self.radio_propeller.setChecked(is_prop)
        self.radio_rotor.setChecked(not is_prop)
        self.radio_rotor.blockSignals(False)
        self.radio_propeller.blockSignals(False)

    def _on_mode_toggled(self, _checked: bool):
        if self.state.project is None:
            return
        new_value = self.radio_propeller.isChecked()
        old_value = bool(self.state.project.config.get("is_propeller", False))
        if new_value == old_value:
            return
        self.state.project.config["is_propeller"] = new_value
        self.state.notify_mode()
        self.state.notify_config()
        QMessageBox.information(
            self, "Mode Changed",
            "This changes the vocabulary of mu_x/J_x and alpha/Vz in the following tabs — "
            "numeric values are NOT automatically converted. Check Run Case/Run Batch "
            "before running.")


