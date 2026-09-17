from loguru import logger
from infrasys.migrations.metadata_migration import (
    component_needs_metadata_migration,
    migrate_component_metadata,
)


SEASON_TO_MONTHS = {
    "summer": ["june", "july", "august"],
    "winter": ["december", "january", "february"],
    "shoulder": ["march", "april", "may", "september", "october", "november"],
}


def _get_component_type(component: dict) -> str | None:
    return component.get("__metadata__", {}).get("fields", {}).get("type")


def _migrate_seasonal_tou_rates(component: dict) -> None:
    """Migrate SeasonalTOURates: rename 'season' -> 'months' (Season -> List[Month])."""
    if "season" in component:
        season_value = component.pop("season")
        component["months"] = SEASON_TO_MONTHS.get(season_value, [season_value])
        logger.debug(
            f"Migrated SeasonalTOURates season={season_value} -> months={component['months']}"
        )


def _migrate_demand_charge(component: dict) -> None:
    """Migrate DemandCharge: add 'months' field if missing (default to all 12 months)."""
    if "months" not in component:
        component["months"] = [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]
        logger.debug("Migrated DemandCharge: added default months (all 12 months)")


def _migrate_tariff_components(obj: dict) -> None:
    """Recursively walk the component dict and apply tariff migrations."""
    component_type = _get_component_type(obj)
    if component_type == "SeasonalTOURates":
        _migrate_seasonal_tou_rates(obj)
    elif component_type == "DemandCharge":
        _migrate_demand_charge(obj)

    for value in obj.values():
        if isinstance(value, dict):
            _migrate_tariff_components(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _migrate_tariff_components(item)


def from__2_3_2__to__2_3_3(data: dict, from_version: str, to_version: str) -> dict:
    logger.info(f"Upgrading DistributionSystem from verion {from_version} to {to_version}")
    data["data_format_version"] = str(to_version)
    number_of_components_before = len(data["components"])

    for component in data["components"]:
        _migrate_tariff_components(component)

    if any(component_needs_metadata_migration(c) for c in data["components"]):
        data["components"] = migrate_component_metadata(data["components"])
    number_of_components_after = len(data["components"])
    assert (
        number_of_components_before == number_of_components_after
    ), "Number of components should be the same before and after model upgrade"

    return data
