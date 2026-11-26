"""The machine: platforms, devices and modes it refuses, with the reasons."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.core.machine import Machine
from vukery.testing import GameRig, expect


def _fast(config):
    config["hardware"] = {"platform": "fast"}


def describe_the_machine():
    def describe_platforms():
        def it_never_uses_hardware_in_test(tmp_path):
            with pytest.raises(ConfigError, match="never uses real hardware"):
                Machine.from_folder(basic_machine(tmp_path, edit=_fast), env="test")

        def it_needs_dash_dash_hardware_in_development(tmp_path):
            with pytest.raises(ConfigError, match="needs --hardware"):
                Machine.from_folder(basic_machine(tmp_path, edit=_fast), env="development")

        def it_names_platforms_it_doesnt_know(tmp_path):
            def edit(config):
                config["hardware"] = {"platform": "p_roc"}

            with pytest.raises(ConfigError, match="'p_roc' isn't supported"):
                Machine.from_folder(basic_machine(tmp_path, edit=edit), env="test")

    def describe_devices():
        def it_only_has_troughs_for_ball_devices_so_far(tmp_path):
            def edit(config):
                config["ball_devices"]["bd_trough"]["tags"] = "home"

            with pytest.raises(ConfigError, match="only troughs"):
                GameRig(basic_machine(tmp_path, edit=edit))

    def describe_modes():
        def it_explains_a_mode_class_named_for_another_mode(tmp_path):
            folder = basic_machine(tmp_path, files={"modes/base/mode.py": '''
                from vukery import Mode


                class Bonus(Mode):
                    pass
            '''})
            with pytest.raises(ConfigError, match="whose mode name is 'bonus'"):
                GameRig(folder)

        def it_wants_one_mode_class_per_file(tmp_path):
            folder = basic_machine(tmp_path, files={"modes/base/mode.py": '''
                from vukery import Mode


                class Base(Mode):
                    pass


                class Base2(Mode):
                    name = "base"
            '''})
            with pytest.raises(ConfigError, match="expected one Mode subclass"):
                GameRig(folder)

        def it_names_a_mode_with_no_folder(tmp_path):
            with pytest.raises(ConfigError, match="no .*modes/jackpot/mode.py"):
                GameRig(basic_machine(tmp_path, edit=lambda c: c["modes"].append("jackpot")))

        def it_describes_a_mode(tmp_path):
            rig = GameRig(basic_machine(tmp_path))
            try:
                expect(repr(rig.mode("base"))).to_equal("<Mode base (stopped, priority 100)>")
                rig.start_game()
                expect(repr(rig.mode("base"))).to_equal("<Mode base (running, priority 100)>")
            finally:
                rig.stop()
