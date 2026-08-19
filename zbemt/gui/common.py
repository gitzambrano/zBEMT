"""Infrastructure shared by the GUI tabs.

``AppState`` (the single state object, with signals), the matplotlib canvases,
the dialog helpers and the pre-execution guards. Knows nothing about any tab:
the dependency only points from the tabs to here, never the other way around.
"""


from __future__ import annotations

import importlib
import os
import traceback
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QMessageBox,
)
from PyQt6.QtCore import pyqtSignal, QEvent, QObject, QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices

#: True whenever Qt is running under the offscreen platform plugin (set by
#: `tests/conftest.py` for every headless test run). QtWebEngineWidgets is
#: known to hard-crash the whole process -- not raise a Python exception --
#: the moment it is imported under this platform on some Qt/Chromium
#: builds, before a single `QWebEngineView` is ever constructed (a step
#: below the already-documented instantiation-time crash on
#: `PlotlyCanvasHost`). There is nothing to catch: skip the import
#: entirely rather than let it take the interpreter down.
_HEADLESS = os.environ.get("QT_QPA_PLATFORM") == "offscreen"

if _HEADLESS:
    QWebEngineView = None
    HAS_INTERACTIVE_PLOTS = False
else:
    try:
        from PyQt6.QtWebEngineWidgets import QWebEngineView
        HAS_INTERACTIVE_PLOTS = True
    except ImportError:
        QWebEngineView = None
        HAS_INTERACTIVE_PLOTS = False

# This module is imported by ALL other GUI modules, so it is the right
# place to fix the matplotlib backend: it must happen before any
# `FigureCanvasQTAgg` exists. Headless test runs already set the Agg
# backend in `tests/conftest.py` (QtAgg needs a real/offscreen Qt
# application, which `matplotlib.use` does not always detect correctly
# once QT_QPA_PLATFORM=offscreen); respect that instead of overriding it.
import matplotlib
if not _HEADLESS:
    matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from .. import api
from .. import nomenclature
from .. import paths
from ..models import Project, ResultEntry


#: `docs/`, `projects/` and `outputs/` do NOT live inside the package --
#: they are user data and documentation, not code. `zbemt.paths` resolves
#: each one depending on whether zBEMT is running from the repository
#: (clone / `pip install -e .`) or actually installed, in which case
#: `parents[2]` would point inside `site-packages`.
PROJECTS_ROOT = str(paths.projects_root())


def parse_list(text: str) -> list[float]:
    text = text.strip()
    if not text:
        return []
    return [float(v) for v in text.split(",") if v.strip()]


def symbol_to_plain_text(simbolo_html: str) -> str:
    """`api.SUMMARY_SYMBOLS` stores symbols in HTML (`"C<sub>T</sub>"`,
    `"&mu;"`) intended for the report; a `QTableWidgetItem` does not
    render HTML, so "&mu;" would appear literally instead of "μ".
    Converts subscript to a `_` suffix and decodes HTML entities into
    the actual Unicode character. Shared between `ResultsTab` (column
    header) and `RunCaseTab` (row label) -- same conversion, a single
    implementation."""
    import html
    texto = simbolo_html.replace("<sub>", "_").replace("</sub>", "")
    return html.unescape(texto)


def describe_case_settings(summary: dict) -> str:
    """Short string with the parameters that define a case ("μ_x=0.3,
    θ₀=8°, rpm=600"), so that a history entry (Results tab) states by
    itself what was run, instead of a generic label like "case μ_x=0.3"
    (which could already be confused between two cases with the same
    μ_x but different collective/rpm). Reads directly from
    `Results.summary` -- the same keys `api.SUMMARY_SYMBOLS`/the report
    use, so the description never diverges from what the report would
    show for the same case.

    The symbols are the ones from the final nomenclature (`μ_x`,
    `V_z`), never `μ` or `V` without an index: the same label appears
    in both modes and without the index it is impossible to tell which
    component it is."""
    partes = []
    if "mu_x" in summary:
        partes.append(f"μ_x={summary['mu_x']:.3g}")
    if "collective_deg" in summary:
        partes.append(f"θ₀={summary['collective_deg']:.3g}°")
    if "rpm" in summary and summary["rpm"] is not None:
        partes.append(f"rpm={summary['rpm']:.0f}")
    componente_z = summary.get("Vz")
    if componente_z is not None and abs(componente_z) > 1e-9:
        partes.append(f"V_z={componente_z:.3g}")
    return ", ".join(partes) if partes else "case"


def describe_batch_settings(results_list: list) -> str:
    """Same idea as `describe_case_settings`, for a batch: for each key
    quantity, shows the RANGE if it varies between cases ("μ_x:
    0→0.4, 9 cases") or the single value if it is constant across the
    whole batch ("θ₀=8°") -- tells at a glance what the sweep axis
    was without having to open the case queue."""
    if not results_list:
        return "batch"
    partes = []
    n = len(results_list)
    for chave, simbolo, fmt, sufixo in (
        ("mu_x", "μ_x", "{:.3g}", ""),
        ("collective_deg", "θ₀", "{:.3g}", "°"),
        ("rpm", "rpm", "{:.0f}", ""),
        ("Vz", "V_z", "{:.3g}", ""),
    ):
        valores = [r.summary[chave] for r in results_list
                   if chave in r.summary and r.summary[chave] is not None]
        if not valores:
            continue
        if chave == "Vz" and all(abs(v) < 1e-9 for v in valores):
            continue
        lo, hi = min(valores), max(valores)
        if hi - lo > 1e-9 * max(1.0, abs(hi)):
            partes.append(f"{simbolo}: {fmt.format(lo)}{sufixo}→{fmt.format(hi)}{sufixo}")
        else:
            partes.append(f"{simbolo}={fmt.format(lo)}{sufixo}")
    partes.append(f"{n} case(s)")
    return ", ".join(partes)


# =============================================================================
# State shared between tabs
# =============================================================================

class AppState(QObject):
    project_changed = pyqtSignal()
    geometry_changed = pyqtSignal()
    airfoil_changed = pyqtSignal()
    config_changed = pyqtSignal()
    results_changed = pyqtSignal()
    history_changed = pyqtSignal()   # docs/plano_v3.md Part 4.1 -- Results hub
    mode_changed = pyqtSignal()   # rotor <-> propeller (docs/plano.md Section 2)

    def __init__(self):
        super().__init__()
        self.project: Project | None = None
        self.last_results = None          # Results | list[Results] | None
        self.last_maps: dict | None = None
        # --- results history for this session (Part 4.1) ------------------
        # Unlike `last_results` above (overwritten by EVERY Run Case/Run
        # Batch, used only by each tab's local "Export" button),
        # `results_history` is a list that only GROWS (append), consumed by
        # `ResultsTab` (multi-selection history). "For this session": cleared
        # in `set_project` (switch/close project) -- see docs/plano_v3.md
        # Section 4.4, computed results are expensive and are not
        # "pre-definition" data.
        self.results_history: list = []   # list[models.ResultEntry]
        self._history_counter = 0
        # Q7: "Apply to project" only writes to memory; nothing auto-saves.
        # Without this flag, closing the window would silently discard
        # work. Set by the `notify_*` methods (called by a tab when it
        # applies) and cleared by `mark_saved`/`set_project`.
        self.unsaved = False

    def set_project(self, project: Project):
        self.project = project
        self.unsaved = False
        self.clear_history()
        self.project_changed.emit()
        self.geometry_changed.emit()
        self.airfoil_changed.emit()
        self.config_changed.emit()
        self.mode_changed.emit()

    def add_history_entry(self, kind: str, label: str, results) -> "ResultEntry":
        """Records a new run (Run Case or Run Batch) in the session
        history -- NEVER replaces an existing entry (docs/plano_v3.md
        Part 4.1). ``kind``: "case" (``results`` is a single ``Results``)
        or "batch" (``results`` is ``list[Results]``)."""
        import time
        self._history_counter += 1
        entry = ResultEntry(
            id=f"r{self._history_counter}", label=label, kind=kind,
            results=results, timestamp=time.strftime("%H:%M:%S"),
        )
        self.results_history.append(entry)
        self.history_changed.emit()
        return entry

    def clear_history(self):
        self.results_history = []
        self._history_counter = 0
        self.history_changed.emit()

    def remove_history_entry(self, entry_id: str) -> bool:
        """Removes ONE entry from the history (unlike `clear_history`,
        which clears everything) -- returns True if something was
        removed. `entry_id` is the `ResultEntry.id` (e.g. `"r3"`), the
        same value stored in `Qt.ItemDataRole.UserRole` of the list item
        in `ResultsTab`."""
        antes = len(self.results_history)
        self.results_history = [e for e in self.results_history if e.id != entry_id]
        removeu = len(self.results_history) < antes
        if removeu:
            self.history_changed.emit()
        return removeu

    def is_propeller(self) -> bool:
        if self.project is None:
            return False
        return bool(self.project.config.get("is_propeller", False))

    def notify_geometry(self):
        self.unsaved = True
        self.geometry_changed.emit()

    def notify_airfoil(self):
        self.unsaved = True
        self.airfoil_changed.emit()

    def notify_config(self):
        self.unsaved = True
        self.config_changed.emit()

    def notify_results(self):
        self.results_changed.emit()

    def notify_mode(self):
        self.unsaved = True
        self.mode_changed.emit()

    def mark_saved(self):
        """Called after `api.save_project`: what is in memory is now
        on disk."""
        self.unsaved = False


def definir_linha_visivel(form, widget, visivel: bool) -> None:
    """Hides/shows the entire ROW of a ``QFormLayout`` -- label included.

    Two pitfalls this function exists to avoid:

    1. ``widget.setVisible(False)`` hides only the field: the label
       stays on screen, pointing at nothing.
    2. ``form.setRowVisible(widget, ...)`` looks up the row by the FIELD
       widget. If the field was wrapped (which is what `ajuda_de_campo`
       does to fit the "?" next to it), the original widget is no
       longer the row's field, and Qt finds nothing -- failing
       silently.
    """
    alvo = getattr(widget, "_container_de_ajuda", None) or widget
    try:
        form.setRowVisible(alvo, visivel)
    except RuntimeError:
        # widget outside this form: fall back to the simple behavior
        alvo.setVisible(visivel)


# =============================================================================
# Width of form fields
# =============================================================================
#
# A `QFormLayout` stretches the field to the end of the row. In a 1400px
# window that gave a ~1370px box to type "72" into -- and, worse, the SAME
# quantity appeared with different widths in each tab, depending on which
# panel it landed in. It is not a matter of taste: a field that wide
# separates the label from the value by half the screen, and the eye loses
# the row.
#
# The rule is by content TYPE, not by tab, so the same kind of data always
# has the same box throughout the GUI:
#
#   number          short, fixed box -- a number has a known size
#   enumeration     width of the longest option (+ arrow clearance), capped
#   free text       grows (folder path, list of values, name)
#
LARGURA_DE_NUMERO = 150      # px: fits "-1234.567890" with room to spare
LARGURA_MIN_DE_ENUM = 180    # px: a combo never gets narrow enough to
                             #     elide the selected option
LARGURA_MAX_DE_ENUM = 340    # px: cap, so it does not go back to the
                             #     stretched-field problem

# Condition fields (Run Case/Run Batch) use the same geometry, including
# when the value sits inside a composite widget (mu_x/J_x or alpha/Vz).
LARGURA_UNIDADE_DE_CONDICAO = 110
LARGURA_VALOR_DE_CONDICAO = LARGURA_DE_NUMERO
ESPACO_DE_CONDICAO = 6

#: Texts of the unit-label combos (`widgets.LongitudinalInput` and
#: `widgets.AxialInput`). Listed here, rather than read from the widgets,
#: because the width has to be the SAME in both tabs and both field
#: families: measured per combo, the x-field row (mu_x/J_x/Vx [m/s]) would
#: end up narrower than the z-field row (alpha_rotor [deg]/Vz [m/s]) and
#: the number in each row would start at a different x -- the misalignment
#: this module exists to prevent.
#: Derived from `widgets.UNIDADES_DE_CONDICAO` (every mode, every slot):
#: the width has to fit the longest label of ANY mode, otherwise switching
#: to propeller would cut off "alpha_disk [deg]" -- and a hand-copied list
#: would silently go stale the moment a new unit was added.
def _todos_os_rotulos_de_unidade() -> tuple:
    from .widgets import UNIDADES_DE_CONDICAO
    return tuple(sorted({rotulo
                          for pares in UNIDADES_DE_CONDICAO.values()
                          for rotulo, _var in pares}))

#: Slack for the text inside a QComboBox: arrow (22px, see styles.py),
#: side padding (6+6) and border (1+1).
_FOLGA_DE_COMBO = 38


def largura_de_unidade_de_condicao(combos=()) -> int:
    """Width of the unit-label combos, MEASURED instead of fixed.

    "alpha [deg]" used to come out clipped ("alpha [deg") at the old
    fixed 110px -- and the clipping point changes with the font, the
    theme and the monitor scale, so the right number is not a
    constant, it is a measurement.
    `LARGURA_UNIDADE_DE_CONDICAO` becomes the FLOOR (no row shrinks
    below what already looked good).

    ``combos``: the actual unit `QComboBox` widgets, when they exist.
    Their `sizeHint` is the only measurement that includes EVERYTHING
    -- the widget's real font (not the app's), the stylesheet's
    padding and the dropdown arrow --, but it is only valid AFTER the
    QSS polish, which happens on first display. That is why the caller
    passes the combos from inside a `showEvent`
    (see `RunCaseTab`/`RunBatchTab._ajustar_largura_de_unidade`), and
    the font-metric calculation below serves as the floor for
    construction time, when there is no reliable `sizeHint` yet.

    Without a `QApplication` (import in a pure logic test), returns the
    floor instead of blowing up."""
    from PyQt6.QtGui import QFontMetrics
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return LARGURA_UNIDADE_DE_CONDICAO
    fm = QFontMetrics(app.font())
    preciso = max(fm.horizontalAdvance(t) for t in _todos_os_rotulos_de_unidade())
    largura = max(LARGURA_UNIDADE_DE_CONDICAO, preciso + _FOLGA_DE_COMBO)
    for combo in combos:
        # A QComboBox's `sizeHint` already embeds the longest option;
        # `minimumSizeHint` covers the case of a combo with an imposed
        # maximum width (none of these have one, but it costs nothing
        # and prevents a regression).
        largura = max(largura, combo.sizeHint().width(),
                      combo.minimumSizeHint().width())
    return largura


#: Engine field each input slot is bound to. `field_help` identifies the row
#: by the quoted token that opens the tooltip, so this has to be the ENGINE's
#: name (disk axes) and not the one displayed, which rotates with the mode.
_CAMPO_DO_SLOT = {"inplane": "mu_x", "axial": "Vz"}


def resolver_par_de_condicao(advance, axial, rpm: float, radius_m: float) -> tuple:
    """``(mu_x, Vz)`` for the pair of condition fields, in the ORDER the
    chosen unit requires.

    Normally the in-plane component is the known one and the axial one
    can be derived from it (the disk angle). With `alpha_disk` -- the
    angle measured from the SHAFT, which is what a propeller uses --
    the dependency reverses: the axial one is the known one and the
    in-plane one comes from it. Always resolving in the old order would
    give `mu_x` from a `Vz` that has not been read yet, i.e. zero.

    Same inversion as `bemt.resolve_advance_velocity` and
    `studies.build_factorial_conditions`; it exists here because Run
    Case and the standalone Run Batch row build the condition without
    going through either of the two."""
    if getattr(advance, "is_alpha_disk", lambda: False)():
        Vz = axial.vv(0.0, rpm, radius_m)
        return advance.mu_x(Vz), Vz
    mu_x = advance.mu_x()
    return mu_x, axial.vv(mu_x, rpm, radius_m)


def aplicar_par_de_condicao(advance, axial, mu_x: float, Vz: float,
                             rpm: float, radius_m: float) -> None:
    """Writes ``(mu_x, Vz)`` into the two fields -- the inverse of
    `resolver_par_de_condicao`, used when loading a saved case.

    The axial one goes first: with `alpha_disk` in the in-plane field,
    it is the already-written `Vz` that gives the angle its meaning."""
    axial.set_vv(Vz, mu_x, rpm, radius_m)
    if getattr(advance, "is_alpha_disk", lambda: False)():
        advance.set_mu(mu_x, Vz)
    else:
        advance.set_mu(mu_x)


def rotulo_e_dica_de_condicao(is_propeller: bool, slot: str) -> tuple:
    """``(row label, tooltip)`` for field ``slot``
    (``"inplane"``/``"axial"``) in the current mode's convention.

    The text itself lives in `nomenclature.slot_label`, which owns every
    axis name the user meets. All this adds is the quoted engine key that
    opens the tooltip: `field_help` reads it to find which field the row
    belongs to, and without it the row loses its help popup.
    """
    rotulo, dica = nomenclature.slot_label(slot, is_propeller)
    # QToolTip renders plain text as running text, so the paragraph breaks
    # have to be HTML for them to survive the hover.
    dica = dica.replace("\n\n", "<br><br>").replace("\n", "<br>")
    return rotulo, f'"{_CAMPO_DO_SLOT[slot]}" — {dica}'


def definir_rotulo_de_linha(form, widget, texto: str) -> bool:
    """Changes the TEXT of the row label of ``widget`` in a
    ``QFormLayout``.

    Same pitfall as `definir_linha_visivel`: the field may be wrapped
    by the "?" help container, and the row label may already have
    become a clickable `QToolButton` (`field_help`). Both cases are
    handled here, instead of keeping a reference to the original
    `QLabel` -- which would stop being the row's label as soon as the
    help was installed."""
    from PyQt6.QtWidgets import QFormLayout

    alvo = getattr(widget, "_container_de_ajuda", None) or widget
    linha, _papel = form.getWidgetPosition(alvo)
    if linha < 0:
        return False
    item = form.itemAt(linha, QFormLayout.ItemRole.LabelRole)
    rotulo = item.widget() if item is not None else None
    if rotulo is None or not hasattr(rotulo, "setText"):
        return False
    rotulo.setText(texto)
    return True


def aplicar_largura_de_unidade_de_condicao(raiz) -> int:
    """Measures and applies the common width of the unit-label combos
    under ``raiz`` (a tab), adjusting the simple fields' indent along
    with it.

    Called from the tab's ``showEvent``, not from construction: it is
    only after the stylesheet's polish that a combo's `sizeHint`
    reflects the real font, padding and arrow -- calculated earlier,
    the width came out short and "alpha [deg]" got clipped precisely
    on screens whose font/scale differs from the developer's.

    The simple fields (Collective/RPM) are indented up to the number
    column by a container marked with ``_recuo_de_unidade`` (see
    ``_com_recuo_de_unidade`` in both tabs); their indent moves along
    with it, otherwise the values column would split in two.

    Returns the applied width."""
    from PyQt6.QtWidgets import QWidget
    from .widgets import LongitudinalInput, AxialInput

    from PyQt6.QtWidgets import QComboBox

    campos = raiz.findChildren((LongitudinalInput, AxialInput))
    combos = [c.unit_combo for c in campos if getattr(c, "unit_combo", None) is not None]
    # STANDALONE unit combos (the factorial's axis rows), marked at
    # construction: they get included in the same measurement,
    # otherwise the "values:" column would land at a different x per
    # row -- "mu_x" and "alpha [deg]" have quite different natural
    # widths.
    combos += [c for c in raiz.findChildren(QComboBox)
               if getattr(c, "_combo_de_unidade", False)]
    largura = largura_de_unidade_de_condicao(combos)
    for combo in combos:
        combo.setFixedWidth(largura)
    for container in raiz.findChildren(QWidget):
        if getattr(container, "_recuo_de_unidade", False):
            layout = container.layout()
            if layout is not None:
                layout.setContentsMargins(largura + ESPACO_DE_CONDICAO, 0, 0, 0)
        elif getattr(container, "_reserva_de_unidade", False):
            # Reserves the column even with the combo hidden (axis
            # "(none)"): a hidden widget takes up no width, and the
            # whole row would slide to the left.
            container.setFixedWidth(largura)
    return largura


#: Clearance for the label inside a `QPushButton` (frame + theme padding).
FOLGA_DE_BOTAO = 26


def uniformizar_largura_de_botoes(botoes, rotulos_extras=()) -> int:
    """Gives the SAME width to a group of buttons that read together,
    and returns the applied width.

    Two pitfalls, learned on screen and both invisible without the
    theme applied:

    1. `setFixedWidth` does NOT hold a button's width here. The
       stylesheet declares ``QPushButton { max-width: 520px }``, and a
       QSS width rule overrides the maximum fixed in code -- each
       button would grow back to its own `sizeHint`. That is why what
       gets fixed is the common MINIMUM: each one's `sizeHint` stays
       below it, and the group settles at the same width.
    2. `sizeHint` only includes the theme's padding AFTER the QSS
       polish, which happens on first display -- hence this function
       being called from the tab's `showEvent`, not from construction.

    ``rotulos_extras``: texts the button will still display (the
    generate-cases one alternates between two), so it does not change
    size on the switch.

    Each button gets marked with ``_largura_de_grupo``: the sweep in
    `tests/test_gui_layout.py` forbids a button much wider than its
    own text -- a sign of a missing `addStretch` -- and a short button
    in a group is exactly that, on purpose."""
    botoes = [b for b in botoes if b is not None]
    if not botoes:
        return 0
    metrica = botoes[0].fontMetrics()
    rotulos = [b.text() for b in botoes] + list(rotulos_extras)
    largura = max(
        max(metrica.horizontalAdvance(t) for t in rotulos) + FOLGA_DE_BOTAO,
        max(b.sizeHint().width() for b in botoes),
    )
    for botao in botoes:
        botao.setMinimumWidth(largura)
        botao._largura_de_grupo = largura
    return largura


def garantir_botoes_legiveis(raiz) -> int:
    """Prevents a `QPushButton` from ending up narrower than its own
    text.

    Returns how many buttons were widened.

    In a tight `QHBoxLayout` (or inside a `QDialogButtonBox`, which
    distributes width between the buttons) Qt shrinks the button below
    what is needed and ELIDES the label: "Generate cases → replace
    queue" turned into "Generate cases → replace q…", and "Restore
    from disk"/"Validate configuration"/"Generate report…" showed up
    clipped the same way. The tooltip stayed correct, but nobody reads
    the tooltip of a button that appears to already be spelled out in
    full.

    The floor comes from the button's own FONT METRICS, not a fixed
    number: this way it keeps working if the text, the font or the
    language changes (no pixel assertions -- see CLAUDE.md rule 3).

    Called once per tab, from outside, like
    `compactar_campos_de_formulario` and
    `field_help.instalar_popups_de_campo` -- it is window policy, and
    a new tab obeys it without having to remember anything.
    """
    from PyQt6.QtWidgets import QPushButton

    #: Clearance for the frame, the theme's padding and (when present)
    #: the icon.
    FOLGA = 26
    ajustados = 0
    for botao in raiz.findChildren(QPushButton):
        texto = botao.text().replace("&", "")
        if not texto:
            continue
        preciso = botao.fontMetrics().horizontalAdvance(texto) + FOLGA
        if botao.icon() is not None and not botao.icon().isNull():
            preciso += botao.iconSize().width() + 6
        if botao.minimumWidth() < preciso:
            botao.setMinimumWidth(preciso)
            ajustados += 1
    return ajustados


#: Minimum vertical spacing between rows of a `QFormLayout`.
#: The style's default (6px) is too tight when the row is a lone
#: QCheckBox followed by a field: the two stick together and read as
#: one thing (seen in "Enable dynamic stall" + "Lag constant A", in
#: the three rows of "3D rotational effects" and in "Adaptive
#: relaxation" right above its parameter box).
ESPACAMENTO_MINIMO_DE_LINHA = 10

#: Minimum horizontal spacing between NEIGHBORING checkboxes on the
#: same row. A `QCheckBox` draws its indicator and label flush against
#: its own border, so two of them side by side with the style's
#: default spacing (~6px) read as one thing: "Coefficients" touched
#: the square of "Azimuthal loads", and the eye could not tell which
#: box each word belonged to. The value is larger than the ordinary
#: layout spacing on purpose -- it is the distance that separates
#: independent CONTROLS, not parts of the same field.
ESPACAMENTO_MINIMO_ENTRE_CAIXAS = 18


def arejar_formularios(raiz, minimo: int = ESPACAMENTO_MINIMO_DE_LINHA,
                        minimo_entre_caixas: int = ESPACAMENTO_MINIMO_ENTRE_CAIXAS) -> int:
    """Gives breathing room to the layout under ``raiz``, in two
    directions, and returns how many layouts changed.

    * VERTICAL: minimum spacing between the rows of every
      ``QFormLayout`` -- a row occupied only by a `QCheckBox` is
      shorter than a field row, and the two would stick together.
    * HORIZONTAL: minimum spacing between neighboring checkboxes on
      the same ``QHBoxLayout`` (see `ESPACAMENTO_MINIMO_ENTRE_CAIXAS`).

    WINDOW policy, applied from outside alongside
    `compactar_campos_de_formulario` and `garantir_botoes_legiveis` --
    for the same reason: this way a new tab is born obeying it,
    without having to remember anything. Only INCREASES: a layout that
    already explicitly asked for more space keeps what it asked for."""
    from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QCheckBox, QRadioButton

    ajustados = 0
    for form in raiz.findChildren(QFormLayout):
        if form.verticalSpacing() < minimo:
            form.setVerticalSpacing(minimo)
            ajustados += 1
    for linha in raiz.findChildren(QHBoxLayout):
        caixas = sum(1 for i in range(linha.count())
                     if isinstance(linha.itemAt(i).widget(), (QCheckBox, QRadioButton)))
        if caixas >= 2 and linha.spacing() < minimo_entre_caixas:
            linha.setSpacing(minimo_entre_caixas)
            ajustados += 1
    return ajustados


def alinhar_rotulos_de_formulario(raiz) -> int:
    """Left-aligns the label of every ``QFormLayout`` under ``raiz``
    and returns how many layouts changed.

    The style's default on Windows is `AlignRight`: labels get
    right-justified, flush against the field, and the START of each
    row's word falls in a different column ("Type:" starts far to the
    right of "Number of blades:"). The eye looks for the start of a
    word, not the end, so the label column reads as a jagged margin
    and is more expensive to scan top to bottom -- this is what the
    user saw in the "Generate radial table" dialog.

    `AlignVCenter` comes along because the vertical default aligns the
    label with the top of the field, and a tall row (combo, spin box
    with arrows) would leave the text floating above the center of the
    field it belongs to.

    WINDOW policy like `arejar_formularios` and
    `compactar_campos_de_formulario`, applied from outside for the
    same reason: a new tab is born obeying it without having to
    remember anything."""
    from PyQt6.QtWidgets import QFormLayout

    alvo = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    ajustados = 0
    for form in raiz.findChildren(QFormLayout):
        if form.labelAlignment() != alvo:
            form.setLabelAlignment(alvo)
            ajustados += 1
    return ajustados


def compactar_campos_de_formulario(raiz) -> int:
    """Gives a readable width to numeric and enumeration fields under
    ``raiz``. Returns how many widgets were adjusted.

    Called ONCE per tab, from outside (``app.MainWindow``), for the
    same reason as ``field_help.instalar_popups_de_campo``: it is
    visual policy for the whole window, not a per-tab decision -- and
    a new tab starts obeying it without having to remember anything.

    Deliberately does NOT touch ``QLineEdit``/``QPlainTextEdit``:
    there the content is free text of unpredictable size (``outputs/``
    folder path, list ``0, 0.1, 0.2``, project name) and shortening
    the box would hide the beginning or the end of what the user
    typed.

    Idempotent: a widget already adjusted is not readjusted (the
    second calculation would see the already-limited ``sizeHint`` and
    shrink the field on every call).
    """
    from PyQt6.QtWidgets import QAbstractSpinBox, QComboBox

    ajustados = 0
    for w in raiz.findChildren(QAbstractSpinBox):
        if getattr(w, "_largura_compactada", False):
            continue
        w.setMaximumWidth(LARGURA_DE_NUMERO)
        w._largura_compactada = True
        ajustados += 1
    for w in raiz.findChildren(QComboBox):
        if getattr(w, "_largura_compactada", False):
            continue
        # `sizeHint` already embeds the longest option; the clearance
        # covers the dropdown arrow (styles.py) and the side padding.
        largura = min(max(w.sizeHint().width() + 24, LARGURA_MIN_DE_ENUM),
                      LARGURA_MAX_DE_ENUM)
        # The cap NEVER overrides the minimum the combo itself asks
        # for: `dialogs.ajustar_largura_de_combo` already fixes a
        # `minimumWidth` equal to the longest item, precisely so the
        # popup does not come out elided with "…". A cap smaller than
        # that would shrink nothing (Qt honors the minimum) and would
        # only create a misleading constraint -- and there is a real
        # option wider than `LARGURA_MAX_DE_ENUM` ("Full range (-180°
        # to 180°)", 354px).
        largura = max(largura, w.minimumWidth(), w.minimumSizeHint().width())
        w.setMaximumWidth(largura)
        w._largura_compactada = True
        ajustados += 1
    return ajustados


#: alignments used in numeric tables (text left, number right -- so a
#: column's decimal places line up under one another)
ALINHAMENTO_DE_TEXTO = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
ALINHAMENTO_DE_NUMERO = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def alinhar_cabecalhos_com_conteudo(tabela, colunas_numericas) -> None:
    """Aligns each header like the column it sits above.

    Qt's default centers every header; over a column of text flush
    left (or numbers flush right) this leaves the label offset from
    what it names.
    """
    for coluna in range(tabela.columnCount()):
        item = tabela.horizontalHeaderItem(coluna)
        if item is None:
            continue
        item.setTextAlignment(ALINHAMENTO_DE_NUMERO if coluna in colunas_numericas
                              else ALINHAMENTO_DE_TEXTO)


def show_error(parent, title: str, exc: Exception):
    QMessageBox.critical(parent, title, f"{exc}\n\n{traceback.format_exc(limit=3)}")


# =============================================================================
# Help (docs/documentation.html) -- single source of physics + GUI +
# shortcuts documentation. The "?" button (FlowIndicatorBar) and the F1
# shortcut (MainWindow) call this same function: it opens the HTML in the
# system's default browser via QDesktopServices, without embedding any
# HTML engine inside the GUI itself.
# =============================================================================

def open_help(parent=None, anchor: str | None = None):
    """Opens the documentation in the default browser.

    ``anchor``: section id (e.g. ``"cap-3-2-1"``). With it, the browser
    jumps straight to the field -- this is what makes the "?" next to
    each field worth more than the global "?"."""
    help_path = paths.documentation_path()
    if help_path is None:
        QMessageBox.warning(
            parent, "Help not found",
            "File docs/documentation.html not found within the package or in the repository.")
        return
    url = QUrl.fromLocalFile(str(help_path))
    if anchor:
        url.setFragment(anchor)
    QDesktopServices.openUrl(url)


class _TituloDeBlocoClicavel(QObject):
    """Makes the TITLE of a QGroupBox clickable (opens the block's
    popup).

    Replaces the old floating "?" button: no "?" exists in the window
    anymore. The groupbox neither gains nor loses any widget -- just
    an event filter --, so the internal layout and widget order that
    ``tools/field_index.py`` depends on stay identical.
    """

    def __init__(self, groupbox, block_id: str):
        super().__init__(groupbox)
        self._gb = groupbox
        self._bloco = block_id
        groupbox.installEventFilter(self)

    def retangulo_do_titulo(self):
        """Area occupied by the title text, in the groupbox's
        coordinates."""
        from PyQt6.QtWidgets import QStyle, QStyleOptionGroupBox
        opcao = QStyleOptionGroupBox()
        self._gb.initStyleOption(opcao)
        return self._gb.style().subControlRect(
            QStyle.ComplexControl.CC_GroupBox, opcao,
            QStyle.SubControl.SC_GroupBoxLabel, self._gb)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.MouseButtonPress:
            try:
                ponto = event.position().toPoint()
            except AttributeError:                      # pragma: no cover
                return False
            if self.retangulo_do_titulo().contains(ponto):
                from .help_popup import HelpPopup
                HelpPopup.instancia(self._gb.window()).mostrar_bloco(
                    self._bloco, self._gb)
                # A "checkable" groupbox uses the title to toggle: do
                # not swallow the click in that case, just add the
                # help.
                return not self._gb.isCheckable()
        return False


def tornar_titulo_de_bloco_clicavel(groupbox, block_id: str) -> bool:
    """The QGroupBox title opens the block's conceptual explanation.

    Returns ``True`` if it was installed. Idempotent.
    """
    from . import help_blocks

    if block_id not in help_blocks.BLOCK_HELP:
        return False
    if groupbox.layout() is None:
        return False
    if getattr(groupbox, "_ajuda_de_bloco", None) is not None:
        return False

    groupbox.setStyleSheet(
        (groupbox.styleSheet() or "")
        + "\nQGroupBox::title { color: #3a6dbd; }"
    )
    groupbox.setToolTip(
        "Click the section title for an overview and the full physics "
        "documentation of this block.")
    groupbox._ajuda_de_bloco = _TituloDeBlocoClicavel(groupbox, block_id)
    return True


# Historical name: the call stays the same, it is the "?" that stopped
# existing.
add_block_help_button = tornar_titulo_de_bloco_clicavel


class MplCanvas(FigureCanvasQTAgg):
    """Single-axis canvas (most of the simple plots)."""
    def __init__(self, figsize=(5, 3.5)):
        self.fig = Figure(figsize=figsize, tight_layout=True)
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)

    def clear(self):
        for extra in list(self.fig.axes):
            if extra is not self.ax:
                self.fig.delaxes(extra)
        self.ax.clear()


class CanvasHost(QWidget):
    """Drawing area that swaps its content dynamically: sometimes a
    single-axis ``MplCanvas`` (which is only cleared/redrawn),
    sometimes an entire multi-panel ``Figure`` returned by a grid
    function of ``plots.py`` (plot_disk_map_grid, plot_coefficients_vs_mu,
    plot_blade_loads_vs_span, plot_loads_vs_azimuth) -- used by the
    Results tab (docs/plano.md Section 8; docs/plano_v3.md Part 4),
    which is the only tab with drawing on screen.
    """
    def __init__(self, with_toolbar: bool = False):
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._current: FigureCanvasQTAgg | None = None
        self._with_toolbar = with_toolbar
        self._toolbar: NavigationToolbar2QT | None = None
        self.simple = MplCanvas(figsize=(6, 5))
        self._show(self.simple)

    def _show(self, canvas: FigureCanvasQTAgg):
        if self._current is not None:
            self._layout.removeWidget(self._current)
            self._current.setParent(None)
        # NavigationToolbar2QT gives zoom (rectangle/wheel), pan, view
        # "back/forward", and the "Edit axis, curve and image
        # parameters" button (axes+curve icon), which opens a dialog
        # to edit min/max and scale (linear/log) of each axis -- this
        # is what covers "zoom in" and "change axis scale" on the
        # plots (Airfoil and Results, docs/plano_v3.md Part 7/8),
        # without reinventing the UI. Since `show_figure` swaps the
        # canvas instance on every new figure (multi-panel grids), the
        # toolbar is rebuilt here, bound to the CURRENTLY shown canvas
        # -- an old toolbar pointing at an already-removed canvas does
        # not work.
        if self._with_toolbar:
            if self._toolbar is not None:
                self._layout.removeWidget(self._toolbar)
                self._toolbar.setParent(None)
                self._toolbar.deleteLater()
            self._toolbar = NavigationToolbar2QT(canvas, self)
            self._toolbar.setIconSize(QSize(15, 15))
            self._layout.addWidget(self._toolbar)
        self._layout.addWidget(canvas)
        self._current = canvas

    def use_simple(self) -> MplCanvas:
        """Returns the single-axis canvas, already visible, ready for
        ``clear()`` + drawing on ``.ax`` + ``.draw()``."""
        self._show(self.simple)
        return self.simple

    def show_figure(self, fig: Figure):
        """Replaces the content with an entire multi-panel figure that
        is already built (returned by a ``plots.plot_*_grid``/
        ``plot_*`` function called with ``fname=None``)."""
        canvas = FigureCanvasQTAgg(fig)
        self._show(canvas)
        canvas.draw()

    def show_message(self, text: str):
        c = self.use_simple()
        c.clear()
        # No axes in the empty state: the default 0-1 frame with ticks
        # announces a pair of quantities that does not exist and makes
        # the message look like data plotted in the middle of a real
        # chart.
        c.ax.set_axis_off()
        c.ax.text(0.5, 0.5, text, ha="center", va="center", transform=c.ax.transAxes, wrap=True)
        c.draw()


class PlotlyCanvasHost(QWidget):
    """Hosts a Plotly figure inside the Qt GUI via an embedded Chromium view.

    Mirrors CanvasHost's contract (set_figure/show_message) but renders
    interactive Plotly charts instead of static matplotlib. Requires the
    optional `interactive` dependency group (PyQt6-WebEngine + plotly).

    Known limitation: QWebEngineView hard-crashes (native crash, no
    exception) under QT_QPA_PLATFORM=offscreen — Chromium's compositor has
    no offscreen-compatible software path there. Works fine under a real
    display. Tests that instantiate this class must skip under offscreen.
    """
    def __init__(self):
        super().__init__()
        if not HAS_INTERACTIVE_PLOTS:
            raise RuntimeError(
                "Interactive plots need the 'interactive' optional dependency group "
                "(pip install \"zbemt[interactive]\"): PyQt6-WebEngine + plotly.")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._view = QWebEngineView()
        self._layout.addWidget(self._view)
        import tempfile
        self._tmp_dir = tempfile.mkdtemp(prefix="zbemt_plotly_")
        self._tmp_html = Path(self._tmp_dir) / "figure.html"
        #: plotly.js written ONCE next to the HTML -- see `set_figure`
        self._tmp_plotly_js = Path(self._tmp_dir) / "plotly.min.js"

    def _garantir_plotlyjs(self) -> None:
        """Writes plotly.js next to the figure, once per session.

        `include_plotlyjs="directory"` only WRITES that file from
        `write_html`; `to_html` assumes it is already there."""
        if self._tmp_plotly_js.exists():
            return
        from plotly.offline import get_plotlyjs
        self._tmp_plotly_js.write_text(get_plotlyjs(), encoding="utf-8")

    def set_figure(self, fig):
        """Renders a plotly.graph_objects.Figure. Named set_figure (not
        `show`) because QWidget already defines `.show()` and a method
        override there would silently shadow it.

        plotly.js is LINKED, not inlined. With `include_plotlyjs=True`
        every redraw wrote a ~5.5 MB page — 3.5 MB of it the library —
        and Chromium re-parsed and re-executed the whole bundle on each
        load: changing the field of the 3D view froze the window for
        seconds. Written once beside the figure, the page drops to
        ~0.6 MB and the browser serves the library from its own cache.
        `validate=False` skips re-validating arrays that were just built
        here (another traversal of a 90x145 grid, for figures this code
        assembles itself)."""
        self._garantir_plotlyjs()
        html = fig.to_html(include_plotlyjs="directory", full_html=True,
                            validate=False, config={"displaylogo": False})
        self._tmp_html.write_text(html, encoding="utf-8")
        self._view.load(QUrl.fromLocalFile(str(self._tmp_html)))

    def show_message(self, text: str):
        html = f'<div style="display:flex;align-items:center;justify-content:center;height:100%;font-family:sans-serif;color:#666;">{text}</div>'
        self._tmp_html.write_text(html, encoding="utf-8")
        self._view.load(QUrl.fromLocalFile(str(self._tmp_html)))

    def closeEvent(self, event):
        import shutil
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
        super().closeEvent(event)


#: OPTIONAL packages: feature -> (module to import, install command,
#: what stops working without it). Single source for the
#: `require_optional_package` dialog -- a new optional feature goes
#: here, not into a stray message inside a tab.
PACOTES_OPCIONAIS = {
    "neuralfoil": ("neuralfoil", "pip install neuralfoil",
                    "generating airfoil polars with NeuralFoil"),
    "pyvista": ("pyvista", "pip install pyvista",
                 "the interactive 3D rotor view"),
    "interactive": ("PyQt6.QtWebEngineWidgets", 'pip install "zbemt[interactive]"',
                     "interactive (Plotly) charts"),
}


def require_optional_package(widget: QWidget, recurso: str) -> bool:
    """True if the optional package for ``recurso`` is installed;
    otherwise opens a dialog with the INSTALL COMMAND and returns
    False.

    Before, each optional feature just disabled its own button and
    hid the reason in a tooltip -- anyone who did not hover exactly
    there saw only a dead button, with nothing saying a package was
    missing or which one. Now the button stays clickable and the click
    explains what to install, with the command ready to copy."""
    modulo, comando, descricao = PACOTES_OPCIONAIS[recurso]
    try:
        importlib.import_module(modulo)
        return True
    except ImportError:
        pass
    QMessageBox.information(
        widget, "Optional package not installed",
        f"This feature needs the optional package '{recurso}', which is not installed, "
        f"so {descricao} is unavailable.\n\nInstall it with:\n\n    {comando}\n\n"
        "Then restart zBEMT.")
    return False


def require_project(widget: QWidget, state: AppState) -> bool:
    if state.project is None:
        QMessageBox.warning(widget, "No project", "Create or open a project first.")
        return False
    return True


def save_project_from_tab(widget: QWidget, state: AppState) -> None:
    """"Save project" identical to `ProjectTab._save_project` -- exposed
    here so that Geometry/Airfoil/Config (where edits now write
    directly to `state.project`, with no "Apply" button) can also
    write to disk without forcing the user to switch tabs first."""
    if not require_project(widget, state):
        return
    try:
        api.save_project(state.project)
        state.mark_saved()
        QMessageBox.information(widget, "Saved", f"Project saved at {state.project.path}")
    except Exception as exc:
        show_error(widget, "Error saving project", exc)


def restore_project_from_disk(widget: QWidget, state: AppState) -> None:
    """Discards the edits in memory and reloads `state.project` from
    disk (`api.open_project` -- a full re-read, not a partial "undo").
    Confirms first if there is something unsaved (`state.unsaved`);
    without this, a click would silently lose work -- same spirit as
    the close-window warning (Q7, `app.py.trabalho_nao_salvo`)."""
    if not require_project(widget, state):
        return
    if state.unsaved:
        resposta = QMessageBox.question(
            widget, "Discard unsaved changes?",
            "There are changes applied to the project but not saved to disk. "
            "Restoring reloads the project as it is on disk, discarding them.\n\n"
            "Discard and restore?")
        if resposta != QMessageBox.StandardButton.Yes:
            return
    try:
        project = api.open_project(state.project.path)
        state.set_project(project)
    except Exception as exc:
        show_error(widget, "Error restoring project", exc)


def confirm_run_despite_issues(widget: QWidget, state: AppState) -> bool:
    """validate_project + decides whether the run can proceed: blocks
    outright on 'error', asks for confirmation on 'warning'/'info'
    (Run Case/Run Batch never call the engine silently over a
    combination already known to be inconsistent)."""
    issues = api.validate_project(state.project)
    errors = [i for i in issues if i.level == "error"]
    if errors:
        QMessageBox.critical(widget, "Invalid configuration",
                              "Cannot run with the following errors:\n\n"
                              + "\n".join(str(i) for i in errors))
        return False
    others = [i for i in issues if i.level != "error"]
    if others:
        reply = QMessageBox.question(
            widget, "Configuration warnings",
            "There are warnings in the current configuration:\n\n" + "\n".join(str(i) for i in others)
            + "\n\nRun anyway?")
        return reply == QMessageBox.StandardButton.Yes
    return True


