"""Substation system container and topology visualization helpers."""

from __future__ import annotations

from pathlib import Path
from math import isclose
from typing import TYPE_CHECKING

from infrasys import System

if TYPE_CHECKING:
    from gdm.systems.distribution import DistributionSystem

from gdm.systems.distribution.enums import (
    ColorLineBy,
    ColorNodeBy,
    MapType,
    PlotingStyle,
)
from gdm.systems.substation.enums import EquipmentState
from gdm.systems.substation.topology import (
    BusbarSection,
)


class SubstationSystem(System):
    """Utility substation design and station-automation system."""

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
        "GeometryRole",
    ]
    _EDGE_COLORS = ("#2563eb", "#0f766e", "#7c3aed", "#d97706", "#dc2626", "#0891b2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.data_format_version:
            from importlib.metadata import version

            self.data_format_version = version("grid-data-models")

    def get_undirected_graph(self):
        """Build a bus-branch connectivity graph of the station.

        Nodes are :class:`BusbarSection` instances. Edges are primary equipment
        that connect two or more nodes in series. Shunt devices (surge
        arresters, earthing switches, shunt instrument transformers) are not
        edges. Edge metadata carries the device name, type, and switch state so
        downstream SCADA consumers can filter on state.
        """

        import networkx as nx

        from gdm.systems.substation.components import PrimaryEquipmentComponent

        graph = nx.MultiGraph()
        for bus in self.get_components(BusbarSection):
            graph.add_node(
                bus.name,
                is_busbar=bus.length is not None,
                voltage_level=bus.voltage_level.name if bus.voltage_level else None,
                voltage=bus.rated_voltage.magnitude,
                phases=[phase.value for phase in bus.phases],
                in_service=bus.in_service,
            )

        for device in self.get_components(PrimaryEquipmentComponent):
            buses = getattr(device, "buses", None)
            if not buses or len(buses) < 2:
                continue
            names = [bus.name for bus in buses]
            state = getattr(device, "state", EquipmentState.CLOSED)
            is_closed = state in (EquipmentState.CLOSED, EquipmentState.RACKED_IN)
            data = {
                "name": device.name,
                "type": type(device),
                "state": state.value,
                "is_closed": is_closed,
            }
            if len(names) == 2:
                graph.add_edge(names[0], names[1], **data)
            else:
                for other in names[1:]:
                    graph.add_edge(names[0], other, **data)
        return graph

    def to_distribution_system(  # noqa: C901
        self,
        feeder_systems: list["DistributionSystem"],
        output_name: str | None = None,
        keep_time_series: bool = True,
    ) -> "DistributionSystem":
        """Combine station topology and single-feeder systems into one model.

        Each feeder system must contain one feeder. Its matching
        :class:`FeederBoundary` declares the feeder root bus name through
        ``source_equivalent_id``. The root bus is merged into the boundary bus,
        feeder-local voltage sources are removed, and a source is created on the
        highest-voltage station transformer bus.
        """

        from gdm.systems.distribution import DistributionSystem
        from gdm.systems.distribution.components import (
            DistributionBus,
            DistributionVoltageSource,
        )
        from gdm.systems.distribution.equipment import VoltageSourceEquipment
        from gdm.systems.substation.components import PowerTransformer
        from gdm.systems.substation.topology import FeederBoundary

        boundaries = list(self.get_components(FeederBoundary))
        if not boundaries:
            raise ValueError("SubstationSystem must contain at least one FeederBoundary.")
        boundary_by_feeder_id = {boundary.feeder_id: boundary for boundary in boundaries}
        if len(boundary_by_feeder_id) != len(boundaries):
            raise ValueError("SubstationSystem FeederBoundary feeder IDs must be unique.")

        station_transformers = list(self.get_components(PowerTransformer))
        if not station_transformers:
            raise ValueError("SubstationSystem requires a PowerTransformer to create a source.")
        source_bus = max(
            (bus for transformer in station_transformers for bus in transformer.buses),
            key=lambda bus: bus.rated_voltage.to("kilovolt").magnitude,
        )

        result = DistributionSystem(
            name=output_name or f"{self.name}-complete",
            auto_add_composed_components=True,
        )
        station_components = [
            component
            for component in self.iter_all_components()
            if type(component).__module__.startswith("gdm.systems.substation")
        ]
        for component in station_components:
            if not result.has_component(component):
                result.add_component(component)
        source = DistributionVoltageSource(
            name=f"{self.name}-source",
            bus=source_bus,
            phases=list(source_bus.phases),
            equipment=VoltageSourceEquipment.example(),
        )
        result.add_component(source)

        added_feeder_ids = set()
        component_map = []
        for feeder_system in feeder_systems:
            feeder_ids = {
                component.feeder.name
                for component in feeder_system.iter_all_components()
                if getattr(component, "feeder", None) is not None
            }
            if len(feeder_ids) != 1:
                raise ValueError(
                    f"DistributionSystem '{feeder_system.name}' must contain exactly one feeder."
                )
            feeder_id = feeder_ids.pop()
            if feeder_id in added_feeder_ids:
                raise ValueError(f"Duplicate feeder system for feeder '{feeder_id}'.")
            boundary = boundary_by_feeder_id.get(feeder_id)
            if boundary is None:
                raise ValueError(f"No FeederBoundary exists for feeder '{feeder_id}'.")
            if boundary.source_equivalent_id is None:
                raise ValueError(
                    f"FeederBoundary '{boundary.name}' requires source_equivalent_id."
                )

            root_bus = feeder_system.get_component(DistributionBus, boundary.source_equivalent_id)
            if root_bus.name not in feeder_system.get_undirected_graph():
                raise ValueError(
                    f"Feeder root bus '{root_bus.name}' is not connected in '{feeder_system.name}'."
                )
            if not isclose(
                root_bus.rated_voltage.to("kilovolt").magnitude,
                boundary.bus.rated_voltage.to("kilovolt").magnitude,
                rel_tol=0.001,
            ):
                raise ValueError(
                    f"Feeder '{feeder_id}' root voltage does not match its boundary bus."
                )
            if not set(root_bus.phases).issubset(boundary.bus.phases):
                raise ValueError(
                    f"Feeder '{feeder_id}' phases are not supported by its boundary bus."
                )

            for component in feeder_system.iter_all_components():
                if component is root_bus or isinstance(component, DistributionVoltageSource):
                    continue
                if getattr(component, "feeder", None) is None:
                    continue

                updates = {}
                if getattr(component, "bus", None) is root_bus:
                    updates["bus"] = boundary.bus
                buses = getattr(component, "buses", None)
                if buses is not None:
                    updates["buses"] = [boundary.bus if bus is root_bus else bus for bus in buses]
                replacement = component.model_copy(update=updates)
                if not result.has_component(replacement):
                    result.add_component(replacement)
                component_map.append((feeder_system, component, replacement))
            added_feeder_ids.add(feeder_id)

        missing_feeders = set(boundary_by_feeder_id) - added_feeder_ids
        if missing_feeders:
            raise ValueError(
                f"No DistributionSystem supplied for feeder boundaries: {sorted(missing_feeders)}."
            )

        if keep_time_series:
            for feeder_system, component, replacement in component_map:
                if not feeder_system.has_time_series(component):
                    continue
                for metadata in feeder_system.list_time_series_metadata(component):
                    time_series = feeder_system.get_time_series(
                        component, metadata.name, type(metadata)
                    )
                    result.add_time_series(time_series, replacement, **metadata.features)

        return result

    def to_gdf(self, export_file: Path | None = None):
        """Convert the station nodes and equipment edges to a GeoDataFrame."""

        import geopandas as gpd
        import pandas as pd

        coordinates, crs = self._coordinate_data()
        nodes = self._build_node_geodataframe(crs)
        edges = self._build_edge_geodataframe(coordinates, crs)
        footprints = self._build_footprint_geodataframe(crs)
        final_gdf = gpd.GeoDataFrame(
            pd.concat([nodes, edges, footprints], ignore_index=True), geometry="geometry", crs=crs
        )
        if export_file:
            final_gdf.to_csv(export_file)
        return final_gdf

    @staticmethod
    def _selection_value(selection) -> str:
        return selection.value if hasattr(selection, "value") else str(selection)

    @staticmethod
    def _phase_text(component) -> str:
        return ",".join(
            phase.value if hasattr(phase, "value") else str(phase)
            for phase in getattr(component, "phases", [])
        )

    def _coordinate_data(self):
        coordinates = {}
        crs = None
        for bus in self.get_components(BusbarSection):
            if bus.coordinate is None:
                continue
            coordinates[bus.name] = (bus.coordinate.x, bus.coordinate.y)
            if crs is None and bus.coordinate.crs:
                crs = bus.coordinate.crs
        return coordinates, crs or "EPSG:4326"

    @classmethod
    def _empty_geodataframe(cls, crs):
        import geopandas as gpd
        import pandas as pd

        frame = pd.DataFrame(columns=cls._GEODATAFRAME_COLUMNS)
        geometry = gpd.GeoSeries([], crs=crs)
        return gpd.GeoDataFrame(frame, geometry=geometry, crs=crs)

    def _build_node_geodataframe(self, crs):
        import geopandas as gpd
        import pandas as pd

        rows = []
        for bus in self.get_components(BusbarSection):
            if bus.coordinate is None:
                continue
            rows.append(
                {
                    "Name": bus.name,
                    "Type": "BusbarSection",
                    "Phases": self._phase_text(bus),
                    "kV": bus.rated_voltage.to("kilovolt").magnitude,
                    "Length": (
                        bus.length.to("foot").magnitude if bus.length is not None else None
                    ),
                    "X": bus.coordinate.x,
                    "Y": bus.coordinate.y,
                    "VoltageLevel": bus.voltage_level.name if bus.voltage_level else None,
                    "State": bus.state.value,
                    "IsClosed": bus.state.value != "open",
                    "NodeRole": "busbar" if bus.length is not None else "junction",
                    "GeometryRole": "node",
                }
            )
        if not rows:
            return self._empty_geodataframe(crs)
        frame = pd.DataFrame(rows)
        return gpd.GeoDataFrame(
            frame,
            geometry=gpd.points_from_xy(frame["X"], frame["Y"]),
            crs=crs,
        )

    def _build_edge_geodataframe(self, coordinates, crs):
        import geopandas as gpd
        import pandas as pd
        from shapely import LineString

        rows = []
        geometries = []
        for source_name, target_name, data in self.get_undirected_graph().edges(data=True):
            if source_name not in coordinates or target_name not in coordinates:
                continue
            component = self.get_component(data["type"], data["name"])
            source_x, source_y = coordinates[source_name]
            target_x, target_y = coordinates[target_name]
            component_length = getattr(component, "length", None)
            rows.append(
                {
                    "Name": data["name"],
                    "Type": data["type"].__name__,
                    "Phases": self._phase_text(component),
                    "kV": None,
                    "Length": (
                        component_length.to("foot").magnitude
                        if component_length is not None
                        else None
                    ),
                    "X": [source_x, target_x],
                    "Y": [source_y, target_y],
                    "VoltageLevel": None,
                    "State": data.get("state"),
                    "IsClosed": data.get("is_closed", True),
                    "NodeRole": None,
                    "GeometryRole": "edge",
                }
            )
            geometries.append(LineString([(source_x, source_y), (target_x, target_y)]))
        if not rows:
            return self._empty_geodataframe(crs)
        return gpd.GeoDataFrame(pd.DataFrame(rows), geometry=geometries, crs=crs)

    def _build_footprint_geodataframe(self, crs):
        import geopandas as gpd
        import pandas as pd
        from shapely import Polygon

        from gdm.systems.substation.topology import Bay, Substation

        rows = []
        geometries = []
        for component_type in (Substation, Bay):
            for component in self.get_components(component_type):
                if len(component.footprint) < 3:
                    continue
                coordinates = [(point.x, point.y) for point in component.footprint]
                rows.append(
                    {
                        "Name": component.name,
                        "Type": component_type.__name__,
                        "Phases": None,
                        "kV": None,
                        "Length": None,
                        "X": [point[0] for point in coordinates],
                        "Y": [point[1] for point in coordinates],
                        "VoltageLevel": (
                            component.voltage_level.name
                            if isinstance(component, Bay) and component.voltage_level
                            else None
                        ),
                        "State": None,
                        "IsClosed": None,
                        "NodeRole": None,
                        "GeometryRole": "footprint",
                    }
                )
                geometries.append(Polygon(coordinates))
        if not rows:
            return self._empty_geodataframe(crs)
        return gpd.GeoDataFrame(pd.DataFrame(rows), geometry=geometries, crs=crs)

    def to_geojson(self, export_file: Path | str) -> None:
        """Export the station topology to a GeoJSON file."""

        from loguru import logger

        export_file = Path(export_file)
        system_gdf = self.to_gdf()
        system_gdf.to_file(export_file, driver="GeoJSON")
        logger.info(f"GeoJSON export completed in CRS {system_gdf.crs}: {export_file}")

    @staticmethod
    def _line_trace_data(edges_gdf):
        import pandas as pd
        from shapely import LineString, MultiLineString

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

    @classmethod
    def _add_edge_traces(cls, figure, edges_gdf, color_line_by, map_type: MapType) -> None:
        import plotly.graph_objects as go

        map_obj = getattr(go, map_type.value)
        color_key = cls._selection_value(color_line_by)
        if color_key == ColorLineBy.DEFAULT.value:
            options = ["default"]
        else:
            options = sorted(edges_gdf[color_key].dropna().unique(), key=str)
        edge_colors = {
            str(edge_option): cls._EDGE_COLORS[index % len(cls._EDGE_COLORS)]
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
                lons, lats, names = cls._line_trace_data(state_gdf)
                if not lons:
                    continue
                state_label = "closed" if is_closed else "open"
                line_color = (
                    "#475569" if edge_option == "default" else edge_colors[str(edge_option)]
                )
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

    @classmethod
    def _add_node_traces(cls, figure, nodes_gdf, color_node_by, map_type: MapType) -> None:
        import plotly.graph_objects as go

        map_obj = getattr(go, map_type.value)
        color_key = cls._selection_value(color_node_by)
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

    @staticmethod
    def _add_footprint_traces(figure, footprints_gdf, map_type: MapType) -> None:
        import plotly.graph_objects as go
        from shapely import Polygon

        map_obj = getattr(go, map_type.value)
        for footprint, name, model_type in zip(
            footprints_gdf.geometry,
            footprints_gdf.Name,
            footprints_gdf.Type,
        ):
            if not isinstance(footprint, Polygon):
                continue
            x_values, y_values = footprint.exterior.xy
            figure.add_trace(
                map_obj(
                    lon=list(x_values),
                    lat=list(y_values),
                    mode="lines",
                    fill="toself",
                    fillcolor="rgba(20, 184, 166, 0.12)",
                    line={"color": "#0f766e", "width": 1},
                    hovertemplate=f"<b>{model_type}</b><br>{name}<extra></extra>",
                    name=f"Footprint - {model_type}",
                )
            )

    def plot(
        self,
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
        """Plot the station on a geographic map using node ``coordinate`` values."""

        import plotly.graph_objects as go
        from loguru import logger

        system_gdf = self.to_gdf()
        nodes_gdf = system_gdf[system_gdf.Type == "BusbarSection"].copy()
        edges_gdf = system_gdf[system_gdf.GeometryRole == "edge"].copy()
        footprints_gdf = system_gdf[system_gdf.GeometryRole == "footprint"].copy()
        if nodes_gdf.empty or not nodes_gdf.crs or not nodes_gdf.crs.is_geographic:
            raise ValueError(
                "SubstationSystem.plot() requires geographic coordinates on at least one "
                "BusbarSection."
            )

        figure = go.Figure()
        self._add_footprint_traces(figure, footprints_gdf, map_type)
        self._add_edge_traces(figure, edges_gdf, color_line_by, map_type)
        self._add_node_traces(figure, nodes_gdf, color_node_by, map_type)

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
                "text": kwargs.get("title", self.name.replace("-", " ").title()),
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
                filename = output / f"{self.name}_plot.html"
                figure.write_html(filename)
                logger.info(f"Plot saved to {filename}")
            elif output.exists() and not output.is_dir():
                raise NotADirectoryError("Provided path is not a directory")
            else:
                raise FileNotFoundError("Provided path does not exist")
        return figure

    def plot_schematic(  # noqa: C901
        self,
        export_path: Path | None = None,
        show: bool = True,
        show_legend: bool = True,
    ):
        """Plot station topology as a Cartesian electrical schematic.

        Unlike :meth:`plot`, this view does not use a geographic projection and
        is intended for compact reference layouts and engineering review.
        """

        import plotly.graph_objects as go
        from loguru import logger
        from shapely import Polygon

        system_gdf = self.to_gdf()
        nodes_gdf = system_gdf[system_gdf.GeometryRole == "node"].copy()
        edges_gdf = system_gdf[system_gdf.GeometryRole == "edge"].copy()
        footprints_gdf = system_gdf[system_gdf.GeometryRole == "footprint"].copy()
        if nodes_gdf.empty:
            raise ValueError(
                "SubstationSystem.plot_schematic() requires positioned BusbarSections."
            )

        figure = go.Figure()
        node_coordinates = {
            row.Name: (row.geometry.x, row.geometry.y) for row in nodes_gdf.itertuples()
        }
        busbar_names = set(nodes_gdf.loc[nodes_gdf.NodeRole == "busbar", "Name"])
        ring_bus_names = {name for name in busbar_names if name.startswith("ring-node-")}
        graph = self.get_undirected_graph()

        for footprint, name, model_type in zip(
            footprints_gdf.geometry,
            footprints_gdf.Name,
            footprints_gdf.Type,
        ):
            if isinstance(footprint, Polygon):
                x_values, y_values = footprint.exterior.xy
                figure.add_trace(
                    go.Scatter(
                        x=list(x_values),
                        y=list(y_values),
                        mode="lines",
                        fill="toself",
                        fillcolor="rgba(20, 184, 166, 0.12)",
                        line={"color": "#0f766e", "width": 1},
                        hovertemplate=f"<b>{model_type}</b><br>{name}<extra></extra>",
                        name=f"Footprint - {model_type}",
                    )
                )

        for busbar_name in busbar_names:
            if busbar_name in ring_bus_names:
                continue
            x_value, y_value = node_coordinates[busbar_name]
            connected_x = [
                node_coordinates[neighbor][0]
                for neighbor in graph.neighbors(busbar_name)
                if neighbor in node_coordinates and neighbor not in busbar_names
            ]
            if connected_x:
                low_x, high_x = min(connected_x), max(connected_x)
                if low_x == high_x:
                    busbar = self.get_component(BusbarSection, busbar_name)
                    half_span = (
                        busbar.length.to("meter").magnitude / 8
                        if busbar.length is not None
                        else 0.8
                    )
                    low_x, high_x = low_x - half_span, high_x + half_span
            else:
                low_x, high_x = x_value - 0.8, x_value + 0.8
            figure.add_trace(
                go.Scatter(
                    x=[low_x, high_x],
                    y=[y_value, y_value],
                    mode="lines",
                    line={"color": "#17212b", "width": 7},
                    hovertemplate=f"<b>{busbar_name}</b><br>Busbar<extra></extra>",
                    name="Busbars",
                    showlegend=not any(trace.name == "Busbars" for trace in figure.data),
                )
            )

        for model_type, type_edges in edges_gdf.groupby("Type"):
            x_values = []
            y_values = []
            symbol_x = []
            symbol_y = []
            symbol_text = []
            for row in type_edges.itertuples():
                start = (row.X[0], row.Y[0])
                end = (row.X[1], row.Y[1])
                start_is_bus = start in {node_coordinates[name] for name in busbar_names}
                end_is_bus = end in {node_coordinates[name] for name in busbar_names}
                if start_is_bus and not end_is_bus:
                    route = [start, (end[0], start[1]), end]
                    mark = (end[0], (start[1] + end[1]) / 2)
                elif end_is_bus and not start_is_bus:
                    route = [start, (start[0], end[1]), end]
                    mark = (start[0], (start[1] + end[1]) / 2)
                elif start[0] == end[0] or start[1] == end[1]:
                    route = [start, end]
                    mark = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
                else:
                    route = [start, (end[0], start[1]), end]
                    mark = (end[0], (start[1] + end[1]) / 2)
                x_values.extend([point[0] for point in route] + [None])
                y_values.extend([point[1] for point in route] + [None])
                symbol_x.append(mark[0])
                symbol_y.append(mark[1])
                symbol_text.append(f"<b>{row.Name}</b><br>{model_type}")
            if x_values:
                figure.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=y_values,
                        mode="lines",
                        line={"color": "#465563", "width": 2},
                        hoverinfo="skip",
                        name=f"Connections - {model_type}",
                        showlegend=False,
                    )
                )
                marker_symbol = {
                    "CircuitBreaker": "square",
                    "Disconnector": "diamond-open",
                    "PowerTransformer": "circle",
                }.get(model_type)
                if marker_symbol:
                    figure.add_trace(
                        go.Scatter(
                            x=symbol_x,
                            y=symbol_y,
                            mode="markers",
                            hovertext=symbol_text,
                            hoverinfo="text",
                            marker={
                                "size": 10,
                                "symbol": marker_symbol,
                                "color": "#f4a261" if model_type == "Disconnector" else "white",
                                "line": {"color": "#17212b", "width": 2},
                            },
                            name={
                                "CircuitBreaker": "Circuit breakers",
                                "Disconnector": "Disconnectors",
                                "PowerTransformer": "Power transformers",
                            }[model_type],
                        )
                    )

        node_text = [
            f"<b>{name}</b><br>{role}<br>{phases}<br>{voltage} kV"
            for name, role, phases, voltage in zip(
                nodes_gdf.Name,
                nodes_gdf.NodeRole,
                nodes_gdf.Phases,
                nodes_gdf.kV,
            )
        ]
        from gdm.systems.substation.topology import FeederBoundary

        feeder_labels = {
            boundary.bus.name: boundary.feeder_id
            for boundary in self.get_components(FeederBoundary)
        }
        visible_node_labels = [
            name if role == "busbar" else feeder_labels.get(name, "")
            for name, role in zip(nodes_gdf.Name, nodes_gdf.NodeRole)
        ]
        figure.add_trace(
            go.Scatter(
                x=nodes_gdf.geometry.x,
                y=nodes_gdf.geometry.y,
                mode="markers+text",
                text=visible_node_labels,
                hovertext=node_text,
                hoverinfo="text",
                textposition="top center",
                marker={
                    "size": [14 if role == "busbar" else 9 for role in nodes_gdf.NodeRole],
                    "symbol": [
                        "square" if role == "busbar" else "circle" for role in nodes_gdf.NodeRole
                    ],
                    "color": "#14b8a6",
                    "line": {"color": "white", "width": 1},
                },
                name="Busbar sections",
                showlegend=False,
            )
        )
        figure.update_layout(
            title=self.name.replace("-", " ").title(),
            showlegend=show_legend,
            plot_bgcolor="white",
            paper_bgcolor="white",
            margin={"l": 30, "r": 30, "t": 70, "b": 30},
            xaxis={
                "visible": False,
                "showgrid": False,
                "zeroline": False,
                "showticklabels": False,
            },
            yaxis={
                "visible": False,
                "showgrid": False,
                "zeroline": False,
                "showticklabels": False,
                "scaleanchor": "x",
                "scaleratio": 1,
            },
        )
        if show:
            figure.show()
        if export_path:
            output = Path(export_path)
            if not output.exists() or not output.is_dir():
                raise FileNotFoundError(
                    "Provided export path does not exist or is not a directory."
                )
            filename = output / f"{self.name}_schematic.html"
            figure.write_html(filename)
            logger.info(f"Schematic saved to {filename}")
        return figure
