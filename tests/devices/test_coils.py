"""Coils: limits checked in the engine, before anything reaches the hardware."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import CoilLimitError, ConfigError
from vukery.devices.coil import CoilConfig
from vukery.testing import GameRig


@pytest.fixture
def rig(tmp_path):
    def edit(config):
        config["coils"]["c_limited"] = {"number": "9", "default_pulse_ms": 20, "default_pulse_power": 0.5,
                                        "max_pulse_power": 0.5,
                                        "max_hold_power": 0.25}

    game = GameRig(basic_machine(tmp_path, edit=edit))
    yield game
    game.stop()


def describe_coil_limits():
    def it_rejects_settings_it_doesnt_know():
        with pytest.raises(ConfigError, match="unknown setting"):
            CoilConfig.from_yaml("c_x", {"number": "1", "pulse": 20})

    def it_refuses_a_default_pulse_power_above_the_max(tmp_path):  # checked as the machine starts
        def edit(config):
            config["coils"]["c_limited"] = {"number": "9", "max_pulse_power": 0.5}  # default power is 1.0

        with pytest.raises(CoilLimitError, match="above max_pulse_power"):
            GameRig(basic_machine(tmp_path, edit=edit))

    def it_refuses_a_pulse_longer_than_the_platform_allows(rig):
        with pytest.raises(CoilLimitError, match="outside 0-"):
            rig.machine.coils["c_limited"].pulse(pulse_ms=10_000)

    def it_refuses_more_pulse_power_than_the_coils_max(rig):
        with pytest.raises(CoilLimitError, match="above max_pulse_power"):
            rig.machine.coils["c_limited"].pulse(pulse_power=0.75)

    def it_refuses_more_hold_power_than_the_coils_max(rig):
        with pytest.raises(CoilLimitError, match="above its limit"):
            rig.machine.coils["c_limited"].enable(hold_power=0.5)

    def it_holds_at_its_max_hold_power_by_default(rig):
        coil = rig.machine.coils["c_limited"]
        coil.enable()
        assert coil.hw_driver.enabled.power == 0.25

    def it_refuses_a_negative_timed_enable(rig):
        with pytest.raises(CoilLimitError, match="negative"):
            rig.machine.coils["c_limited"].timed_enable(timed_enable_ms=-5)

    def it_timed_enables_within_its_limits(rig):
        coil = rig.machine.coils["c_limited"]
        coil.timed_enable(timed_enable_ms=500, hold_power=0.2)
        assert (coil.pulses, coil.hw_driver.enabled.power, coil.hw_driver.enabled.duration) == (1, 0.2, 500)
