"""A fully detailed distribution substation reference design.

``build_detailed_distribution_substation`` returns a 69 kV / 12.47 kV
distribution substation that exercises the complete station model: two
sectionalized HV and MV buses, two incoming lines, two power transformers, four
MV feeders, instrument transformers, surge arresters, earthing switches,
protection, metering, and SCADA point mappings.
"""

from __future__ import annotations

from infrasys import Location

from gdm.quantities import Voltage
from gdm.systems.substation.builder import SubstationBuilder
from gdm.systems.substation.components import CircuitBreaker
from gdm.systems.substation.enums import (
    CircuitDirection,
    EquipmentState,
    MeasurementPurpose,
    ProtocolType,
    ProtectionFunctionType,
)
from gdm.systems.substation.topology import SubstationSystem

_HV_LEVEL = "voltage-level-69kv"
_MV_LEVEL = "voltage-level-12kv"

_LON = -105.2000
_LAT = 39.7400


def _footprint(index: int) -> Location:
    """Deterministic geographic footprint coordinate for a station node."""

    column = index % 6
    row = index // 6
    return Location(
        x=_LON + (column - 2.5) * 0.0007,
        y=_LAT + (2.5 - row) * 0.0005,
        crs="EPSG:4326",
    )


def build_detailed_distribution_substation() -> SubstationSystem:
    """Build and return a detailed 69/12.47 kV distribution substation."""

    builder = SubstationBuilder(
        "detailed-distribution-substation",
        "69 kV / 12.47 kV distribution substation with protection and SCADA.",
        _HV_LEVEL,
        Voltage(69, "kilovolt"),
        coordinate_provider=_footprint,
    )
    builder.add_voltage_level(_MV_LEVEL, Voltage(12.47, "kilovolt"))

    builder.add_bus("hv-bus-1", _HV_LEVEL)
    builder.add_bus("hv-bus-2", _HV_LEVEL)
    builder.add_bus("mv-bus-1", _MV_LEVEL)
    builder.add_bus("mv-bus-2", _MV_LEVEL)

    # Sectionalizing bus ties -------------------------------------------------
    builder.add_breaker(
        "hv-bus-tie",
        "hv-bus-tie-bay",
        "hv-bus-1",
        "hv-bus-2",
        state=EquipmentState.OPEN,
        normal_state=EquipmentState.OPEN,
    )
    builder.add_breaker(
        "mv-bus-tie",
        "mv-bus-tie-bay",
        "mv-bus-1",
        "mv-bus-2",
        state=EquipmentState.OPEN,
        normal_state=EquipmentState.OPEN,
    )

    # Incoming 69 kV lines ----------------------------------------------------
    for number, hv_bus in ((1, "hv-bus-1"), (2, "hv-bus-2")):
        line_id = f"line-{number}"
        bay = f"{line_id}-bay"
        builder.add_external_circuit(
            line_id, bay, f"{line_id}-line-node", CircuitDirection.INCOMING, _HV_LEVEL
        )
        builder.add_line_trap(
            f"{line_id}-trap", bay, f"{line_id}-line-node", f"{line_id}-trap-node"
        )
        builder.add_disconnector(
            f"{line_id}-isolator", bay, f"{line_id}-trap-node", f"{line_id}-isolator-node"
        )
        line_ct = builder.add_instrument_transformer(
            f"{line_id}-ct",
            bay,
            f"{line_id}-isolator-node",
            f"{line_id}-ct-node",
            cores=[
                builder.add_instrument_core(
                    f"{line_id}-ct-protection-core", accuracy_class="5P20", burden_va=15
                )
            ],
        )
        breaker_from, _ = builder.add_breaker(
            f"{line_id}-breaker", bay, f"{line_id}-ct-node", hv_bus
        )
        builder.add_earthing_switch(f"{line_id}-earth-switch", bay, breaker_from)
        builder.add_surge_arrester(
            f"{line_id}-arrester", bay, hv_bus, mcov=Voltage(72, "kilovolt")
        )
        relay = builder.add_protection_ied(f"{line_id}-relay", builder.bays[bay])
        builder.add_protection_function(
            f"{line_id}-distance",
            ProtectionFunctionType.DISTANCE,
            relay,
            ansi_function_number="21",
            input_cores=line_ct.cores,
        )

    # Power transformers ------------------------------------------------------
    for number, (hv_bus, mv_bus) in ((1, ("hv-bus-1", "mv-bus-1")), (2, ("hv-bus-2", "mv-bus-2"))):
        xfmr_id = f"transformer-{number}"
        bay = f"{xfmr_id}-bay"
        _, hv_to = builder.add_breaker(f"{xfmr_id}-hv-breaker", bay, hv_bus, f"{xfmr_id}-hv-node")
        hv_ct = builder.add_instrument_transformer(
            f"{xfmr_id}-hv-ct",
            bay,
            f"{xfmr_id}-hv-node",
            f"{xfmr_id}-hv-ct-node",
            cores=[builder.add_instrument_core(f"{xfmr_id}-hv-ct-core", accuracy_class="5P20")],
        )
        hv_winding_bus = builder.add_node(f"{xfmr_id}-hv-winding-node", _HV_LEVEL)
        lv_winding_bus = builder.add_node(f"{xfmr_id}-lv-winding-node", _MV_LEVEL)
        transformer = builder.add_two_winding_transformer(
            xfmr_id, bay, hv_winding_bus, lv_winding_bus
        )
        builder.add_breaker(f"{xfmr_id}-lv-breaker", bay, f"{xfmr_id}-lv-winding-node", mv_bus)
        builder.add_earthing_switch(f"{xfmr_id}-earth-switch", bay, hv_to)
        relay = builder.add_protection_ied(f"{xfmr_id}-relay", builder.bays[bay])
        builder.add_setting_group(
            f"{xfmr_id}-relay-group",
            settings=[
                builder.add_setting(f"{xfmr_id}-87-pickup", "differential_pickup", 0.3, "pu")
            ],
            approved=True,
        )
        builder.add_protection_function(
            f"{xfmr_id}-differential",
            ProtectionFunctionType.DIFFERENTIAL,
            relay,
            ansi_function_number="87T",
            protects_equipment=[transformer],
            input_cores=hv_ct.cores,
            output_equipment=[transformer],
        )
        del hv_ct

    # MV voltage sensing and protection --------------------------------------
    for bus_id in ("mv-bus-1", "mv-bus-2"):
        builder.add_shunt_instrument_transformer(
            f"{bus_id}-vt", "mv-metering-bay", bus_id, instrument_type="voltage_transformer"
        )
        builder.add_surge_arrester(
            f"{bus_id}-arrester", "mv-protection-bay", bus_id, mcov=Voltage(10, "kilovolt")
        )

    # MV feeders --------------------------------------------------------------
    for number, mv_bus in ((1, "mv-bus-1"), (2, "mv-bus-1"), (3, "mv-bus-2"), (4, "mv-bus-2")):
        feeder_id = f"feeder-{number}"
        bay = f"{feeder_id}-bay"
        _, breaker_to = builder.add_breaker(
            f"{feeder_id}-breaker", bay, mv_bus, f"{feeder_id}-node"
        )
        feeder_ct = builder.add_instrument_transformer(
            f"{feeder_id}-ct",
            bay,
            f"{feeder_id}-node",
            f"{feeder_id}-ct-node",
            cores=[
                builder.add_instrument_core(f"{feeder_id}-protection-core", accuracy_class="5P20"),
                builder.add_instrument_core(
                    f"{feeder_id}-metering-core",
                    core_type="metering",
                    purpose=MeasurementPurpose.REVENUE,
                    accuracy_class="0.3B0.1",
                ),
            ],
        )
        _, line_node = builder.add_disconnector(
            f"{feeder_id}-disconnector", bay, f"{feeder_id}-ct-node", f"{feeder_id}-line-node"
        )
        builder.add_feeder(
            feeder_id,
            bay,
            f"{feeder_id}-line-node",
            bus=line_node,
            distribution_model_reference_id="detailed-distribution-feeders",
        )
        builder.add_earthing_switch(f"{feeder_id}-earth-switch", bay, breaker_to)

        breaker = builder.system.get_component(CircuitBreaker, f"{feeder_id}-breaker")
        relay = builder.add_protection_ied(f"{feeder_id}-relay", builder.bays[bay])
        builder.add_setting_group(
            f"{feeder_id}-relay-group",
            settings=[
                builder.add_setting(f"{feeder_id}-51-pickup", "pickup_current", 480, "ampere")
            ],
            approved=True,
        )
        function = builder.add_protection_function(
            f"{feeder_id}-overcurrent",
            ProtectionFunctionType.OVERCURRENT,
            relay,
            ansi_function_number="50/51",
            protects_equipment=[breaker],
            input_cores=feeder_ct.cores,
            output_equipment=[breaker],
        )
        builder.add_protection_scheme(
            f"{feeder_id}-scheme", zone=feeder_id, functions=[function], equipment=[breaker]
        )
        builder.add_metering_point(
            f"{feeder_id}-metering",
            MeasurementPurpose.REVENUE,
            breaker_to,
            f"{feeder_id}-meter",
            cores=[feeder_ct.cores[-1]],
            interval_seconds=900,
        )
        builder.add_power_quality_monitor(
            f"{feeder_id}-pq", line_node, monitored_phenomena=["harmonics", "voltage_sag"]
        )

    # Station automation and SCADA -------------------------------------------
    endpoint = builder.add_protocol_endpoint(
        "station-dnp3", ProtocolType.DNP3, "outstation-1", host="station-rtu", port=20000
    )
    station_ied = builder.add_automation_ied(
        "station-rtu",
        "station_gateway",
        manufacturer="example",
        model="rtu-3000",
        protocol_endpoints=[endpoint],
    )
    for point_address, breaker in enumerate(builder.system.get_components(CircuitBreaker)):
        signal = builder.add_semantic_signal(
            f"{breaker.name}-position",
            "status",
            breaker,
            engineering_description=f"{breaker.name} open/closed position",
        )
        builder.add_protocol_mapping(
            f"{breaker.name}-dnp3-position",
            signal,
            endpoint,
            ProtocolType.DNP3,
            "binary_input",
            str(point_address),
        )
    builder.add_scl_configuration(
        "station-scd",
        "SCD",
        "urn:example:substation:detailed:scd",
        revision="A",
        schema_version="2007B",
        ieds=[station_ied],
    )

    return builder.build()
