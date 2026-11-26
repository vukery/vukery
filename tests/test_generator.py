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
        for path in ("config/machine.yaml", "config/environments/development.yaml",
                     "config/environments/production.yaml", "modes/base/base.py", "modes/vukery/README.md",
                     "tests/test_my_machine.py", "pyproject.toml", "README.md", ".gitignore", ".python-version",
                     "assets/sounds/.gitkeep", "assets/images/.gitkeep", "assets/videos/.gitkeep",
                     "assets/fonts/.gitkeep"):
            assert (folder / path).is_file(), path
        assert len(created) == 14

    def it_fills_in_the_name_and_pins_this_vukery(made):
        folder, created = made
        for path in created:
            assert "{{" not in (folder / path).read_text(), path
        assert f"vukery@v{__version__}" in (folder / "pyproject.toml").read_text()
        assert 'name = "my-machine"' in (folder / "pyproject.toml").read_text()

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
        assert result.returncode == 0, result.stdout + result.stderr
        assert "passed" in result.stdout

    def it_wont_write_into_a_folder_with_files(tmp_path):
        (tmp_path / "combat").mkdir()
        (tmp_path / "combat" / "notes.txt").write_text("mine")
        with pytest.raises(ConfigError, match="isn't empty"):
            create_machine(tmp_path / "combat")

    def it_rejects_names_that_dont_make_good_folders(tmp_path):
        with pytest.raises(ConfigError, match="isn't a good machine name"):
            create_machine(tmp_path / "My Game")

    def it_is_the_vuk_it_command(tmp_path, capsys):
        assert main(["-C", str(tmp_path), "it", "combat"]) == 0
        out = capsys.readouterr().out
        assert "create  config/machine.yaml" in out
        assert "uv run vuk me" in out
        assert (tmp_path / "combat" / "tests" / "test_combat.py").is_file()

    def it_asks_for_a_name_when_none_is_given(tmp_path, capsys, monkeypatch):
        answers = iter(["", "grand-prix"])  # an empty answer asks again
        monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
        assert main(["-C", str(tmp_path), "it"]) == 0
        assert (tmp_path / "grand-prix" / "config" / "machine.yaml").is_file()

    def it_stops_if_no_name_ever_comes(tmp_path, capsys, monkeypatch):
        def no_input(prompt):
            raise EOFError
        monkeypatch.setattr("builtins.input", no_input)
        assert main(["-C", str(tmp_path), "it"]) == 1
        assert "no name given" in capsys.readouterr().err
