"""Single-line-diagram generation for substations.

``render_sld_html`` builds a deterministic single-line diagram from the
bus-branch topology and returns a standalone interactive HTML document with
pan/zoom, draggable nodes and equipment that keep connectivity, snapping,
voltage-level coloring, and hover highlighting.
``schematic_coordinate`` is used when a node defines one; otherwise a
voltage-level band layout is computed.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from infrasys import Location

from gdm.quantities import Distance
from gdm.systems.substation.topology import BusbarSection, SubstationSystem

_DEFAULT_WIDTH = 1400
_DEFAULT_HEIGHT = 900
_PAD = 70
_LEGEND_W = 232
_SLD_PX_PER_METER = 7.0
_DEFAULT_BUS_LENGTH_M = 12.0

# Voltage-level palette (falls back to gray beyond the list).
_PALETTE = ["#b91c1c", "#1d4ed8", "#047857", "#b45309", "#7c3aed", "#0e7490", "#be185d"]
_INK = "#111827"
_OPEN = "#b91c1c"

_LEGEND_ENTRIES = [
    ("CircuitBreaker", True, "breaker (closed)"),
    ("CircuitBreaker", False, "breaker (open)"),
    ("Disconnector", True, "disconnector"),
    ("EarthingSwitch", False, "earthing switch"),
    ("PowerTransformer", True, "power transformer"),
    ("InstrumentTransformer", True, "CT / VT core"),
    ("SurgeArrester", True, "surge arrester"),
    ("LineTrap", True, "line trap"),
    ("FeederBoundary", True, "circuit / feeder"),
]


def _band_key(bus: BusbarSection) -> tuple[str, float]:
    if bus.voltage_level is not None:
        return bus.voltage_level.name, bus.voltage_level.nominal_voltage.magnitude
    return "", -1.0


def _layer_band(names, subgraph, anchors, band_y: float, spacing: float, row_gap: float):
    """Layer one voltage band by bus-branch distance from its anchors."""

    from collections import deque

    depths: dict[str, int | None] = dict.fromkeys(names)
    queue: deque[str] = deque()
    for anchor in sorted(anchors):
        if depths[anchor] is None:
            depths[anchor] = 0
            queue.append(anchor)
    while queue:
        current = queue.popleft()
        for neighbor in sorted(subgraph.neighbors(current)):
            if depths.get(neighbor) is None:
                depths[neighbor] = (depths[current] or 0) + 1
                queue.append(neighbor)

    rows: dict[int, list[str]] = {}
    for name in names:
        rows.setdefault(depths.get(name) or 0, []).append(name)

    positions: dict[str, tuple[float, float]] = {}
    parent_x: dict[str, float] = {}
    for depth in sorted(rows):
        row = sorted(rows[depth], key=lambda name: (parent_x.get(name, 0.0), name))
        count = len(row)
        for index, name in enumerate(row):
            x = (index - (count - 1) / 2.0) * spacing
            positions[name] = (x, band_y - depth * row_gap)
            parent_x[name] = x
    return positions


def build_sld_layout(system: SubstationSystem) -> dict[str, tuple[float, float]]:
    """Return schematic (x, y) positions for every busbar-section node.

    Nodes are grouped into voltage-level bands ordered from highest nominal
    voltage to lowest. Within a band, nodes are layered by their bus-branch
    distance from the busbar anchors so series equipment forms readable fans,
    and each row is centered and ordered by parent position. Any explicit
    ``schematic_coordinate`` overrides the computed position.
    """

    buses = list(system.get_components(BusbarSection))
    graph = system.get_undirected_graph()
    groups: dict[tuple[str, float], list[BusbarSection]] = {}
    for bus in buses:
        groups.setdefault(_band_key(bus), []).append(bus)

    band_gap, row_gap, spacing = 7.0, 1.7, 3.2
    positions: dict[str, tuple[float, float]] = {}
    ordered = sorted(groups.items(), key=lambda item: -item[0][1])
    for band_index, (_, members) in enumerate(ordered):
        names = {bus.name for bus in members}
        anchors = [bus.name for bus in members if bus.length is not None] or sorted(names)
        positions.update(
            _layer_band(
                names,
                graph.subgraph(names),
                anchors,
                -band_index * band_gap,
                spacing,
                row_gap,
            )
        )

    for bus in buses:
        if bus.schematic_coordinate is not None:
            positions[bus.name] = (bus.schematic_coordinate.x, bus.schematic_coordinate.y)
    return positions


def _ground(color: str, y: float = 10.0) -> str:
    return (
        f'<line x1="-7" y1="{y}" x2="7" y2="{y}" stroke="{color}" stroke-width="1.6"/>'
        f'<line x1="-4.5" y1="{y + 3}" x2="4.5" y2="{y + 3}" stroke="{color}" stroke-width="1.6"/>'
        f'<line x1="-2" y1="{y + 6}" x2="2" y2="{y + 6}" stroke="{color}" stroke-width="1.6"/>'
    )


def _sym_instrument(is_closed: bool, color: str) -> str:
    return (
        f'<circle cx="0" cy="0" r="8" fill="none" stroke="{color}" stroke-width="2"/>'
        f'<circle cx="0" cy="0" r="3" fill="none" stroke="{_INK}"/>'
    )


def _sym_transformer(is_closed: bool, color: str) -> str:
    return (
        f'<circle cx="-7" cy="0" r="8" fill="white" stroke="{color}" stroke-width="2"/>'
        f'<circle cx="7" cy="0" r="8" fill="white" stroke="{color}" stroke-width="2"/>'
    )


def _sym_line_trap(is_closed: bool, color: str) -> str:
    return (
        '<path d="M -12 0 a 3 3 0 0 1 6 0 a 3 3 0 0 1 6 0 a 3 3 0 0 1 6 0 '
        f'a 3 3 0 0 1 6 0" fill="none" stroke="{color}" stroke-width="2"/>'
        f'<line x1="-12" y1="0" x2="-16" y2="0" stroke="{color}" stroke-width="2"/>'
        f'<line x1="12" y1="0" x2="16" y2="0" stroke="{color}" stroke-width="2"/>'
    )


def _sym_arrester(is_closed: bool, color: str) -> str:
    return (
        f'<rect x="-6" y="-10" width="12" height="13" fill="white" stroke="{color}"/>'
        f'<line x1="-8" y1="8" x2="8" y2="-11" stroke="{_INK}" stroke-width="1.4"/>'
        f'<line x1="0" y1="3" x2="0" y2="7" stroke="{_INK}" stroke-width="1.6"/>'
        f"{_ground(_INK, 8)}"
    )


def _sym_breaker(is_closed: bool, color: str) -> str:
    if is_closed:
        return f'<rect x="-8" y="-8" width="16" height="16" fill="{color}" stroke="{_INK}"/>'
    return (
        f'<rect x="-8" y="-8" width="16" height="16" fill="white" stroke="{_OPEN}" '
        f'stroke-dasharray="4 3"/>'
    )


def _sym_disconnector(is_closed: bool, color: str) -> str:
    dots = (
        f'<circle cx="-9" cy="0" r="2" fill="{_INK}"/><circle cx="9" cy="0" r="2" fill="{_INK}"/>'
    )
    if is_closed:
        return dots + f'<line x1="-9" y1="0" x2="9" y2="0" stroke="{color}" stroke-width="2.4"/>'
    return dots + f'<line x1="-9" y1="0" x2="4" y2="-10" stroke="{_OPEN}" stroke-width="2.4"/>'


def _sym_earthing(is_closed: bool, color: str) -> str:
    if is_closed:
        blade = f'<line x1="0" y1="-9" x2="0" y2="4" stroke="{color}" stroke-width="2.4"/>'
    else:
        blade = f'<line x1="0" y1="-9" x2="9" y2="-5" stroke="{_OPEN}" stroke-width="2.4"/>'
    return blade + f'<line x1="0" y1="4" x2="0" y2="7" stroke="{_INK}"/>' + _ground(_INK, 7)


def _sym_circuit(is_closed: bool, color: str) -> str:
    return (
        f'<line x1="-12" y1="0" x2="6" y2="0" stroke="{color}" stroke-width="2.4"/>'
        f'<polygon points="6,-6 16,0 6,6" fill="{color}"/>'
    )


_SYMBOL_RULES = [
    ("InstrumentTransformer", _sym_instrument),
    ("Transformer", _sym_transformer),
    ("LineTrap", _sym_line_trap),
    ("SurgeArrester", _sym_arrester),
    ("CircuitBreaker", _sym_breaker),
    ("Disconnector", _sym_disconnector),
    ("EarthingSwitch", _sym_earthing),
    ("ExternalCircuit", _sym_circuit),
    ("FeederBoundary", _sym_circuit),
]


def _symbol(device_type: str, is_closed: bool, color: str) -> str:
    """Return an IEC-inspired SVG symbol centered on the origin (0, 0)."""

    for keyword, builder in _SYMBOL_RULES:
        if keyword in device_type:
            return builder(is_closed, color)
    return (
        f'<polygon points="0,-6 6,0 0,6 -6,0" fill="white" stroke="{color}" stroke-width="1.6"/>'
    )


def _level_colors(nodes):
    """Return (color-by-level, ordered-levels) for the station."""

    level_order = sorted({_band_key(bus) for bus in nodes.values()}, key=lambda item: -item[1])
    colors = {level: _PALETTE[index % len(_PALETTE)] for index, level in enumerate(level_order)}
    return colors, level_order


def _legend_svg(level_order, width: int, height: int) -> str:
    """Render a right-side panel with symbol and voltage-level legends."""

    x = width - _LEGEND_W
    y = 58
    row = 26
    parts: list[str] = [
        '<g id="legend">',
        f'<rect x="{x}" y="12" width="{_LEGEND_W - 12}" height="{height - 24}" '
        f'fill="#ffffff" stroke="#d1d5db" rx="6"/>',
        f'<text x="{x + 14}" y="{y - 22}" font-size="13" font-weight="bold" '
        f'fill="{_INK}">Symbols</text>',
    ]
    for kind, closed, label in _LEGEND_ENTRIES:
        parts.append(
            f'<g transform="translate({x + 26},{y})">{_symbol(kind, closed, "#334155")}</g>'
        )
        parts.append(
            f'<text x="{x + 50}" y="{y + 4}" font-size="11" font-family="sans-serif" '
            f'fill="{_INK}">{escape(label)}</text>'
        )
        y += row

    y += 10
    parts.append(f'<line x1="{x + 14}" y1="{y}" x2="{width - 24}" y2="{y}" stroke="#e5e7eb"/>')
    y += 24
    parts.append(
        f'<text x="{x + 14}" y="{y}" font-size="13" font-weight="bold" '
        f'fill="{_INK}">Voltage levels</text>'
    )
    y += 20
    for index, (level, _) in enumerate(level_order):
        parts.append(
            f'<rect x="{x + 14}" y="{y - 10}" width="14" height="12" '
            f'fill="{_PALETTE[index % len(_PALETTE)]}"/>'
            f'<text x="{x + 38}" y="{y}" font-size="11" font-family="sans-serif" '
            f'fill="{_INK}">{escape(level or "unassigned")}</text>'
        )
        y += 20
    parts.append(
        f'<line x1="{x + 14}" y1="{y - 4}" x2="{x + 28}" y2="{y - 4}" stroke="{_OPEN}" '
        f'stroke-width="2" stroke-dasharray="5 3"/>'
        f'<text x="{x + 38}" y="{y}" font-size="11" font-family="sans-serif" '
        f'fill="{_INK}">open equipment</text>'
    )
    parts.append("</g>")
    return "".join(parts)


def _shunts_svg(system, projected, node_color) -> str:
    """Render shunt devices (arresters, earthing switches, external circuits)."""

    from gdm.systems.substation.components import PrimaryEquipmentComponent

    parts: list[str] = []
    for device in system.get_components(PrimaryEquipmentComponent):
        bus = getattr(device, "bus", None)
        if bus is None or bus.name not in projected:
            continue
        px, py = projected[bus.name]
        parts.append(
            f'<g class="sld-device sld-shunt" data-attach={quoteattr(bus.name)} data-dx="30" '
            f'data-dy="22" transform="translate({px + 30:.1f},{py + 22:.1f})">'
            f"{_symbol(type(device).__name__, True, node_color(bus.name))}"
            f'<text x="0" y="-13" font-size="10" text-anchor="middle" '
            f'font-family="sans-serif" fill="{_INK}">{escape(device.name)}</text></g>'
        )
    return "".join(parts)


def render_sld_svg(
    system: SubstationSystem,
    title: str | None = None,
    width: int = _DEFAULT_WIDTH,
    height: int = _DEFAULT_HEIGHT,
) -> str:
    """Render the station single-line diagram to an SVG string."""

    positions = build_sld_layout(system)
    if not positions:
        raise ValueError("SubstationSystem.to_sld() requires at least one BusbarSection.")

    xs = [point[0] for point in positions.values()]
    ys = [point[1] for point in positions.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    left, right = _PAD, width - _LEGEND_W - _PAD
    usable_w = max(right - left, 10)
    usable_h = height - 2 * _PAD
    scale = min(usable_w / span_x, usable_h / span_y, 150.0)
    origin_x = (left + right) / 2.0 - span_x * scale / 2.0
    origin_y = (height - span_y * scale) / 2.0

    def project(x: float, y: float) -> tuple[float, float]:
        return origin_x + (x - min_x) * scale, height - origin_y - (y - min_y) * scale

    nodes = {bus.name: bus for bus in system.get_components(BusbarSection)}
    projected = {name: project(*point) for name, point in positions.items()}

    color_by_level, level_order = _level_colors(nodes)

    def node_color(name: str) -> str:
        return color_by_level.get(_band_key(nodes[name]), "#64748b")

    parts: list[str] = []
    parts.append(
        f'<svg id="sld" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" height="100%" style="background:#ffffff" '
        f'data-min-x="{min_x}" data-min-y="{min_y}" data-scale="{scale}" '
        f'data-origin-x="{origin_x}" data-origin-y="{origin_y}" data-height="{height}" '
        f'data-px-per-m="{_SLD_PX_PER_METER}">'
    )
    parts.append('<g id="viewport">')
    if title:
        parts.append(
            f'<text x="{width / 2:.0f}" y="30" text-anchor="middle" font-size="20" '
            f'font-family="sans-serif">{escape(title)}</text>'
        )

    graph = system.get_undirected_graph()
    for index, (source, target, data) in enumerate(graph.edges(data=True)):
        if source not in projected or target not in projected:
            continue
        x1, y1 = projected[source]
        x2, y2 = projected[target]
        mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
        is_closed = bool(data.get("is_closed", True))
        color = node_color(source)
        stroke = _INK if is_closed else _OPEN
        dash = ' stroke-dasharray="6 4"' if not is_closed else ""
        device_type = data["type"].__name__
        parts.append(
            f'<polyline class="sld-wire" data-edge="{index}" data-source={quoteattr(source)} '
            f'data-target={quoteattr(target)} points="{x1:.1f},{y1:.1f} {mx:.1f},{my:.1f} '
            f'{x2:.1f},{y2:.1f}" fill="none" stroke="{stroke}" stroke-width="2"{dash} '
            f"data-component-type={quoteattr(device_type)} "
            f"data-state={quoteattr(str(data.get('state', '')))}/>"
        )
        parts.append(
            f'<g class="sld-device" data-edge="{index}" transform="translate({mx:.1f},{my:.1f})">'
            f"{_symbol(device_type, is_closed, color)}"
            f'<text x="0" y="-15" font-size="10" text-anchor="middle" '
            f'font-family="sans-serif" fill="{_INK}">{escape(str(data["name"]))}</text></g>'
        )

    for name, (px, py) in projected.items():
        color = node_color(name)
        parts.append(
            f'<g class="sld-node" data-node={quoteattr(name)} '
            f'transform="translate({px:.1f},{py:.1f})">'
        )
        if nodes[name].length is not None:
            length_m = nodes[name].length.to("meter").magnitude
            half = max(12.0, min(160.0, length_m * _SLD_PX_PER_METER / 2.0))
            parts.append(
                f'<line x1="{-half}" y1="0" x2="{half}" y2="0" stroke="{_INK}" stroke-width="8" '
                f'data-busbar="true" data-state={quoteattr(nodes[name].state.value)}/>'
                f'<line x1="{-half}" y1="0" x2="{half}" y2="0" stroke="{color}" stroke-width="3.5" '
                f'data-busbar="true"/>'
                f'<circle class="sld-handle" data-side="left" cx="{-half}" cy="0" r="5"/>'
                f'<circle class="sld-handle" data-side="right" cx="{half}" cy="0" r="5"/>'
            )
        else:
            parts.append(
                f'<circle cx="0" cy="0" r="4" fill="{color}" stroke="{_INK}" data-busbar="false"/>'
            )
        parts.append(
            f'<text x="0" y="-13" font-size="10" text-anchor="middle" '
            f'font-family="sans-serif" fill="{_INK}">{escape(name)}</text></g>'
        )

    parts.append(_shunts_svg(system, projected, node_color))
    parts.append(_legend_svg(level_order, width, height))
    parts.append("</g></svg>")
    return "".join(parts)


def _html_document(svg: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
  html, body {{ margin: 0; height: 100%; font-family: sans-serif; }}
  #toolbar {{ padding: 8px 12px; background: #f3f4f6; border-bottom: 1px solid #d1d5db;
              display: flex; align-items: center; gap: 10px; }}
  #hint {{ color: #6b7280; font-size: 12px; }}
  #wrap {{ height: calc(100% - 45px); overflow: hidden; cursor: grab; }}
  #wrap.dragging {{ cursor: grabbing; }}
  .sld-node, .sld-device {{ cursor: move; user-select: none; }}
  .sld-node:hover, .sld-device:hover {{ filter: drop-shadow(0 0 4px #2563eb); }}
  .sld-node.snap, .sld-device.snap {{ filter: drop-shadow(0 0 7px #f59e0b); }}
  .sld-wire {{ transition: stroke-width 80ms linear; }}
  .sld-wire.hl {{ stroke-width: 4.5; }}
  .sld-wire.active {{ stroke-width: 5; stroke: #2563eb; stroke-dasharray: none; }}
  .sld-handle {{ fill: #2563eb; stroke: #ffffff; stroke-width: 1.5; cursor: ew-resize;
                 opacity: 0; pointer-events: none; }}
  .sld-node:hover .sld-handle {{ opacity: 1; pointer-events: auto; }}
</style>
</head>
<body>
<div id="toolbar">
  <button id="zoom-in" type="button">+</button>
  <button id="zoom-out" type="button">&minus;</button>
  <button id="reset" type="button">reset view</button>
  <button id="export" type="button">save layout</button>
  <button id="clear" type="button">clear saved</button>
  <label><input type="checkbox" id="snap" checked> snap</label>
  <span id="hint">drag nodes/equipment; drag busbar ends to resize; scroll to zoom</span>
</div>
<div id="wrap">{svg}</div>
<script>
(function () {{
  var wrap = document.getElementById('wrap');
  var svg = wrap.querySelector('svg');
  var vp = document.getElementById('viewport');
  var scale = 1, tx = 0, ty = 0;
  var GRID = 10, ALIGN = 7, NODE_SNAP = 16, MIN_HALF = 12, MAX_HALF = 200;
  var MIN_X = parseFloat(svg.dataset.minX), MIN_Y = parseFloat(svg.dataset.minY);
  var BASE_SCALE = parseFloat(svg.dataset.scale), ORIGIN_X = parseFloat(svg.dataset.originX);
  var ORIGIN_Y = parseFloat(svg.dataset.originY), BASE_HEIGHT = parseFloat(svg.dataset.height);
  var PX_PER_M = parseFloat(svg.dataset.pxPerM);
  var LS_KEY = 'gdm-sld-layout:' + {title!r};

  function snapOn() {{ return document.getElementById('snap').checked; }}
  function toSvg(clientX, clientY) {{
    var point = svg.createSVGPoint();
    point.x = clientX; point.y = clientY;
    return point.matrixTransform(vp.getScreenCTM().inverse());
  }}
  function apply() {{
    vp.setAttribute('transform', 'translate(' + tx + ',' + ty + ') scale(' + scale + ')');
  }}

  var nodes = {{}};
  Array.prototype.forEach.call(document.querySelectorAll('.sld-node'), function (group) {{
    var m = /translate\\(([-\\d.]+),\\s*([-\\d.]+)\\)/.exec(group.getAttribute('transform'));
    var node = {{ g: group, x: parseFloat(m[1]), y: parseFloat(m[2]) }};
    var bars = group.querySelectorAll('line[data-busbar]');
    if (bars.length) {{
      node.bars = Array.prototype.slice.call(bars);
      node.handles = Array.prototype.slice.call(group.querySelectorAll('.sld-handle'));
      node.half = Math.abs(parseFloat(bars[0].getAttribute('x2')));
    }}
    nodes[group.getAttribute('data-node')] = node;
  }});

  var edges = {{}};
  Array.prototype.forEach.call(document.querySelectorAll('polyline[data-edge]'), function (wire) {{
    edges[wire.getAttribute('data-edge')] = {{
      wire: wire, source: wire.getAttribute('data-source'), target: wire.getAttribute('data-target')
    }};
  }});
  Array.prototype.forEach.call(document.querySelectorAll('.sld-device[data-edge]'), function (group) {{
    var edge = edges[group.getAttribute('data-edge')];
    if (!edge) return;
    var m = /translate\\(([-\\d.]+),\\s*([-\\d.]+)\\)/.exec(group.getAttribute('transform'));
    edge.device = group; edge.x = parseFloat(m[1]); edge.y = parseFloat(m[2]);
  }});

  var shunts = [];
  Array.prototype.forEach.call(document.querySelectorAll('.sld-shunt'), function (group) {{
    shunts.push({{ g: group, node: group.getAttribute('data-attach') }});
  }});

  function updateWire(edge) {{
    var s = nodes[edge.source], t = nodes[edge.target];
    edge.wire.setAttribute('points', s.x + ',' + s.y + ' ' + edge.x + ',' + edge.y + ' ' + t.x + ',' + t.y);
  }}
  function edgesFor(name) {{
    return Object.keys(edges).map(function (k) {{ return edges[k]; }})
      .filter(function (e) {{ return e.source === name || e.target === name; }});
  }}
  function moveNode(name) {{
    var node = nodes[name];
    node.g.setAttribute('transform', 'translate(' + node.x + ',' + node.y + ')');
    edgesFor(name).forEach(updateWire);
    shunts.forEach(function (shunt) {{
      if (shunt.node === name) {{
        shunt.g.setAttribute('transform', 'translate(' + (node.x + 30) + ',' + (node.y + 22) + ')');
      }}
    }});
  }}
  function clearSnap() {{
    Array.prototype.forEach.call(document.querySelectorAll('.snap'), function (el) {{
      el.classList.remove('snap');
    }});
  }}
  function setHalf(name, half) {{
    var node = nodes[name];
    node.half = half;
    node.bars.forEach(function (bar) {{ bar.setAttribute('x1', -half); bar.setAttribute('x2', half); }});
    node.handles.forEach(function (handle) {{
      handle.setAttribute('cx', handle.getAttribute('data-side') === 'left' ? -half : half);
    }});
  }}
  function moveShuntsFor(name) {{
    var node = nodes[name];
    shunts.forEach(function (shunt) {{
      if (shunt.node === name) {{
        shunt.g.setAttribute('transform', 'translate(' + (node.x + 30) + ',' + (node.y + 22) + ')');
      }}
    }});
  }}
  function currentLayout() {{
    var data = {{}};
    Object.keys(nodes).forEach(function (name) {{
      var node = nodes[name];
      var entry = {{
        x: (node.x - ORIGIN_X) / BASE_SCALE + MIN_X,
        y: (BASE_HEIGHT - ORIGIN_Y - node.y) / BASE_SCALE + MIN_Y
      }};
      if (node.bars) entry.length_m = (2 * node.half) / PX_PER_M;
      data[name] = entry;
    }});
    return data;
  }}
  function saveState() {{
    try {{ localStorage.setItem(LS_KEY, JSON.stringify(currentLayout())); }} catch (error) {{}}
  }}
  function loadState() {{
    var raw = null;
    try {{ raw = localStorage.getItem(LS_KEY); }} catch (error) {{ return; }}
    if (!raw) return;
    var data = JSON.parse(raw);
    Object.keys(data).forEach(function (name) {{
      var node = nodes[name];
      if (!node) return;
      var entry = data[name];
      node.x = ORIGIN_X + (entry.x - MIN_X) * BASE_SCALE;
      node.y = BASE_HEIGHT - ORIGIN_Y - (entry.y - MIN_Y) * BASE_SCALE;
      node.g.setAttribute('transform', 'translate(' + node.x + ',' + node.y + ')');
      if (node.bars && entry.length_m) setHalf(name, entry.length_m * PX_PER_M / 2);
    }});
    Object.keys(edges).forEach(function (key) {{ updateWire(edges[key]); }});
    Object.keys(nodes).forEach(moveShuntsFor);
  }}

  function highlight(target, on) {{
    if (target.classList.contains('sld-node')) {{
      edgesFor(target.getAttribute('data-node')).forEach(function (e) {{ e.wire.classList.toggle('hl', on); }});
    }} else {{
      var e = edges[target.getAttribute('data-edge')];
      if (e) e.wire.classList.toggle('hl', on);
    }}
  }}
  Array.prototype.forEach.call(document.querySelectorAll('.sld-node, .sld-device'), function (el) {{
    el.addEventListener('mouseenter', function () {{ highlight(el, true); }});
    el.addEventListener('mouseleave', function () {{ highlight(el, false); }});
  }});

  var drag = null;
  wrap.addEventListener('mousedown', function (event) {{
    var handleElement = event.target.closest ? event.target.closest('.sld-handle') : null;
    var nodeElement = event.target.closest('.sld-node');
    var deviceElement = event.target.closest('.sld-device');
    if (handleElement) {{
      drag = {{ type: 'resize', name: handleElement.closest('.sld-node').getAttribute('data-node') }};
    }} else if (nodeElement) {{
      var name = nodeElement.getAttribute('data-node');
      drag = {{ type: 'node', name: name, start: toSvg(event.clientX, event.clientY),
                x: nodes[name].x, y: nodes[name].y }};
      edgesFor(name).forEach(function (e) {{ e.wire.classList.add('active'); }});
    }} else if (deviceElement && deviceElement.getAttribute('data-edge') !== null) {{
      var edge = edges[deviceElement.getAttribute('data-edge')];
      drag = {{ type: 'device', edge: edge, element: deviceElement,
                start: toSvg(event.clientX, event.clientY), x: edge.x, y: edge.y }};
      edge.wire.classList.add('active');
    }} else {{
      drag = {{ type: 'pan', clientX: event.clientX, clientY: event.clientY, tx: tx, ty: ty }};
      wrap.classList.add('dragging');
    }}
    event.preventDefault();
  }});

  window.addEventListener('mousemove', function (event) {{
    if (!drag) return;
    if (drag.type === 'pan') {{
      tx = drag.tx + (event.clientX - drag.clientX);
      ty = drag.ty + (event.clientY - drag.clientY);
      apply();
      return;
    }}
    if (drag.type === 'resize') {{
      var resizeNode = nodes[drag.name];
      var grow = Math.abs(toSvg(event.clientX, event.clientY).x - resizeNode.x);
      if (snapOn()) grow = Math.round(grow / GRID) * GRID;
      setHalf(drag.name, Math.max(MIN_HALF, Math.min(MAX_HALF, grow)));
      return;
    }}
    var point = toSvg(event.clientX, event.clientY);
    var nx = drag.x + (point.x - drag.start.x);
    var ny = drag.y + (point.y - drag.start.y);
    if (snapOn()) nx = Math.round(nx / GRID) * GRID, ny = Math.round(ny / GRID) * GRID;

    if (drag.type === 'node') {{
      if (snapOn()) {{
        Object.keys(nodes).forEach(function (key) {{
          if (key === drag.name) return;
          if (Math.abs(nodes[key].x - nx) < ALIGN) nx = nodes[key].x;
          if (Math.abs(nodes[key].y - ny) < ALIGN) ny = nodes[key].y;
        }});
      }}
      nodes[drag.name].x = nx; nodes[drag.name].y = ny;
      moveNode(drag.name);
      return;
    }}

    clearSnap();
    if (snapOn()) {{
      var best = null, bestDistance = NODE_SNAP;
      Object.keys(nodes).forEach(function (key) {{
        var node = nodes[key];
        var distance = Math.sqrt(Math.pow(node.x - nx, 2) + Math.pow(node.y - ny, 2));
        if (distance < bestDistance) {{ bestDistance = distance; best = key; }}
      }});
      if (best) {{
        nx = nodes[best].x; ny = nodes[best].y;
        nodes[best].g.classList.add('snap');
      }}
    }}
    drag.edge.x = nx; drag.edge.y = ny;
    drag.element.setAttribute('transform', 'translate(' + nx + ',' + ny + ')');
    updateWire(drag.edge);
  }});

  window.addEventListener('mouseup', function () {{
    if (drag && drag.type === 'node') {{
      edgesFor(drag.name).forEach(function (e) {{ e.wire.classList.remove('active'); }});
    }}
    if (drag && drag.type === 'device') {{ drag.edge.wire.classList.remove('active'); }}
    if (drag && drag.type !== 'pan') {{ saveState(); }}
    clearSnap();
    drag = null;
    wrap.classList.remove('dragging');
  }});

  svg.addEventListener('wheel', function (event) {{
    event.preventDefault();
    scale = Math.min(12, Math.max(0.15, scale * (event.deltaY < 0 ? 1.1 : 1 / 1.1)));
    apply();
  }}, {{ passive: false }});

  document.getElementById('zoom-in').addEventListener('click', function () {{ scale = Math.min(12, scale * 1.2); apply(); }});
  document.getElementById('zoom-out').addEventListener('click', function () {{ scale = Math.max(0.15, scale / 1.2); apply(); }});
  document.getElementById('reset').addEventListener('click', function () {{ scale = 1; tx = 0; ty = 0; apply(); }});
  document.getElementById('export').addEventListener('click', function () {{
    var blob = new Blob([JSON.stringify(currentLayout(), null, 2)], {{ type: 'application/json' }});
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = ({title!r} || 'sld') + '.layout.json';
    link.click();
    URL.revokeObjectURL(link.href);
  }});
  document.getElementById('clear').addEventListener('click', function () {{
    try {{ localStorage.removeItem(LS_KEY); }} catch (error) {{}}
  }});
  loadState();
}})();
</script>
</body>
</html>
"""


def sld_layout(system: SubstationSystem) -> dict[str, dict[str, float]]:
    """Return the current schematic layout as a serializable mapping.

    Each entry is ``{name: {"x": float, "y": float, "length_m": float}}`` for
    busbar sections (junctions omit ``length_m``).
    """

    positions = build_sld_layout(system)
    layout: dict[str, dict[str, float]] = {}
    for name, (x, y) in positions.items():
        bus = system.get_component(BusbarSection, name)
        entry: dict[str, float] = {"x": float(x), "y": float(y)}
        if bus.length is not None:
            entry["length_m"] = float(bus.length.to("meter").magnitude)
        layout[name] = entry
    return layout


def apply_sld_layout(system: SubstationSystem, layout: dict[str, dict[str, float]]) -> None:
    """Apply an edited schematic layout to a station.

    Updates ``schematic_coordinate`` (and busbar ``length`` when present) so the
    edits survive JSON serialization. Coordinates are registered with the system
    before assignment so composed ``Location`` objects resolve on reload.
    """

    for name, entry in layout.items():
        try:
            bus = system.get_component(BusbarSection, name)
        except Exception:  # noqa: BLE001 - missing node is ignored
            continue
        location = Location(x=float(entry["x"]), y=float(entry["y"]), crs="SCHEMATIC")
        system.add_component(location)
        bus.schematic_coordinate = location
        if entry.get("length_m") is not None:
            bus.length = Distance(float(entry["length_m"]), "meter")


def render_sld_html(
    system: SubstationSystem,
    output_path: str | Path | None = None,
    title: str | None = None,
    width: int = _DEFAULT_WIDTH,
    height: int = _DEFAULT_HEIGHT,
) -> str:
    """Render an interactive draggable single-line-diagram HTML document.

    Returns the HTML text and, when ``output_path`` is provided, writes it to
    that file.
    """

    diagram_title = title or f"{system.name} single-line diagram"
    svg = render_sld_svg(system, title=diagram_title, width=width, height=height)
    html = _html_document(svg, diagram_title)
    if output_path is not None:
        output = Path(output_path)
        output.write_text(html, encoding="utf-8")
    return html
