from gdm.version import VERSION

__version__ = VERSION

# from gdm.tracked_changes import apply_tracked_changes, apply_update_scenario, get_distribution_system_on_date
from gdm.distribution.model_reduction.reducer import (
    reduce_to_primary_system,
    reduce_to_radial_network,
    reduce_to_three_phase_system,
)
from gdm.distribution.distribution_graph import build_graph_from_system
from gdm.distribution.distribution_system import DistributionSystem
from gdm.distribution.catalog_system import CatalogSystem
