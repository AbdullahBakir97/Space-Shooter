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
    d.configure(1, 2.5)
    assert d.charges == 1  # a newly fitted thruster arrives charged
    d.try_start()
    d.configure(2, 2.0)
    assert d.charges == 1  # the second thruster adds its own charge, not a full refill
