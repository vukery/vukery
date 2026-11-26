"""vuk it NAME: a new machine folder that plays and passes its own specs."""

import subprocess
import sys

import pytest

from vukery import __version__
from vukery.cli import main
from vukery.core.errors import ConfigError
from vukery.generator import create_machine
from vukery.testing import GameRig, expect


@pytest.fixture
def made(tmp_path):
    folder = tmp_path / "my-machine"
    return folder, create_machine(folder)


def describe_vuk_it():
    def it_creates_a_complete_machine_folder(made):
        folder, created = made
        for path in ("config/machine.yaml", "config/dashboard.yaml", "config/environments/development.yaml",
                     "config/environments/production.yaml", "modes/base/mode.py", "modes/vukery/README.md",
                     "tests/test_my_machine.py", "pyproject.toml", "README.md", ".gitignore", ".python-version",
                     "assets/sounds/.gitkeep", "assets/images/.gitkeep", "assets/videos/.gitkeep",
                     "assets/fonts/.gitkeep"):
            expect((folder / path).is_file()).to_be_true()
        expect(len(created)).to_equal(15)

    def it_fills_in_the_name_and_pins_this_vukery(made):
        folder, created = made
        for path in created:
            expect((folder / path).read_text()).not_to_contain("{{")  # path
        expect((folder / "pyproject.toml").read_text()).to_contain(f"vukery@v{__version__}")
        expect((folder / "pyproject.toml").read_text()).to_contain('name = "my-machine"')

    def it_makes_a_machine_that_plays(made):
        folder, _ = made
        game = GameRig(folder)
        try:
            game.start_game()
            game.switch("s_target")
            expect(game.player.score).to_equal(1000)
        finally:
            game.stop()

    def it_makes_a_machine_whose_own_specs_pass(made):
        folder, _ = made
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=folder,
                                capture_output=True, text=True, timeout=120, check=False)
        expect(result.returncode).to_equal(0)  # result.stdout + result.stderr
        expect(result.stdout).to_contain("passed")

    def it_wont_write_into_a_folder_with_files(tmp_path):
        (tmp_path / "combat").mkdir()
        (tmp_path / "combat" / "notes.txt").write_text("mine")
        with pytest.raises(ConfigError, match="isn't empty"):
            create_machine(tmp_path / "combat")

    def it_rejects_names_that_dont_make_good_folders(tmp_path):
        with pytest.raises(ConfigError, match="isn't a good machine name"):
            create_machine(tmp_path / "My Game")

    def it_is_the_vuk_it_command(tmp_path, capsys):
        expect(main(["-C", str(tmp_path), "it", "combat"])).to_equal(0)
        out = capsys.readouterr().out
        expect(out).to_contain("create  config/machine.yaml")
        expect(out).to_contain("uv run vuk me")
        expect((tmp_path / "combat" / "tests" / "test_combat.py").is_file()).to_be_true()

    def it_asks_for_a_name_when_none_is_given(tmp_path, capsys, monkeypatch):
        answers = iter(["", "grand-prix"])  # an empty answer asks again
        monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
        expect(main(["-C", str(tmp_path), "it"])).to_equal(0)
        expect((tmp_path / "grand-prix" / "config" / "machine.yaml").is_file()).to_be_true()

    def it_stops_if_no_name_ever_comes(tmp_path, capsys, monkeypatch):
        def no_input(prompt):
            raise EOFError
        monkeypatch.setattr("builtins.input", no_input)
        expect(main(["-C", str(tmp_path), "it"])).to_equal(1)
        expect(capsys.readouterr().err).to_contain("no name given")
