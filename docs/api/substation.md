# Substation System

The canonical substation namespace is `gdm.systems.substation`:

```python
from gdm.systems.substation import (
    CircuitBreaker,
    PowerTransformer,
    SubstationSystem,
)
```

`SubstationSystem` is the authoritative model for utility substation design and
station data. It covers distribution substations, wind collector substations,
solar collector substations, hybrid renewable substations, and colocated energy
storage interfaces.

## Ownership Boundary

`DistributionSystem` owns feeder-level analysis: distribution buses, lines,
loads, DER, feeder topology, and distribution time series. `SubstationSystem`
owns station topology and design: substations, voltage levels, bays, terminals,
connectivity nodes, primary equipment, protection, metering, station automation,
SCADA mappings, and renewable plant interconnection profiles.

The models use stable string IDs for cross-system references. A feeder boundary
can reference a distribution model, station bay, station terminal, and an
optional source equivalent without duplicating the physical station equipment.

## Scope

The current datamodels include:

- station topology: substations, voltage levels, bays, busbar sections, terminals, connectivity nodes, and feeder boundaries;
- primary equipment: breakers, disconnectors, earthing switches, power transformers, instrument transformers, and surge arresters;
- protection: IEDs, functions, schemes, setting groups, settings, and test records;
- automation: IEDs, IEC 61850 logical nodes, SCL metadata, semantic signals, and DNP3/IEC 60870/IEC 61850 mappings;
- metering and power quality: instrument-transformer cores, metering points, meter tests, and PQ monitors;
- renewable interfaces: collector feeders, plant controllers, IEEE 1547/IEEE 2800 profiles, solar/wind plant references, and energy-storage interfaces;
- lifecycle and evidence: asset references, external identifiers, ratings, standards profiles, document metadata, lifecycle records, and state observations.

SCL, relay-settings, SCADA, and study files are represented by metadata and
hash/URI references only. File parsing and external utility integrations are
outside the current scope.

## Plotting

`SubstationSystem.plot()` creates an interactive Plotly schematic from terminal
references. It is intentionally a schematic rather than a geographic map,
because station topology components do not carry geographic coordinates.

```python
from gdm.systems.substation import SubstationSystem

system = SubstationSystem.example()
figure = system.plot(show=False)
system.plot("./plots", show=False)
```

The schematic includes connectivity nodes, busbar sections, primary equipment,
and feeder boundaries. Open equipment connections are drawn with dashed lines.
`export_path` follows the same existing-directory behavior as
`DistributionSystem.plot()` and writes `<system-name>_plot.html`.

The executable examples include `hv_mv_single_bus_substation()`, which models a
69 kV bus, a 69/12.47 kV `PowerTransformer`, a 12.47 kV bus, and MV feeder
bays. This is the common distribution-station pattern where the station model
contains more than one voltage level and the transformer is the explicit
electrical bridge between their busbars.

`hv_mv_substation_with_distribution_feeders()` returns this station together
with a separate `DistributionSystem` containing three radial feeder models.
Each station `FeederBoundary.feeder_id` matches a `DistributionFeeder.name`,
and `distribution_model_reference_id` identifies the downstream model. This
keeps the transformer and station switching equipment in `SubstationSystem`
while the distribution feeder model owns the feeder buses and line segments.

## Single-Line Examples

The executable fixtures in `tests/substation/textbook_examples.py` transcribe
the following Desktop single-line diagrams into `SubstationSystem` objects:

- `fig_25_4_bus_section_and_transfer_bus()`
- `fig_25_5_11kv_400v_single_bus()`
- `fig_25_6_33kv_sectionalized_bus()`
- `fig_25_7_double_main_bus_with_spare_bus()`
- `fig_25_8_11kv_400v_line_trap()`
- `fig_25_9_66kv_through_bus()`
- `fig_25_10_dual_66kv_11kv_bus_sections()`

They model busbars, circuit breakers, disconnectors, grounding switches,
current and voltage instrument transformers, surge arresters, line traps,
incoming/outgoing circuits, and power transformers. `DiagramPosition` stores
authored schematic coordinates so `SubstationSystem.plot()` preserves the
source diagram's arrangement after serialization.

## Standards Profiles

The model is generic by default. Projects can associate applicable editions and
authorities with `StandardProfile`, including profiles based on:

- [IEEE 1547-2018](https://standards.ieee.org/standard/1547-2018.html) for distribution-connected DER;
- [IEEE 2800-2022](https://standards.ieee.org/standard/2800-2022.html) for transmission/subtransmission IBR interfaces;
- [IEEE C37.2-2022](https://standards.ieee.org/standard/C37_2-2022.html) for protection and device function vocabulary;
- [IEC 61850](https://webstore.iec.ch/en/search?query=IEC%2061850) and IEC 61850-6 for station automation and SCL;
- [IEC 61970/61968 CIM](https://webstore.iec.ch/en/search?query=IEC%2061970-301) for utility information-model exchange;
- [IEEE 519-2022](https://standards.ieee.org/standard/519-2022.html) and IEC 61000 profiles for power quality.

Standards applicability, adopted editions, utility requirements, and authority
having jurisdiction remain project data rather than global assumptions in the
model.
