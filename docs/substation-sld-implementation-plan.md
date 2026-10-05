# Substation Location and Single-Line Diagram Implementation Plan

## 1. Goal

Add two related but independent capabilities:

1. Store the physical facility location of a `Substation` using `infrasys.Location`.
2. Generate a clean engineering single-line diagram (SLD) from `SubstationSystem` without mutating the electrical model or reusing geographic coordinates as schematic positions.

The implementation must preserve the existing substation topology model, remain serializable through the existing `infrasys` mechanisms, and support deterministic SVG output suitable for browser display and later PDF export.

## 2. Design Decisions

### 2.1 Separate geographic and schematic coordinates

- `Substation.location: Location | None` represents the facility's physical location.
- Geographic coordinates remain on `DistributionBus.coordinate`.
- `BusbarSection` (a `DistributionBus` subclass) stores an explicit schematic
  `schematic_coordinate` in addition to the geographic coordinate. The two are
  never conflated: `coordinate` is geographic, `schematic_coordinate` is the SLD
  position and may be `None` when a layout engine must compute one.
- SLD layout must be deterministic from topology and stable component ordering,
  falling back to computed positions when `schematic_coordinate` is absent.

### 2.2 Do not mutate the source model

SLD generation reads `SubstationSystem` and creates a view model. It must not replace components, alter switch states, add layout fields to components, or reduce the source topology in place.

### 2.3 Preserve topology semantics

The SLD view must retain:

- busbar-section nodes and the equipment that connects them;
- bay and voltage-level membership;
- equipment types and identities;
- breaker, disconnector, and earthing-switch states;
- transformer winding order;
- incoming and outgoing circuit direction;
- feeder boundaries.

### 2.4 Use an intermediate SLD view model

The renderer must not depend directly on Pydantic or `infrasys` component internals. Use a small intermediate model containing nodes, connections, symbols, labels, states, and positions.

## 3. Proposed Package Structure

```text
src/gdm/systems/substation/sld/
    __init__.py
    view_model.py       # SldDiagram, SldNode, SldConnection, SldLabel
    symbols.py          # symbol names and component substitutions
    substitutions.py    # component/state -> SLD symbol rules
    topology.py         # topology extraction and validation
    layout.py           # deterministic schematic layout
    render_svg.py       # SVG renderer
    render_html.py      # optional interactive HTML wrapper
```

Potential public exports from `gdm.systems.substation.sld`:

```python
build_sld_view(system) -> SldDiagram
render_sld_svg(system, output_path=None) -> str
render_sld_html(system, output_path=None) -> str
```

The public API should accept a `SubstationSystem` and optional configuration rather than requiring callers to assemble graph internals.

## 4. Data Model Changes

### 4.1 Add facility location

Modify `src/gdm/systems/substation/topology.py`:

```python
from infrasys import Component, Location, System

class Substation(Component):
    location: Location | None = None
```

Requirements:

- Keep the field optional for backward compatibility.
- Do not add location fields to every substation component.
- Add an example location only if doing so does not change existing fixture expectations.
- Confirm JSON round-trip behavior with `Location` and CRS values.

### 4.2 SLD view model

Use plain Pydantic models or dataclasses in `sld/view_model.py`:

```python
class SldNode:
    id: str
    kind: str
    symbol: str
    label: str
    x: float | None = None
    y: float | None = None
    voltage_level_id: str | None = None
    bay_id: str | None = None
    state: str | None = None
    attributes: dict[str, object] = {}

class SldConnection:
    id: str
    source: str
    target: str
    kind: str
    state: str | None = None
    label: str | None = None
    attributes: dict[str, object] = {}

class SldDiagram:
    name: str
    nodes: list[SldNode]
    connections: list[SldConnection]
    labels: list[SldLabel]
    metadata: dict[str, object]
```

Use `default_factory=dict` in the real implementation. IDs must come from stable model names or UUIDs, never from list indexes alone.

## 5. Topology Extraction

Implement `sld/topology.py` to derive an SLD graph from the existing substation entities.

### 5.1 Build lookup tables

Index the system by:

- component name and UUID;
- voltage level ID;
- bay ID;
- busbar-section name;
- equipment ID.

Raise clear validation errors for missing references rather than silently dropping topology.

### 5.2 Convert electrical entities into view elements

Recommended mapping:

| Source entity | SLD representation |
|---|---|
| `BusbarSection` | electrical node (physical busbar when `length` is set, otherwise a junction) |
| `CircuitBreaker` | breaker symbol with state |
| `Disconnector` | disconnector symbol with state |
| `EarthingSwitch` | ground-switch symbol with state |
| `PowerTransformer` | transformer symbol with ordered windings |
| `InstrumentTransformer` | CT/VT symbol attached to a conductor |
| `SurgeArrester` | arrester symbol |
| `LineTrap` | line-trap symbol |
| `ExternalCircuit` | incoming/outgoing circuit endpoint |
| `FeederBoundary` | feeder endpoint and label |
| `Bay` | grouping/layout container, not necessarily a visible symbol |
| `VoltageLevel` | voltage-level grouping and annotation |

### 5.3 State handling

Represent equipment state in the view model rather than choosing a different source component type:

- closed breaker/disconnector: continuous electrical connection;
- open breaker/disconnector: visible gap or open symbol;
- closed earthing switch: ground connection shown;
- open earthing switch: ground connection omitted or visibly open.

The renderer must still show open equipment so topology state is not hidden.

## 6. Substitution Registry

Implement `sld/substitutions.py` with an explicit, overrideable registry.

Conceptual API:

```python
registry.register(CircuitBreaker, symbol="circuit_breaker")
registry.register(Disconnector, symbol="disconnector")
registry.register(PowerTransformer, symbol="power_transformer")
registry.register_state(CircuitBreaker, EquipmentState.OPEN, "circuit_breaker_open")
```

Requirements:

- Match subclasses safely.
- Provide a default symbol for every supported primary component.
- Fail loudly for unsupported visible equipment unless an `allow_unknown=True` option is explicitly selected.
- Permit a caller-provided registry for utility-specific symbols and labels.
- Keep symbol names independent of SVG path implementation.

## 7. Layout Algorithm

Implement a deterministic first layout without geographic coordinates.

### 7.1 Layout rules

1. Group by `VoltageLevel`.
2. Order voltage levels from highest nominal voltage to lowest unless configured otherwise.
3. Place incoming circuits on the left and feeder boundaries on the right.
4. Place buses horizontally inside each voltage-level band.
5. Place bays in stable order by bay name.
6. Place equipment along the bay path in bus/equipment order.
7. Place transformers between voltage-level bands.
8. Use fixed grid spacing and minimum symbol spacing.
9. Route connections orthogonally where possible.
10. Use stable tie-breaking by component name.

### 7.2 External layout option

The initial implementation may use a deterministic Python layout. Add an optional Graphviz backend later for larger or more irregular systems:

```text
NetworkX topology -> Graphviz coordinates/routes -> custom SLD symbols
```

Graphviz must not determine symbol semantics; it only supplies layout information.

## 8. SVG Rendering

Implement `sld/render_svg.py` with custom SVG primitives or SVG templates.

### 8.1 Rendering requirements

- Use IEC-inspired symbols with consistent stroke width and spacing.
- Render busbars thicker than conductors.
- Render open and closed switch states distinctly.
- Render voltage-level, bay, feeder, and equipment labels.
- Escape all user-provided labels before inserting them into SVG.
- Include stable element IDs based on source component IDs.
- Include `data-component-id`, `data-component-type`, and state attributes for HTML consumers.
- Return SVG text and optionally write it to a path.

### 8.2 Symbol implementation

Start with a small internal SVG symbol library rather than adding a large dependency:

- busbar;
- conductor;
- circuit breaker;
- disconnector;
- earthing switch;
- two-winding transformer;
- incoming/outgoing circuit;
- CT/VT;
- surge arrester;
- feeder boundary.

Support custom symbol providers later through the substitution registry.

## 9. Optional HTML Output

Implement `render_html.py` only after SVG output is stable.

HTML features:

- pan and zoom;
- hover metadata;
- click selection;
- optional state filtering;
- no dependency on the geographic Plotly plot.

A small standalone HTML wrapper around inline SVG is preferable initially. Add Cytoscape.js or React Flow only if editing or large interactive diagrams becomes a requirement.

## 10. Dependencies

### Required initially

No new runtime dependency is required if SVG is generated directly.

Existing dependencies already cover model traversal:

- `infrasys`;
- `pydantic`;
- `networkx`.

### Optional extras

Add optional dependency groups only when implemented:

```toml
[project.optional-dependencies]
sld = [
  "svgwrite",
  "pygraphviz",
]
```

Recommended roles:

- `svgwrite`: structured SVG generation;
- `pygraphviz`: Graphviz layout backend, requiring a system Graphviz installation;
- `schemdraw`: useful for symbol prototyping, but less suitable as the primary topology/layout engine;
- `Cytoscape.js`: browser-side interactive graph behavior;
- `elkjs`: high-quality browser-side layered and orthogonal layout.

Do not add Plotly, GeoPandas, or geographic map dependencies to the SLD path.

## 11. Tests

### 11.1 Location tests

Add tests covering:

- `Substation(location=Location(...))` construction;
- absent location remains valid;
- JSON export/import preserves location values and CRS;
- existing substation examples remain valid.

Suggested file: `tests/substation/test_location.py`.

### 11.2 View-model tests

Add tests covering:

- every supported primary component maps to one symbol;
- unsupported components produce a clear error;
- component and connection IDs are stable across repeated builds;
- source system is unchanged after SLD generation;
- open/closed equipment states appear correctly;
- transformer winding order is retained;
- missing bus or equipment references fail clearly.

Suggested file: `tests/substation/test_sld_view_model.py`.

### 11.3 Layout tests

Assert:

- repeated generation returns identical coordinates;
- incoming circuits and feeders are on the configured sides;
- voltage-level bands do not overlap;
- minimum spacing is respected;
- all connections reference existing node IDs.

Suggested file: `tests/substation/test_sld_layout.py`.

### 11.4 SVG tests

Assert:

- SVG output is well-formed XML;
- all expected component IDs exist;
- open and closed switch symbols differ;
- labels are escaped;
- output can be written to a temporary file.

Suggested file: `tests/substation/test_sld_rendering.py`.

### 11.5 Visual fixture

Keep one small golden SVG fixture for the single-bus example and one for a sectionalized or breaker-and-a-half example. Prefer structural assertions over pixel comparisons, because font and renderer differences make pixel tests brittle.

## 12. Documentation

Add `docs/substation-sld.md` containing:

- distinction between facility location and schematic position;
- example using `Substation.location`;
- example generating SVG;
- supported symbol mappings;
- switch-state behavior;
- custom substitution example;
- optional dependency installation;
- limitations of the initial layout engine.

Add a short API entry under the existing substation documentation if one exists.

## 13. Delivery Phases

### Phase 1: Facility location

- Add optional `Substation.location`.
- Add construction, serialization, and regression tests.
- Update documentation.

Acceptance criterion: existing examples pass, and a substation round-trips through JSON with a preserved `infrasys.Location`.

### Phase 2: SLD view model and topology extraction

- Add package structure.
- Implement lookup tables and reference validation.
- Implement `SldDiagram` models.
- Implement default substitution registry.
- Add structural tests.

Acceptance criterion: all supported parameterized and detailed substation examples produce a complete view model without modifying the source system.

### Phase 3: Deterministic layout

- Implement voltage-level, bay, busbar, transformer, and feeder layout.
- Add routing and spacing rules.
- Add deterministic layout tests.

Acceptance criterion: repeated generation yields identical coordinates and no overlapping primary elements in the supported fixtures.

### Phase 4: SVG rendering

- Implement core symbols.
- Render labels, states, metadata, and connections.
- Add XML and structural output tests.
- Add one or two SVG fixtures.

Acceptance criterion: generated SVG is readable as an engineering SLD and contains all visible topology and equipment states.

### Phase 5: Optional HTML and external layout backends

- Add inline SVG HTML wrapper with hover metadata.
- Add optional Graphviz backend for complex diagrams.
- Keep both optional and independent from the core model.

Acceptance criterion: browser output supports inspection without changing the canonical SVG or electrical model.

## 14. Validation Commands

Run after each phase:

```bash
pytest tests/substation -q
ruff check src/gdm/systems/substation tests/substation
```

For the complete implementation:

```bash
pytest -q
ruff check src tests
```

If Graphviz support is added, also run the SLD tests once with the optional dependency installed and once in the core-dependency environment.

## 15. Risks and Mitigations

- **Ambiguous topology references**: validate all IDs before rendering and report the source component and missing reference.
- **Overloaded symbols**: keep symbol selection in a registry, not in layout code.
- **Geographic/schematic confusion**: never derive SLD positions from `Location`.
- **Non-deterministic diagrams**: use stable names, explicit sorting, fixed spacing, and seeded or no-random layout.
- **Large stations**: support Graphviz/ELK as an optional backend after the deterministic baseline works.
- **Standards compliance**: describe symbols as IEC-inspired until a formal symbol library and review process are established.
- **Backward compatibility**: make facility location optional and keep SLD generation additive.

## 16. Definition of Done

- `Substation` optionally stores an `infrasys.Location`.
- Location construction and serialization are tested.
- SLD generation is separate from geographic plotting.
- The source `SubstationSystem` is never mutated by SLD generation.
- Supported equipment and state substitutions are explicit and overrideable.
- Layout is deterministic and topology-aware.
- SVG output is valid, inspectable, and contains stable component metadata.
- Documentation and focused tests are included.
- Optional rendering/layout dependencies are isolated behind extras.
