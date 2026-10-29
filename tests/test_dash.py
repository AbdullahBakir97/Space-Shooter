import pytest

from space_shooter.dash import DASH_SPEED, DASH_TIME, Dash


def test_constants():
    assert pytest.approx(0.18) == DASH_TIME and pytest.approx(1100.0) == DASH_SPEED


def test_dash_without_charges_refuses():
    assert Dash(0, 2.5).try_start() is False


def test_dash_active_window():
    d = Dash(1, 2.5)
    assert d.try_start() and d.active and d.charges == 0
    d.update(0.1)
    assert d.active and d.remaining == pytest.approx(0.08)
    d.update(0.1)
    assert not d.active
    assert d.try_start() is False  # still recharging


def test_dash_charges_recharge_one_at_a_time():
    d = Dash(2, 2.0)
    assert d.try_start()
    d.update(DASH_TIME)
    assert d.try_start() and d.charges == 0
    d.update(2.0)
    assert d.charges == 1
    d.update(2.0)
    assert d.charges == 2
    d.update(5.0)
    assert d.charges == 2


def test_dash_configure_follows_thrusters():
    d = Dash(2, 2.0)
    d.configure(1, 2.5)
    assert d.charges == 1 and d.max_charges == 1
    d.configure(0, 2.5)
    assert d.charges == 0
    fresh = Dash(0, 2.5)
    fresh.configure(1, 2.5)
    assert fresh.charges == 1  # a thruster fitted for the first time arrives charged
    fresh.try_start()
    fresh.configure(2, 2.0)
    assert fresh.charges == 1  # the second new thruster adds its own charge, not a full refill


def test_refitting_the_same_thruster_does_not_refill():
    d = Dash(0, 2.5)
    d.configure(1, 2.5)
    assert d.try_start() and d.charges == 0
    d.update(0.2)
    d.configure(0, 2.5)  # knocked off
    d.configure(1, 2.5)  # picked straight back up
    assert d.charges == 0
    d.update(2.5)
    assert d.charges == 1  # it still recharges normally
