"""Component relationship analysis tools."""

import contextlib
from uuid import UUID

from gdm.systems.distribution import DistributionSystem

from gdm.mcp.schemas import ComponentInfo


def find_orphaned_components(system: DistributionSystem) -> list[ComponentInfo]:
    """
    Find components that don't have substation or feeder assignments.

    Args:
        system: DistributionSystem to search

    Returns:
        List of ComponentInfo for orphaned components
    """
    orphaned = []

    for component in system.iter_all_components():
        substation = getattr(component, "substation", None)
        feeder = getattr(component, "feeder", None)

        # Component is orphaned if both are None
        if substation is None and feeder is None:
            phases = getattr(component, "phases", None)
            in_service = getattr(component, "in_service", None)

            orphaned.append(
                ComponentInfo(
                    uuid=component.uuid
                    if isinstance(component.uuid, UUID)
                    else UUID(component.uuid),
                    component_type=component.__class__.__name__,
                    name=component.name,
                    substation=None,
                    feeder=None,
                    phases=phases,
                    in_service=in_service,
                )
            )

    return orphaned


def _to_component_info(comp) -> ComponentInfo:
    """Convert a component to ComponentInfo."""
    substation = getattr(comp, "substation", None)
    feeder = getattr(comp, "feeder", None)
    phases = getattr(comp, "phases", None)
    in_service = getattr(comp, "in_service", None)

    return ComponentInfo(
        uuid=comp.uuid if isinstance(comp.uuid, UUID) else UUID(comp.uuid),
        component_type=comp.__class__.__name__,
        name=comp.name,
        substation=substation.name if substation and hasattr(substation, "name") else None,
        feeder=feeder.name if feeder and hasattr(feeder, "name") else None,
        phases=phases,
        in_service=in_service,
    )


def _is_child_of(component, target_uuid) -> bool:
    """Check if component references the target component (i.e., is a child)."""
    for attr in ["bus", "buses", "equipment", "controller"]:
        ref = getattr(component, attr, None)
        if ref is None:
            continue
        # Handle single reference
        if hasattr(ref, "uuid") and ref.uuid == target_uuid:
            return True
        # Handle list of references
        if isinstance(ref, list):
            for item in ref:
                if hasattr(item, "uuid") and item.uuid == target_uuid:
                    return True
    return False


def get_component_relationships(
    system: DistributionSystem,
    component_id: str,
) -> dict[str, list[ComponentInfo]]:
    """
    Get parent and child relationships for a component.

    Args:
        system: DistributionSystem to search
        component_id: UUID or name of component

    Returns:
        Dictionary with 'parents' and 'children' lists of ComponentInfo
    """
    # Find the component
    component = None
    try:
        component = system.get_component_by_uuid(component_id)
    except Exception:
        # Try by name
        for comp in system.iter_all_components():
            if comp.name == component_id:
                component = comp
                break

    if component is None:
        return {"parents": [], "children": [], "error": f"Component not found: {component_id}"}

    # Get parent components
    parents = []
    with contextlib.suppress(Exception):
        parent_components = system.list_parent_components(component)
        parents = [_to_component_info(parent) for parent in parent_components]

    # Get child components (components that reference this one)
    component_uuid = component.uuid
    children = [
        _to_component_info(other_comp)
        for other_comp in system.iter_all_components()
        if other_comp.uuid != component_uuid and _is_child_of(other_comp, component_uuid)
    ]

    return {
        "parents": parents,
        "children": children,
    }
