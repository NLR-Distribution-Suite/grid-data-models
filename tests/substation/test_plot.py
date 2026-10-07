"""Tests for geographic substation plotting."""

import json

import pytest

from gdm.systems.distribution.enums import ColorLineBy, ColorNodeBy, MapType
from tests.substation import build_layout_example
from gdm.systems.substation.builder import SubstationBuilder
from gdm.systems.substation.detailed_reference import build_detailed_distribution_substation
from gdm.systems.substation.reference_designs import build_reference_design
from gdm.systems.substation.topology import Bay, BusbarSection, Substation


def test_plot_returns_plotly_figure_with_traces():
    system = build_detailed_distribution_substation()
    figure = system.plot(show=False)

    assert len(figure.data) >= 2
    assert any(trace.type in {"scattergeo", "scattermap"} for trace in figure.data)


def test_to_gdf_contains_nodes_and_equipment_edges(tmp_path):
    system = build_detailed_distribution_substation()

    geodataframe = system.to_gdf(tmp_path / "station.csv")

    assert (tmp_path / "station.csv").exists()
    assert {"Name", "Type", "Phases", "kV", "geometry"}.issubset(geodataframe.columns)
    assert "BusbarSection" in set(geodataframe.Type)
    assert any(geometry.geom_type == "Point" for geometry in geodataframe.geometry)
    assert any(geometry.geom_type == "LineString" for geometry in geodataframe.geometry)
    assert geodataframe.crs.to_string() == "EPSG:4326"


def test_to_geojson_exports_topology(tmp_path):
    system = build_detailed_distribution_substation()
    output = tmp_path / "station.geojson"

    system.to_geojson(output)

    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["type"] == "FeatureCollection"
    assert document["features"]


def test_plot_requires_geographic_coordinates():
    system = build_layout_example("single_bus")

    with pytest.raises(ValueError, match="geographic coordinates"):
        system.plot(show=False)


def test_plot_aligns_with_distribution_plot_options():
    system = build_detailed_distribution_substation()
    figure = system.plot(
        show=False,
        color_node_by=ColorNodeBy.VOLTAGE_LEVEL,
        color_line_by=ColorLineBy.EQUIPMENT_TYPE,
        show_legend=False,
        map_type=MapType.SCATTER_GEO,
    )
    names = {trace.name for trace in figure.data}

    assert any(name.startswith("Nodes - kV -") for name in names)
    assert any(name.startswith("Edges - Type -") for name in names)
    assert figure.layout.showlegend is False


def test_plot_exports_html(tmp_path):
    system = build_detailed_distribution_substation()

    system.plot(export_path=tmp_path, show=False)

    output = tmp_path / f"{system.name}_plot.html"
    assert output.exists()
    assert "<html" in output.read_text(encoding="utf-8").lower()


def test_plot_with_geometry_from_builder():
    from infrasys import Location

    builder = SubstationBuilder("geo")
    builder.add_bus("bus-a", coordinate=Location(x=-105.2, y=39.74))
    builder.add_bus("bus-b", coordinate=Location(x=-105.199, y=39.74))
    builder.add_breaker("tie", "tie-bay", "bus-a", "bus-b")
    system = builder.build()

    figure = system.plot(show=False)

    assert figure.data


def test_schematic_plot_renders_cartesian_topology():
    from infrasys import Location

    system = build_layout_example("double_breaker_double_bus")
    for index, bus in enumerate(system.get_components(BusbarSection)):
        bus.coordinate = Location(x=float(index), y=float(index % 2))

    figure = system.plot_schematic(show=False)

    assert figure.data
    assert figure.layout.yaxis.scaleanchor == "x"


@pytest.mark.parametrize(
    "layout",
    [
        "single_bus",
        "sectionalized_single_bus",
        "main_and_transfer",
        "double_bus_single_breaker",
        "ring_bus",
        "breaker_and_a_half",
        "double_breaker_double_bus",
        "hv_mv_single_bus",
    ],
)
def test_reference_design_schematics_have_layout_coordinates(layout):
    system = build_layout_example(layout)

    buses = list(system.get_components(BusbarSection))
    figure = system.plot_schematic(show=False)

    assert buses
    assert all(bus.coordinate is not None for bus in buses)
    assert all(bus.coordinate.crs == "EPSG:3857" for bus in buses)
    assert figure.data
    if layout == "ring_bus":
        busbar_traces = [trace for trace in figure.data if trace.name == "Busbars"]
        assert len(busbar_traces) == 1
        assert "hv-bus" in busbar_traces[0].hovertemplate
    if layout in {"double_bus_single_breaker", "double_breaker_double_bus"}:
        branch_node_id = (
            "feeder-1-breaker-node"
            if layout == "double_bus_single_breaker"
            else "feeder-1-circuit-node"
        )
        branch_node = system.get_component(BusbarSection, branch_node_id)
        feeder_node = system.get_component(BusbarSection, "feeder-1-node")
        assert branch_node.coordinate.y == feeder_node.coordinate.y
        assert branch_node.coordinate.x != feeder_node.coordinate.x
    if layout == "breaker_and_a_half":
        node_trace = next(trace for trace in figure.data if trace.name == "Busbar sections")
        labels = {label for label in node_trace.text if label}
        assert "feeder-1" in labels
        assert not any("circuit-node" in label for label in labels)
        feeder_1 = system.get_component(BusbarSection, "feeder-1-node")
        feeder_2 = system.get_component(BusbarSection, "feeder-2-node")
        feeder_3 = system.get_component(BusbarSection, "feeder-3-node")
        feeder_4 = system.get_component(BusbarSection, "feeder-4-node")
        assert feeder_1.coordinate.x == feeder_2.coordinate.x < 0
        assert feeder_3.coordinate.x == feeder_4.coordinate.x > 0
        assert feeder_1.coordinate.y != feeder_2.coordinate.y
        assert feeder_3.coordinate.y != feeder_4.coordinate.y


def test_reference_schematic_coordinates_do_not_replace_custom_coordinates(tmp_path):
    from infrasys import Location

    system = build_reference_design(
        "single_bus",
        outfeed_count=2,
        coordinate_provider=lambda index: Location(
            x=-105.0 + index * 0.001,
            y=39.7,
            crs="EPSG:4326",
        ),
    )

    assert all(bus.coordinate.crs == "EPSG:4326" for bus in system.get_components(BusbarSection))
    filename = tmp_path / "custom-coordinates.json"
    system.to_json(filename, overwrite=True)
    restored = type(system).from_json(filename)
    assert all(bus.coordinate.crs == "EPSG:4326" for bus in restored.get_components(BusbarSection))


def test_parameterized_ring_bus_positions_extra_outfeeds_on_a_polygon():
    system = build_reference_design("ring_bus", outfeed_count=5)
    ring_nodes = [
        bus for bus in system.get_components(BusbarSection) if bus.name.startswith("ring-node-")
    ]

    positions = {(bus.coordinate.x, bus.coordinate.y) for bus in ring_nodes}

    assert len(ring_nodes) == 5
    assert len(positions) == 5


def test_plot_and_geodataframe_include_bay_and_substation_footprints():
    from infrasys import Location

    system = build_detailed_distribution_substation()
    substation = next(system.get_components(Substation))
    bay = next(system.get_components(Bay))
    footprint = [
        Location(x=-105.201, y=39.739, crs="EPSG:4326"),
        Location(x=-105.199, y=39.739, crs="EPSG:4326"),
        Location(x=-105.199, y=39.741, crs="EPSG:4326"),
        Location(x=-105.201, y=39.741, crs="EPSG:4326"),
    ]
    substation.footprint = footprint
    bay.footprint = footprint

    geodataframe = system.to_gdf()
    figure = system.plot(show=False)

    assert sum(geometry.geom_type == "Polygon" for geometry in geodataframe.geometry) == 2
    assert sum(trace.name.startswith("Footprint -") for trace in figure.data) == 2
