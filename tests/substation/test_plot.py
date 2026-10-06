"""Tests for geographic substation plotting."""

import json

import pytest

from gdm.systems.distribution.enums import ColorLineBy, ColorNodeBy, MapType
from tests.substation import build_layout_example
from tests.substation.builder import SubstationBuilder
from tests.substation.detailed_example import build_detailed_distribution_substation


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
