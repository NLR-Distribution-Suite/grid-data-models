"""Backward-compatible imports for distribution system reducers."""

from gdm.systems.distribution.model_reduction.primary import reduce_to_primary_system
from gdm.systems.distribution.model_reduction.radial import reduce_to_radial_network
from gdm.systems.distribution.model_reduction.three_phase import reduce_to_three_phase_system
from gdm.systems.distribution.model_reduction.trivial import reduce_trivial_nodes

__all__ = [
    "reduce_to_primary_system",
    "reduce_to_radial_network",
    "reduce_to_three_phase_system",
    "reduce_trivial_nodes",
]
