"""System merger for combining multiple distribution systems."""

from collections import defaultdict
from uuid import UUID

from gdm.systems.distribution import DistributionSystem

from gdm.mcp.exceptions import MergeConflictError
from gdm.mcp.schemas import MergeConflict, MergeReport
from gdm.mcp.validation.diagnostics import diagnose_system


def _detect_conflicts(
    systems: list[DistributionSystem],
) -> list[MergeConflict]:
    """Detect UUID and name conflicts across systems."""
    conflicts: list[MergeConflict] = []
    uuid_map: dict[UUID, list[int]] = defaultdict(list)
    name_map: dict[tuple[str, str], list[int]] = defaultdict(list)

    for idx, system in enumerate(systems):
        for component in system.iter_all_components():
            component_uuid = (
                component.uuid if isinstance(component.uuid, UUID) else UUID(component.uuid)
            )
            uuid_map[component_uuid].append(idx)
            name_map[(component.__class__.__name__, component.name)].append(idx)

    for uuid, system_indices in uuid_map.items():
        if len(system_indices) > 1:
            conflicts.append(
                MergeConflict(
                    conflict_type="uuid",
                    identifier=str(uuid),
                    system_indices=system_indices,
                    details=f"UUID {uuid} found in systems {system_indices}",
                )
            )

    for (comp_type, comp_name), system_indices in name_map.items():
        if len(system_indices) > 1:
            conflicts.append(
                MergeConflict(
                    conflict_type="name",
                    component_type=comp_type,
                    identifier=comp_name,
                    system_indices=system_indices,
                    details=f"{comp_type} '{comp_name}' found in systems {system_indices}",
                )
            )

    return conflicts


def _should_skip_component(component, system_idx: int, conflicts: list[MergeConflict]) -> bool:
    """Check if a component should be skipped due to conflicts."""
    component_uuid = component.uuid if isinstance(component.uuid, UUID) else UUID(component.uuid)
    component_type = component.__class__.__name__

    for conflict in conflicts:
        if conflict.conflict_type == "uuid" and str(component_uuid) == conflict.identifier:
            if system_idx in conflict.system_indices[1:]:
                return True
        elif (
            conflict.conflict_type == "name"
            and component_type == conflict.component_type
            and component.name == conflict.identifier
        ):
            if system_idx in conflict.system_indices[1:]:
                return True
    return False


def _merge_component(
    component,
    source_system: DistributionSystem,
    merged_system: DistributionSystem,
    components_by_type: dict[str, int],
    warnings: list[str],
    system_idx: int,
) -> tuple[int, int]:
    """Merge a single component and its time series. Returns (components_added, ts_transferred)."""
    component_type = component.__class__.__name__
    try:
        merged_system.add_component(component)
        components_by_type[component_type] += 1

        ts_count = 0
        if source_system.has_time_series(component):
            for ts_metadata in source_system.list_time_series_metadata(component):
                ts_type = type(ts_metadata)
                ts_data = source_system.get_time_series(
                    component, ts_metadata.variable_name, ts_type
                )
                merged_system.add_time_series(ts_data, component, **ts_metadata.features)
                ts_count += 1

        return 1, ts_count
    except Exception as e:
        warnings.append(f"Failed to add {component_type} '{component.name}': {str(e)}")
        return 0, 0


def merge_systems(
    systems: list[DistributionSystem],
    name: str,
    strict: bool = True,
) -> tuple[DistributionSystem, MergeReport]:
    """
    Merge multiple distribution systems into one.

    Args:
        systems: List of DistributionSystem objects to merge
        name: Name for the merged system
        strict: If True, raise error on conflicts. If False, warn and skip.

    Returns:
        Tuple of (merged_system, MergeReport)

    Raises:
        MergeConflictError: If conflicts detected in strict mode
    """
    if not systems:
        return DistributionSystem(name=name), MergeReport(
            success=False,
            output_system_name=name,
            input_system_count=0,
            total_components_merged=0,
            error_message="No systems provided to merge",
        )

    warnings: list[str] = []
    conflicts = _detect_conflicts(systems)

    if conflicts and strict:
        raise MergeConflictError(
            conflicts=[c.model_dump() for c in conflicts],
            message=f"Found {len(conflicts)} conflicts during merge. Use strict=False to skip conflicts.",
        )

    merged_system = DistributionSystem(name=name)
    components_by_type: dict[str, int] = defaultdict(int)
    total_components = 0
    timeseries_transferred = 0

    for system_idx, system in enumerate(systems):
        for component in system.iter_all_components():
            if _should_skip_component(component, system_idx, conflicts):
                component_type = component.__class__.__name__
                warnings.append(
                    f"Skipped {component_type} '{component.name}' from system {system_idx} due to conflict"
                )
                continue

            added, ts = _merge_component(
                component, system, merged_system, components_by_type, warnings, system_idx
            )
            total_components += added
            timeseries_transferred += ts

    validation_report = diagnose_system(merged_system)
    if not validation_report.is_valid:
        warnings.append(
            f"Merged system has {len(validation_report.issues)} validation issues. Consider running diagnostics."
        )

    return merged_system, MergeReport(
        success=True,
        output_system_name=name,
        input_system_count=len(systems),
        total_components_merged=total_components,
        components_by_type=dict(components_by_type),
        timeseries_transferred=timeseries_transferred,
        conflicts=conflicts,
        warnings=warnings,
    )
