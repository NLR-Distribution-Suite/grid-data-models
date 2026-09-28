"""Distribution substation bus-arrangement examples.

These examples intentionally live with the tests.  They are compact, executable
reference topologies for exercising the generic substation models and are not
intended to prescribe a utility's normal operating configuration.
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
from gdm.systems.distribution.common.sequence_pair import SequencePair
from gdm.systems.distribution.enums import ConnectionType, Phase, VoltageTypes
from gdm.systems.distribution.equipment import (
    CircuitBreakerEquipment,
    DisconnectorEquipment,
    EarthingSwitchEquipment,
    MatrixImpedanceBranchEquipment,
    PowerTransformerEquipment,
    WindingEquipment,
)
from gdm.systems.substation import (
    Bay,
    BusbarSection,
    CircuitDirection,
    CircuitBreaker,
    ConnectivityNode,
    DiagramPosition,
    Disconnector,
    EarthingSwitch,
    EquipmentState,
    ExternalCircuit,
    FeederBoundary,
    InstrumentTransformer,
    LineTrap,
    PowerTransformer,
    Substation,
    SubstationSystem,
    SubstationType,
    SurgeArrester,
    Terminal,
    TerminalRole,
    VoltageLevel,
)
from gdm.quantities import ApparentPower, Distance, Voltage
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
_VOLTAGE_LEVEL_HV_ID = "voltage-level-hv"
_VOLTAGE_LEVEL_ID = "voltage-level-mv"
_SUBSTATION_ID = "substation"


class _SubstationExampleBuilder:
    """Build a station while keeping cross-component IDs consistent."""

    def __init__(
        self,
        name: str,
        description: str,
        initial_voltage_level_id: str = _VOLTAGE_LEVEL_ID,
        initial_nominal_voltage: Voltage = Voltage(12.47, "kilovolt"),
    ):
        self.system = SubstationSystem(
            auto_add_composed_components=True,
            name=name,
            description=description,
        )
        self.nodes: dict[str, str] = {}
        self.bays: dict[str, Bay] = {}
        self.substation = Substation(
            name=_SUBSTATION_ID,
            substation_type=SubstationType.DISTRIBUTION,
            voltage_level_ids=[],
        )
        self.system.add_components(
            self.substation,
        )
        self.add_voltage_level(initial_voltage_level_id, initial_nominal_voltage)

    def add_voltage_level(self, voltage_level_id: str, nominal_voltage: Voltage) -> None:
        """Add a voltage level and register it on the substation."""

        self.system.add_component(
            VoltageLevel(
                name=voltage_level_id,
                nominal_voltage=nominal_voltage,
                voltage_type=VoltageTypes.LINE_TO_LINE,
            )
        )
        self.substation.voltage_level_ids.append(voltage_level_id)

    def add_bus(
        self,
        bus_id: str,
        voltage_level_id: str = _VOLTAGE_LEVEL_ID,
        diagram_start: tuple[float, float] | None = None,
        diagram_end: tuple[float, float] | None = None,
    ) -> str:
        """Add a busbar section and return its connectivity-node ID."""

        node_id = f"{bus_id}-node"
        self.add_node(node_id, voltage_level_id)
        self.system.add_component(
            BusbarSection(
                name=bus_id,
                voltage_level_id=voltage_level_id,
                connectivity_node_id=node_id,
                phases=_PHASES,
                diagram_start=diagram_start,
                diagram_end=diagram_end,
            )
        )
        self.nodes[bus_id] = node_id
        return node_id

    def add_node(self, node_id: str, voltage_level_id: str = _VOLTAGE_LEVEL_ID) -> str:
        if node_id not in self.nodes.values():
            self.system.add_component(
                ConnectivityNode(
                    name=node_id,
                    voltage_level_id=voltage_level_id,
                    phases=_PHASES,
                )
            )
            self.nodes[node_id] = node_id
        return node_id

    def add_bay(self, bay_id: str, voltage_level_id: str = _VOLTAGE_LEVEL_ID) -> Bay:
        bay = self.bays.get(bay_id)
        if bay is None:
            bay = Bay(name=bay_id, voltage_level_id=voltage_level_id)
            self.bays[bay_id] = bay
            self.substation.bay_ids.append(bay_id)
            self.system.add_component(bay)
        return bay

    def endpoint_node(self, endpoint: str, voltage_level_id: str = _VOLTAGE_LEVEL_ID) -> str:
        if endpoint in self.nodes:
            return self.nodes[endpoint]
        return self.add_node(endpoint, voltage_level_id)

    def add_two_terminal_equipment(
        self,
        equipment_id: str,
        bay_id: str,
        from_endpoint: str,
        to_endpoint: str,
        equipment_type: type[CircuitBreaker] | type[Disconnector],
        state: EquipmentState = EquipmentState.CLOSED,
        normal_state: EquipmentState = EquipmentState.CLOSED,
        bay_voltage_level_id: str = _VOLTAGE_LEVEL_ID,
        voltage_level_id: str = _VOLTAGE_LEVEL_ID,
        terminal_positions: tuple[tuple[float, float] | None, tuple[float, float] | None] = (
            None,
            None,
        ),
    ) -> tuple[str, str]:
        """Add switching equipment and its two terminal components."""

        from_node = self.endpoint_node(from_endpoint, voltage_level_id)
        to_node = self.endpoint_node(to_endpoint, voltage_level_id)
        terminal_ids = [f"{equipment_id}-terminal-1", f"{equipment_id}-terminal-2"]
        self.system.add_components(
            Terminal(
                name=terminal_ids[0],
                connectivity_node_id=from_node,
                phases=_PHASES,
                role=TerminalRole.BUS_SIDE,
                equipment_id=equipment_id,
                diagram_position=terminal_positions[0],
            ),
            Terminal(
                name=terminal_ids[1],
                connectivity_node_id=to_node,
                phases=_PHASES,
                role=TerminalRole.FEEDER_SIDE,
                equipment_id=equipment_id,
                diagram_position=terminal_positions[1],
            ),
        )
        equipment_definitions = {
            CircuitBreaker: CircuitBreakerEquipment,
            Disconnector: DisconnectorEquipment,
        }
        equipment = equipment_type(
            name=equipment_id,
            bay_id=bay_id,
            terminal_ids=terminal_ids,
            equipment=equipment_definitions[equipment_type].example(),
            state=state,
            normal_state=normal_state,
        )
        bay = self.add_bay(bay_id, bay_voltage_level_id)
        bay.equipment_ids.append(equipment_id)
        bay.terminal_ids.extend(terminal_ids)
        self.system.add_component(equipment)
        return tuple(terminal_ids)

    def add_breaker(
        self,
        breaker_id: str,
        bay_id: str,
        from_endpoint: str,
        to_endpoint: str,
        state: EquipmentState = EquipmentState.CLOSED,
        normal_state: EquipmentState = EquipmentState.CLOSED,
        voltage_level_id: str = _VOLTAGE_LEVEL_ID,
        terminal_positions: tuple[tuple[float, float] | None, tuple[float, float] | None] = (
            None,
            None,
        ),
    ) -> tuple[str, str]:
        return self.add_two_terminal_equipment(
            breaker_id,
            bay_id,
            from_endpoint,
            to_endpoint,
            CircuitBreaker,
            state,
            normal_state,
            bay_voltage_level_id=voltage_level_id,
            voltage_level_id=voltage_level_id,
            terminal_positions=terminal_positions,
        )

    def add_disconnector(
        self,
        disconnector_id: str,
        bay_id: str,
        from_endpoint: str,
        to_endpoint: str,
        state: EquipmentState = EquipmentState.CLOSED,
        normal_state: EquipmentState = EquipmentState.CLOSED,
        voltage_level_id: str = _VOLTAGE_LEVEL_ID,
        terminal_positions: tuple[tuple[float, float] | None, tuple[float, float] | None] = (
            None,
            None,
        ),
    ) -> tuple[str, str]:
        return self.add_two_terminal_equipment(
            disconnector_id,
            bay_id,
            from_endpoint,
            to_endpoint,
            Disconnector,
            state,
            normal_state,
            bay_voltage_level_id=voltage_level_id,
            voltage_level_id=voltage_level_id,
            terminal_positions=terminal_positions,
        )

    def add_line_trap(
        self,
        line_trap_id: str,
        bay_id: str,
        from_endpoint: str,
        to_endpoint: str,
        voltage_level_id: str = _VOLTAGE_LEVEL_ID,
    ) -> tuple[str, str]:
        """Add a carrier-wave line trap in series with an external circuit."""

        terminal_ids = [f"{line_trap_id}-terminal-1", f"{line_trap_id}-terminal-2"]
        self.system.add_components(
            Terminal(
                name=terminal_ids[0],
                connectivity_node_id=self.endpoint_node(from_endpoint, voltage_level_id),
                phases=_PHASES,
                role=TerminalRole.PRIMARY,
                equipment_id=line_trap_id,
            ),
            Terminal(
                name=terminal_ids[1],
                connectivity_node_id=self.endpoint_node(to_endpoint, voltage_level_id),
                phases=_PHASES,
                role=TerminalRole.SECONDARY,
                equipment_id=line_trap_id,
            ),
        )
        bay = self.add_bay(bay_id, voltage_level_id)
        bay.equipment_ids.append(line_trap_id)
        bay.terminal_ids.extend(terminal_ids)
        self.system.add_component(
            LineTrap(
                name=line_trap_id,
                bay_id=bay_id,
                terminal_ids=terminal_ids,
                tuning_frequency_hz=100_000,
            )
        )
        return tuple(terminal_ids)

    def add_instrument_transformer(
        self,
        transformer_id: str,
        bay_id: str,
        from_endpoint: str,
        to_endpoint: str,
        instrument_type: str,
        voltage_level_id: str = _VOLTAGE_LEVEL_ID,
    ) -> tuple[str, str]:
        """Add a CT, PT, or CVT represented by an instrument transformer."""

        terminal_ids = [f"{transformer_id}-terminal-1", f"{transformer_id}-terminal-2"]
        self.system.add_components(
            Terminal(
                name=terminal_ids[0],
                connectivity_node_id=self.endpoint_node(from_endpoint, voltage_level_id),
                phases=_PHASES,
                role=TerminalRole.PRIMARY,
                equipment_id=transformer_id,
            ),
            Terminal(
                name=terminal_ids[1],
                connectivity_node_id=self.endpoint_node(to_endpoint, voltage_level_id),
                phases=_PHASES,
                role=TerminalRole.SECONDARY,
                equipment_id=transformer_id,
            ),
        )
        bay = self.add_bay(bay_id, voltage_level_id)
        bay.equipment_ids.append(transformer_id)
        bay.terminal_ids.extend(terminal_ids)
        self.system.add_component(
            InstrumentTransformer(
                name=transformer_id,
                bay_id=bay_id,
                terminal_ids=terminal_ids,
                instrument_type=instrument_type,
                primary_rating=600,
                secondary_rating=5,
                ratio_unit="ampere" if instrument_type == "current_transformer" else "volt",
            )
        )
        return tuple(terminal_ids)

    def add_shunt_instrument_transformer(
        self,
        transformer_id: str,
        bay_id: str,
        endpoint: str,
        instrument_type: str,
        voltage_level_id: str = _VOLTAGE_LEVEL_ID,
    ) -> str:
        """Add a PT or CVT shunt-connected to a single circuit node."""

        terminal_id = f"{transformer_id}-terminal"
        self.system.add_component(
            Terminal(
                name=terminal_id,
                connectivity_node_id=self.endpoint_node(endpoint, voltage_level_id),
                phases=_PHASES,
                role=TerminalRole.PRIMARY,
                equipment_id=transformer_id,
            )
        )
        bay = self.add_bay(bay_id, voltage_level_id)
        bay.equipment_ids.append(transformer_id)
        bay.terminal_ids.append(terminal_id)
        self.system.add_component(
            InstrumentTransformer(
                name=transformer_id,
                bay_id=bay_id,
                terminal_ids=[terminal_id],
                instrument_type=instrument_type,
                primary_rating=11_000,
                secondary_rating=110,
                ratio_unit="volt",
            )
        )
        return terminal_id

    def add_surge_arrester(
        self,
        arrester_id: str,
        bay_id: str,
        endpoint: str,
        voltage_level_id: str = _VOLTAGE_LEVEL_ID,
    ) -> None:
        """Add a shunt surge arrester at a bus or circuit node."""

        terminal_id = f"{arrester_id}-terminal"
        self.system.add_component(
            Terminal(
                name=terminal_id,
                connectivity_node_id=self.endpoint_node(endpoint, voltage_level_id),
                phases=_PHASES,
                role=TerminalRole.PRIMARY,
                equipment_id=arrester_id,
            )
        )
        bay = self.add_bay(bay_id, voltage_level_id)
        bay.equipment_ids.append(arrester_id)
        bay.terminal_ids.append(terminal_id)
        self.system.add_component(
            SurgeArrester(
                name=arrester_id,
                bay_id=bay_id,
                terminal_ids=[terminal_id],
                mcov=Voltage(9, "kilovolt"),
                terminal_id=terminal_id,
                ground_terminal_id=f"{arrester_id}-ground",
            )
        )

    def add_earthing_switch(self, switch_id: str, bay_id: str, target_terminal_id: str) -> None:
        """Add an open safety ground switch to the indicated station terminal."""

        bay = self.add_bay(bay_id)
        bay.equipment_ids.append(switch_id)
        self.system.add_component(
            EarthingSwitch(
                name=switch_id,
                bay_id=bay_id,
                target_terminal_id=target_terminal_id,
                equipment=EarthingSwitchEquipment.example(),
            )
        )

    def add_external_circuit(
        self,
        circuit_id: str,
        bay_id: str,
        endpoint: str,
        direction: CircuitDirection,
        voltage_level_id: str,
    ) -> None:
        """Add an incoming or outgoing line at an explicit station terminal."""

        terminal_id = f"{circuit_id}-terminal"
        self.system.add_component(
            Terminal(
                name=terminal_id,
                connectivity_node_id=self.endpoint_node(endpoint, voltage_level_id),
                phases=_PHASES,
                role=TerminalRole.FEEDER_SIDE,
                equipment_id=circuit_id,
            )
        )
        bay = self.add_bay(bay_id, voltage_level_id)
        bay.terminal_ids.append(terminal_id)
        self.system.add_component(
            ExternalCircuit(
                name=circuit_id,
                circuit_id=circuit_id,
                terminal_id=terminal_id,
                direction=direction,
                voltage_level_id=voltage_level_id,
                bay_id=bay_id,
            )
        )

    def add_diagram_position(self, target_id: str, x: float, y: float) -> None:
        """Pin a component or connectivity node to a schematic coordinate."""

        self.system.add_component(
            DiagramPosition(
                name=f"{target_id}-position",
                target_id=target_id,
                x=x,
                y=y,
            )
        )

    def add_power_transformer(
        self,
        transformer_id: str,
        bay_id: str,
        high_voltage_endpoint: str,
        medium_voltage_endpoint: str,
        high_voltage_level_id: str = _VOLTAGE_LEVEL_HV_ID,
        medium_voltage_level_id: str = _VOLTAGE_LEVEL_ID,
        high_voltage: Voltage = Voltage(69, "kilovolt"),
        medium_voltage: Voltage = Voltage(12.47, "kilovolt"),
    ) -> tuple[str, str]:
        """Add a station transformer between the HV and MV busbars."""

        high_voltage_terminal_id = f"{transformer_id}-hv-terminal"
        medium_voltage_terminal_id = f"{transformer_id}-mv-terminal"
        self.system.add_components(
            Terminal(
                name=high_voltage_terminal_id,
                connectivity_node_id=self.endpoint_node(
                    high_voltage_endpoint, high_voltage_level_id
                ),
                phases=_PHASES,
                role=TerminalRole.HIGH_VOLTAGE,
                equipment_id=transformer_id,
            ),
            Terminal(
                name=medium_voltage_terminal_id,
                connectivity_node_id=self.endpoint_node(
                    medium_voltage_endpoint, medium_voltage_level_id
                ),
                phases=_PHASES,
                role=TerminalRole.LOW_VOLTAGE,
                equipment_id=transformer_id,
            ),
        )
        transformer = PowerTransformer(
            name=transformer_id,
            bay_id=bay_id,
            terminal_ids=[high_voltage_terminal_id, medium_voltage_terminal_id],
            winding_terminal_ids=[high_voltage_terminal_id, medium_voltage_terminal_id],
            equipment=PowerTransformerEquipment(
                name=f"{transformer_id}-equipment",
                pct_no_load_loss=0.1,
                pct_full_load_loss=1,
                is_center_tapped=False,
                windings=[
                    WindingEquipment(
                        name=f"{transformer_id}-hv-winding",
                        resistance=1,
                        is_grounded=False,
                        rated_voltage=high_voltage,
                        voltage_type=VoltageTypes.LINE_TO_LINE,
                        rated_power=ApparentPower(30, "megavolt_ampere"),
                        num_phases=3,
                        connection_type=ConnectionType.DELTA,
                        tap_positions=[1.0, 1.0, 1.0],
                    ),
                    WindingEquipment(
                        name=f"{transformer_id}-mv-winding",
                        resistance=1,
                        is_grounded=True,
                        rated_voltage=medium_voltage,
                        voltage_type=VoltageTypes.LINE_TO_LINE,
                        rated_power=ApparentPower(30, "megavolt_ampere"),
                        num_phases=3,
                        connection_type=ConnectionType.STAR,
                        tap_positions=[1.0, 1.0, 1.0],
                    ),
                ],
                coupling_sequences=[SequencePair(0, 1)],
                winding_reactances=[8.5],
                vector_group="Dyn1",
                cooling_class="ONAN",
                fluid_type="mineral_oil",
            ),
        )
        bay = self.add_bay(bay_id, high_voltage_level_id)
        bay.equipment_ids.append(transformer_id)
        bay.terminal_ids.extend([high_voltage_terminal_id, medium_voltage_terminal_id])
        self.system.add_component(transformer)
        return high_voltage_terminal_id, medium_voltage_terminal_id

    def add_feeder(
        self,
        feeder_id: str,
        bay_id: str,
        station_endpoint: str,
        with_disconnector: bool = False,
        terminal_id: str | None = None,
        distribution_model_reference_id: str | None = None,
        disconnector_terminal_positions: tuple[
            tuple[float, float] | None, tuple[float, float] | None
        ] = (None, None),
    ) -> None:
        """Add a feeder boundary, optionally through a line disconnector."""

        if with_disconnector:
            terminal_ids = self.add_disconnector(
                f"{feeder_id}-disconnector",
                bay_id,
                station_endpoint,
                f"{feeder_id}-node",
                terminal_positions=disconnector_terminal_positions,
            )
            terminal_id = terminal_ids[1]
        elif terminal_id is None:
            terminal_id = f"{feeder_id}-boundary-terminal"
            self.system.add_component(
                Terminal(
                    name=terminal_id,
                    connectivity_node_id=self.endpoint_node(station_endpoint),
                    phases=_PHASES,
                    role=TerminalRole.FEEDER_SIDE,
                    equipment_id=feeder_id,
                )
            )
            self.add_bay(bay_id).terminal_ids.append(terminal_id)
        self.system.add_component(
            FeederBoundary(
                name=f"{feeder_id}-boundary",
                feeder_id=feeder_id,
                substation_id=_SUBSTATION_ID,
                voltage_level_id=_VOLTAGE_LEVEL_ID,
                bay_id=bay_id,
                terminal_id=terminal_id,
                distribution_model_reference_id=distribution_model_reference_id,
            )
        )
        self.substation.feeder_boundary_ids.append(f"{feeder_id}-boundary")

    def build(self) -> SubstationSystem:
        return self.system


def build_parameterized_substation(  # noqa: C901
    name: str,
    feeder_ids: list[str],
    layout: SubstationLayout | str = SubstationLayout.SINGLE_BUS,
) -> SubstationSystem:
    """Build an example layout with caller-provided feeder IDs."""

    selected_layout = SubstationLayout(layout)
    builder = _SubstationExampleBuilder(
        name,
        f"Parameterized {selected_layout.value} distribution substation example.",
    )
    feeder_ids = list(dict.fromkeys(feeder_ids))

    if selected_layout == SubstationLayout.HV_MV_SINGLE_BUS:
        builder.add_voltage_level(_VOLTAGE_LEVEL_HV_ID, Voltage(69, "kilovolt"))
        builder.add_bus("hv-bus", _VOLTAGE_LEVEL_HV_ID)
        builder.add_bus("mv-bus")
        builder.add_power_transformer(
            "station-transformer", "station-transformer-bay", "hv-bus", "mv-bus"
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
        elif selected_layout == SubstationLayout.BREAKER_AND_A_HALF:
            bus_ids = ["bus-a", "bus-b"]
    elif selected_layout == SubstationLayout.RING_BUS:
        bus_ids = [f"ring-node-{number}" for number in range(max(2, len(feeder_ids)))]
        for bus_id in bus_ids:
            builder.add_bus(bus_id)
    for index, feeder_id in enumerate(feeder_ids):
        bay_id = f"{feeder_id}-bay"
        feeder_node = f"{feeder_id}-node"
        bus_id = bus_ids[index % len(bus_ids)]
        if selected_layout == SubstationLayout.RING_BUS:
            builder.add_feeder(feeder_id, bay_id, bus_id, with_disconnector=True)
        elif selected_layout == SubstationLayout.MAIN_AND_TRANSFER:
            breaker_terminals = builder.add_breaker(
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
            builder.add_feeder(feeder_id, bay_id, feeder_node, terminal_id=breaker_terminals[1])
        elif selected_layout == SubstationLayout.DOUBLE_BUS_SINGLE_BREAKER:
            breaker_node = f"{feeder_id}-breaker-node"
            breaker_terminals = builder.add_breaker(
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
            builder.add_feeder(feeder_id, bay_id, feeder_node, terminal_id=breaker_terminals[1])
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
            breaker_terminals = builder.add_breaker(
                f"{feeder_id}-breaker", bay_id, bus_id, feeder_node
            )
            builder.add_feeder(feeder_id, bay_id, feeder_node, terminal_id=breaker_terminals[1])
    return builder.build()


def single_bus_substation() -> SubstationSystem:
    """One common bus with three feeder breakers."""

    builder = _SubstationExampleBuilder(
        "single-bus-substation",
        "Distribution substation with one common bus and three feeder bays.",
    )
    builder.add_bus("bus-a")
    for feeder_number in range(1, 4):
        feeder_id = f"feeder-{feeder_number}"
        breaker_terminals = builder.add_breaker(
            f"{feeder_id}-breaker",
            f"{feeder_id}-bay",
            "bus-a",
            f"{feeder_id}-node",
        )
        builder.add_feeder(
            feeder_id,
            f"{feeder_id}-bay",
            f"{feeder_id}-node",
            terminal_id=breaker_terminals[1],
        )
    return builder.build()


def sectionalized_single_bus_substation() -> SubstationSystem:
    """Two bus sections connected by a normally open bus-tie breaker."""

    builder = _SubstationExampleBuilder(
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
        breaker_terminals = builder.add_breaker(
            f"{feeder_id}-breaker",
            f"{feeder_id}-bay",
            bus_id,
            f"{feeder_id}-node",
        )
        builder.add_feeder(
            feeder_id,
            f"{feeder_id}-bay",
            f"{feeder_id}-node",
            terminal_id=breaker_terminals[1],
        )
    return builder.build()


def main_and_transfer_substation() -> SubstationSystem:
    """Main bus with a transfer bus and a normally open transfer breaker."""

    builder = _SubstationExampleBuilder(
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
        breaker_terminals = builder.add_breaker(
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
        builder.add_feeder(feeder_id, bay_id, feeder_node, terminal_id=breaker_terminals[1])
    return builder.build()


def double_bus_single_breaker_substation() -> SubstationSystem:
    """Two selectable buses with one breaker and two bus disconnectors per feeder."""

    builder = _SubstationExampleBuilder(
        "double-bus-single-breaker-substation",
        "Distribution substation with two selectable buses and one breaker per feeder.",
    )
    builder.add_bus("bus-a")
    builder.add_bus("bus-b")
    for feeder_number in (1, 2):
        feeder_id = f"feeder-{feeder_number}"
        bay_id = f"{feeder_id}-bay"
        breaker_node = f"{feeder_id}-breaker-node"
        breaker_terminals = builder.add_breaker(
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
            terminal_id=breaker_terminals[1],
        )
    return builder.build()


def ring_bus_substation() -> SubstationSystem:
    """Four-breaker ring bus with one feeder circuit at each ring position."""

    builder = _SubstationExampleBuilder(
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

    builder = _SubstationExampleBuilder(
        "breaker-and-a-half-substation",
        "Distribution substation with two buses and two parallel three-breaker diameters.",
    )
    builder.add_bus("bus-a", diagram_start=(-7, 4), diagram_end=(7, 4))
    builder.add_bus("bus-b", diagram_start=(-7, -4), diagram_end=(7, -4))
    for diameter_number, x_position, direction in ((1, -3, -1), (2, 3, 1)):
        bay_id = f"diameter-{diameter_number}-bay"
        circuit_node_a = f"diameter-{diameter_number}-circuit-node-a"
        circuit_node_b = f"diameter-{diameter_number}-circuit-node-b"
        builder.add_breaker(
            f"diameter-{diameter_number}-breaker-a",
            bay_id,
            "bus-a",
            circuit_node_a,
            terminal_positions=((x_position, 4), (x_position, 1.5)),
        )
        builder.add_breaker(
            f"diameter-{diameter_number}-breaker-middle",
            bay_id,
            circuit_node_a,
            circuit_node_b,
            terminal_positions=((x_position, 1.5), (x_position, -1.5)),
        )
        builder.add_breaker(
            f"diameter-{diameter_number}-breaker-b",
            bay_id,
            circuit_node_b,
            "bus-b",
            terminal_positions=((x_position, -1.5), (x_position, -4)),
        )
        for circuit_number, circuit_node, y_position in (
            (1, circuit_node_a, 1.5),
            (2, circuit_node_b, -1.5),
        ):
            feeder_number = (diameter_number - 1) * 2 + circuit_number
            feeder_position = x_position + direction * 3
            builder.add_feeder(
                f"feeder-{feeder_number}",
                f"feeder-{feeder_number}-bay",
                circuit_node,
                with_disconnector=True,
                disconnector_terminal_positions=(
                    (x_position, y_position),
                    (feeder_position, y_position),
                ),
            )
    return builder.build()


def double_breaker_double_bus_substation() -> SubstationSystem:
    """Two buses with two breakers assigned to each feeder circuit."""

    builder = _SubstationExampleBuilder(
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

    builder = _SubstationExampleBuilder(
        "hv-mv-single-bus-substation",
        "Distribution substation with 69 kV and 12.47 kV buses joined by a station transformer.",
    )
    builder.add_voltage_level(_VOLTAGE_LEVEL_HV_ID, Voltage(69, "kilovolt"))
    builder.add_bus("hv-bus", _VOLTAGE_LEVEL_HV_ID)
    builder.add_bus("mv-bus", _VOLTAGE_LEVEL_ID)
    builder.add_power_transformer(
        "station-transformer",
        "station-transformer-bay",
        "hv-bus",
        "mv-bus",
    )

    for feeder_number in range(1, 4):
        feeder_id = f"feeder-{feeder_number}"
        bay_id = f"{feeder_id}-bay"
        breaker_terminals = builder.add_breaker(
            f"{feeder_id}-breaker",
            bay_id,
            "mv-bus",
            f"{feeder_id}-node",
        )
        builder.add_feeder(
            feeder_id,
            bay_id,
            f"{feeder_id}-node",
            terminal_id=breaker_terminals[1],
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
