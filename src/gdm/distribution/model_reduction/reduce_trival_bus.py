


def _branches_are_compatible(
    branch_a: MatrixImpedanceBranch,
    branch_b: MatrixImpedanceBranch,
) -> bool:
    """Check if two MatrixImpedanceBranch components can be merged.

    Branches are compatible if they have identical phases, construction type,
    ampacity, and per-unit-length impedance/capacitance matrices.
    """
    if sorted(branch_a.phases, key=lambda p: p.value) != sorted(
        branch_b.phases, key=lambda p: p.value
    ):
        return False

    eq_a = branch_a.equipment
    eq_b = branch_b.equipment

    if eq_a.construction != eq_b.construction:
        return False

    if not np.isclose(
        eq_a.ampacity.to("ampere").magnitude,
        eq_b.ampacity.to("ampere").magnitude,
        rtol=1e-6,
    ):
        return False

    for mat_attr in ("r_matrix", "x_matrix", "c_matrix"):
        mat_a = getattr(eq_a, mat_attr)
        mat_b = getattr(eq_b, mat_attr).to(mat_a.units)
        if not np.allclose(mat_a.magnitude, mat_b.magnitude, rtol=1e-6, atol=0):
            return False

    return True


def _merge_branches(
    dist_system: DistributionSystem,
    branch_a: MatrixImpedanceBranch,
    branch_b: MatrixImpedanceBranch,
    middle_bus: DistributionBus,
) -> MatrixImpedanceBranch:
    """Create a merged branch replacing two series branches through a trivial bus."""
    outer_bus_a = (
        branch_a.buses[0] if branch_a.buses[1].name == middle_bus.name else branch_a.buses[1]
    )
    outer_bus_b = (
        branch_b.buses[0] if branch_b.buses[1].name == middle_bus.name else branch_b.buses[1]
    )

    new_length = branch_a.length.to("meter").magnitude + branch_b.length.to("meter").magnitude

    return MatrixImpedanceBranch(
        buses=[outer_bus_a, outer_bus_b],
        length=Distance(new_length, "meter"),
        phases=list(branch_a.phases),
        equipment=branch_a.equipment,
        name=f"{branch_a.name}__{branch_b.name}",
        in_service=branch_a.in_service and branch_b.in_service,
        substation=branch_a.substation,
        feeder=branch_a.feeder,
    )


def _find_buses_with_non_branch_components(dist_system: DistributionSystem) -> set[str]:
    buses_with_components: set[str] = set()
    branch_types = (DistributionBranchBase, DistributionTransformerBase)
    for model_type in dist_system.get_model_types_with_field_type(DistributionBus):
        if issubclass(model_type, branch_types):
            continue
        for comp in dist_system.get_components(model_type):
            bus_field = getattr(comp, "bus", None)
            if bus_field is not None:
                buses_with_components.add(bus_field.name)
    return buses_with_components


def _build_bus_to_branches_map(
    dist_system: DistributionSystem,
) -> dict[str, list[MatrixImpedanceBranch]]:
    bus_to_branches: dict[str, list[MatrixImpedanceBranch]] = {}
    for branch in dist_system.get_components(MatrixImpedanceBranch):
        for bus in branch.buses:
            bus_to_branches.setdefault(bus.name, []).append(branch)
    return bus_to_branches


def _find_trivial_buses(
    dist_system: DistributionSystem,
    graph: nx.MultiGraph,
    buses_with_components: set[str],
    bus_to_branches: dict[str, list[MatrixImpedanceBranch]],
) -> set[str]:
    trivial_buses: set[str] = set()
    source_bus_name = dist_system.get_source_bus().name
    for bus in dist_system.get_components(DistributionBus):
        if bus.name == source_bus_name or bus.name in buses_with_components:
            continue
        if graph.degree(bus.name) != 2:
            continue
        branches = bus_to_branches.get(bus.name, [])
        if len(branches) != 2:
            continue
        if _branches_are_compatible(branches[0], branches[1]):
            trivial_buses.add(bus.name)
    return trivial_buses


def _extend_merge_chain(
    dist_system: DistributionSystem,
    merged: MatrixImpedanceBranch,
    trivial_buses: set[str],
    bus_to_branches: dict[str, list[MatrixImpedanceBranch]],
    consumed_branches: set[str],
    consumed_buses: set[str],
) -> MatrixImpedanceBranch:
    while True:
        extended = False
        for ob in (merged.buses[0].name, merged.buses[1].name):
            if ob not in trivial_buses or ob in consumed_buses:
                continue
            next_branch = next(
                (nb for nb in bus_to_branches[ob] if nb.name not in consumed_branches),
                None,
            )
            if next_branch is None or not _branches_are_compatible(merged, next_branch):
                continue
            ob_bus = dist_system.get_component(DistributionBus, ob)
            merged = _merge_branches(dist_system, merged, next_branch, ob_bus)
            consumed_branches.add(next_branch.name)
            consumed_buses.add(ob)
            extended = True
        if not extended:
            return merged


def reduce_trivial_nodes(
    dist_system: DistributionSystem,
    name: str | None = None,
) -> DistributionSystem:
    """Remove trivial pass-through nodes from the distribution system.

    A bus is trivial if it connects exactly two MatrixImpedanceBranch components
    with identical per-unit-length electrical characteristics (impedance matrices,
    construction type, ampacity) and has no other components attached. The two
    branches are merged into a single branch whose length is the sum of the
    originals.

    Parameters
    ----------
    dist_system : DistributionSystem
        The system to reduce.
    name : str | None
        Name for the reduced system. Defaults to the original name.

    Returns
    -------
    DistributionSystem
        A new reduced system with trivial nodes removed.
    """

    dist_system = dist_system.deepcopy()

    if name is None:
        name = dist_system.name

    graph = dist_system.get_undirected_graph()

    buses_with_components = _find_buses_with_non_branch_components(dist_system)
    bus_to_branches = _build_bus_to_branches_map(dist_system)
    trivial_buses = _find_trivial_buses(dist_system, graph, buses_with_components, bus_to_branches)

    if not trivial_buses:
        return dist_system

    merged_branches: list[MatrixImpedanceBranch] = []
    consumed_branches: set[str] = set()
    consumed_buses: set[str] = set()

    for bus_name in list(trivial_buses):
        if bus_name in consumed_buses:
            continue
        branch_a, branch_b = bus_to_branches[bus_name]
        if branch_a.name in consumed_branches or branch_b.name in consumed_branches:
            continue

        bus = dist_system.get_component(DistributionBus, bus_name)
        merged = _merge_branches(dist_system, branch_a, branch_b, bus)
        consumed_branches.add(branch_a.name)
        consumed_branches.add(branch_b.name)
        consumed_buses.add(bus_name)

        merged = _extend_merge_chain(
            dist_system,
            merged,
            trivial_buses,
            bus_to_branches,
            consumed_branches,
            consumed_buses,
        )
        merged_branches.append(merged)

    for comp_type in [MatrixImpedanceBranch, DistributionBus]:
        for comp in dist_system.get_components(comp_type):
            if comp.name in consumed_buses or comp.name in consumed_branches:
                dist_system.remove_component(comp)

    dist_system.auto_add_composed_components = True
    for merged in merged_branches:
        dist_system.add_component(merged)

    return dist_system
