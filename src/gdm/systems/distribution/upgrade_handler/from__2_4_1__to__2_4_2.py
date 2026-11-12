from loguru import logger


def from__2_4_1__to__2_4_2(data: dict, from_version: str, to_version: str) -> dict:
    """Advance the version for the additive generator models."""
    logger.info(f"Upgrading DistributionSystem from version {from_version} to {to_version}")
    data["data_format_version"] = str(to_version)
    return data
