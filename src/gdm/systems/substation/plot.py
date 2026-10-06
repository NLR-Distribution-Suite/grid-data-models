"""Interactive geographic plotting for substations."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
from loguru import logger
from shapely import LineString, MultiLineString

from gdm.systems.distribution.enums import ColorLineBy, ColorNodeBy, MapType, PlotingStyle
from gdm.systems.substation.topology import BusbarSection, SubstationSystem

_GEODATAFRAME_COLUMNS = [
    "Name",
    "Type",
    "Phases",
    "kV",
    "Length",
    "X",
    "Y",
    "VoltageLevel",
    "State",
    "IsClosed",
    "NodeRole",
]

_EDGE_COLORS = (
    "#2563eb",
    "#0f766e",
    "#7c3aed",
    "#d97706",
    "#dc2626",
    "#0891b2",
)


def _selection_value(selection) -> str:
    return selection.value if hasattr(selection, "value") else str(selection)


def _phase_text(component) -> str:
    return ",".join(
        phase.value if hasattr(phase, "value") else str(phase)
        for phase in getattr(component, "phases", [])
    )


def _coordinate_data(system: SubstationSystem):
    coordinates = {}
    crs = None
    for bus in system.get_components(BusbarSection):
        if bus.coordinate is None:
            continue
        coordinates[bus.name] = (bus.coordinate.x, bus.coordinate.y)
        if crs is None and bus.coordinate.crs:
            crs = bus.coordinate.crs
    return coordinates, crs or "EPSG:4326"


def _empty_geodataframe(crs):
    frame = pd.DataFrame(columns=_GEODATAFRAME_COLUMNS)
    geometry = gpd.GeoSeries([], crs=crs)
    return gpd.GeoDataFrame(frame, geometry=geometry, crs=crs)


def _build_node_geodataframe(system: SubstationSystem, crs):
    rows = []
    for bus in system.get_components(BusbarSection):
        if bus.coordinate is None:
            continue
        rows.append(
            {
                "Name": bus.name,
                "Type": "BusbarSection",
                "Phases": _phase_text(bus),
                "kV": bus.rated_voltage.to("kilovolt").magnitude,
                "Length": (bus.length.to("foot").magnitude if bus.length is not None else None),
                "X": bus.coordinate.x,
                "Y": bus.coordinate.y,
                "VoltageLevel": bus.voltage_level.name if bus.voltage_level else None,
                "State": bus.state.value,
                "IsClosed": bus.state.value != "open",
                "NodeRole": "busbar" if bus.length is not None else "junction",
            }
        )
    if not rows:
        return _empty_geodataframe(crs)
    frame = pd.DataFrame(rows)
    return gpd.GeoDataFrame(
        frame,
        geometry=gpd.points_from_xy(frame["X"], frame["Y"]),
        crs=crs,
    )


def _build_edge_geodataframe(system: SubstationSystem, coordinates, crs):
    rows = []
    geometries = []
    for source_name, target_name, data in system.get_undirected_graph().edges(data=True):
        if source_name not in coordinates or target_name not in coordinates:
            continue
        component = system.get_component(data["type"], data["name"])
        source_x, source_y = coordinates[source_name]
        target_x, target_y = coordinates[target_name]
        component_length = getattr(component, "length", None)
        rows.append(
            {
                "Name": data["name"],
                "Type": data["type"].__name__,
                "Phases": _phase_text(component),
                "kV": None,
                "Length": (
                    component_length.to("foot").magnitude if component_length is not None else None
                ),
                "X": [source_x, target_x],
                "Y": [source_y, target_y],
                "VoltageLevel": None,
                "State": data.get("state"),
                "IsClosed": data.get("is_closed", True),
                "NodeRole": None,
            }
        )
        geometries.append(LineString([(source_x, source_y), (target_x, target_y)]))
    if not rows:
        return _empty_geodataframe(crs)
    return gpd.GeoDataFrame(pd.DataFrame(rows), geometry=geometries, crs=crs)


def build_substation_geodataframe(
    system: SubstationSystem, export_file: Path | None = None
) -> gpd.GeoDataFrame:
    """Build a combined point-and-edge GeoDataFrame for a substation."""

    coordinates, crs = _coordinate_data(system)
    nodes = _build_node_geodataframe(system, crs)
    edges = _build_edge_geodataframe(system, coordinates, crs)
    final_gdf = gpd.GeoDataFrame(
        pd.concat([nodes, edges], ignore_index=True), geometry="geometry", crs=crs
    )
    if export_file:
        final_gdf.to_csv(export_file)
    return final_gdf


def export_substation_geojson(system: SubstationSystem, export_file: Path | str) -> None:
    """Export a substation GeoDataFrame to GeoJSON."""

    export_file = Path(export_file)
    system_gdf = build_substation_geodataframe(system)
    system_gdf.to_file(export_file, driver="GeoJSON")
    logger.info(f"GeoJSON export completed in CRS {system_gdf.crs}: {export_file}")


def _line_trace_data(edges_gdf):
    lons = []
    lats = []
    names = []
    for feature, name, model_type, state in zip(
        edges_gdf.geometry,
        edges_gdf.Name,
        edges_gdf.Type,
        edges_gdf.State,
    ):
        if isinstance(feature, LineString):
            linestrings = [feature]
        elif isinstance(feature, MultiLineString):
            linestrings = feature.geoms
        else:
            continue
        for linestring in linestrings:
            x_values, y_values = linestring.xy
            lons.extend(x_values)
            lats.extend(y_values)
            hover = f"<br> <b>Name:</b> {name} <br> <b>Type:</b> {model_type}"
            if pd.notna(state):
                hover += f" <br> <b>State:</b> {state}"
            names.extend([hover] * len(x_values))
            lons.append(None)
            lats.append(None)
            names.append(None)
    return lons, lats, names


def _add_edge_traces(figure, edges_gdf, color_line_by, map_type: MapType) -> None:
    map_obj = getattr(go, map_type.value)
    color_key = _selection_value(color_line_by)
    if color_key == ColorLineBy.DEFAULT.value:
        options = ["default"]
    else:
        options = sorted(edges_gdf[color_key].dropna().unique(), key=str)
    edge_colors = {
        str(edge_option): _EDGE_COLORS[index % len(_EDGE_COLORS)]
        for index, edge_option in enumerate(options)
        if edge_option != "default"
    }

    for edge_option in options:
        if edge_option == "default":
            filtered_gdf = edges_gdf
        else:
            filtered_gdf = edges_gdf[edges_gdf[color_key] == edge_option]
        state_options = [True, False] if not filtered_gdf.empty else []
        for is_closed in state_options:
            state_gdf = filtered_gdf[filtered_gdf.IsClosed == is_closed]
            lons, lats, names = _line_trace_data(state_gdf)
            if not lons:
                continue
            state_label = "closed" if is_closed else "open"
            line_color = "#475569" if edge_option == "default" else edge_colors[str(edge_option)]
            figure.add_trace(
                map_obj(
                    lon=lons,
                    lat=lats,
                    mode="lines",
                    hoverinfo="text",
                    text=names,
                    line={
                        "color": line_color,
                        "width": 3 if is_closed else 2,
                        "dash": "solid" if is_closed else "dash",
                    },
                    name=f"Edges - {color_key} - {edge_option} ({state_label})",
                )
            )


def _add_node_traces(figure, nodes_gdf, color_node_by, map_type: MapType) -> None:
    map_obj = getattr(go, map_type.value)
    color_key = _selection_value(color_node_by)
    if color_key == ColorNodeBy.DEFAULT.value:
        options = ["default"]
    else:
        options = sorted(nodes_gdf[color_key].dropna().unique(), key=str)

    for node_option in options:
        if node_option == "default":
            filtered_gdf = nodes_gdf
        else:
            filtered_gdf = nodes_gdf[nodes_gdf[color_key] == node_option]
        is_busbar = filtered_gdf.NodeRole == "busbar"
        text = [
            f"<br> <b>Name:</b> {name} <br> <b>Role:</b> {role} "
            f"<br> <b>Phases:</b> {phases} <br> <b>kV:</b> {voltage}"
            for name, role, phases, voltage in zip(
                filtered_gdf.Name,
                filtered_gdf.NodeRole,
                filtered_gdf.Phases,
                filtered_gdf.kV,
            )
        ]
        figure.add_trace(
            map_obj(
                lon=filtered_gdf.geometry.x,
                lat=filtered_gdf.geometry.y,
                mode="markers",
                marker={
                    "size": [14 if value else 9 for value in is_busbar],
                    "symbol": ["square" if value else "circle" for value in is_busbar],
                    "line": {"color": "white", "width": 1},
                },
                hovertext=text,
                text=text,
                name=f"Nodes - {color_key} - {node_option}",
                textfont=dict(size=12, color="black"),
                textposition="top center",
            )
        )


def plot_substation(
    system: SubstationSystem,
    export_path: Path | None = None,
    show: bool = True,
    color_node_by: ColorNodeBy = ColorNodeBy.PHASE,
    color_line_by: ColorLineBy = ColorLineBy.EQUIPMENT_TYPE,
    show_legend: bool = True,
    map_type: MapType = MapType.SCATTER_GEO,
    style: PlotingStyle = PlotingStyle.CARTO_POSITRON,
    zoom_level: int = 11,
    **kwargs,
):
    """Plot the station topology on a geographic map.

    Nodes are :class:`BusbarSection` instances positioned by their geographic
    ``coordinate``. Edges are bus-branch primary equipment. Returns the Plotly
    figure.
    """

    system_gdf = system.to_gdf()
    nodes_gdf = system_gdf[system_gdf.Type == "BusbarSection"].copy()
    edges_gdf = system_gdf[system_gdf.Type != "BusbarSection"].copy()
    if nodes_gdf.empty:
        raise ValueError(
            "SubstationSystem.plot() requires geographic coordinates on at least one "
            "BusbarSection."
        )

    figure = go.Figure()
    _add_edge_traces(figure, edges_gdf, color_line_by, map_type)
    _add_node_traces(figure, nodes_gdf, color_node_by, map_type)

    center_lon = (nodes_gdf.geometry.x.min() + nodes_gdf.geometry.x.max()) / 2
    center_lat = (nodes_gdf.geometry.y.min() + nodes_gdf.geometry.y.max()) / 2
    coordinate_extent = max(
        nodes_gdf.geometry.x.max() - nodes_gdf.geometry.x.min(),
        nodes_gdf.geometry.y.max() - nodes_gdf.geometry.y.min(),
    )
    geo_projection_scale = min(
        1_000_000,
        max(1, 440 / max(coordinate_extent, 0.001) * 2 ** (zoom_level - 11)),
    )
    figure.update_layout(
        title={
            "text": kwargs.get("title", system.name.replace("-", " ").title()),
            "x": 0.01,
            "xanchor": "left",
            "y": 1.0,
            "yanchor": "top",
        },
        showlegend=show_legend,
        margin={"l": 20, "r": 20, "t": 135, "b": 20},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.03,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 11},
            "bgcolor": "rgba(255,255,255,0.9)",
            "bordercolor": "#cbd5e1",
            "borderwidth": 1,
        },
        hoverlabel={"namelength": -1},
    )

    if map_type == MapType.SCATTER_MAP:
        figure.update_layout(
            map={
                "style": style.value,
                "center": {"lon": center_lon, "lat": center_lat},
                "zoom": zoom_level,
            }
        )
    else:
        figure.update_layout(
            geo={
                "center": {"lon": center_lon, "lat": center_lat},
                "projection_scale": geo_projection_scale,
                "projection": {"type": "mercator"},
                "showland": kwargs.get("showland", True),
                "landcolor": kwargs.get("landcolor", "#e2e8f0"),
                "showocean": True,
                "oceancolor": "#dbeafe",
                "showlakes": True,
                "lakecolor": "#dbeafe",
                "showcoastlines": True,
                "coastlinecolor": "#64748b",
                "showcountries": True,
                "countrycolor": "#94a3b8",
                "showsubunits": True,
                "subunitcolor": "#cbd5e1",
                "showframe": False,
            }
        )

    if show:
        figure.show()
    if export_path:
        output = Path(export_path)
        if output.exists() and output.is_dir():
            filename = output / f"{system.name}_plot.html"
            figure.write_html(filename)
            logger.info(f"Plot saved to {filename}")
        elif output.exists() and not output.is_dir():
            raise NotADirectoryError("Provided path is not a directory")
        else:
            raise FileNotFoundError("Provided path does not exist")
    return figure
