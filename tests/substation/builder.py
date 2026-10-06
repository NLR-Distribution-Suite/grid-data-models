"""Test support for constructing detailed distribution substations.

``SubstationBuilder`` assembles a :class:`SubstationSystem` while keeping the
bus-branch component references, bays, and administrative objects consistent.
It is the supported way to construct a detailed station instead of wiring
components together by hand. This helper is intentionally kept outside the
production package.
"""

from __future__ import annotations

from collections.abc import Callable

from infrasys import Location

from gdm.quantities import ApparentPower, Distance, Frequency, Voltage
from gdm.systems.distribution.common.sequence_pair import SequencePair
from gdm.systems.distribution.enums import ConnectionType, Phase, VoltageTypes
from gdm.systems.distribution.equipment import (
    CircuitBreakerEquipment,
    DisconnectorEquipment,
    EarthingSwitchEquipment,
    PowerTransformerEquipment,
    WindingEquipment,
)
from gdm.systems.substation.automation import (
    IED,
    ProtocolEndpoint,
    ProtocolMapping,
    SCLConfiguration,
    SemanticSignal,
)
from gdm.systems.substation.components import (
    CircuitBreaker,
    Disconnector,
    EarthingSwitch,
    PowerTransformer,
    PrimaryEquipmentComponent,
)
from gdm.systems.substation.enums import (
    CircuitDirection,
    EquipmentState,
    MeasurementPurpose,
    ProtocolType,
    ProtectionFunctionType,
    SubstationType,
)
from gdm.systems.substation.equipment import InstrumentTransformer, LineTrap, SurgeArrester
from gdm.systems.substation.metering import (
    InstrumentTransformerCore,
    MeteringPoint,
    PowerQualityMonitor,
)
from gdm.systems.substation.protection import (
    ProtectionFunction,
    ProtectionIED,
    ProtectionScheme,
    ProtectionSetting,
    ProtectionSettingGroup,
)
from gdm.systems.substation.substation_system import SubstationSystem
from gdm.systems.substation.topology import (
    Bay,
    BusbarSection,
    ExternalCircuit,
    FeederBoundary,
    Substation,
    VoltageLevel,
)

_PHASES = [Phase.A, Phase.B, Phase.C]
DEFAULT_VOLTAGE_LEVEL_ID = "voltage-level-mv"
DEFAULT_HV_VOLTAGE_LEVEL_ID = "voltage-level-hv"
DEFAULT_SUBSTATION_NAME = "substation"


class SubstationBuilder:
    """Build a detailed substation with consistent component references.

    Parameters
    ----------
    name : str
        Name of the resulting :class:`SubstationSystem`.
    description : str | None
        Optional system description.
    initial_voltage_level_id : str
        Name of the first voltage level to create.
    initial_nominal_voltage : Voltage
        Nominal voltage of the first voltage level.
    substation_type : SubstationType
        Facility type for the enclosing :class:`Substation`.
    substation_name : str
        Name of the enclosing :class:`Substation`.
    coordinate_provider : Callable[[int], Location] | None
        Optional factory assigning a geographic coordinate to each node created
        without an explicit one. Receives a monotonically increasing index.
    """

    def __init__(
        self,
        name: str,
        description: str | None = None,
        initial_voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID,
        initial_nominal_voltage: Voltage = Voltage(12.47, "kilovolt"),
        substation_type: SubstationType = SubstationType.DISTRIBUTION,
        substation_name: str = DEFAULT_SUBSTATION_NAME,
        coordinate_provider: Callable[[int], Location] | None = None,
    ):
        self.system = SubstationSystem(
            auto_add_composed_components=True,
            name=name,
            description=description,
        )
        self.nodes: dict[str, BusbarSection] = {}
        self.bays: dict[str, Bay] = {}
        self.voltage_levels: dict[str, VoltageLevel] = {}
        self._coordinate_provider = coordinate_provider
        self._node_index = 0
        self.substation = Substation(name=substation_name, substation_type=substation_type)
        self.system.add_component(self.substation)
        self.add_voltage_level(initial_voltage_level_id, initial_nominal_voltage)

    # ------------------------------------------------------------------
    # Buses, bays, and voltage levels
    # ------------------------------------------------------------------
    def add_voltage_level(
        self,
        voltage_level_id: str,
        nominal_voltage: Voltage,
        voltage_type: VoltageTypes = VoltageTypes.LINE_TO_LINE,
    ) -> VoltageLevel:
        """Add a voltage level and register it on the substation."""

        voltage_level = VoltageLevel(
            name=voltage_level_id,
            nominal_voltage=nominal_voltage,
            voltage_type=voltage_type,
        )
        self.voltage_levels[voltage_level_id] = voltage_level
        self.substation.voltage_levels.append(voltage_level)
        self.system.add_component(voltage_level)
        return voltage_level

    def add_bus(
        self,
        bus_id: str,
        voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID,
        *,
        length: Distance | None = Distance(12, "meter"),
        coordinate: Location | None = None,
    ) -> BusbarSection:
        """Add a physical busbar section node and return it."""

        bus = self._make_node(
            bus_id,
            voltage_level_id,
            length=length,
            coordinate=coordinate,
        )
        self.nodes[bus_id] = bus
        return bus

    def _make_node(
        self,
        node_id: str,
        voltage_level_id: str,
        length: Distance | None = None,
        coordinate: Location | None = None,
    ) -> BusbarSection:
        if coordinate is None and self._coordinate_provider is not None:
            coordinate = self._coordinate_provider(self._node_index)
        self._node_index += 1
        voltage_level = self.voltage_levels[voltage_level_id]
        node = BusbarSection(
            name=node_id,
            voltage_level=voltage_level,
            rated_voltage=voltage_level.nominal_voltage,
            voltage_type=voltage_level.voltage_type,
            phases=list(_PHASES),
            length=length,
            coordinate=coordinate,
        )
        self.system.add_component(node)
        return node

    def add_node(
        self,
        node_id: str,
        voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID,
        *,
        coordinate: Location | None = None,
    ) -> BusbarSection:
        """Add an electrical junction node (no busbar length)."""

        if node_id not in self.nodes:
            self.nodes[node_id] = self._make_node(
                node_id,
                voltage_level_id,
                coordinate=coordinate,
            )
        return self.nodes[node_id]

    def endpoint_node(
        self, endpoint: str, voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID
    ) -> BusbarSection:
        if endpoint in self.nodes:
            return self.nodes[endpoint]
        return self.add_node(endpoint, voltage_level_id)

    def add_bay(self, bay_id: str, voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID) -> Bay:
        """Add or return a functional bay grouping."""

        bay = self.bays.get(bay_id)
        if bay is None:
            bay = Bay(name=bay_id, voltage_level=self.voltage_levels[voltage_level_id])
            self.bays[bay_id] = bay
            self.substation.bays.append(bay)
            self.system.add_component(bay)
        return bay

    # ------------------------------------------------------------------
    # Primary equipment
    # ------------------------------------------------------------------
    def add_two_terminal_equipment(
        self,
        equipment_id: str,
        bay_id: str,
        from_endpoint: str,
        to_endpoint: str,
        equipment_type: type[CircuitBreaker] | type[Disconnector],
        state: EquipmentState = EquipmentState.CLOSED,
        normal_state: EquipmentState = EquipmentState.CLOSED,
        bay_voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID,
        voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID,
    ) -> tuple[BusbarSection, BusbarSection]:
        """Add series switching equipment and return the two nodes it connects."""

        from_node = self.endpoint_node(from_endpoint, voltage_level_id)
        if from_node.voltage_level is not None:
            voltage_level_id = from_node.voltage_level.name
            bay_voltage_level_id = voltage_level_id
        to_node = self.endpoint_node(to_endpoint, voltage_level_id)
        equipment_definitions = {
            CircuitBreaker: CircuitBreakerEquipment,
            Disconnector: DisconnectorEquipment,
        }
        equipment = equipment_type(
            name=equipment_id,
            bay=self.add_bay(bay_id, bay_voltage_level_id),
            buses=[from_node, to_node],
            equipment=equipment_definitions[equipment_type].example(),
            state=state,
            normal_state=normal_state,
        )
        self.system.add_component(equipment)
        return from_node, to_node

    def add_breaker(
        self,
        breaker_id: str,
        bay_id: str,
        from_endpoint: str,
        to_endpoint: str,
        state: EquipmentState = EquipmentState.CLOSED,
        normal_state: EquipmentState = EquipmentState.CLOSED,
        voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID,
    ) -> tuple[BusbarSection, BusbarSection]:
        """Add a circuit breaker between two nodes."""

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
        )

    def add_disconnector(
        self,
        disconnector_id: str,
        bay_id: str,
        from_endpoint: str,
        to_endpoint: str,
        state: EquipmentState = EquipmentState.CLOSED,
        normal_state: EquipmentState = EquipmentState.CLOSED,
        voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID,
    ) -> tuple[BusbarSection, BusbarSection]:
        """Add a visible isolation switch between two nodes."""

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
        )

    def add_earthing_switch(
        self, switch_id: str, bay_id: str, bus: BusbarSection
    ) -> EarthingSwitch:
        """Add an open safety ground switch on a node."""

        switch = EarthingSwitch(
            name=switch_id,
            bay=self.add_bay(
                bay_id,
                bus.voltage_level.name if bus.voltage_level else DEFAULT_VOLTAGE_LEVEL_ID,
            ),
            bus=bus,
            equipment=EarthingSwitchEquipment.example(),
        )
        self.system.add_component(switch)
        return switch

    def add_line_trap(
        self,
        line_trap_id: str,
        bay_id: str,
        from_endpoint: str,
        to_endpoint: str,
        tuning_frequency_hz: Frequency | None = Frequency(100_000, "hertz"),
        voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID,
    ) -> tuple[BusbarSection, BusbarSection]:
        """Add a carrier-wave line trap in series with an external circuit."""

        from_node = self.endpoint_node(from_endpoint, voltage_level_id)
        if from_node.voltage_level is not None:
            voltage_level_id = from_node.voltage_level.name
        to_node = self.endpoint_node(to_endpoint, voltage_level_id)
        self.system.add_component(
            LineTrap(
                name=line_trap_id,
                bay=self.add_bay(bay_id, voltage_level_id),
                buses=[from_node, to_node],
                tuning_frequency_hz=tuning_frequency_hz,
            )
        )
        return from_node, to_node

    def add_instrument_transformer(
        self,
        transformer_id: str,
        bay_id: str,
        from_endpoint: str,
        to_endpoint: str,
        instrument_type: str = "current_transformer",
        primary_rating: float = 600,
        secondary_rating: float = 5,
        ratio_unit: str = "ampere",
        cores: list[InstrumentTransformerCore] | None = None,
        voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID,
    ) -> InstrumentTransformer:
        """Add a series-connected CT, PT, or CVT between two nodes."""

        from_node = self.endpoint_node(from_endpoint, voltage_level_id)
        if from_node.voltage_level is not None:
            voltage_level_id = from_node.voltage_level.name
        to_node = self.endpoint_node(to_endpoint, voltage_level_id)
        transformer = InstrumentTransformer(
            name=transformer_id,
            bay=self.add_bay(bay_id, voltage_level_id),
            buses=[from_node, to_node],
            instrument_type=instrument_type,
            primary_rating=primary_rating,
            secondary_rating=secondary_rating,
            ratio_unit=ratio_unit,
            cores=cores or [],
        )
        self.system.add_component(transformer)
        return transformer

    def add_shunt_instrument_transformer(
        self,
        transformer_id: str,
        bay_id: str,
        endpoint: str,
        instrument_type: str = "voltage_transformer",
        primary_rating: float = 11_000,
        secondary_rating: float = 110,
        ratio_unit: str = "volt",
        cores: list[InstrumentTransformerCore] | None = None,
        voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID,
    ) -> InstrumentTransformer:
        """Add a shunt-connected PT or CVT on a single node."""

        bus = self.endpoint_node(endpoint, voltage_level_id)
        if bus.voltage_level is not None:
            voltage_level_id = bus.voltage_level.name
        transformer = InstrumentTransformer(
            name=transformer_id,
            bay=self.add_bay(bay_id, voltage_level_id),
            buses=[bus],
            instrument_type=instrument_type,
            primary_rating=primary_rating,
            secondary_rating=secondary_rating,
            ratio_unit=ratio_unit,
            cores=cores or [],
        )
        self.system.add_component(transformer)
        return transformer

    def add_surge_arrester(
        self,
        arrester_id: str,
        bay_id: str,
        endpoint: str,
        mcov: Voltage = Voltage(9, "kilovolt"),
        voltage_level_id: str = DEFAULT_VOLTAGE_LEVEL_ID,
    ) -> SurgeArrester:
        """Add a shunt surge arrester at a node."""

        bus = self.endpoint_node(endpoint, voltage_level_id)
        if bus.voltage_level is not None:
            voltage_level_id = bus.voltage_level.name
        arrester = SurgeArrester(
            name=arrester_id,
            bay=self.add_bay(bay_id, voltage_level_id),
            bus=bus,
            mcov=mcov,
        )
        self.system.add_component(arrester)
        return arrester

    def add_external_circuit(
        self,
        circuit_id: str,
        bay_id: str,
        endpoint: str,
        direction: CircuitDirection,
        voltage_level_id: str,
    ) -> ExternalCircuit:
        """Add an incoming or outgoing transmission/distribution circuit."""

        bus = self.endpoint_node(endpoint, voltage_level_id)
        if bus.voltage_level is not None:
            voltage_level_id = bus.voltage_level.name
        circuit = ExternalCircuit(
            name=circuit_id,
            circuit_id=circuit_id,
            bus=bus,
            direction=direction,
            voltage_level=self.voltage_levels[voltage_level_id],
            bay=self.add_bay(bay_id, voltage_level_id),
        )
        self.system.add_component(circuit)
        return circuit

    def add_power_transformer(
        self,
        transformer_id: str,
        bay_id: str,
        buses: list[BusbarSection],
        windings: list[WindingEquipment],
        *,
        pct_no_load_loss: float = 0.1,
        pct_full_load_loss: float = 1,
        coupling_sequences: list[SequencePair] | None = None,
        winding_reactances: list[float] | None = None,
        vector_group: str | None = "Dyn1",
        cooling_class: str | None = "ONAN",
        fluid_type: str | None = "mineral_oil",
    ) -> PowerTransformer:
        """Add a multi-winding power transformer between ordered buses."""

        sequences = coupling_sequences or [
            SequencePair(i, i + 1) for i in range(len(windings) - 1)
        ]
        transformer = PowerTransformer(
            name=transformer_id,
            bay=self.add_bay(
                bay_id,
                buses[0].voltage_level.name
                if buses[0].voltage_level
                else DEFAULT_VOLTAGE_LEVEL_ID,
            ),
            buses=buses,
            equipment=PowerTransformerEquipment(
                name=f"{transformer_id}-equipment",
                pct_no_load_loss=pct_no_load_loss,
                pct_full_load_loss=pct_full_load_loss,
                is_center_tapped=False,
                windings=windings,
                coupling_sequences=sequences,
                winding_reactances=winding_reactances or [8.5] * len(sequences),
                vector_group=vector_group,
                cooling_class=cooling_class,
                fluid_type=fluid_type,
            ),
        )
        self.system.add_component(transformer)
        return transformer

    def add_two_winding_transformer(
        self,
        transformer_id: str,
        bay_id: str,
        high_voltage_bus: BusbarSection,
        low_voltage_bus: BusbarSection,
        *,
        rated_power: ApparentPower = ApparentPower(30, "megavolt_ampere"),
        high_voltage_connection: ConnectionType = ConnectionType.DELTA,
        low_voltage_connection: ConnectionType = ConnectionType.STAR,
        vector_group: str = "Dyn1",
        high_voltage_is_grounded: bool = False,
        low_voltage_is_grounded: bool = True,
    ) -> PowerTransformer:
        """Add a two-winding power transformer between two buses."""

        windings = [
            WindingEquipment(
                name=f"{transformer_id}-hv-winding",
                resistance=1,
                is_grounded=high_voltage_is_grounded,
                rated_voltage=high_voltage_bus.rated_voltage,
                voltage_type=VoltageTypes.LINE_TO_LINE,
                rated_power=rated_power,
                num_phases=3,
                connection_type=high_voltage_connection,
                tap_positions=[1.0, 1.0, 1.0],
            ),
            WindingEquipment(
                name=f"{transformer_id}-lv-winding",
                resistance=1,
                is_grounded=low_voltage_is_grounded,
                rated_voltage=low_voltage_bus.rated_voltage,
                voltage_type=VoltageTypes.LINE_TO_LINE,
                rated_power=rated_power,
                num_phases=3,
                connection_type=low_voltage_connection,
                tap_positions=[1.0, 1.0, 1.0],
            ),
        ]
        return self.add_power_transformer(
            transformer_id,
            bay_id,
            buses=[high_voltage_bus, low_voltage_bus],
            windings=windings,
            vector_group=vector_group,
        )

    def add_feeder(
        self,
        feeder_id: str,
        bay_id: str,
        station_endpoint: str,
        with_disconnector: bool = False,
        bus: BusbarSection | None = None,
        distribution_model_reference_id: str | None = None,
    ) -> FeederBoundary:
        """Add a feeder boundary, optionally through a line disconnector."""

        if with_disconnector:
            _, bus = self.add_disconnector(
                f"{feeder_id}-disconnector",
                bay_id,
                station_endpoint,
                f"{feeder_id}-node",
            )
        elif bus is None:
            bus = self.endpoint_node(station_endpoint)
        boundary = FeederBoundary(
            name=f"{feeder_id}-boundary",
            feeder_id=feeder_id,
            bus=bus,
            substation=self.substation,
            voltage_level=bus.voltage_level,
            bay=self.add_bay(
                bay_id,
                bus.voltage_level.name if bus.voltage_level else DEFAULT_VOLTAGE_LEVEL_ID,
            ),
            distribution_model_reference_id=distribution_model_reference_id,
        )
        self.system.add_component(boundary)
        return boundary

    # ------------------------------------------------------------------
    # Protection, metering, and SCADA
    # ------------------------------------------------------------------
    def add_instrument_core(
        self,
        core_id: str,
        core_type: str = "protection",
        purpose: MeasurementPurpose = MeasurementPurpose.OPERATIONAL,
        accuracy_class: str | None = None,
        burden_va: float | None = None,
    ) -> InstrumentTransformerCore:
        core = InstrumentTransformerCore(
            name=core_id,
            core_type=core_type,
            purpose=purpose,
            accuracy_class=accuracy_class,
            burden_va=burden_va,
        )
        self.system.add_component(core)
        return core

    def add_protection_ied(
        self,
        ied_id: str,
        bay: Bay | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        firmware_version: str | None = None,
        documents=None,
    ) -> ProtectionIED:
        ied = ProtectionIED(
            name=ied_id,
            bay=bay,
            manufacturer=manufacturer,
            model=model,
            firmware_version=firmware_version,
            documents=documents or [],
        )
        self.system.add_component(ied)
        return ied

    def add_setting_group(
        self,
        group_id: str,
        group_name: str = "normal",
        settings: list[ProtectionSetting] | None = None,
        approved: bool = False,
    ) -> ProtectionSettingGroup:
        group = ProtectionSettingGroup(
            name=group_id,
            group_name=group_name,
            settings=settings or [],
            approved=approved,
        )
        self.system.add_component(group)
        return group

    def add_setting(
        self,
        setting_id: str,
        parameter: str,
        value,
        unit: str | None = None,
        phase_scope: str | None = None,
    ) -> ProtectionSetting:
        setting = ProtectionSetting(
            name=setting_id,
            parameter=parameter,
            value=value,
            unit=unit,
            phase_scope=phase_scope,
        )
        self.system.add_component(setting)
        return setting

    def add_protection_function(
        self,
        function_id: str,
        function_type: ProtectionFunctionType,
        ied: ProtectionIED,
        *,
        ansi_function_number: str | None = None,
        instance: str | None = None,
        protects_equipment: list[PrimaryEquipmentComponent] | None = None,
        input_cores: list[InstrumentTransformerCore] | None = None,
        output_equipment: list[PrimaryEquipmentComponent] | None = None,
        setting_groups: list[ProtectionSettingGroup] | None = None,
    ) -> ProtectionFunction:
        function = ProtectionFunction(
            name=function_id,
            function_type=function_type,
            ied=ied,
            ansi_function_number=ansi_function_number,
            instance=instance,
            protects_equipment=protects_equipment or [],
            input_cores=input_cores or [],
            output_equipment=output_equipment or [],
            setting_groups=setting_groups or [],
        )
        self.system.add_component(function)
        return function

    def add_protection_scheme(
        self,
        scheme_id: str,
        zone: str,
        *,
        functions=None,
        equipment=None,
        documents=None,
    ) -> ProtectionScheme:
        scheme = ProtectionScheme(
            name=scheme_id,
            zone=zone,
            functions=functions or [],
            equipment=equipment or [],
            documents=documents or [],
        )
        self.system.add_component(scheme)
        return scheme

    def add_metering_point(
        self,
        point_id: str,
        purpose: MeasurementPurpose,
        bus: BusbarSection,
        meter_id: str,
        *,
        cores=None,
        multiplier: float = 1,
        interval_seconds: int | None = None,
        owner: str | None = None,
    ) -> MeteringPoint:
        point = MeteringPoint(
            name=point_id,
            purpose=purpose,
            bus=bus,
            meter_id=meter_id,
            cores=cores or [],
            multiplier=multiplier,
            interval_seconds=interval_seconds,
            owner=owner,
        )
        self.system.add_component(point)
        return point

    def add_power_quality_monitor(
        self,
        monitor_id: str,
        bus: BusbarSection,
        measurement_method: str = "IEEE 1159",
        monitored_phenomena=None,
        pcc: bool = False,
    ) -> PowerQualityMonitor:
        monitor = PowerQualityMonitor(
            name=monitor_id,
            bus=bus,
            measurement_method=measurement_method,
            monitored_phenomena=monitored_phenomena or [],
            pcc=pcc,
        )
        self.system.add_component(monitor)
        return monitor

    def add_protocol_endpoint(
        self,
        endpoint_id: str,
        protocol: ProtocolType,
        address: str,
        host: str | None = None,
        port: int | None = None,
        secure: bool = False,
    ) -> ProtocolEndpoint:
        endpoint = ProtocolEndpoint(
            name=endpoint_id,
            protocol=protocol,
            address=address,
            host=host,
            port=port,
            secure=secure,
        )
        self.system.add_component(endpoint)
        return endpoint

    def add_automation_ied(
        self,
        ied_id: str,
        device_type: str,
        *,
        bay: Bay | None = None,
        manufacturer: str | None = None,
        model: str | None = None,
        firmware_version: str | None = None,
        protocol_endpoints=None,
    ) -> IED:
        ied = IED(
            name=ied_id,
            device_type=device_type,
            bay=bay,
            manufacturer=manufacturer,
            model=model,
            firmware_version=firmware_version,
            protocol_endpoints=protocol_endpoints or [],
        )
        self.system.add_component(ied)
        return ied

    def add_semantic_signal(
        self,
        signal_id: str,
        signal_type: str,
        source_object,
        unit: str | None = None,
        engineering_description: str | None = None,
    ) -> SemanticSignal:
        signal = SemanticSignal(
            name=signal_id,
            signal_type=signal_type,
            source_object=source_object,
            unit=unit,
            engineering_description=engineering_description,
        )
        self.system.add_component(signal)
        return signal

    def add_protocol_mapping(
        self,
        mapping_id: str,
        signal: SemanticSignal,
        endpoint: ProtocolEndpoint,
        protocol: ProtocolType,
        point_type: str,
        point_address: str,
        variation: str | None = None,
    ) -> ProtocolMapping:
        mapping = ProtocolMapping(
            name=mapping_id,
            signal=signal,
            endpoint=endpoint,
            protocol=protocol,
            point_type=point_type,
            point_address=point_address,
            variation=variation,
        )
        self.system.add_component(mapping)
        return mapping

    def add_scl_configuration(
        self,
        configuration_id: str,
        document_type: str,
        uri: str,
        *,
        revision: str | None = None,
        schema_version: str | None = None,
        ieds=None,
    ) -> SCLConfiguration:
        configuration = SCLConfiguration(
            name=configuration_id,
            document_type=document_type,
            uri=uri,
            revision=revision,
            schema_version=schema_version,
            ieds=ieds or [],
        )
        self.system.add_component(configuration)
        return configuration

    def build(self) -> SubstationSystem:
        """Return the assembled system."""

        return self.system
