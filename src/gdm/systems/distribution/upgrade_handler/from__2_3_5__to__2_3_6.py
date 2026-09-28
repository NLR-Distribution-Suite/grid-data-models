from loguru import logger
from infrasys.migrations.metadata_migration import migrate_component_metadata


TRANSFORMER_TYPES = {"DistributionTransformer", "DistributionRegulator"}
CAPACITOR_TYPE = "DistributionCapacitor"


def _get_component_type(component: dict) -> str | None:
    metadata = component.get("__metadata__", {})
    if "fields" in metadata:
        return metadata["fields"].get("type")
    return metadata.get("type")


def _add_tap_positions(obj: dict) -> None:
    """Add tap_positions field to transformer-based components if missing."""
    component_type = _get_component_type(obj)
    if component_type in TRANSFORMER_TYPES:
        if "tap_positions" not in obj:
            winding_phases = obj.get("winding_phases", [])
            obj["tap_positions"] = [[1.0] * len(phases) for phases in winding_phases]
            logger.debug(f"Migrated {component_type}: added default tap_positions")

    # Recurse into nested dicts/lists
    for value in obj.values():
        if isinstance(value, dict):
            _add_tap_positions(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _add_tap_positions(item)


def _add_capacitor_state(obj: dict) -> None:
    """Add state field to DistributionCapacitor components if missing."""
    component_type = _get_component_type(obj)
    if component_type == CAPACITOR_TYPE:
        if "state" not in obj:
            # Default: all banks on, one per phase
            phases = obj.get("phases", [])
            obj["state"] = [True] * len(phases)
            logger.debug("Migrated DistributionCapacitor: added default state (all True)")

    # Recurse into nested dicts/lists
    for value in obj.values():
        if isinstance(value, dict):
            _add_capacitor_state(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _add_capacitor_state(item)


def from__2_3_5__to__2_3_6(data: dict, from_version: str, to_version: str) -> dict:
    logger.info(f"Upgrading DistributionSystem from verion {from_version} to {to_version}")
    data["data_format_version"] = str(to_version)
    number_of_components_before = len(data["components"])

    for component in data["components"]:
        _add_tap_positions(component)
        _add_capacitor_state(component)

    data["components"] = migrate_component_metadata(data["components"])
    number_of_components_after = len(data["components"])
    assert (
        number_of_components_before == number_of_components_after
    ), "Number of components should be the same before and after model upgrade"

    return data
