"""Reusable substation layout examples used by the test suite."""

from tests.substation.examples import (
    LAYOUT_EXAMPLES,
    SubstationLayout,
    breaker_and_a_half_substation,
    build_layout_example,
    double_breaker_double_bus_substation,
    double_bus_single_breaker_substation,
    hv_mv_single_bus_substation,
    hv_mv_substation_with_distribution_feeders,
    main_and_transfer_substation,
    ring_bus_substation,
    sectionalized_single_bus_substation,
    single_bus_substation,
)
from tests.substation.textbook_examples import (
    comprehensive_substation_single_line,
    fig_25_4_bus_section_and_transfer_bus,
    fig_25_5_11kv_400v_single_bus,
    fig_25_6_33kv_sectionalized_bus,
    fig_25_7_double_main_bus_with_spare_bus,
    fig_25_8_11kv_400v_line_trap,
    fig_25_9_66kv_through_bus,
    fig_25_10_dual_66kv_11kv_bus_sections,
)

__all__ = [
    "LAYOUT_EXAMPLES",
    "SubstationLayout",
    "breaker_and_a_half_substation",
    "build_layout_example",
    "double_breaker_double_bus_substation",
    "double_bus_single_breaker_substation",
    "hv_mv_single_bus_substation",
    "hv_mv_substation_with_distribution_feeders",
    "comprehensive_substation_single_line",
    "fig_25_4_bus_section_and_transfer_bus",
    "fig_25_5_11kv_400v_single_bus",
    "fig_25_6_33kv_sectionalized_bus",
    "fig_25_7_double_main_bus_with_spare_bus",
    "fig_25_8_11kv_400v_line_trap",
    "fig_25_9_66kv_through_bus",
    "fig_25_10_dual_66kv_11kv_bus_sections",
    "main_and_transfer_substation",
    "ring_bus_substation",
    "sectionalized_single_bus_substation",
    "single_bus_substation",
]
