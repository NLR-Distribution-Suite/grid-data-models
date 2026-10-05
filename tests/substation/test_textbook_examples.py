"""Tests for the Desktop textbook single-line diagram transcriptions."""

import pytest

from gdm.quantities import Frequency
from gdm.systems.substation import (
    BusbarSection,
    CircuitBreaker,
    Disconnector,
    EarthingSwitch,
    ExternalCircuit,
    InstrumentTransformer,
    LineTrap,
    PowerTransformer,
    SubstationSystem,
    SurgeArrester,
)
from tests.substation import (
    comprehensive_substation_single_line,
    fig_25_4_bus_section_and_transfer_bus,
    fig_25_5_11kv_400v_single_bus,
    fig_25_6_33kv_sectionalized_bus,
    fig_25_7_double_main_bus_with_spare_bus,
    fig_25_8_11kv_400v_line_trap,
    fig_25_9_66kv_through_bus,
    fig_25_10_dual_66kv_11kv_bus_sections,
)


@pytest.mark.parametrize(
    ("builder", "busbars", "breakers", "circuits", "instrument_transformers", "transformers"),
    [
        (fig_25_4_bus_section_and_transfer_bus, 3, 4, 2, 2, 1),
        (fig_25_5_11kv_400v_single_bus, 1, 4, 4, 4, 2),
        (fig_25_6_33kv_sectionalized_bus, 2, 5, 4, 4, 2),
        (fig_25_7_double_main_bus_with_spare_bus, 3, 5, 4, 4, 2),
        (fig_25_8_11kv_400v_line_trap, 1, 2, 2, 3, 1),
        (fig_25_9_66kv_through_bus, 1, 2, 3, 2, 1),
        (fig_25_10_dual_66kv_11kv_bus_sections, 4, 6, 10, 4, 2),
    ],
)
def test_textbook_fixture_component_counts(
    builder,
    busbars,
    breakers,
    circuits,
    instrument_transformers,
    transformers,
):
    system = builder()

    assert isinstance(system, SubstationSystem)
    assert len(list(system.get_components(BusbarSection))) == busbars
    assert len(list(system.get_components(CircuitBreaker))) == breakers
    assert len(list(system.get_components(ExternalCircuit))) == circuits
    assert len(list(system.get_components(InstrumentTransformer))) == instrument_transformers
    assert len(list(system.get_components(PowerTransformer))) == transformers


def test_fig_25_6_models_a_normally_open_bus_section_coupler():
    system = fig_25_6_33kv_sectionalized_bus()
    coupler = next(
        system.get_components(
            CircuitBreaker, filter_func=lambda x: x.name == "bus-section-coupler-ocb"
        )
    )

    assert coupler.state.value == "open"
    assert coupler.normal_state.value == "open"


def test_fig_25_8_models_the_carrier_wave_line_trap():
    system = fig_25_8_11kv_400v_line_trap()
    line_trap = next(system.get_components(LineTrap))
    cvt = next(
        system.get_components(
            InstrumentTransformer,
            filter_func=lambda x: x.name == "capacitive-voltage-transformer",
        )
    )

    assert line_trap.name == "incoming-line-line-trap"
    assert line_trap.tuning_frequency_hz == Frequency(100_000, "hertz")
    assert cvt.instrument_type == "capacitive_voltage_transformer"
    assert len(cvt.terminal_ids) == 1


@pytest.mark.parametrize(
    "builder,coupler_name",
    [
        (fig_25_4_bus_section_and_transfer_bus, "bus-coupler-ocb"),
        (fig_25_7_double_main_bus_with_spare_bus, "bus-coupler-ocb"),
    ],
)
def test_open_bus_couplers_remain_explicit_in_the_source_diagram_fixtures(builder, coupler_name):
    system = builder()
    coupler = next(
        system.get_components(CircuitBreaker, filter_func=lambda x: x.name == coupler_name)
    )

    assert coupler.state.value == "open"


def test_fig_25_10_has_two_voltage_levels_and_two_bus_couplers():
    system = fig_25_10_dual_66kv_11kv_bus_sections()
    couplers = [
        breaker
        for breaker in system.get_components(CircuitBreaker)
        if "bus-coupler" in breaker.name
    ]

    assert len(couplers) == 2


def test_comprehensive_single_line_covers_every_supported_station_symbol():
    system = comprehensive_substation_single_line()

    assert len(list(system.get_components(BusbarSection))) == 2
    assert len(list(system.get_components(CircuitBreaker))) >= 2
    assert len(list(system.get_components(Disconnector))) >= 4
    assert len(list(system.get_components(EarthingSwitch))) >= 2
    assert len(list(system.get_components(ExternalCircuit))) >= 2
    assert len(list(system.get_components(InstrumentTransformer))) >= 3
    assert len(list(system.get_components(LineTrap))) == 1
    assert len(list(system.get_components(PowerTransformer))) == 1
    assert len(list(system.get_components(SurgeArrester))) == 2
