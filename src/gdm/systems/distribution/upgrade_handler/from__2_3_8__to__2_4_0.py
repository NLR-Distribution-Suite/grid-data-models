from loguru import logger


def from__2_3_8__to__2_4_0(data: dict, from_version: str, to_version: str) -> dict:
    """Advance the serialized data format for the 2.4.0 schema additions."""

    logger.info(f"Upgrading DistributionSystem from version {from_version} to {to_version}")
    data["data_format_version"] = str(to_version)
    return data
