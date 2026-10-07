"""Utility to aggregate parallel single-phase transformer-based components into three-phase."""

from collections import defaultdict
from typing import TypeVar

from gdm.systems.distribution import DistributionSystem
from gdm.systems.distribution.components.base.distribution_transformer_base import (
    DistributionTransformerBase,
)
from gdm.systems.distribution.components.distribution_transformer import DistributionTransformer
from gdm.systems.distribution.components.distribution_regulator import DistributionRegulator
from gdm.systems.distribution.equipment.distribution_transformer_equipment import (
    DistributionTransformerEquipment,
    WindingEquipment,
)

T = TypeVar("T", bound=DistributionTransformerBase)


def _bus_key(component: DistributionTransformerBase) -> tuple[str, ...]:
    """Return a hashable key of bus names for grouping parallel components."""
    return tuple(bus.name for bus in component.buses)


def _is_single_phase(component: DistributionTransformerBase) -> bool:
    """Check if all windings are single-phase."""
    return all(wdg.num_phases == 1 for wdg in component.equipment.windings)


def _merge_windings(components: list[DistributionTransformerBase]) -> list[WindingEquipment]:
    """Merge single-phase windings into three-phase windings.

    Assumes all components have the same number of windings and compatible equipment.
    Rated power is summed; resistance and tap bounds are averaged.
    """
    num_windings = len(components[0].equipment.windings)
    merged = []
    for wdg_idx in range(num_windings):
        ref_wdg = components[0].equipment.windings[wdg_idx]
        total_power = sum(comp.equipment.windings[wdg_idx].rated_power for comp in components)
        avg_resistance = sum(
            comp.equipment.windings[wdg_idx].resistance for comp in components
        ) / len(components)
        all_taps = [comp.equipment.windings[wdg_idx].tap_positions[0] for comp in components]
        merged.append(
            WindingEquipment(
                name=ref_wdg.name,
                resistance=avg_resistance,
                is_grounded=ref_wdg.is_grounded,
                rated_voltage=ref_wdg.rated_voltage,
                voltage_type=ref_wdg.voltage_type,
                rated_power=total_power,
                num_phases=len(components),
                connection_type=ref_wdg.connection_type,
                tap_positions=all_taps,
                total_taps=ref_wdg.total_taps,
                min_tap_pu=ref_wdg.min_tap_pu,
                max_tap_pu=ref_wdg.max_tap_pu,
            )
        )
    return merged


def _merge_group(components: list[T]) -> T:
    """Merge a group of parallel single-phase components into one three-phase component.

    Parameters
    ----------
    components : list[T]
        List of single-phase components connected to the same buses.

    Returns
    -------
    T
        A single three-phase component of the same type.
    """
    ref = components[0]
    component_type = type(ref)

    merged_windings = _merge_windings(components)

    # Build merged winding_phases and tap_positions from each component's per-winding phases
    merged_winding_phases = []
    merged_tap_positions = []
    for wdg_idx in range(len(ref.equipment.windings)):
        phases = []
        taps = []
        for comp in components:
            phases.extend(comp.winding_phases[wdg_idx])
            if comp.tap_positions is not None:
                taps.extend(comp.tap_positions[wdg_idx])
            else:
                taps.extend([1.0] * len(comp.winding_phases[wdg_idx]))
        merged_winding_phases.append(phases)
        merged_tap_positions.append(taps)

    merged_equipment = DistributionTransformerEquipment(
        name=f"{ref.equipment.name}_merged",
        mounting=ref.equipment.mounting,
        pct_no_load_loss=ref.equipment.pct_no_load_loss,
        pct_full_load_loss=ref.equipment.pct_full_load_loss,
        windings=merged_windings,
        coupling_sequences=ref.equipment.coupling_sequences,
        winding_reactances=ref.equipment.winding_reactances,
        is_center_tapped=False,
    )

    kwargs = {
        "name": f"{ref.name}_merged",
        "buses": ref.buses,
        "winding_phases": merged_winding_phases,
        "tap_positions": merged_tap_positions,
        "equipment": merged_equipment,
    }

    # Preserve substation/feeder if present
    if hasattr(ref, "substation") and ref.substation is not None:
        kwargs["substation"] = ref.substation
    if hasattr(ref, "feeder") and ref.feeder is not None:
        kwargs["feeder"] = ref.feeder

    # For regulators, merge controllers
    if component_type is DistributionRegulator:
        controllers = []
        for comp in components:
            controllers.extend(comp.controllers)
        kwargs["controllers"] = controllers

    return component_type(**kwargs)


def aggregate_single_phase_transformers(
    system: DistributionSystem,
) -> DistributionSystem:
    """Replace groups of parallel single-phase transformer-based components with
    a single three-phase equivalent.

    Finds all DistributionTransformer and DistributionRegulator components that are:
    - Single-phase (all windings have num_phases == 1)
    - Connected to the same set of buses

    Groups of 2 (open-wye / open-delta) or 3 such components are merged into one
    multi-phase equivalent.  The original single-phase components are removed and
    the merged component is added.

    Parameters
    ----------
    system : DistributionSystem
        Input distribution system (will be modified in place).

    Returns
    -------
    DistributionSystem
        The same system reference, modified with merged components.
    """
    for component_type in (DistributionTransformer, DistributionRegulator):
        # Group single-phase components by their bus connections
        groups: dict[tuple[str, ...], list] = defaultdict(list)
        for comp in system.get_components(component_type):
            if _is_single_phase(comp):
                groups[_bus_key(comp)].append(comp)

        # Merge groups of 2 (open-wye/open-delta) or 3 parallel single-phase components
        for key, group in groups.items():
            if len(group) < 2 or len(group) > 3:
                continue

            merged = _merge_group(group)

            # Remove originals and add merged.
            # cascade_down=False because grouped components share children (buses, equipment)
            # that the merged component still references.
            for comp in group:
                system.remove_component(comp, cascade_down=False)

            # Add composed children (windings, equipment) before the merged component
            for winding in merged.equipment.windings:
                system.add_component(winding)
            system.add_component(merged.equipment)
            system.add_component(merged)

    return system
