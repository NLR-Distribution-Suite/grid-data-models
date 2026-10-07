"""Reusable reference designs for common distribution substation arrangements."""

from enum import Enum
from math import cos, hypot, pi, sin
from typing import Callable

from gdm.systems.distribution import DistributionSystem
from gdm.systems.distribution.components import (
    DistributionBus,
    DistributionFeeder,
    DistributionSubstation,
    MatrixImpedanceBranch,
)
from gdm.systems.distribution.enums import Phase, VoltageTypes
from gdm.systems.distribution.equipment import MatrixImpedanceBranchEquipment
from gdm.systems.substation.components import CircuitBreaker, PowerTransformer
from gdm.systems.substation.enums import (
    CircuitDirection,
    EquipmentState,
    MeasurementPurpose,
    ProtectionFunctionType,
    ProtocolType,
)
from gdm.systems.substation.topology import BusbarSection, FeederBoundary
from gdm.systems.substation.substation_system import SubstationSystem
from gdm.systems.substation.builder import (
    DEFAULT_HV_VOLTAGE_LEVEL_ID as _VOLTAGE_LEVEL_HV_ID,
)
from gdm.systems.substation.builder import (
    DEFAULT_VOLTAGE_LEVEL_ID as _VOLTAGE_LEVEL_ID,
)
from gdm.systems.substation.builder import SubstationBuilder
from gdm.quantities import Distance, Voltage
from infrasys import Location


class SubstationLayout(str, Enum):
    """Bus arrangements included in the example collection."""

    SINGLE_BUS = "single_bus"
    SECTIONALIZED_SINGLE_BUS = "sectionalized_single_bus"
    MAIN_AND_TRANSFER = "main_and_transfer"
    DOUBLE_BUS_SINGLE_BREAKER = "double_bus_single_breaker"
    RING_BUS = "ring_bus"
    BREAKER_AND_A_HALF = "breaker_and_a_half"
    DOUBLE_BREAKER_DOUBLE_BUS = "double_breaker_double_bus"
    HV_MV_SINGLE_BUS = "hv_mv_single_bus"


_PHASES = [Phase.A, Phase.B, Phase.C]
_HV_VOLTAGE_LEVEL_ID = "voltage-level-hv"


def _transformer_targets(builder: SubstationBuilder, layout: SubstationLayout):
    if layout == SubstationLayout.SECTIONALIZED_SINGLE_BUS:
        names = ["bus-a", "bus-b"]
    elif layout == SubstationLayout.MAIN_AND_TRANSFER:
        names = ["main-bus" if "main-bus" in builder.nodes else "bus-a"]
    elif layout == SubstationLayout.RING_BUS:
        names = ["ring-node-1"]
    elif layout == SubstationLayout.HV_MV_SINGLE_BUS:
        names = ["mv-bus"]
    elif layout == SubstationLayout.SINGLE_BUS:
        names = ["bus-a"]
    else:
        names = ["bus-a", "bus-b"]
    return [builder.nodes[name] for name in names]


def _feeder_protection_breaker(
    builder: SubstationBuilder,
    layout: SubstationLayout,
    feeder_id: str,
    feeder_index: int,
) -> CircuitBreaker:
    if layout == SubstationLayout.RING_BUS:
        breaker_name = f"ring-breaker-{feeder_index + 1}"
    elif layout == SubstationLayout.BREAKER_AND_A_HALF:
        diameter_number = feeder_index // 2 + 1
        suffix = "breaker-a" if feeder_index % 2 == 0 else "breaker-middle"
        breaker_name = f"diameter-{diameter_number}-{suffix}"
        breaker_names = {item.name for item in builder.system.get_components(CircuitBreaker)}
        if f"{feeder_id}-middle-breaker" in breaker_names:
            breaker_name = f"{feeder_id}-middle-breaker"
    elif layout == SubstationLayout.DOUBLE_BREAKER_DOUBLE_BUS:
        breaker_name = f"{feeder_id}-bus-a-breaker"
    else:
        breaker_name = f"{feeder_id}-breaker"
    return builder.system.get_component(CircuitBreaker, breaker_name)


def _complete_reference_builder(
    builder: SubstationBuilder,
    layout: SubstationLayout,
    feeder_ids: list[str],
) -> None:
    """Add representative primary, protection, metering, and automation equipment."""

    if _HV_VOLTAGE_LEVEL_ID not in builder.voltage_levels:
        builder.add_voltage_level(_HV_VOLTAGE_LEVEL_ID, Voltage(69, "kilovolt"))
    hv_bus = builder.nodes.get("hv-bus") or builder.add_bus("hv-bus", _HV_VOLTAGE_LEVEL_ID)

    for number in (1, 2):
        line_id = f"incoming-line-{number}"
        bay_id = f"{line_id}-bay"
        line_node = f"{line_id}-line-node"
        trap_node = f"{line_id}-trap-node"
        isolator_node = f"{line_id}-isolator-node"
        ct_node = f"{line_id}-ct-node"
        builder.add_external_circuit(
            line_id, bay_id, line_node, CircuitDirection.INCOMING, _HV_VOLTAGE_LEVEL_ID
        )
        builder.add_line_trap(
            f"{line_id}-trap",
            bay_id,
            line_node,
            trap_node,
            voltage_level_id=_HV_VOLTAGE_LEVEL_ID,
        )
        builder.add_disconnector(
            f"{line_id}-isolator",
            bay_id,
            trap_node,
            isolator_node,
            voltage_level_id=_HV_VOLTAGE_LEVEL_ID,
        )
        cores = [
            builder.add_instrument_core(
                f"{line_id}-protection-core", accuracy_class="5P20", burden_va=15
            ),
            builder.add_instrument_core(
                f"{line_id}-metering-core",
                core_type="metering",
                purpose=MeasurementPurpose.REVENUE,
                accuracy_class="0.3B0.1",
            ),
        ]
        ct = builder.add_instrument_transformer(
            f"{line_id}-ct",
            bay_id,
            isolator_node,
            ct_node,
            cores=cores,
            voltage_level_id=_HV_VOLTAGE_LEVEL_ID,
        )
        breaker_from, _ = builder.add_breaker(
            f"{line_id}-breaker",
            bay_id,
            ct_node,
            hv_bus.name,
            voltage_level_id=_HV_VOLTAGE_LEVEL_ID,
        )
        builder.add_earthing_switch(f"{line_id}-earth-switch", bay_id, breaker_from)
        relay = builder.add_protection_ied(f"{line_id}-relay", builder.bays[bay_id])
        function = builder.add_protection_function(
            f"{line_id}-distance",
            ProtectionFunctionType.DISTANCE,
            relay,
            ansi_function_number="21",
            input_cores=ct.cores,
            output_equipment=[builder.system.get_component(CircuitBreaker, f"{line_id}-breaker")],
        )
        builder.add_protection_scheme(
            f"{line_id}-scheme",
            zone=line_id,
            functions=[function],
            equipment=[builder.system.get_component(CircuitBreaker, f"{line_id}-breaker")],
        )

    builder.add_surge_arrester(
        "hv-bus-arrester", "hv-bus-protection-bay", hv_bus.name, mcov=Voltage(72, "kilovolt")
    )

    for number, target_bus in enumerate(_transformer_targets(builder, layout), start=1):
        transformer_id = f"transformer-{number}"
        bay_id = f"{transformer_id}-bay"
        hv_node = f"{transformer_id}-hv-node"
        hv_winding_node = f"{transformer_id}-hv-winding-node"
        lv_winding_node = f"{transformer_id}-lv-winding-node"
        _, breaker_side = builder.add_breaker(
            f"{transformer_id}-hv-breaker",
            bay_id,
            hv_bus.name,
            hv_node,
            voltage_level_id=_HV_VOLTAGE_LEVEL_ID,
        )
        hv_ct = builder.add_instrument_transformer(
            f"{transformer_id}-hv-ct",
            bay_id,
            hv_node,
            hv_winding_node,
            cores=[
                builder.add_instrument_core(
                    f"{transformer_id}-differential-core", accuracy_class="5P20"
                )
            ],
            voltage_level_id=_HV_VOLTAGE_LEVEL_ID,
        )
        builder.add_node(lv_winding_node, target_bus.voltage_level.name)
        transformer = builder.add_two_winding_transformer(
            transformer_id,
            bay_id,
            builder.nodes[hv_winding_node],
            builder.nodes[lv_winding_node],
        )
        builder.add_breaker(
            f"{transformer_id}-lv-breaker",
            bay_id,
            lv_winding_node,
            target_bus.name,
            voltage_level_id=target_bus.voltage_level.name,
        )
        builder.add_earthing_switch(f"{transformer_id}-hv-earth-switch", bay_id, breaker_side)
        builder.add_earthing_switch(
            f"{transformer_id}-lv-earth-switch", bay_id, builder.nodes[lv_winding_node]
        )
        relay = builder.add_protection_ied(f"{transformer_id}-relay", builder.bays[bay_id])
        settings = builder.add_setting_group(
            f"{transformer_id}-relay-group",
            settings=[
                builder.add_setting(
                    f"{transformer_id}-87-pickup", "differential_pickup", 0.3, "pu"
                )
            ],
            approved=True,
        )
        function = builder.add_protection_function(
            f"{transformer_id}-differential",
            ProtectionFunctionType.DIFFERENTIAL,
            relay,
            ansi_function_number="87T",
            protects_equipment=[transformer],
            input_cores=hv_ct.cores,
            output_equipment=[transformer],
            setting_groups=[settings],
        )
        builder.add_protection_scheme(
            f"{transformer_id}-scheme",
            zone=transformer_id,
            functions=[function],
            equipment=[transformer],
        )

    mv_busbars = [
        bus
        for bus in builder.nodes.values()
        if bus.length is not None and bus.voltage_level.name != _HV_VOLTAGE_LEVEL_ID
    ]
    for bus in mv_busbars:
        builder.add_shunt_instrument_transformer(
            f"{bus.name}-vt",
            f"{bus.name}-metering-bay",
            bus.name,
            instrument_type="voltage_transformer",
        )
        builder.add_surge_arrester(
            f"{bus.name}-arrester",
            f"{bus.name}-protection-bay",
            bus.name,
            mcov=Voltage(10, "kilovolt"),
        )

    for feeder_index, feeder_id in enumerate(feeder_ids):
        boundary = builder.system.get_component(FeederBoundary, f"{feeder_id}-boundary")
        original_bus = boundary.bus
        voltage_level_id = original_bus.voltage_level.name
        ct_node = builder.add_node(f"{feeder_id}-ct-node", voltage_level_id)
        line_node = builder.add_node(f"{feeder_id}-line-node", voltage_level_id)
        cores = [
            builder.add_instrument_core(f"{feeder_id}-protection-core", accuracy_class="5P20"),
            builder.add_instrument_core(
                f"{feeder_id}-metering-core",
                core_type="metering",
                purpose=MeasurementPurpose.REVENUE,
                accuracy_class="0.3B0.1",
            ),
        ]
        ct = builder.add_instrument_transformer(
            f"{feeder_id}-ct",
            boundary.bay.name,
            original_bus.name,
            ct_node.name,
            cores=cores,
            voltage_level_id=voltage_level_id,
        )
        builder.add_disconnector(
            f"{feeder_id}-line-disconnector",
            boundary.bay.name,
            ct_node.name,
            line_node.name,
            voltage_level_id=voltage_level_id,
        )
        builder.add_earthing_switch(f"{feeder_id}-earth-switch", boundary.bay.name, ct_node)
        boundary.bus = line_node
        boundary.voltage_level = line_node.voltage_level

        breaker = _feeder_protection_breaker(builder, layout, feeder_id, feeder_index)
        relay = builder.add_protection_ied(f"{feeder_id}-relay", boundary.bay)
        setting_group = builder.add_setting_group(
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
            input_cores=ct.cores,
            output_equipment=[breaker],
            setting_groups=[setting_group],
        )
        builder.add_protection_scheme(
            f"{feeder_id}-scheme",
            zone=feeder_id,
            functions=[function],
            equipment=[breaker],
        )
        builder.add_metering_point(
            f"{feeder_id}-revenue-metering",
            MeasurementPurpose.REVENUE,
            line_node,
            f"{feeder_id}-revenue-meter",
            cores=[ct.cores[-1]],
            interval_seconds=900,
        )
        builder.add_power_quality_monitor(
            f"{feeder_id}-power-quality",
            line_node,
            monitored_phenomena=["harmonics", "voltage_sag"],
        )

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
    for address, breaker in enumerate(builder.system.get_components(CircuitBreaker)):
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
            str(address),
        )
    builder.add_scl_configuration(
        "station-scd",
        "SCD",
        f"urn:example:substation:{builder.system.name}:scd",
        revision="A",
        schema_version="2007B",
        ieds=[station_ied],
    )


def _position_reference_layout(  # noqa: C901
    system: SubstationSystem,
    layout: SubstationLayout,
    feeder_ids: list[str],
) -> SubstationSystem:
    """Assign textbook-style schematic coordinates from circuit roles."""

    feeder_count = len(feeder_ids)
    feeder_x = {
        feeder_id: (index - (feeder_count - 1) / 2) * 2.5
        for index, feeder_id in enumerate(feeder_ids)
    }
    coordinates: dict[str, tuple[float, float]] = {}
    ring_positions: list[tuple[float, float]] = []

    if layout == SubstationLayout.SINGLE_BUS:
        coordinates["bus-a"] = (0.0, 0.0)
        for feeder_id, x_value in feeder_x.items():
            coordinates[f"{feeder_id}-node"] = (x_value, -2.5)
    elif layout == SubstationLayout.SECTIONALIZED_SINGLE_BUS:
        coordinates.update({"bus-a": (-1.25, 0.0), "bus-b": (1.25, 0.0)})
        for index, (feeder_id, x_value) in enumerate(feeder_x.items()):
            coordinates[f"{feeder_id}-node"] = (x_value, -2.5)
            if index == 0:
                coordinates["bus-tie-bay"] = (0.0, 0.0)
    elif layout == SubstationLayout.MAIN_AND_TRANSFER:
        coordinates.update(
            {
                "bus-a": (0.0, 2.5),
                "bus-b": (0.0, -2.5),
                "main-bus": (0.0, 2.5),
                "transfer-bus": (0.0, -2.5),
            }
        )
        coordinates["transfer-node"] = (0.0, -1.0)
        coordinates["transfer-breaker-node"] = (0.0, -1.0)
        for feeder_id, x_value in feeder_x.items():
            coordinates[f"{feeder_id}-node"] = (x_value, -1.0)
    elif layout == SubstationLayout.DOUBLE_BUS_SINGLE_BREAKER:
        coordinates.update({"bus-a": (0.0, 2.5), "bus-b": (0.0, 0.0)})
        for feeder_id, x_value in feeder_x.items():
            coordinates[f"{feeder_id}-breaker-node"] = (x_value, 1.25)
            outward = -1.5 if x_value < 0 else 1.5
            coordinates[f"{feeder_id}-node"] = (x_value + outward, 1.25)
    elif layout == SubstationLayout.DOUBLE_BREAKER_DOUBLE_BUS:
        coordinates.update({"bus-a": (0.0, 2.5), "bus-b": (0.0, 0.0)})
        for feeder_id, x_value in feeder_x.items():
            coordinates[f"{feeder_id}-circuit-node"] = (x_value, 1.25)
            outward = -1.5 if x_value < 0 else 1.5
            coordinates[f"{feeder_id}-node"] = (x_value + outward, 1.25)
    elif layout == SubstationLayout.BREAKER_AND_A_HALF:
        coordinates.update({"bus-a": (0.0, 3.0), "bus-b": (0.0, -3.0)})
        for index, feeder_id in enumerate(feeder_ids):
            diameter = -3.5 if index < 2 else 3.5
            circuit_a = f"diameter-{index // 2 + 1}-circuit-node-a"
            circuit_b = f"diameter-{index // 2 + 1}-circuit-node-b"
            coordinates[circuit_a] = (diameter, 1.0)
            coordinates[circuit_b] = (diameter, -1.0)
            boundary_y = 1.0 if index % 2 == 0 else -1.0
            outward = -1 if index < 2 else 1
            coordinates[f"{feeder_id}-node"] = (diameter + outward * 1.5, boundary_y)
    elif layout == SubstationLayout.RING_BUS:
        ring_count = max(2, feeder_count)
        if ring_count == 4:
            ring_positions = [(-3.0, 2.0), (3.0, 2.0), (3.0, -2.0), (-3.0, -2.0)]
        else:
            ring_positions = [
                (3.0 * cos(2 * pi * index / ring_count), 3.0 * sin(2 * pi * index / ring_count))
                for index in range(ring_count)
            ]
        for index, feeder_id in enumerate(feeder_ids):
            ring_node = f"ring-node-{index + 1}"
            ring_x, ring_y = ring_positions[index % len(ring_positions)]
            coordinates[ring_node] = (ring_x, ring_y)
            radius = hypot(ring_x, ring_y)
            coordinates[f"{feeder_id}-node"] = (
                ring_x + ring_x / radius * 1.5,
                ring_y + ring_y / radius * 1.5,
            )
    elif layout == SubstationLayout.HV_MV_SINGLE_BUS:
        coordinates.update({"hv-bus": (0.0, 3.0), "mv-bus": (0.0, 0.0)})
        for feeder_id, x_value in feeder_x.items():
            coordinates[f"{feeder_id}-node"] = (x_value, -2.5)

    coordinates["hv-bus"] = (0.0, 8.0)
    for number, x_value in ((1, -2.0), (2, 2.0)):
        line_id = f"incoming-line-{number}"
        coordinates[f"{line_id}-line-node"] = (x_value, 11.0)
        coordinates[f"{line_id}-trap-node"] = (x_value, 10.0)
        coordinates[f"{line_id}-isolator-node"] = (x_value, 9.0)
        coordinates[f"{line_id}-ct-node"] = (x_value, 8.0)

    transformers = list(system.get_components(PowerTransformer))
    for index, transformer in enumerate(transformers):
        transformer_id = f"transformer-{index + 1}"
        target_bus = next(
            bus
            for bus in system.get_component(CircuitBreaker, f"{transformer_id}-lv-breaker").buses
            if bus.name != f"{transformer_id}-lv-winding-node"
        )
        if layout == SubstationLayout.RING_BUS:
            x_value, target_y = coordinates[target_bus.name]
            winding_y = target_y + (2.5 if target_y >= 0 else -2.5)
        elif layout in {
            SubstationLayout.BREAKER_AND_A_HALF,
            SubstationLayout.DOUBLE_BUS_SINGLE_BREAKER,
            SubstationLayout.DOUBLE_BREAKER_DOUBLE_BUS,
        }:
            transformer_extent = 8.5 if layout == SubstationLayout.BREAKER_AND_A_HALF else 7.0
            x_value = -transformer_extent if index == 0 else transformer_extent
            winding_y = 4.5
        else:
            x_value = -4.5 if index == 0 else 4.5
            winding_y = 4.5
        coordinates[f"{transformer_id}-hv-node"] = (x_value, 8.0)
        coordinates[f"{transformer_id}-hv-winding-node"] = (x_value, 7.0)
        coordinates[f"{transformer_id}-lv-winding-node"] = (x_value, winding_y)

    for feeder_index, feeder_id in enumerate(feeder_ids):
        x_value, y_value = coordinates.get(f"{feeder_id}-node", (0.0, -2.5))
        if layout == SubstationLayout.RING_BUS:
            ring_x, ring_y = coordinates[f"ring-node-{feeder_index + 1}"]
            radius = hypot(ring_x, ring_y)
            direction = (ring_x / radius, ring_y / radius)
            coordinates[f"{feeder_id}-ct-node"] = (
                ring_x + direction[0] * 2.25,
                ring_y + direction[1] * 2.25,
            )
            coordinates[f"{feeder_id}-line-node"] = (
                ring_x + direction[0] * 3.0,
                ring_y + direction[1] * 3.0,
            )
        elif layout == SubstationLayout.BREAKER_AND_A_HALF:
            outward = -1 if feeder_index < 2 else 1
            coordinates[f"{feeder_id}-ct-node"] = (x_value + outward, y_value)
            coordinates[f"{feeder_id}-line-node"] = (x_value + outward * 2, y_value)
        elif layout in {
            SubstationLayout.DOUBLE_BUS_SINGLE_BREAKER,
            SubstationLayout.DOUBLE_BREAKER_DOUBLE_BUS,
        }:
            outward = -1 if x_value < 0 else 1
            coordinates[f"{feeder_id}-ct-node"] = (x_value + outward, y_value)
            coordinates[f"{feeder_id}-line-node"] = (x_value + outward * 2, y_value)
        else:
            coordinates[f"{feeder_id}-ct-node"] = (x_value, y_value - 1.0)
            coordinates[f"{feeder_id}-line-node"] = (x_value, y_value - 2.0)

    for bus in system.get_components(BusbarSection):
        if bus.name in coordinates:
            x_value, y_value = coordinates[bus.name]
        elif "ring-node-" in bus.name:
            ring_index = int(bus.name.rsplit("-", 1)[1]) - 1
            x_value, y_value = ring_positions[ring_index % len(ring_positions)]
        else:
            feeder_id = next(
                (feeder for feeder in feeder_ids if bus.name.startswith(f"{feeder}-")),
                None,
            )
            x_value = feeder_x.get(feeder_id, 0.0)
            if layout == SubstationLayout.MAIN_AND_TRANSFER:
                y_value = -1.0
            elif layout in {
                SubstationLayout.DOUBLE_BUS_SINGLE_BREAKER,
                SubstationLayout.DOUBLE_BREAKER_DOUBLE_BUS,
            }:
                y_value = (
                    1.25 if "breaker-node" in bus.name or "circuit-node" in bus.name else -1.25
                )
            elif layout == SubstationLayout.BREAKER_AND_A_HALF:
                y_value = 1.0 if bus.name.endswith("node-a") else -1.0
            else:
                y_value = -2.5
        if bus.coordinate is None:
            bus.coordinate = Location(
                name=f"{system.name}-{bus.name}-schematic-position",
                x=x_value,
                y=y_value,
                crs="EPSG:3857",
            )
        if not system.has_component(bus.coordinate):
            system.add_component(bus.coordinate)
    return system


def build_parameterized_substation(  # noqa: C901
    name: str,
    feeder_ids: list[str],
    layout: SubstationLayout | str = SubstationLayout.SINGLE_BUS,
    coordinate_provider: Callable[[int], Location] | None = None,
) -> SubstationSystem:
    """Build a reference layout with caller-provided feeder IDs and coordinates."""

    selected_layout = SubstationLayout(layout)
    builder = SubstationBuilder(
        name,
        f"Parameterized {selected_layout.value} distribution substation example.",
        coordinate_provider=coordinate_provider,
    )
    feeder_ids = list(dict.fromkeys(feeder_ids))

    if selected_layout == SubstationLayout.HV_MV_SINGLE_BUS:
        builder.add_voltage_level(_VOLTAGE_LEVEL_HV_ID, Voltage(69, "kilovolt"))
        builder.add_bus("hv-bus", _VOLTAGE_LEVEL_HV_ID)
        builder.add_bus("mv-bus")
        bus_ids = ["mv-bus"]
    elif selected_layout in {
        SubstationLayout.SECTIONALIZED_SINGLE_BUS,
        SubstationLayout.MAIN_AND_TRANSFER,
        SubstationLayout.DOUBLE_BUS_SINGLE_BREAKER,
        SubstationLayout.BREAKER_AND_A_HALF,
        SubstationLayout.DOUBLE_BREAKER_DOUBLE_BUS,
    }:
        builder.add_bus("bus-a")
        builder.add_bus("bus-b")
        bus_ids = ["bus-a", "bus-b"]
        if selected_layout == SubstationLayout.SECTIONALIZED_SINGLE_BUS:
            builder.add_breaker(
                "bus-tie-breaker",
                "bus-tie-bay",
                "bus-a",
                "bus-b",
                state=EquipmentState.OPEN,
                normal_state=EquipmentState.OPEN,
            )
        elif selected_layout == SubstationLayout.MAIN_AND_TRANSFER:
            builder.add_breaker(
                "transfer-breaker",
                "transfer-bay",
                "bus-b",
                "transfer-node",
                state=EquipmentState.OPEN,
                normal_state=EquipmentState.OPEN,
            )
    elif selected_layout == SubstationLayout.RING_BUS:
        bus_ids = [f"ring-node-{number}" for number in range(1, max(2, len(feeder_ids)) + 1)]
        for bus_id in bus_ids:
            builder.add_bus(bus_id)
        for index, bus_id in enumerate(bus_ids):
            builder.add_breaker(
                f"ring-breaker-{index + 1}",
                f"ring-breaker-{index + 1}-bay",
                bus_id,
                bus_ids[(index + 1) % len(bus_ids)],
            )
    else:
        builder.add_bus("bus-a")
        bus_ids = ["bus-a"]
    for index, feeder_id in enumerate(feeder_ids):
        bay_id = f"{feeder_id}-bay"
        feeder_node = f"{feeder_id}-node"
        bus_id = bus_ids[index % len(bus_ids)]
        if selected_layout == SubstationLayout.RING_BUS:
            builder.add_feeder(feeder_id, bay_id, bus_id, with_disconnector=True)
        elif selected_layout == SubstationLayout.MAIN_AND_TRANSFER:
            _, breaker_to = builder.add_breaker(
                f"{feeder_id}-breaker", bay_id, "bus-a", feeder_node
            )
            builder.add_disconnector(
                f"{feeder_id}-transfer-disconnector",
                bay_id,
                "transfer-node",
                feeder_node,
                state=EquipmentState.OPEN,
                normal_state=EquipmentState.OPEN,
            )
            builder.add_feeder(feeder_id, bay_id, feeder_node, bus=breaker_to)
        elif selected_layout == SubstationLayout.DOUBLE_BUS_SINGLE_BREAKER:
            breaker_node = f"{feeder_id}-breaker-node"
            _, breaker_to = builder.add_breaker(
                f"{feeder_id}-breaker", bay_id, breaker_node, feeder_node
            )
            builder.add_disconnector(
                f"{feeder_id}-bus-a-disconnector", bay_id, "bus-a", breaker_node
            )
            builder.add_disconnector(
                f"{feeder_id}-bus-b-disconnector",
                bay_id,
                "bus-b",
                breaker_node,
                state=EquipmentState.OPEN,
                normal_state=EquipmentState.OPEN,
            )
            builder.add_feeder(feeder_id, bay_id, feeder_node, bus=breaker_to)
        elif selected_layout == SubstationLayout.BREAKER_AND_A_HALF:
            circuit_node_a = f"{feeder_id}-circuit-node-a"
            circuit_node_b = f"{feeder_id}-circuit-node-b"
            builder.add_breaker(f"{feeder_id}-bus-a-breaker", bay_id, "bus-a", circuit_node_a)
            builder.add_breaker(
                f"{feeder_id}-middle-breaker", bay_id, circuit_node_a, circuit_node_b
            )
            builder.add_breaker(f"{feeder_id}-bus-b-breaker", bay_id, circuit_node_b, "bus-b")
            builder.add_feeder(feeder_id, bay_id, circuit_node_a, with_disconnector=True)
        elif selected_layout == SubstationLayout.DOUBLE_BREAKER_DOUBLE_BUS:
            circuit_node = f"{feeder_id}-circuit-node"
            builder.add_breaker(f"{feeder_id}-bus-a-breaker", bay_id, "bus-a", circuit_node)
            builder.add_breaker(f"{feeder_id}-bus-b-breaker", bay_id, circuit_node, "bus-b")
            builder.add_feeder(feeder_id, bay_id, feeder_node, with_disconnector=True)
        else:
            _, breaker_to = builder.add_breaker(
                f"{feeder_id}-breaker", bay_id, bus_id, feeder_node
            )
            builder.add_feeder(feeder_id, bay_id, feeder_node, bus=breaker_to)
    _complete_reference_builder(builder, selected_layout, feeder_ids)
    return _position_reference_layout(builder.build(), selected_layout, feeder_ids)


def single_bus_substation() -> SubstationSystem:
    """One common bus with three feeder breakers."""

    builder = SubstationBuilder(
        "single-bus-substation",
        "Distribution substation with one common bus and three feeder bays.",
    )
    builder.add_bus("bus-a")
    for feeder_number in range(1, 4):
        feeder_id = f"feeder-{feeder_number}"
        _, breaker_to = builder.add_breaker(
            f"{feeder_id}-breaker",
            f"{feeder_id}-bay",
            "bus-a",
            f"{feeder_id}-node",
        )
        builder.add_feeder(
            feeder_id,
            f"{feeder_id}-bay",
            f"{feeder_id}-node",
            bus=breaker_to,
        )
    feeder_ids = [f"feeder-{number}" for number in range(1, 4)]
    _complete_reference_builder(builder, SubstationLayout.SINGLE_BUS, feeder_ids)
    return _position_reference_layout(builder.build(), SubstationLayout.SINGLE_BUS, feeder_ids)


def sectionalized_single_bus_substation() -> SubstationSystem:
    """Two bus sections connected by a normally open bus-tie breaker."""

    builder = SubstationBuilder(
        "sectionalized-single-bus-substation",
        "Distribution substation with two bus sections and a bus-tie breaker.",
    )
    builder.add_bus("bus-a")
    builder.add_bus("bus-b")
    builder.add_breaker(
        "bus-tie-breaker",
        "bus-tie-bay",
        "bus-a",
        "bus-b",
        state=EquipmentState.OPEN,
        normal_state=EquipmentState.OPEN,
    )
    for feeder_number, bus_id in ((1, "bus-a"), (2, "bus-a"), (3, "bus-b"), (4, "bus-b")):
        feeder_id = f"feeder-{feeder_number}"
        _, breaker_to = builder.add_breaker(
            f"{feeder_id}-breaker",
            f"{feeder_id}-bay",
            bus_id,
            f"{feeder_id}-node",
        )
        builder.add_feeder(
            feeder_id,
            f"{feeder_id}-bay",
            f"{feeder_id}-node",
            bus=breaker_to,
        )
    feeder_ids = [f"feeder-{number}" for number in range(1, 5)]
    _complete_reference_builder(builder, SubstationLayout.SECTIONALIZED_SINGLE_BUS, feeder_ids)
    return _position_reference_layout(
        builder.build(),
        SubstationLayout.SECTIONALIZED_SINGLE_BUS,
        feeder_ids,
    )


def main_and_transfer_substation() -> SubstationSystem:
    """Main bus with a transfer bus and a normally open transfer breaker."""

    builder = SubstationBuilder(
        "main-and-transfer-substation",
        "Distribution substation with a main bus, transfer bus, and transfer breaker.",
    )
    builder.add_bus("main-bus")
    builder.add_bus("transfer-bus")
    builder.add_breaker(
        "transfer-breaker",
        "transfer-bay",
        "transfer-bus",
        "transfer-breaker-node",
        state=EquipmentState.OPEN,
        normal_state=EquipmentState.OPEN,
    )
    for feeder_number in (1, 2):
        feeder_id = f"feeder-{feeder_number}"
        bay_id = f"{feeder_id}-bay"
        feeder_node = f"{feeder_id}-node"
        _, breaker_to = builder.add_breaker(
            f"{feeder_id}-breaker", bay_id, "main-bus", feeder_node
        )
        builder.add_disconnector(
            f"{feeder_id}-transfer-disconnector",
            bay_id,
            "transfer-breaker-node",
            feeder_node,
            state=EquipmentState.OPEN,
            normal_state=EquipmentState.OPEN,
        )
        builder.add_feeder(feeder_id, bay_id, feeder_node, bus=breaker_to)
    feeder_ids = ["feeder-1", "feeder-2"]
    _complete_reference_builder(builder, SubstationLayout.MAIN_AND_TRANSFER, feeder_ids)
    return _position_reference_layout(
        builder.build(), SubstationLayout.MAIN_AND_TRANSFER, feeder_ids
    )


def double_bus_single_breaker_substation() -> SubstationSystem:
    """Two selectable buses with one breaker and two bus disconnectors per feeder."""

    builder = SubstationBuilder(
        "double-bus-single-breaker-substation",
        "Distribution substation with two selectable buses and one breaker per feeder.",
    )
    builder.add_bus("bus-a")
    builder.add_bus("bus-b")
    for feeder_number in (1, 2):
        feeder_id = f"feeder-{feeder_number}"
        bay_id = f"{feeder_id}-bay"
        breaker_node = f"{feeder_id}-breaker-node"
        _, breaker_to = builder.add_breaker(
            f"{feeder_id}-breaker",
            bay_id,
            breaker_node,
            f"{feeder_id}-node",
        )
        builder.add_disconnector(
            f"{feeder_id}-bus-a-disconnector",
            bay_id,
            "bus-a",
            breaker_node,
        )
        builder.add_disconnector(
            f"{feeder_id}-bus-b-disconnector",
            bay_id,
            "bus-b",
            breaker_node,
            state=EquipmentState.OPEN,
            normal_state=EquipmentState.OPEN,
        )
        builder.add_feeder(
            feeder_id,
            bay_id,
            f"{feeder_id}-node",
            bus=breaker_to,
        )
    feeder_ids = ["feeder-1", "feeder-2"]
    _complete_reference_builder(builder, SubstationLayout.DOUBLE_BUS_SINGLE_BREAKER, feeder_ids)
    return _position_reference_layout(
        builder.build(),
        SubstationLayout.DOUBLE_BUS_SINGLE_BREAKER,
        feeder_ids,
    )


def ring_bus_substation() -> SubstationSystem:
    """Four-breaker ring bus with one feeder circuit at each ring position."""

    builder = SubstationBuilder(
        "ring-bus-substation",
        "Distribution substation with four breakers arranged in a ring bus.",
    )
    ring_nodes = [f"ring-node-{number}" for number in range(1, 5)]
    for node_id in ring_nodes:
        builder.add_bus(node_id)
    for index, node_id in enumerate(ring_nodes):
        next_node = ring_nodes[(index + 1) % len(ring_nodes)]
        builder.add_breaker(
            f"ring-breaker-{index + 1}",
            f"ring-breaker-{index + 1}-bay",
            node_id,
            next_node,
        )
        feeder_id = f"feeder-{index + 1}"
        builder.add_feeder(
            feeder_id,
            f"{feeder_id}-bay",
            node_id,
            with_disconnector=True,
        )
    feeder_ids = [f"feeder-{number}" for number in range(1, 5)]
    _complete_reference_builder(builder, SubstationLayout.RING_BUS, feeder_ids)
    return _position_reference_layout(builder.build(), SubstationLayout.RING_BUS, feeder_ids)


def breaker_and_a_half_substation() -> SubstationSystem:
    """Two parallel three-breaker diameters serving four circuits."""

    builder = SubstationBuilder(
        "breaker-and-a-half-substation",
        "Distribution substation with two buses and two parallel three-breaker diameters.",
    )
    builder.add_bus("bus-a")
    builder.add_bus("bus-b")
    for diameter_number in (1, 2):
        bay_id = f"diameter-{diameter_number}-bay"
        circuit_node_a = f"diameter-{diameter_number}-circuit-node-a"
        circuit_node_b = f"diameter-{diameter_number}-circuit-node-b"
        builder.add_breaker(
            f"diameter-{diameter_number}-breaker-a",
            bay_id,
            "bus-a",
            circuit_node_a,
        )
        builder.add_breaker(
            f"diameter-{diameter_number}-breaker-middle",
            bay_id,
            circuit_node_a,
            circuit_node_b,
        )
        builder.add_breaker(
            f"diameter-{diameter_number}-breaker-b",
            bay_id,
            circuit_node_b,
            "bus-b",
        )
        for circuit_number, circuit_node in (
            (1, circuit_node_a),
            (2, circuit_node_b),
        ):
            feeder_number = (diameter_number - 1) * 2 + circuit_number
            builder.add_feeder(
                f"feeder-{feeder_number}",
                f"feeder-{feeder_number}-bay",
                circuit_node,
                with_disconnector=True,
            )
    feeder_ids = [f"feeder-{number}" for number in range(1, 5)]
    _complete_reference_builder(builder, SubstationLayout.BREAKER_AND_A_HALF, feeder_ids)
    return _position_reference_layout(
        builder.build(),
        SubstationLayout.BREAKER_AND_A_HALF,
        feeder_ids,
    )


def double_breaker_double_bus_substation() -> SubstationSystem:
    """Two buses with two breakers assigned to each feeder circuit."""

    builder = SubstationBuilder(
        "double-breaker-double-bus-substation",
        "Distribution substation with two buses and two breakers per feeder.",
    )
    builder.add_bus("bus-a")
    builder.add_bus("bus-b")
    for feeder_number in (1, 2):
        feeder_id = f"feeder-{feeder_number}"
        bay_id = f"{feeder_id}-bay"
        circuit_node = f"{feeder_id}-circuit-node"
        builder.add_breaker(
            f"{feeder_id}-bus-a-breaker",
            bay_id,
            "bus-a",
            circuit_node,
        )
        builder.add_breaker(
            f"{feeder_id}-bus-b-breaker",
            bay_id,
            circuit_node,
            "bus-b",
        )
        builder.add_feeder(feeder_id, bay_id, circuit_node, with_disconnector=True)
    feeder_ids = ["feeder-1", "feeder-2"]
    _complete_reference_builder(builder, SubstationLayout.DOUBLE_BREAKER_DOUBLE_BUS, feeder_ids)
    return _position_reference_layout(
        builder.build(),
        SubstationLayout.DOUBLE_BREAKER_DOUBLE_BUS,
        feeder_ids,
    )


def hv_mv_single_bus_substation() -> SubstationSystem:
    """69 kV source bus feeding a 12.47 kV bus through a station transformer."""

    builder = SubstationBuilder(
        "hv-mv-single-bus-substation",
        "Distribution substation with 69 kV and 12.47 kV buses joined by a transformer.",
    )
    builder.add_voltage_level(_VOLTAGE_LEVEL_HV_ID, Voltage(69, "kilovolt"))
    builder.add_bus("hv-bus", _VOLTAGE_LEVEL_HV_ID)
    builder.add_bus("mv-bus", _VOLTAGE_LEVEL_ID)
    for feeder_number in range(1, 4):
        feeder_id = f"feeder-{feeder_number}"
        bay_id = f"{feeder_id}-bay"
        _, breaker_to = builder.add_breaker(
            f"{feeder_id}-breaker",
            bay_id,
            "mv-bus",
            f"{feeder_id}-node",
        )
        builder.add_feeder(
            feeder_id,
            bay_id,
            f"{feeder_id}-node",
            bus=breaker_to,
            distribution_model_reference_id="hv-mv-distribution-feeders",
        )
    feeder_ids = [f"feeder-{number}" for number in range(1, 4)]
    _complete_reference_builder(builder, SubstationLayout.HV_MV_SINGLE_BUS, feeder_ids)
    return _position_reference_layout(
        builder.build(), SubstationLayout.HV_MV_SINGLE_BUS, feeder_ids
    )


def hv_mv_substation_with_distribution_feeders() -> tuple[SubstationSystem, DistributionSystem]:
    """Build a station and its three downstream radial distribution feeders.

    The systems intentionally remain separate. ``FeederBoundary.feeder_id``
    matches ``DistributionFeeder.name`` and its model reference identifies the
    downstream ``DistributionSystem``.
    """

    substation_system = hv_mv_single_bus_substation()
    distribution_system = DistributionSystem(
        name="hv-mv-distribution-feeders",
        auto_add_composed_components=True,
    )
    feeders = [DistributionFeeder(name=f"feeder-{number}") for number in range(1, 4)]
    distribution_substation = DistributionSubstation(
        name="substation",
        feeders=feeders,
    )
    distribution_system.add_component(distribution_substation)

    for index, feeder in enumerate(feeders):
        source_x = -105.1770 + index * 0.0010
        source_y = 39.7420
        source_bus = DistributionBus(
            name=f"{feeder.name}-source-bus",
            voltage_type=VoltageTypes.LINE_TO_LINE,
            phases=_PHASES,
            rated_voltage=Voltage(12.47, "kilovolt"),
            substation=distribution_substation,
            feeder=feeder,
            coordinate=Location(x=source_x, y=source_y, crs="EPSG:4326"),
        )
        load_bus = DistributionBus(
            name=f"{feeder.name}-load-bus",
            voltage_type=VoltageTypes.LINE_TO_LINE,
            phases=_PHASES,
            rated_voltage=Voltage(12.47, "kilovolt"),
            substation=distribution_substation,
            feeder=feeder,
            coordinate=Location(x=source_x, y=source_y + 0.0060, crs="EPSG:4326"),
        )
        branch = MatrixImpedanceBranch(
            name=f"{feeder.name}-main-line",
            buses=[source_bus, load_bus],
            length=Distance(1 + index * 0.25, "mile"),
            phases=_PHASES,
            substation=distribution_substation,
            feeder=feeder,
            equipment=MatrixImpedanceBranchEquipment.example().model_copy(
                update={"name": f"{feeder.name}-main-line-equipment"}
            ),
        )
        distribution_system.add_components(source_bus, load_bus, branch)

    return substation_system, distribution_system


LAYOUT_EXAMPLES: dict[SubstationLayout, Callable[[], SubstationSystem]] = {
    SubstationLayout.SINGLE_BUS: single_bus_substation,
    SubstationLayout.SECTIONALIZED_SINGLE_BUS: sectionalized_single_bus_substation,
    SubstationLayout.MAIN_AND_TRANSFER: main_and_transfer_substation,
    SubstationLayout.DOUBLE_BUS_SINGLE_BREAKER: double_bus_single_breaker_substation,
    SubstationLayout.RING_BUS: ring_bus_substation,
    SubstationLayout.BREAKER_AND_A_HALF: breaker_and_a_half_substation,
    SubstationLayout.DOUBLE_BREAKER_DOUBLE_BUS: double_breaker_double_bus_substation,
    SubstationLayout.HV_MV_SINGLE_BUS: hv_mv_single_bus_substation,
}


def build_layout_example(layout: SubstationLayout | str) -> SubstationSystem:
    """Build a canonical layout using its default reference configuration."""

    return LAYOUT_EXAMPLES[SubstationLayout(layout)]()


def list_reference_designs() -> list[str]:
    """Return the names of canonical and detailed reusable station designs."""

    return [*(layout.value for layout in SubstationLayout), "detailed_distribution"]


def build_reference_design(
    design: SubstationLayout | str,
    *,
    name: str | None = None,
    outfeed_count: int | None = None,
    coordinate_provider: Callable[[int], Location] | None = None,
) -> SubstationSystem:
    """Build a reusable station design with optional outfeed and coordinate overrides.

    ``outfeed_count`` applies to canonical bus arrangements. The detailed
    distribution design has a fixed two-infeed, two-transformer, four-outfeed
    configuration that exercises protection, metering, and automation models.
    """

    if str(design) == "detailed_distribution":
        if name is not None or outfeed_count is not None or coordinate_provider is not None:
            raise ValueError("The detailed_distribution design does not accept overrides.")
        from gdm.systems.substation.detailed_reference import (
            build_detailed_distribution_substation,
        )

        return build_detailed_distribution_substation()

    layout = SubstationLayout(design)
    if name is None and outfeed_count is None and coordinate_provider is None:
        return build_layout_example(layout)

    feeder_count = outfeed_count if outfeed_count is not None else 3
    if feeder_count < 1:
        raise ValueError("outfeed_count must be at least one.")
    return build_parameterized_substation(
        name=name or f"{layout.value.replace('_', '-')}-substation",
        feeder_ids=[f"feeder-{index}" for index in range(1, feeder_count + 1)],
        layout=layout,
        coordinate_provider=coordinate_provider,
    )
