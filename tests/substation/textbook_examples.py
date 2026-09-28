"""Executable transcriptions of the Desktop textbook single-line diagrams.

The fixtures preserve the electrical topology in Figs. 25.4 through 25.10.
Shunt-connected PT/CVT and lightning-arrester symbols are connected to their
associated circuit node because the current primary-equipment model does not
yet expose an explicit grounding-grid terminal.
"""

from gdm.quantities import Voltage
from gdm.systems.substation import CircuitDirection, EquipmentState, SubstationSystem, Terminal

from tests.substation.examples import _SubstationExampleBuilder


_PHASES = ["A", "B", "C"]
_V11 = "voltage-level-11kv"
_V33 = "voltage-level-33kv"
_V66 = "voltage-level-66kv"
_V400 = "voltage-level-400v"


def _pin(builder: _SubstationExampleBuilder, coordinates: dict[str, tuple[float, float]]) -> None:
    """Persist source-diagram coordinates for the visible one-line objects."""

    for target_id, (x, y) in coordinates.items():
        builder.add_diagram_position(target_id, x, y)


def _position_terminals(
    builder: _SubstationExampleBuilder,
    equipment_id: str,
    positions: list[tuple[float, float]],
) -> None:
    """Assign authored terminal coordinates in the equipment terminal order."""

    terminals = sorted(
        (
            terminal
            for terminal in builder.system.get_components(Terminal)
            if terminal.equipment_id == equipment_id
        ),
        key=lambda terminal: terminal.name,
    )
    if len(terminals) != len(positions):
        raise ValueError(f"Expected {len(positions)} terminals for {equipment_id}.")
    for terminal, position in zip(terminals, positions):
        terminal.diagram_position = position


def _add_incoming_line_bay(
    builder: _SubstationExampleBuilder,
    circuit_id: str,
    bay_id: str,
    bus_id: str,
    voltage_level_id: str,
    with_line_trap: bool = False,
) -> str:
    """Add a line, isolator, breaker, CT, and circuit connection to a bus."""

    line_node = f"{circuit_id}-line-node"
    builder.add_external_circuit(
        circuit_id,
        bay_id,
        line_node,
        CircuitDirection.INCOMING,
        voltage_level_id,
    )
    if with_line_trap:
        trap_node = f"{circuit_id}-trap-node"
        builder.add_line_trap(
            f"{circuit_id}-line-trap", bay_id, line_node, trap_node, voltage_level_id
        )
        line_node = trap_node
    isolator_node = f"{circuit_id}-isolator-node"
    builder.add_disconnector(
        f"{circuit_id}-isolator",
        bay_id,
        line_node,
        isolator_node,
        voltage_level_id=voltage_level_id,
    )
    ct_node = f"{circuit_id}-ct-node"
    builder.add_instrument_transformer(
        f"{circuit_id}-ct",
        bay_id,
        isolator_node,
        ct_node,
        "current_transformer",
        voltage_level_id,
    )
    breaker_terminals = builder.add_breaker(
        f"{circuit_id}-ocb", bay_id, ct_node, bus_id, voltage_level_id=voltage_level_id
    )
    builder.add_earthing_switch(f"{circuit_id}-earth-switch", bay_id, breaker_terminals[0])
    return breaker_terminals[1]


def _add_outgoing_transformer_bay(
    builder: _SubstationExampleBuilder,
    circuit_id: str,
    bay_id: str,
    bus_id: str,
    high_voltage_level_id: str,
    high_voltage: Voltage,
    low_voltage_level_id: str,
    low_voltage: Voltage,
) -> None:
    """Add an isolator, CT, transformer, and outgoing circuit from a bus."""

    breaker_node = f"{circuit_id}-breaker-node"
    breaker_terminals = builder.add_breaker(
        f"{circuit_id}-ocb", bay_id, bus_id, breaker_node, voltage_level_id=high_voltage_level_id
    )
    ct_node = f"{circuit_id}-ct-node"
    builder.add_instrument_transformer(
        f"{circuit_id}-ct",
        bay_id,
        breaker_node,
        ct_node,
        "current_transformer",
        high_voltage_level_id,
    )
    builder.add_disconnector(
        f"{circuit_id}-isolator",
        bay_id,
        ct_node,
        f"{circuit_id}-transformer-hv-node",
        voltage_level_id=high_voltage_level_id,
    )
    low_voltage_node = f"{circuit_id}-outgoing-node"
    builder.add_power_transformer(
        f"{circuit_id}-transformer",
        bay_id,
        f"{circuit_id}-transformer-hv-node",
        low_voltage_node,
        high_voltage_level_id,
        low_voltage_level_id,
        high_voltage,
        low_voltage,
    )
    builder.add_external_circuit(
        f"{circuit_id}-outgoing-line",
        bay_id,
        low_voltage_node,
        CircuitDirection.OUTGOING,
        low_voltage_level_id,
    )
    builder.add_earthing_switch(f"{circuit_id}-earth-switch", bay_id, breaker_terminals[1])


def fig_25_5_11kv_400v_single_bus() -> SubstationSystem:
    """Fig. 25.5: 11 kV bus with two transformers and two incoming circuits."""

    builder = _SubstationExampleBuilder(
        "fig-25-5-11kv-400v-single-bus",
        "Fig. 25.5: 11 kV single bus, two incoming lines, and two 11 kV/400 V transformers.",
        _V11,
        Voltage(11, "kilovolt"),
    )
    builder.add_voltage_level(_V400, Voltage(0.4, "kilovolt"))
    builder.add_bus("11kv-bus", _V11)
    _add_incoming_line_bay(builder, "incoming-line-1", "incoming-line-1-bay", "11kv-bus", _V11)
    _add_incoming_line_bay(builder, "incoming-line-2", "incoming-line-2-bay", "11kv-bus", _V11)
    _add_outgoing_transformer_bay(
        builder,
        "transformer-1",
        "transformer-1-bay",
        "11kv-bus",
        _V11,
        Voltage(11, "kilovolt"),
        _V400,
        Voltage(0.4, "kilovolt"),
    )
    _add_outgoing_transformer_bay(
        builder,
        "transformer-2",
        "transformer-2-bay",
        "11kv-bus",
        _V11,
        Voltage(11, "kilovolt"),
        _V400,
        Voltage(0.4, "kilovolt"),
    )
    builder.add_surge_arrester("bus-lightning-arrester", "bus-protection-bay", "11kv-bus")
    _pin(
        builder,
        {
            "11kv-bus-node": (0, 3),
            "incoming-line-1": (-6, -3),
            "incoming-line-1-isolator": (-6, -1.5),
            "incoming-line-1-ct": (-6, -0.5),
            "incoming-line-1-ocb": (-6, 1),
            "incoming-line-2": (6, -3),
            "incoming-line-2-isolator": (6, -1.5),
            "incoming-line-2-ct": (6, -0.5),
            "incoming-line-2-ocb": (6, 1),
            "transformer-1-ocb": (-2.5, 1),
            "transformer-1-ct": (-2.5, 0),
            "transformer-1-isolator": (-2.5, -1),
            "transformer-1-transformer": (-2.5, -3),
            "transformer-1-outgoing-line": (-2.5, -5),
            "transformer-2-ocb": (2.5, 1),
            "transformer-2-ct": (2.5, 0),
            "transformer-2-isolator": (2.5, -1),
            "transformer-2-transformer": (2.5, -3),
            "transformer-2-outgoing-line": (2.5, -5),
            "bus-lightning-arrester": (0, 1.5),
        },
    )
    return builder.build()


def fig_25_6_33kv_sectionalized_bus() -> SubstationSystem:
    """Fig. 25.6: 33 kV sectionalized bus with two 33/11 kV transformer bays."""

    builder = _SubstationExampleBuilder(
        "fig-25-6-33kv-sectionalized-bus",
        "Fig. 25.6: two 33 kV bus sections, a bus coupler, incoming lines, and transformer bays.",
        _V33,
        Voltage(33, "kilovolt"),
    )
    builder.add_voltage_level(_V11, Voltage(11, "kilovolt"))
    builder.add_bus("33kv-bus-section-1", _V33)
    builder.add_bus("33kv-bus-section-2", _V33)
    builder.add_breaker(
        "bus-section-coupler-ocb",
        "bus-section-coupler-bay",
        "33kv-bus-section-1",
        "33kv-bus-section-2",
        EquipmentState.OPEN,
        EquipmentState.OPEN,
    )
    _add_incoming_line_bay(
        builder, "incoming-line-1", "incoming-line-1-bay", "33kv-bus-section-1", _V33
    )
    _add_incoming_line_bay(
        builder, "incoming-line-2", "incoming-line-2-bay", "33kv-bus-section-2", _V33
    )
    _add_outgoing_transformer_bay(
        builder,
        "transformer-1",
        "transformer-1-bay",
        "33kv-bus-section-1",
        _V33,
        Voltage(33, "kilovolt"),
        _V11,
        Voltage(11, "kilovolt"),
    )
    _add_outgoing_transformer_bay(
        builder,
        "transformer-2",
        "transformer-2-bay",
        "33kv-bus-section-2",
        _V33,
        Voltage(33, "kilovolt"),
        _V11,
        Voltage(11, "kilovolt"),
    )
    _pin(
        builder,
        {
            "33kv-bus-section-1-node": (-3, 3),
            "33kv-bus-section-2-node": (3, 3),
            "bus-section-coupler-ocb": (0, 3),
            "incoming-line-1": (-6, -3),
            "incoming-line-1-isolator": (-6, -1.5),
            "incoming-line-1-ct": (-6, -0.5),
            "incoming-line-1-ocb": (-6, 1),
            "transformer-1-ocb": (-1.5, 1),
            "transformer-1-ct": (-1.5, 0),
            "transformer-1-isolator": (-1.5, -1),
            "transformer-1-transformer": (-1.5, -3),
            "transformer-1-outgoing-line": (-1.5, -5),
            "transformer-2-ocb": (1.5, 1),
            "transformer-2-ct": (1.5, 0),
            "transformer-2-isolator": (1.5, -1),
            "transformer-2-transformer": (1.5, -3),
            "transformer-2-outgoing-line": (1.5, -5),
            "incoming-line-2": (6, -3),
            "incoming-line-2-isolator": (6, -1.5),
            "incoming-line-2-ct": (6, -0.5),
            "incoming-line-2-ocb": (6, 1),
        },
    )
    return builder.build()


def fig_25_8_11kv_400v_line_trap() -> SubstationSystem:
    """Fig. 25.8: 11 kV line trap/CVT bay feeding an 11 kV/400 V transformer."""

    builder = _SubstationExampleBuilder(
        "fig-25-8-11kv-400v-line-trap",
        "Fig. 25.8: 11 kV incoming line with line trap, CVT, OCB, CT, arrester, and transformer.",
        _V11,
        Voltage(11, "kilovolt"),
    )
    builder.add_voltage_level(_V400, Voltage(0.4, "kilovolt"))
    builder.add_bus("11kv-bus", _V11)
    _add_incoming_line_bay(
        builder, "incoming-line", "incoming-line-bay", "11kv-bus", _V11, with_line_trap=True
    )
    builder.add_shunt_instrument_transformer(
        "capacitive-voltage-transformer",
        "incoming-line-bay",
        "incoming-line-trap-node",
        "capacitive_voltage_transformer",
        _V11,
    )
    builder.add_surge_arrester("transformer-lightning-arrester", "transformer-bay", "11kv-bus")
    _add_outgoing_transformer_bay(
        builder,
        "distribution-transformer",
        "transformer-bay",
        "11kv-bus",
        _V11,
        Voltage(11, "kilovolt"),
        _V400,
        Voltage(0.4, "kilovolt"),
    )
    _pin(
        builder,
        {
            "11kv-bus-node": (0, 3),
            "incoming-line": (-6, -3),
            "incoming-line-line-trap": (-5, -2),
            "incoming-line-isolator": (-4, -1),
            "incoming-line-ct": (-3, 0),
            "incoming-line-ocb": (-2, 1),
            "capacitive-voltage-transformer": (-4, 1),
            "distribution-transformer-ocb": (2, 1),
            "distribution-transformer-ct": (3, 0),
            "distribution-transformer-isolator": (4, -1),
            "distribution-transformer-transformer": (4, -3),
            "distribution-transformer-outgoing-line": (4, -5),
            "transformer-lightning-arrester": (1, 2),
        },
    )
    return builder.build()


def fig_25_9_66kv_through_bus() -> SubstationSystem:
    """Fig. 25.9: 66 kV through bus with two OCBs and a 66/11 kV transformer bay."""

    builder = _SubstationExampleBuilder(
        "fig-25-9-66kv-through-bus",
        "Fig. 25.9: 66 kV incoming/outgoing line through bus with a 66/11 kV transformer bay.",
        _V66,
        Voltage(66, "kilovolt"),
    )
    builder.add_voltage_level(_V11, Voltage(11, "kilovolt"))
    builder.add_bus("66kv-through-bus", _V66)
    _add_incoming_line_bay(builder, "incoming-line", "incoming-line-bay", "66kv-through-bus", _V66)
    builder.add_external_circuit(
        "outgoing-line", "outgoing-line-bay", "66kv-through-bus", CircuitDirection.OUTGOING, _V66
    )
    _add_outgoing_transformer_bay(
        builder,
        "station-transformer",
        "station-transformer-bay",
        "66kv-through-bus",
        _V66,
        Voltage(66, "kilovolt"),
        _V11,
        Voltage(11, "kilovolt"),
    )
    builder.add_surge_arrester("bus-lightning-arrester", "bus-protection-bay", "66kv-through-bus")
    _pin(
        builder,
        {
            "66kv-through-bus-node": (0, 3),
            "incoming-line": (-5, -3),
            "incoming-line-isolator": (-5, -1.5),
            "incoming-line-ct": (-5, -0.5),
            "incoming-line-ocb": (-5, 1),
            "outgoing-line": (5, 2),
            "station-transformer-ocb": (0, 1),
            "station-transformer-ct": (0, 0),
            "station-transformer-isolator": (0, -1),
            "station-transformer-transformer": (0, -3),
            "station-transformer-outgoing-line": (0, -5),
            "bus-lightning-arrester": (2, 2),
        },
    )
    return builder.build()


def fig_25_4_bus_section_and_transfer_bus() -> SubstationSystem:
    """Fig. 25.4: sectionalized main bus with a transfer-bus transformer bay."""

    builder = _SubstationExampleBuilder(
        "fig-25-4-bus-section-and-transfer-bus",
        "Fig. 25.4: incoming line, bus sections, line OCB, transfer bus, and transformer bay.",
        _V66,
        Voltage(66, "kilovolt"),
    )
    builder.add_voltage_level(_V11, Voltage(11, "kilovolt"))
    builder.add_bus("main-bus-section-1", _V66)
    builder.add_bus("main-bus-section-2", _V66)
    builder.add_bus("transfer-bus", _V66)
    builder.add_breaker(
        "line-section-ocb",
        "line-section-bay",
        "main-bus-section-1",
        "main-bus-section-2",
        EquipmentState.CLOSED,
        EquipmentState.CLOSED,
        _V66,
    )
    builder.add_breaker(
        "bus-coupler-ocb",
        "bus-coupler-bay",
        "main-bus-section-2",
        "transfer-bus",
        EquipmentState.OPEN,
        EquipmentState.OPEN,
        _V66,
    )
    _add_incoming_line_bay(
        builder, "incoming-line", "incoming-line-bay", "main-bus-section-1", _V66
    )
    _add_outgoing_transformer_bay(
        builder,
        "station-transformer",
        "station-transformer-bay",
        "main-bus-section-2",
        _V66,
        Voltage(66, "kilovolt"),
        _V11,
        Voltage(11, "kilovolt"),
    )
    _pin(
        builder,
        {
            "main-bus-section-1-node": (-4, 3),
            "main-bus-section-2-node": (0, 3),
            "transfer-bus-node": (4, 3),
            "line-section-ocb": (-2, 3),
            "bus-coupler-ocb": (2, 3),
            "incoming-line": (-5, -3),
            "incoming-line-isolator": (-5, -1.5),
            "incoming-line-ct": (-5, -0.5),
            "incoming-line-ocb": (-5, 1),
            "station-transformer-ocb": (0, 1),
            "station-transformer-ct": (0, 0),
            "station-transformer-isolator": (0, -1),
            "station-transformer-transformer": (0, -3),
            "station-transformer-outgoing-line": (0, -5),
        },
    )
    return builder.build()


def fig_25_7_double_main_bus_with_spare_bus() -> SubstationSystem:
    """Fig. 25.7: double 66 kV main bus with spare bus and bus coupler."""

    builder = _SubstationExampleBuilder(
        "fig-25-7-double-main-bus-with-spare-bus",
        "Fig. 25.7: double 66 kV main bus, spare bus, bus coupler, incoming circuits, and transformers.",
        _V66,
        Voltage(66, "kilovolt"),
    )
    builder.add_voltage_level(_V11, Voltage(11, "kilovolt"))
    builder.add_bus("main-bus-1", _V66)
    builder.add_bus("main-bus-2", _V66)
    builder.add_bus("spare-bus", _V66)
    builder.add_breaker(
        "bus-coupler-ocb",
        "bus-coupler-bay",
        "main-bus-1",
        "spare-bus",
        EquipmentState.OPEN,
        EquipmentState.OPEN,
        _V66,
    )
    for number, bus in ((1, "main-bus-1"), (2, "main-bus-2")):
        _add_incoming_line_bay(
            builder, f"incoming-line-{number}", f"incoming-line-{number}-bay", bus, _V66
        )
        _add_outgoing_transformer_bay(
            builder,
            f"station-transformer-{number}",
            f"station-transformer-{number}-bay",
            bus,
            _V66,
            Voltage(66, "kilovolt"),
            _V11,
            Voltage(11, "kilovolt"),
        )
    _pin(
        builder,
        {
            "main-bus-1-node": (-3, 3),
            "main-bus-2-node": (3, 3),
            "spare-bus-node": (0, 1.5),
            "bus-coupler-ocb": (0, 2.25),
            "incoming-line-1": (-6, -3),
            "incoming-line-1-isolator": (-6, -1.5),
            "incoming-line-1-ct": (-6, -0.5),
            "incoming-line-1-ocb": (-6, 1),
            "station-transformer-1-ocb": (-2, 1),
            "station-transformer-1-ct": (-2, 0),
            "station-transformer-1-isolator": (-2, -1),
            "station-transformer-1-transformer": (-2, -3),
            "station-transformer-1-outgoing-line": (-2, -5),
            "station-transformer-2-ocb": (2, 1),
            "station-transformer-2-ct": (2, 0),
            "station-transformer-2-isolator": (2, -1),
            "station-transformer-2-transformer": (2, -3),
            "station-transformer-2-outgoing-line": (2, -5),
            "incoming-line-2": (6, -3),
            "incoming-line-2-isolator": (6, -1.5),
            "incoming-line-2-ct": (6, -0.5),
            "incoming-line-2-ocb": (6, 1),
        },
    )
    return builder.build()


def fig_25_10_dual_66kv_11kv_bus_sections() -> SubstationSystem:
    """Fig. 25.10: paired 66/11 kV bus sections and two transformer banks."""

    builder = _SubstationExampleBuilder(
        "fig-25-10-dual-66kv-11kv-bus-sections",
        "Fig. 25.10: two 66 kV and two 11 kV bus sections joined through two transformer banks.",
        _V66,
        Voltage(66, "kilovolt"),
    )
    builder.add_voltage_level(_V11, Voltage(11, "kilovolt"))
    builder.add_bus("66kv-bus-1", _V66)
    builder.add_bus("66kv-bus-2", _V66)
    builder.add_bus("11kv-bus-1", _V11)
    builder.add_bus("11kv-bus-2", _V11)
    builder.add_breaker(
        "66kv-bus-coupler-ocb",
        "66kv-bus-coupler-bay",
        "66kv-bus-1",
        "66kv-bus-2",
        voltage_level_id=_V66,
    )
    builder.add_breaker(
        "11kv-bus-coupler-ocb",
        "11kv-bus-coupler-bay",
        "11kv-bus-1",
        "11kv-bus-2",
        voltage_level_id=_V11,
    )
    for number, bus in ((1, "66kv-bus-1"), (2, "66kv-bus-2")):
        _add_incoming_line_bay(
            builder, f"incoming-line-{number}", f"incoming-line-{number}-bay", bus, _V66
        )
        _add_outgoing_transformer_bay(
            builder,
            f"transformer-bank-{number}",
            f"transformer-bank-{number}-bay",
            bus,
            _V66,
            Voltage(66, "kilovolt"),
            _V11,
            Voltage(11, "kilovolt"),
        )
        for feeder_number in range(1, 4):
            feeder_id = f"outgoing-feeder-{number}-{feeder_number}"
            builder.add_external_circuit(
                feeder_id,
                f"{feeder_id}-bay",
                "11kv-bus-1" if number == 1 else "11kv-bus-2",
                CircuitDirection.OUTGOING,
                _V11,
            )
    _pin(
        builder,
        {
            "66kv-bus-1-node": (-3, 4),
            "66kv-bus-2-node": (3, 4),
            "66kv-bus-coupler-ocb": (0, 4),
            "11kv-bus-1-node": (-3, 0),
            "11kv-bus-2-node": (3, 0),
            "11kv-bus-coupler-ocb": (0, 0),
            "incoming-line-1": (-6, 2),
            "incoming-line-1-isolator": (-5, 2.5),
            "incoming-line-1-ct": (-4, 3),
            "incoming-line-1-ocb": (-3, 3.5),
            "incoming-line-2": (6, 2),
            "incoming-line-2-isolator": (5, 2.5),
            "incoming-line-2-ct": (4, 3),
            "incoming-line-2-ocb": (3, 3.5),
            "transformer-bank-1-ocb": (-2, 3),
            "transformer-bank-1-ct": (-2, 2),
            "transformer-bank-1-isolator": (-2, 1),
            "transformer-bank-1-transformer": (-2, -1),
            "transformer-bank-1-outgoing-line": (-2, -2),
            "transformer-bank-2-ocb": (2, 3),
            "transformer-bank-2-ct": (2, 2),
            "transformer-bank-2-isolator": (2, 1),
            "transformer-bank-2-transformer": (2, -1),
            "transformer-bank-2-outgoing-line": (2, -2),
            "outgoing-feeder-1-1": (-5, -1),
            "outgoing-feeder-1-2": (-4, -1),
            "outgoing-feeder-1-3": (-3, -1),
            "outgoing-feeder-2-1": (3, -1),
            "outgoing-feeder-2-2": (4, -1),
            "outgoing-feeder-2-3": (5, -1),
        },
    )
    return builder.build()


def comprehensive_substation_single_line() -> SubstationSystem:
    """Comprehensive station fixture covering every supported single-line symbol."""

    builder = _SubstationExampleBuilder(
        "comprehensive-substation-single-line",
        "Reference station with switching, protection, transformation, and feeder equipment.",
        _V66,
        Voltage(66, "kilovolt"),
    )
    builder.add_voltage_level(_V11, Voltage(11, "kilovolt"))
    builder.add_bus("66kv-main-bus", _V66, diagram_start=(-9, 5), diagram_end=(9, 5))
    builder.add_bus("11kv-main-bus", _V11, diagram_start=(-9, -2), diagram_end=(9, -2))
    _add_incoming_line_bay(
        builder,
        "incoming-line",
        "incoming-line-bay",
        "66kv-main-bus",
        _V66,
        with_line_trap=True,
    )
    _add_outgoing_transformer_bay(
        builder,
        "station-transformer",
        "station-transformer-bay",
        "66kv-main-bus",
        _V66,
        Voltage(66, "kilovolt"),
        _V11,
        Voltage(11, "kilovolt"),
    )
    builder.add_shunt_instrument_transformer(
        "66kv-cvt", "66kv-metering-bay", "66kv-main-bus", "voltage_transformer", _V66
    )
    builder.add_surge_arrester("66kv-arrester", "66kv-protection-bay", "66kv-main-bus", _V66)
    builder.add_shunt_instrument_transformer(
        "11kv-cvt", "11kv-metering-bay", "11kv-main-bus", "voltage_transformer", _V11
    )
    builder.add_surge_arrester("11kv-arrester", "11kv-protection-bay", "11kv-main-bus", _V11)
    for feeder_number in range(1, 4):
        builder.add_feeder(
            f"feeder-{feeder_number}",
            f"feeder-{feeder_number}-bay",
            "11kv-main-bus",
            with_disconnector=True,
        )
    _position_terminals(builder, "incoming-line", [(-8, 5)])
    _position_terminals(builder, "incoming-line-line-trap", [(-8, 5), (-7, 5)])
    _position_terminals(builder, "incoming-line-isolator", [(-7, 5), (-6, 5)])
    _position_terminals(builder, "incoming-line-ct", [(-6, 5), (-5, 5)])
    _position_terminals(builder, "incoming-line-ocb", [(-5, 5), (-4, 5)])
    _position_terminals(builder, "station-transformer-ocb", [(0, 5), (0, 4)])
    _position_terminals(builder, "station-transformer-ct", [(0, 4), (0, 3)])
    _position_terminals(builder, "station-transformer-isolator", [(0, 3), (0, 2)])
    _position_terminals(builder, "station-transformer-transformer", [(0, 2), (0, -1)])
    _position_terminals(builder, "station-transformer-outgoing-line", [(0, -1)])
    _position_terminals(builder, "66kv-cvt", [(-1, 5)])
    _position_terminals(builder, "66kv-arrester", [(2, 5)])
    _position_terminals(builder, "11kv-cvt", [(-1, -2)])
    _position_terminals(builder, "11kv-arrester", [(2, -2)])
    for feeder_number, x_position in enumerate((-6, -4, 5), start=1):
        _position_terminals(
            builder,
            f"feeder-{feeder_number}-disconnector",
            [(x_position, -2), (x_position, -4)],
        )
    _pin(
        builder,
        {
            "incoming-line-line-trap": (-7.5, 5),
            "incoming-line-ct": (-5.5, 5),
            "66kv-cvt": (-1, 4),
            "66kv-arrester": (2, 4),
            "station-transformer-ct": (0, 3.5),
            "station-transformer-transformer": (0, 0.5),
            "11kv-cvt": (-1, -1),
            "11kv-arrester": (2, -1),
            "incoming-line-earth-switch": (-4.5, 4.5),
            "station-transformer-earth-switch": (0.5, 4),
        },
    )
    return builder.build()
