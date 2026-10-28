from space_shooter.combo import Combo


def test_multiplier_climbs_every_three_kills():
    c = Combo(window=1.0, max_mult=4)
    mults = [c.register_kill() for _ in range(12)]
    assert mults[:3] == [1, 1, 2]
    assert mults[-1] == 4  # capped


def test_chain_breaks_after_window():
    c = Combo(window=1.0)
    c.register_kill()
    assert not c.update(0.5)
    assert c.update(0.6)
    assert c.multiplier == 1 and c.chain == 0
    assert not c.update(1.0)  # idle combo never "breaks" again


def test_fraction():
    c = Combo(window=2.0)
    assert c.fraction == 0.0
    c.register_kill()
    c.update(1.0)
    assert abs(c.fraction - 0.5) < 1e-9
