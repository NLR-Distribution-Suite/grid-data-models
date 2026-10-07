from loguru import logger


def from__2_1_4__to__2_1_5(data: dict, from_version: str, to_version: str) -> dict:
    logger.info(f"Upgrading DistributionSystem from verion {from_version} to {to_version}")
    return data
