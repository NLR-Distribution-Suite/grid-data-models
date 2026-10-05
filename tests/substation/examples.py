"""Distribution substation bus-arrangement examples.

These examples live with the tests and exercise the public
:class:`gdm.systems.substation.builder.SubstationBuilder`. They are compact,
executable reference topologies and are not intended to prescribe a utility's
normal operating configuration.
"""

from enum import Enum
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
from gdm.systems.substation import EquipmentState, SubstationSystem
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


def build_parameterized_substation(  # noqa: C901
    name: str,
    feeder_ids: list[str],
    layout: SubstationLayout | str = SubstationLayout.SINGLE_BUS,
) -> SubstationSystem:
    """Build an example layout with caller-provided feeder IDs."""

    selected_layout = SubstationLayout(layout)
    builder = SubstationBuilder(
        name,
        f"Parameterized {selected_layout.value} distribution substation example.",
    )
    feeder_ids = list(dict.fromkeys(feeder_ids))

    if selected_layout == SubstationLayout.HV_MV_SINGLE_BUS:
        builder.add_voltage_level(_VOLTAGE_LEVEL_HV_ID, Voltage(69, "kilovolt"))
        hv_bus = builder.add_bus("hv-bus", _VOLTAGE_LEVEL_HV_ID)
        mv_bus = builder.add_bus("mv-bus")
        builder.add_two_winding_transformer(
            "station-transformer", "station-transformer-bay", hv_bus, mv_bus
        )
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
        bus_ids = [f"ring-node-{number}" for number in range(max(2, len(feeder_ids)))]
        for bus_id in bus_ids:
            builder.add_bus(bus_id)
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
    return builder.build()


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
    return builder.build()


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
    return builder.build()


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
    return builder.build()


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
    return builder.build()


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
    return builder.build()


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
    return builder.build()


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
    return builder.build()


def hv_mv_single_bus_substation() -> SubstationSystem:
    """69 kV source bus feeding a 12.47 kV bus through a station transformer."""

    builder = SubstationBuilder(
        "hv-mv-single-bus-substation",
        "Distribution substation with 69 kV and 12.47 kV buses joined by a transformer.",
    )
    builder.add_voltage_level(_VOLTAGE_LEVEL_HV_ID, Voltage(69, "kilovolt"))
    hv_bus = builder.add_bus("hv-bus", _VOLTAGE_LEVEL_HV_ID)
    mv_bus = builder.add_bus("mv-bus", _VOLTAGE_LEVEL_ID)
    builder.add_two_winding_transformer(
        "station-transformer",
        "station-transformer-bay",
        hv_bus,
        mv_bus,
    )

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
    return builder.build()


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
    """Build an example by enum member or serialized layout value."""

    return LAYOUT_EXAMPLES[SubstationLayout(layout)]()
