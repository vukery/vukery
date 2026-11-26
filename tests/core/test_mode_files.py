"""A mode can live in one file, or split itself into files next to it."""

import shutil
import textwrap
from pathlib import Path

import pytest

from vukery.testing import GameRig, expect

BASIC = Path(__file__).parents[2] / "examples" / "basic"


@pytest.fixture
def machine(tmp_path):
    folder = tmp_path / "machine"
    shutil.copytree(BASIC, folder)
    return folder


def _write(path, code):
    path.write_text(textwrap.dedent(code))


def describe_mode_files():
    def it_still_loads_a_mode_in_one_file(machine):
        game = GameRig(machine)
        try:
            game.start_game()
            game.switch("s_target")
            expect(game.player.score).to_equal(1000)
        finally:
            game.stop()

    def it_loads_a_mode_split_into_files_next_to_it(machine):
        base = machine / "modes" / "base"
        _write(base / "scoring.py", """
            SCORING = {"s_target": 2500, "s_left_sling": 10, "s_right_sling": 10}
        """)
        _write(base / "rules.py", """
            def frenzy_due(targets):
                return targets % 3 == 0
        """)
        code = (base / "mode.py").read_text()
        code = code.replace("from vukery import Mode, on\n", "from vukery import Mode, on\n\nfrom .rules import frenzy_due\n"
                            "from .scoring import SCORING\n")
        code = code.replace('''    scoring = {
        "s_target": 1000,
        "s_left_sling": 10,
        "s_right_sling": 10,
    }''', "    scoring = SCORING")
        code = code.replace("self.player.targets % TARGETS_FOR_FRENZY == 0", "frenzy_due(self.player.targets)")
        (base / "mode.py").write_text(code)
        assert "from .scoring import SCORING" in code and "frenzy_due(self.player.targets)" in code
        game = GameRig(machine)
        try:
            game.start_game()
            game.switch("s_target", times=3)
            expect(game.player.score).to_equal(7500)
            expect(game.mode("frenzy")).to_be_running()
        finally:
            game.stop()

    def it_loads_the_files_fresh_every_time_the_machine_starts(machine):
        GameRig(machine).stop()
        scoring = machine / "modes" / "base" / "mode.py"
        scoring.write_text(scoring.read_text().replace('"s_target": 1000', '"s_target": 42'))
        game = GameRig(machine)
        try:
            game.start_game()
            game.switch("s_target")
            expect(game.player.score).to_equal(42)
        finally:
            game.stop()

    def it_asks_for_mode_py_when_a_mode_is_named_the_old_way(machine):
        from vukery.core.errors import ConfigError

        base = machine / "modes" / "base"
        (base / "mode.py").rename(base / "base.py")
        with pytest.raises(ConfigError, match="a mode's main file is mode.py: rename"):
            GameRig(machine)

    def it_needs_a_mode_py_in_every_mode_folder(machine):
        from vukery.core.errors import ConfigError

        (machine / "modes" / "jackpot").mkdir()
        (machine / "modes" / "jackpot" / "scoring.py").write_text("SCORING = {}")
        with pytest.raises(ConfigError, match=r"No mode.py in: modes/jackpot/"):
            GameRig(machine)

    def it_leaves_the_vukery_overrides_folder_and_folders_inside_modes_alone(machine):
        (machine / "modes" / "vukery").mkdir()
        (machine / "modes" / "vukery" / "README.md").write_text("overrides")
        (machine / "modes" / "base" / "helpers").mkdir()
        GameRig(machine).stop()
