from loguru import logger
from infrasys.migrations.metadata_migration import migrate_component_metadata


def from__2_1_5__to__2_2_0(data: dict, from_version: str, to_version: str) -> dict:
    logger.info(f"Upgrading DistributionSystem from verion {from_version} to {to_version}")
    data["data_format_version"] = str(to_version)
    number_of_components_before = len(data["components"])
    data["components"] = migrate_component_metadata(data["components"])
    number_of_components_after = len(data["components"])
    assert (
        number_of_components_before == number_of_components_after
    ), "Number of components should be the same before and after model upgrade"

    return data
