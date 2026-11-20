# Connecting Distribution and Substation Systems

Keep the two models separate while they have separate owners or lifecycles.
Join them when a workflow needs one network graph, one serialized model, or
analysis across the station-to-feeder connection. GDM provides two distinct
operations for those cases.

## Assemble a Station and Its Feeder Models

Use `SubstationSystem.to_distribution_system()` when you have a station model
and one `DistributionSystem` per station outfeed. Each feeder model must
contain exactly one `DistributionFeeder`.

The station's `FeederBoundary` is the connection contract:

- `feeder_id` matches the feeder model's `DistributionFeeder.name`.
- `source_equivalent_id` is the name of that feeder model's root bus.
- Root-bus voltage must match the boundary bus; root phases must be supported
  by the boundary bus.
- Every station boundary must have a corresponding feeder model, and feeder IDs
  must be unique.

The assembly method merges each root bus into its boundary bus, removes the
feeder-local voltage sources, and creates a single source at the
highest-voltage station transformer terminal. Time series are copied by
default.

The following example starts from GDM's three-feeder station example, separates
its feeder components into one model per outfeed, and assembles the result:

```python
from gdm.systems.distribution import DistributionSystem
from gdm.systems.substation import FeederBoundary
from gdm.systems.substation.reference_designs import (
    hv_mv_substation_with_distribution_feeders,
)

station, all_feeders = hv_mv_substation_with_distribution_feeders()
boundaries = list(station.get_components(FeederBoundary))

for boundary in boundaries:
    boundary.source_equivalent_id = f"{boundary.feeder_id}-source-bus"

feeder_systems = []
for boundary in boundaries:
    feeder_system = DistributionSystem(
        name=f"{boundary.feeder_id}-system",
        auto_add_composed_components=True,
    )
    for component in all_feeders.iter_all_components():
        feeder = getattr(component, "feeder", None)
        if feeder is None or feeder.name != boundary.feeder_id:
            continue
        if not feeder_system.has_component(component):
            feeder_system.add_component(component)
    feeder_systems.append(feeder_system)

complete_system = station.to_distribution_system(feeder_systems)
```

Set `keep_time_series=False` to omit feeder time series, or pass `output_name`
to choose the combined system name. The inputs are not mutated into one
another; the method constructs and returns a new `DistributionSystem`.

## Expand One Transformer In Place

Use `DistributionSystem.replace_transformer_with_substation()` when a feeder
model already contains an abstract distribution transformer and you want to
replace it with detailed station topology. The station must contain exactly one
power transformer and one feeder boundary whose `feeder_id` matches the
distribution transformer's feeder name. Its primary equipment must preserve
both original terminal buses. The method adds the station components, removes
the abstract transformer, and returns the replacement `PowerTransformer`.

This operation is for one station at one existing transformer location. It is
not the multi-feeder assembly workflow above.

## Choosing

| Situation | Operation |
| --- | --- |
| A feeder model needs more detail at one existing transformer | `replace_transformer_with_substation()` |
| Several independently modeled feeders need to connect to one station | `SubstationSystem.to_distribution_system()` |
| You only need station topology or feeder analysis separately | Keep the systems separate |