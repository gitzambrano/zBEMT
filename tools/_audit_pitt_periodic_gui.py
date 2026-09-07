from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractButton,
    QComboBox,
    QGroupBox,
    QLabel,
    QScrollArea,
)

from zbemt import api
from zbemt.gui.app import MainWindow


OUT = Path('gui-audit')
OUT.mkdir(exist_ok=True)
SIZES = [(1280, 720), (1366, 768), (1440, 900), (1536, 864), (1920, 1080)]


def _plain(text: str) -> bool:
    return bool(text.strip()) and '<' not in text and '>' not in text


def _clip_findings(root) -> list[str]:
    findings: list[str] = []
    for label in root.findChildren(QLabel):
        if not label.isVisibleTo(root) or label.wordWrap() or not _plain(label.text()):
            continue
        need = label.fontMetrics().horizontalAdvance(label.text())
        have = label.contentsRect().width()
        if need > have + 2:
            findings.append(f'QLabel {label.text()!r}: needs {need}px, has {have}px')
    for button in root.findChildren(QAbstractButton):
        if not button.isVisibleTo(root) or not button.text().strip():
            continue
        need = button.fontMetrics().horizontalAdvance(button.text()) + 22
        have = button.contentsRect().width()
        if need > have + 2:
            findings.append(f'{type(button).__name__} {button.text()!r}: needs {need}px, has {have}px')
    for combo in root.findChildren(QComboBox):
        if not combo.isVisibleTo(root):
            continue
        text = combo.currentText()
        need = combo.fontMetrics().horizontalAdvance(text) + 42
        have = combo.contentsRect().width()
        if text and need > have + 2:
            findings.append(f'QComboBox {text!r}: needs {need}px, has {have}px')
    for box in root.findChildren(QGroupBox):
        if not box.isVisibleTo(root) or not box.title():
            continue
        need = box.fontMetrics().horizontalAdvance(box.title()) + 32
        have = box.contentsRect().width()
        if need > have + 2:
            findings.append(f'QGroupBox {box.title()!r}: needs {need}px, has {have}px')
    return findings


def _no_horizontal_scroll(root, name: str) -> list[str]:
    findings = []
    for area in root.findChildren(QScrollArea):
        if area.isVisibleTo(root) and area.horizontalScrollBar().maximum() > 0:
            findings.append(
                f'{name}: horizontal scrollbar range={area.horizontalScrollBar().maximum()} '
                f'viewport={area.viewport().width()} content={area.widget().width() if area.widget() else None}')
    return findings


def _set_combo_data(combo: QComboBox, value: str) -> None:
    idx = combo.findData(value)
    if idx < 0:
        raise AssertionError(f'{value!r} not found in combo {[combo.itemData(i) for i in range(combo.count())]}')
    combo.setCurrentIndex(idx)


def _audit_inflow_switching(config, app) -> None:
    expected = {
        'glauert': ['local'],
        'coleman': ['local', 'global'],
        'coleman_feingold': ['global'],
        'drees': ['local', 'global'],
        'pitt_peters': ['steady', 'unsteady'],
    }
    for family, couplings in expected.items():
        config.cfg_inflow_family.setCurrentText(family)
        app.processEvents()
        actual = [config.cfg_inflow_coupling.itemData(i)
                  for i in range(config.cfg_inflow_coupling.count())]
        assert actual == couplings, (family, actual, couplings)
        for coupling in couplings:
            _set_combo_data(config.cfg_inflow_coupling, coupling)
            app.processEvents()
            expected_model = f'{family}_{coupling}'
            assert config._inflow_field_model_from_widgets() == expected_model


def main() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    project = api.open_project('projects/starter_rotor')
    window.state.set_project(project)
    window.show()
    app.processEvents()

    config = window.tabs.widget(3)
    airfoil = window.tabs.widget(2)

    _audit_inflow_switching(config, app)

    # Configure the two time-marching models through the GUI itself.
    window.tabs.setCurrentIndex(3)
    config.cfg_inflow_family.setCurrentText('pitt_peters')
    _set_combo_data(config.cfg_inflow_coupling, 'unsteady')
    config.cfg_pitt_peters_time_march_revolutions.setValue(12)
    config.cfg_pitt_peters_time_march_avg_last.setValue(4)
    config.cfg_pitt_peters_time_march_substeps_per_revolution.setValue(24)
    _set_combo_data(config.cfg_pitt_peters_time_march_initial_state, 'equilibrium')
    app.processEvents()

    assert project.config['inflow_field_model'] == 'pitt_peters_unsteady'
    assert project.config['pitt_peters_time_march_revolutions'] == 12
    assert project.config['pitt_peters_time_march_avg_last'] == 4
    assert project.config['pitt_peters_time_march_substeps_per_revolution'] == 24
    assert project.config['pitt_peters_time_march_initial_state'] == 'equilibrium'
    for widget in (
        config.cfg_pitt_peters_time_march_revolutions,
        config.cfg_pitt_peters_time_march_avg_last,
        config.cfg_pitt_peters_time_march_substeps_per_revolution,
        config.cfg_pitt_peters_time_march_initial_state,
    ):
        assert widget.isVisibleTo(config), f'{widget} not visible in dynamic Pitt-Peters'

    # Steady must hide only the time-march rows, not the general Pitt-Peters box.
    _set_combo_data(config.cfg_inflow_coupling, 'steady')
    app.processEvents()
    assert config.pitt_peters_box.isVisibleTo(config)
    assert not config.cfg_pitt_peters_time_march_revolutions.isVisibleTo(config)
    _set_combo_data(config.cfg_inflow_coupling, 'unsteady')
    app.processEvents()

    # Dynamic stall time march through the Airfoil GUI.
    window.tabs.setCurrentIndex(2)
    if airfoil.stall_model_combo.findText('clip') >= 0:
        airfoil.stall_model_combo.setCurrentText('clip')
    airfoil.use_dynamic_stall.setChecked(True)
    _set_combo_data(airfoil.dyn_method, 'time_march')
    airfoil.dyn_revs.setValue(9)
    airfoil.dyn_avg_last.setValue(3)
    app.processEvents()
    assert project.airfoil.use_dynamic_stall is True
    assert project.airfoil.dynamic_stall_method == 'time_march'
    assert project.airfoil.dynamic_stall_time_march_revolutions == 9
    assert project.airfoil.dynamic_stall_time_march_avg_last == 3

    report = {'sizes': {}, 'inflow_switching': 'ok', 'gui_state_roundtrip': 'ok'}
    all_findings: list[str] = []

    for width, height in SIZES:
        size_key = f'{width}x{height}'
        report['sizes'][size_key] = {}
        window.resize(width, height)
        app.processEvents()

        # Config / Pitt-Peters Dynamic screenshot and checks.
        window.tabs.setCurrentIndex(3)
        app.processEvents()
        for area in config.findChildren(QScrollArea):
            area.verticalScrollBar().setValue(0)
        app.processEvents()
        findings = _clip_findings(window) + _no_horizontal_scroll(config, f'{size_key}/config')
        report['sizes'][size_key]['config_dynamic_findings'] = findings
        all_findings.extend(f'{size_key}/config: {f}' for f in findings)
        assert window.grab().save(str(OUT / f'{size_key}-config-pitt-dynamic.png'))

        # Airfoil / Oye Time march screenshot and checks.
        window.tabs.setCurrentIndex(2)
        app.processEvents()
        for area in airfoil.findChildren(QScrollArea):
            area.verticalScrollBar().setValue(0)
        app.processEvents()
        findings = _clip_findings(window) + _no_horizontal_scroll(airfoil, f'{size_key}/airfoil')
        report['sizes'][size_key]['airfoil_time_march_findings'] = findings
        all_findings.extend(f'{size_key}/airfoil: {f}' for f in findings)
        assert window.grab().save(str(OUT / f'{size_key}-airfoil-oye-time-march.png'))

    report['hard_findings'] = all_findings
    (OUT / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')

    if all_findings:
        raise AssertionError('GUI clipping/layout findings:\n' + '\n'.join(all_findings))

    print(json.dumps(report, indent=2))
    window.close()
    app.quit()


if __name__ == '__main__':
    main()
