from gdm.systems.distribution.components import DistributionReactor


def test_distribution_reactor_example():
    reactor = DistributionReactor.example()

    assert reactor.name == "reactor"
    assert len(reactor.buses) == 2
    assert reactor.phases == ["A", "B", "C"]
    assert reactor.equipment.resistance.to("ohm").magnitude == 0
    assert reactor.equipment.reactance.to("ohm").magnitude == 1
