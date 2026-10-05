"""Tests for geographic substation plotting."""

import pytest

from gdm.systems.substation import SubstationBuilder, build_detailed_distribution_substation
from tests.substation import build_layout_example


def test_plot_returns_plotly_figure_with_traces():
    system = build_detailed_distribution_substation()
    figure = system.plot(show=False)

    assert len(figure.data) >= 2
    assert any(trace.type == "scattergeo" for trace in figure.data)


def test_plot_requires_geographic_coordinates():
    system = build_layout_example("single_bus")

    with pytest.raises(ValueError, match="geographic coordinates"):
        system.plot(show=False)


def test_plot_marks_open_equipment():
    system = build_detailed_distribution_substation()
    figure = system.plot(show=False)
    names = {trace.name for trace in figure.data}

    assert "open equipment" in names
    assert "closed equipment" in names


def test_plot_exports_html(tmp_path):
    system = build_detailed_distribution_substation()
    output = tmp_path / "station.html"

    system.plot(export_path=str(output), show=False)

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
