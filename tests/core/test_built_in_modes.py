"""Built-in modes: a game changes them only where they say it can, and replaces only the optional ones."""

from typing import ClassVar

import pytest

from tests.helpers import basic_machine
from vukery import Mode, on
from vukery.core.errors import ConfigError
from vukery.modes import Attract
from vukery.modes.built_in import BuiltInMode, resolve
from vukery.testing import GameRig, expect


class Lottery(BuiltInMode, built_in=True):   # an optional built-in, for these specs
    optional = True
    customizable = frozenset({"odds", "look", "pays"})
    odds: ClassVar[int] = 10
    look: ClassVar[str] = "plain"

    def pays(self, player):
        return "credit"

    def mode_start(self, **_):
        self.started = True


def describe_customizing_a_built_in_mode():
    def it_changes_what_the_mode_says_it_can():
        class Lucky(Lottery):
            odds = 2
            look = "gold"

            def pays(self, player):
                return "extra ball"

        expect((Lucky.odds, Lucky.look)).to_equal((2, "gold"))

    def it_keeps_the_built_in_modes_name():
        class LuckyLottery(Lottery):
            odds = 2

        expect(LuckyLottery.name).to_equal("lottery")

    def it_may_add_helpers_of_its_own():
        class Lucky(Lottery):
            def _odds_tonight(self):
                return 3

        expect(Lucky._odds_tonight(None)).to_equal(3)

    def it_refuses_to_override_anything_else():
        with pytest.raises(ConfigError, match=r"which can change only: look, odds, pays\. It can't change: mode_start"):
            class Rewired(Lottery):
                def mode_start(self, **_):
                    pass

    def it_refuses_new_handlers_and_says_where_they_go():
        with pytest.raises(ConfigError, match="react to the mode's events in a mode of your own, or replace it"):
            class Noisy(Lottery):
                @on.switch("s_target")
                def target(self):
                    pass

    def it_refuses_to_change_a_core_modes_settings():
        with pytest.raises(ConfigError, match="It can't change: priority"):
            class EagerAttract(Attract):
                priority = 50


def describe_replacing_a_built_in_mode():
    def it_runs_a_customized_one():
        class Lucky(Lottery):
            odds = 2

        expect(resolve(Lottery, Lucky)).to_be(Lucky)

    def it_runs_a_games_own_instead_of_an_optional_one():
        class MyLottery(Mode):
            name = "lottery"

        expect(resolve(Lottery, MyLottery)).to_be(MyLottery)

    def it_refuses_to_replace_a_core_one():
        class MyAttract(Mode):
            name = "attract"

        with pytest.raises(ConfigError, match="which a game can't replace. Customize it with a subclass"):
            resolve(Attract, MyAttract)

    def it_loads_a_games_customization_from_its_mode_folder(tmp_path):
        def edit(config):
            config["modes"] = [*config["modes"], "attract"]

        folder = basic_machine(tmp_path, edit=edit, files={"modes/attract/mode.py": """
            from vukery.modes import Attract


            class QuietAttract(Attract):   # changes nothing yet: attract has nothing to customize
                pass
        """})
        rig = GameRig(folder)
        try:
            expect(type(rig.mode("attract")).__name__).to_equal("QuietAttract")
            expect(rig.mode("attract")).to_be_running()
        finally:
            rig.stop()

    def it_explains_a_games_attract_that_isnt_a_customization(tmp_path):
        def edit(config):
            config["modes"] = [*config["modes"], "attract"]

        folder = basic_machine(tmp_path, edit=edit, files={"modes/attract/mode.py": """
            from vukery import Mode


            class Attract(Mode):
                pass
        """})
        with pytest.raises(ConfigError, match="modes: attract is vukery's Attract, which a game can't replace"):
            GameRig(folder)
