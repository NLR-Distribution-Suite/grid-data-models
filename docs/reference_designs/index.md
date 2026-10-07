# Substation Reference Designs

The public reference-design API provides canonical arrangements and a detailed
69/12.47 kV distribution station. Each canonical design includes two incoming
HV circuits, protected transformer bay(s), MV bus voltage sensing and surge
protection, and equipped feeder exits with CTs, disconnectors, earthing
switches, overcurrent protection, revenue metering, and power-quality
monitoring. Station breakers are mapped through DNP3 and an SCL configuration.
Each gallery plot uses deterministic coordinates so its electrical
arrangement can be inspected without facility GIS data.

## Layout Gallery

Each example below constructs the model shown in its schematic. The returned
`SubstationSystem` contains the station topology and its representative
primary, protection, metering, and automation equipment. The canonical designs
use topology-specific default feeder counts; pass `outfeed_count` to choose a
different number.

### Single Bus

A compact arrangement with all circuits connected to one common bus.

[Open the single-bus schematic](../reference_designs/single-bus-substation_schematic.html)

```python
from gdm.systems.substation import build_reference_design

system = build_reference_design("single_bus")
```

### Sectionalized Single Bus

Two bus sections are separated by a normally open tie breaker, allowing the
sections to be operated independently or coupled when needed.

[Open the sectionalized single-bus schematic](../reference_designs/sectionalized-single-bus-substation_schematic.html)

```python
from gdm.systems.substation import build_reference_design

system = build_reference_design("sectionalized_single_bus")
```

### Main and Transfer

A main bus and transfer path provide a way to bypass a circuit breaker during
maintenance while retaining a connection to the station.

[Open the main-and-transfer schematic](../reference_designs/main-and-transfer-substation_schematic.html)

```python
from gdm.systems.substation import build_reference_design

system = build_reference_design("main_and_transfer")
```

### Double Bus, Single Breaker

Each circuit has one breaker and can be selected onto either of two buses.

[Open the double-bus, single-breaker schematic](../reference_designs/double-bus-single-breaker-substation_schematic.html)

```python
from gdm.systems.substation import build_reference_design

system = build_reference_design("double_bus_single_breaker")
```

### Ring Bus

The breakers form a ring, with circuits connected between adjacent breakers so
that a single breaker can be isolated without interrupting every circuit.

[Open the ring-bus schematic](../reference_designs/ring-bus-substation_schematic.html)

```python
from gdm.systems.substation import build_reference_design

system = build_reference_design("ring_bus")
```

### Breaker-and-a-Half

Two circuits share a middle breaker between two buses, providing redundancy
while using fewer breakers than a double-breaker arrangement.

[Open the breaker-and-a-half schematic](../reference_designs/breaker-and-a-half-substation_schematic.html)

```python
from gdm.systems.substation import build_reference_design

system = build_reference_design("breaker_and_a_half")
```

### Double Breaker, Double Bus

Each circuit is connected to both buses through its own pair of breakers,
allowing either bus or breaker to be isolated while maintaining service.

[Open the double-breaker, double-bus schematic](../reference_designs/double-breaker-double-bus-substation_schematic.html)

```python
from gdm.systems.substation import build_reference_design

system = build_reference_design("double_breaker_double_bus")
```

### HV/MV Single Bus

A high-voltage bus supplies a medium-voltage bus through a power transformer;
the feeder exits connect to the medium-voltage side.

[Open the HV/MV single-bus schematic](../reference_designs/hv-mv-single-bus-substation_schematic.html)

```python
from gdm.systems.substation import build_reference_design

system = build_reference_design("hv_mv_single_bus")
```

### Detailed Distribution Station

A fully populated 69/12.47 kV station example with two incoming circuits, two
transformers, four feeders, detailed protection and metering, and station
automation.

[Open the detailed distribution-station schematic](../reference_designs/detailed-distribution-substation_schematic.html)

```python
from gdm.systems.substation import build_reference_design

system = build_reference_design("detailed_distribution")
```

Bay and substation footprints can be supplied as explicit `Location` rings.
When present, they are exported as polygon features and rendered as translucent
boundaries in station plots.