"""Tests for substation single-line-diagram HTML rendering."""

import re
import xml.etree.ElementTree as ET


from gdm.systems.substation import (
    SubstationBuilder,
    SubstationSystem,
    build_detailed_distribution_substation,
)
from gdm.systems.substation.topology import BusbarSection
from tests.substation import build_layout_example


def _extract_svg(html: str) -> str:
    match = re.search(r"(<svg.*?</svg>)", html, re.S)
    assert match is not None
    return match.group(1)


def test_to_sld_returns_interactive_html_with_svg():
    system = build_layout_example("single_bus")
    html = system.to_sld()

    assert "<!DOCTYPE html>" in html
    assert 'id="viewport"' in html
    assert "wheel" in html
    ET.fromstring(_extract_svg(html))


def test_to_sld_writes_output_file(tmp_path):
    system = build_layout_example("ring_bus")
    output = tmp_path / "ring.html"

    html = system.to_sld(output)

    assert output.exists()
    assert output.read_text(encoding="utf-8") == html


def test_to_sld_uses_computed_layout_without_schematic_coordinates():
    system = build_layout_example("sectionalized_single_bus")
    html = system.to_sld()
    svg = _extract_svg(html)

    assert "bus-a" in svg
    assert "bus-b" in svg
    assert "bus-tie-breaker" in svg


def test_to_sld_uses_schematic_coordinates_when_present():
    builder = SubstationBuilder("schematic")
    builder.add_bus("bus-a", schematic_coordinate=_loc(0, 0))
    builder.add_bus("bus-b", schematic_coordinate=_loc(10, 0))
    builder.add_breaker("tie", "tie-bay", "bus-a", "bus-b")
    html = builder.build().to_sld()
    svg = _extract_svg(html)

    ET.fromstring(svg)
    assert 'data-busbar="true"' in svg


def test_to_sld_marks_open_and_closed_equipment():
    html = build_layout_example("sectionalized_single_bus").to_sld()
    svg = _extract_svg(html)

    assert 'data-state="open"' in svg
    assert 'data-state="closed"' in svg
    assert "bus-tie-breaker" in svg


def test_to_sld_escapes_labels():
    builder = SubstationBuilder("escaping")
    builder.add_bus("bus & <main>")
    html = builder.build().to_sld()
    svg = _extract_svg(html)

    assert "&amp;" in svg
    assert "&lt;main&gt;" in svg
    ET.fromstring(svg)


def test_detailed_station_renders_svg_with_all_equipment():
    system = build_detailed_distribution_substation()
    svg = _extract_svg(system.to_sld())

    ET.fromstring(svg)
    assert "CircuitBreaker" in svg
    assert "PowerTransformer" in svg
    assert "feeder-1" in svg


def test_to_sld_includes_resize_handles_and_save_controls():
    html = build_layout_example("single_bus").to_sld()

    assert "sld-handle" in html
    assert "save layout" in html
    assert "localStorage" in html


def test_exported_layout_applies_and_persists(tmp_path):
    system = build_detailed_distribution_substation()
    layout = system.export_sld_layout()

    edited = {
        name: {**entry, "x": entry["x"] + 2, "y": entry["y"] - 1} for name, entry in layout.items()
    }
    edited["hv-bus-1"]["length_m"] = 30.0

    target = build_detailed_distribution_substation()
    target.apply_sld_layout(edited)

    bus = target.get_component(BusbarSection, "hv-bus-1")
    assert bus.length.to("meter").magnitude == 30.0
    assert bus.schematic_coordinate is not None

    filename = tmp_path / "layout.json"
    target.to_json(filename, overwrite=True)
    restored = SubstationSystem.from_json(filename)
    restored_bus = restored.get_component(BusbarSection, "hv-bus-1")

    assert restored_bus.length.to("meter").magnitude == 30.0
    assert restored_bus.schematic_coordinate is not None
    assert restored_bus.schematic_coordinate.x == bus.schematic_coordinate.x


def _loc(x: float, y: float):
    from infrasys import Location

    return Location(x=x, y=y)
