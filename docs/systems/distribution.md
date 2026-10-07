# Distribution System

`DistributionSystem` is the network model for distribution-level connectivity
and analysis. It owns buses, feeders, lines and other branches, loads,
distributed energy resources, voltage sources, and distribution time series.
It is the right starting point when the question is about how power flows
through a feeder or network, rather than how equipment is arranged inside a
station.

```python
from gdm.systems.distribution import DistributionSystem

system = DistributionSystem(name="north-feeder")
```

Distribution components reference one another through typed bus, feeder, and
substation fields. A `DistributionSubstation` groups distribution components;
it is not the detailed station model. For station buses, bays, switching
equipment, protection, or SCADA, use [`SubstationSystem`](../api/substation.md).

## Working With Distribution Models

- [Import and export](../dist_system/import_export.ipynb): load and persist
  supported distribution data.
- [Connectivity graphs](../dist_system/graphs.ipynb): inspect network
  connectivity and traverse buses and branches.
- [Time series](../gdm_intro/time_series.ipynb): attach and query time-series
  data.
- [Network reduction](../dist_system/network_reduction.ipynb): create reduced
  distribution models for analysis.
- [Distribution component API](../api/index.md): browse buses, feeders,
  branches, loads, transformers, DER, and other component types.

When a station contains several feeder boundaries, a larger distribution model
can be filtered to the matching outfeeds with
`DistributionSystem.get_substation_feeder_subsystem()`. To connect those
feeders back to the station, see [Connecting Systems](connecting-systems.md).