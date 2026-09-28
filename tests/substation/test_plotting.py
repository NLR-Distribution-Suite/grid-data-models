"""Tests for substation schematic plotting."""

import plotly.graph_objects as go
import pytest

from tests.substation import SubstationLayout, build_layout_example


@pytest.mark.parametrize("layout", SubstationLayout)
def test_substation_plot_builds_a_schematic(layout, tmp_path):
    system = build_layout_example(layout)

    figure = system.plot(tmp_path, show=False)

    assert isinstance(figure, go.Figure)
    assert figure.data
    assert any(trace.mode == "lines" for trace in figure.data)
    assert any(trace.mode == "markers+text" for trace in figure.data)
    assert (tmp_path / f"{system.name}_plot.html").exists()


def test_substation_plot_accepts_plotly_layout_options():
    system = build_layout_example(SubstationLayout.RING_BUS)

    figure = system.plot(show=False, width=900, height=600)

    assert figure.layout.width == 900
    assert figure.layout.height == 600


def test_substation_plot_validates_export_path(tmp_path):
    system = build_layout_example(SubstationLayout.SINGLE_BUS)

    with pytest.raises(FileNotFoundError):
        system.plot(tmp_path / "missing", show=False)
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("existing file")
    with pytest.raises(NotADirectoryError):
        system.plot(output_file, show=False)


def test_layered_positions_follow_power_flow_direction():
    system = build_layout_example(SubstationLayout.SECTIONALIZED_SINGLE_BUS)
    graph = system._build_plot_graph()
    positions = system._build_plot_positions(graph)

    assert positions == system._build_plot_positions(graph)
    bus_y = positions["connectivity:bus-a-node"][1]
    breaker_y = positions["equipment:feeder-1-breaker"][1]
    feeder_y = positions["boundary:feeder-1-boundary"][1]
    assert bus_y > breaker_y > feeder_y


def test_ring_positions_preserve_circular_bus_arrangement():
    system = build_layout_example(SubstationLayout.RING_BUS)
    graph = system._build_plot_graph()
    positions = system._build_plot_positions(graph)

    bus_positions = [
        positions[node] for node, data in graph.nodes(data=True) if data["kind"] == "busbar"
    ]
    radii = {(x**2 + y**2) ** 0.5 for x, y in bus_positions}
    assert len(bus_positions) == 4
    assert len(radii) == 1
    assert len({position for position in bus_positions}) == 4


def test_hv_mv_plot_places_transformer_between_voltage_level_buses():
    system = build_layout_example(SubstationLayout.HV_MV_SINGLE_BUS)
    graph = system._build_plot_graph()
    positions = system._build_plot_positions(graph)

    hv_y = positions["connectivity:hv-bus-node"][1]
    mv_y = positions["connectivity:mv-bus-node"][1]
    transformer_y = positions["equipment:station-transformer"][1]

    assert hv_y > transformer_y > mv_y
    assert graph.nodes["connectivity:hv-bus-node"]["label"] == "hv-bus<br>69 kV"
    assert graph.nodes["connectivity:mv-bus-node"]["label"] == "mv-bus<br>12.47 kV"
    assert graph.nodes["equipment:station-transformer"]["label"] == (
        "station-transformer<br>69 kV/12.47 kV"
    )
