from loguru import logger


change_map = {
    "PositiveResistance": "Resistance",
    "PositiveWeight": "Weight",
    "PositiveAngle": "Angle",
    "PositiveResistancePULength": "ResistancePULength",
    "PositiveReactancePULength": "ReactancePULength",
    "PositiveReactance": "Reactance",
    "PositiveCapacitancePULength": "CapacitancePULength",
    "PositiveCapacitance": "Capacitance",
    "PositiveReactivePower": "ReactivePower",
    "PositiveApparentPower": "ApparentPower",
    "PositiveActivePower": "ActivePower",
    "PositiveCurrent": "Current",
    "PositiveVoltage": "Voltage",
    "PositiveDistance": "Distance",
}


def _replace_value(d, target, new):
    for k, v in d.items():
        if isinstance(v, dict):
            _replace_value(v, target, new)
        elif v == target:
            d[k] = new


def from__2_0_1__to__2_1_2(data: dict, from_version: str, to_version: str) -> dict:
    logger.info(f"Upgrading DistributionSystem from verion {from_version} to {to_version}")
    data["data_format_version"] = str(to_version)
    number_of_components_before = len(data["components"])
    components = []
    for component in data["components"]:
        for c in change_map:
            _replace_value(component, c, change_map[c])
        components.append(component)
    data["components"] = components
    number_of_components_after = len(data["components"])
    assert (
        number_of_components_before == number_of_components_after
    ), "Number of components should be the same before and after model upgrade"
    return data
