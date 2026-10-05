"""Interactive geographic plotting for substations."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from gdm.systems.substation.topology import BusbarSection, SubstationSystem

_STATE_STYLES = {
    True: {"color": "#1f2937", "dash": "solid", "label": "closed"},
    False: {"color": "#b91c1c", "dash": "dash", "label": "open"},
}


def _add_equipment_traces(figure, graph, node_xy) -> None:
    import plotly.graph_objects as go

    for is_closed, style in _STATE_STYLES.items():
        lons: list[float | None] = []
        lats: list[float | None] = []
        hover: list[str | None] = []
        for source, target, data in graph.edges(data=True):
            if bool(data.get("is_closed", True)) is not is_closed:
                continue
            if source not in node_xy or target not in node_xy:
                continue
            x1, y1 = node_xy[source]
            x2, y2 = node_xy[target]
            lons.extend([x1, x2, None])
            lats.extend([y1, y2, None])
            text = f"<b>{data['name']}</b><br>{data['type'].__name__} ({style['label']})"
            hover.extend([text, text, None])
        if not lons:
            continue
        figure.add_trace(
            go.Scattergeo(
                lon=lons,
                lat=lats,
                mode="lines",
                line={"color": style["color"], "width": 2, "dash": style["dash"]},
                hovertext=hover,
                hoverinfo="text",
                name=f"{style['label']} equipment",
            )
        )


def _add_node_traces(figure, node_xy, node_meta, color_node_by: str) -> None:
    import plotly.graph_objects as go

    groups: dict[str, list[str]] = {}
    for name, meta in node_meta.items():
        key = meta[color_node_by] if color_node_by in meta else "unknown"
        groups.setdefault(str(key), []).append(name)
    for group, names in sorted(groups.items()):
        figure.add_trace(
            go.Scattergeo(
                lon=[node_xy[name][0] for name in names],
                lat=[node_xy[name][1] for name in names],
                mode="markers",
                marker={
                    "size": [11 if node_meta[name]["is_busbar"] else 7 for name in names],
                    "symbol": [
                        "square" if node_meta[name]["is_busbar"] else "circle" for name in names
                    ],
                },
                text=[
                    f"<b>{name}</b><br>{node_meta[name]['voltage_level']} "
                    f"({node_meta[name]['voltage']:.2f} kV)<br>"
                    f"phases: {node_meta[name]['phases']}<br>"
                    f"in service: {node_meta[name]['in_service']}"
                    for name in names
                ],
                hoverinfo="text",
                name=f"nodes - {group}",
            )
        )


def plot_substation(
    system: SubstationSystem,
    export_path: str | Path | None = None,
    show: bool = True,
    color_node_by: str = "voltage_level",
    zoom_level: int = 13,
    height: int = 700,
    title: str | None = None,
    **kwargs,
):
    """Plot the station topology on a geographic map.

    Nodes are :class:`BusbarSection` instances positioned by their geographic
    ``coordinate``. Edges are bus-branch primary equipment, colored and styled
    by switching state. Returns the Plotly figure.
    """

    import plotly.graph_objects as go

    buses = [bus for bus in system.get_components(BusbarSection) if bus.coordinate is not None]
    if not buses:
        raise ValueError(
            "SubstationSystem.plot() requires geographic coordinates on at least one "
            "BusbarSection."
        )

    node_xy = {bus.name: (bus.coordinate.x, bus.coordinate.y) for bus in buses}
    node_meta = {
        bus.name: {
            "voltage_level": bus.voltage_level.name if bus.voltage_level else "unknown",
            "voltage": bus.rated_voltage.magnitude,
            "phases": ",".join(phase.value for phase in bus.phases),
            "in_service": bus.in_service,
            "is_busbar": bus.length is not None,
        }
        for bus in buses
    }

    figure = go.Figure()
    graph = system.get_undirected_graph()
    _add_equipment_traces(figure, graph, node_xy)
    _add_node_traces(figure, node_xy, node_meta, color_node_by)

    center_lon = sum(x for x, _ in node_xy.values()) / len(node_xy)
    center_lat = sum(y for _, y in node_xy.values()) / len(node_xy)
    figure.update_layout(
        title=title or system.name,
        showlegend=True,
        height=height,
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
        geo={
            "center": {"lon": center_lon, "lat": center_lat},
            "projection_scale": zoom_level,
            "showland": kwargs.get("showland", True),
            "landcolor": kwargs.get("landcolor", "lightgray"),
        },
    )

    if show:
        figure.show()
    if export_path is not None:
        output = Path(export_path)
        if output.exists() and output.is_dir():
            output = output / f"{system.name}_plot.html"
        output.write_text(figure.to_html(include_plotlyjs="cdn"), encoding="utf-8")
        logger.info(f"Substation plot saved to {output}")
    return figure
