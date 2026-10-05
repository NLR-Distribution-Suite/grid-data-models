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
owns station topology and design: substations, voltage levels, bays, busbar
sections, primary equipment, protection, metering, station automation, SCADA
mappings, and renewable plant interconnection profiles.

Station topology uses the same bus-branch design as `DistributionSystem`.
Electrical nodes are `BusbarSection` instances, which subclass `DistributionBus`
and add a schematic single-line-diagram `schematic_coordinate` (separate from the
inherited geographic `coordinate`). Installed equipment references the nodes it
connects directly through typed `buses` (series) or `bus` (shunt) fields; there
are no string terminal or connectivity-node IDs inside the station. Cross-system
references (distribution feeder IDs, plant IDs, protocol addresses) remain
strings.

`SubstationSystem.get_undirected_graph()` returns a NetworkX bus-branch graph
whose nodes are busbar sections and whose edges are state-aware primary
equipment, ready for single-line-diagram rendering and SCADA binding.

## Scope

The current datamodels include:

- station topology: substations, voltage levels, bays, busbar sections (nodes), feeder boundaries, and bus-branch primary equipment;
- primary equipment: breakers, disconnectors, earthing switches, power transformers, instrument transformers, and surge arresters;
- protection: IEDs, functions, schemes, setting groups, settings, and test records;
- automation: IEDs, IEC 61850 logical nodes, SCL metadata, semantic signals, and DNP3/IEC 60870/IEC 61850 mappings;
- metering and power quality: instrument-transformer cores, metering points, meter tests, and PQ monitors;
- renewable interfaces: collector feeders, plant controllers, IEEE 1547/IEEE 2800 profiles, solar/wind plant references, and energy-storage interfaces;
- lifecycle and evidence: asset references, external identifiers, ratings, standards profiles, document metadata, lifecycle records, and state observations.

SCL, relay-settings, SCADA, and study files are represented by metadata and
hash/URI references only. File parsing and external utility integrations are
outside the current scope.

## Building a Station

`SubstationBuilder` is the supported way to assemble a detailed station:

```python
from gdm.systems.substation import SubstationBuilder
from gdm.quantities import Voltage

builder = SubstationBuilder("riverside", initial_voltage_level_id="hv", initial_nominal_voltage=Voltage(69, "kilovolt"))
builder.add_voltage_level("mv", Voltage(12.47, "kilovolt"))
hv = builder.add_bus("hv-bus", "hv")
mv = builder.add_bus("mv-bus", "mv")
builder.add_two_winding_transformer("t1", "t1-bay", hv, mv)
builder.add_feeder("feeder-1", "feeder-1-bay", "mv-bus")
system = builder.build()
```

A complete 69 kV / 12.47 kV reference design with two transformers, four
feeders, protection, metering, and SCADA mappings is available as
`build_detailed_distribution_substation()`.

## Plotting and Single-Line Diagrams

- `SubstationSystem.plot()` renders an interactive geographic map using each
  busbar section's geographic `coordinate`, coloring nodes by voltage level and
  equipment by switching state. It returns the Plotly figure and can export an
  HTML file.
- `SubstationSystem.to_sld()` renders an interactive single-line diagram to a
  standalone HTML document. It uses each node's `schematic_coordinate` when
  present and otherwise computes a deterministic voltage-level band layout. It
  returns the HTML string and optionally writes it to a path.

In the SLD you can drag nodes and equipment (wires stay connected), drag the
busbar end handles to change busbar length, snap to a grid or to other nodes,
and hover to highlight connections. Edits are remembered per diagram in the
browser, and **save layout** downloads a JSON layout.

To persist an edited layout into the model:

```python
import json
from gdm.systems.substation import build_detailed_distribution_substation

system = build_detailed_distribution_substation()
system.apply_sld_layout(json.load(open("my-sld.layout.json")))
system.to_json("station.json", overwrite=True)   # coordinates and busbar lengths are stored
```

`SubstationSystem.export_sld_layout()` returns the current layout as data,
which is the same format accepted by `apply_sld_layout()`.

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
