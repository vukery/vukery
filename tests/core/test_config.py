"""Config: shared files, environments, and what's refused."""

import pytest

from tests.helpers import basic_machine
from vukery.core.config import environment, load_game_config
from vukery.core.errors import ConfigError
from vukery.testing import expect


def describe_config():
    def describe_environments():
        def it_reads_vuk_env(monkeypatch):
            monkeypatch.setenv("VUK_ENV", "production")
            expect(environment()).to_equal("production")

        def it_refuses_an_environment_it_doesnt_know(monkeypatch):
            monkeypatch.setenv("VUK_ENV", "staging")
            with pytest.raises(ConfigError, match="VUK_ENV must be one of"):
                environment()

        def it_merges_a_folder_of_environment_files(tmp_path):
            folder = basic_machine(tmp_path, files={"config/environments/test/game.yaml": "game: {balls_per_game: 5}\n",
                                                    "config/environments/test/more.yaml": "game: {max_players: 2}\n"})
            game = load_game_config(folder, "test").section("game")
            expect((game["balls_per_game"], game["max_players"])).to_equal((5, 2))

        def it_refuses_a_file_and_a_folder_for_the_same_environment(tmp_path):
            folder = basic_machine(tmp_path, files={"config/environments/test.yaml": "game: {}\n",
                                                    "config/environments/test/game.yaml": "game: {}\n"})
            with pytest.raises(ConfigError, match="not both"):
                load_game_config(folder, "test")

        def it_needs_a_hardware_platform_in_production(tmp_path):
            with pytest.raises(ConfigError, match="production needs hardware: platform:"):
                _ = load_game_config(basic_machine(tmp_path), "production").platform  # read when used

    def describe_what_it_refuses():
        def it_explains_broken_yaml(tmp_path):
            folder = basic_machine(tmp_path, files={"config/broken.yaml": "switches: [\n"})
            with pytest.raises(ConfigError, match="broken.yaml"):
                load_game_config(folder, "test")

        def it_points_game_logic_to_modes(tmp_path):
            folder = basic_machine(tmp_path, files={"config/logic.yaml": "variable_player: {}\n"})
            with pytest.raises(ConfigError, match="that's game logic"):
                load_game_config(folder, "test")

        def it_names_sections_it_doesnt_support(tmp_path):
            folder = basic_machine(tmp_path, files={"config/later.yaml": "shots: {}\n"})
            with pytest.raises(ConfigError, match="doesn't support \\(yet\\): shots"):
                load_game_config(folder, "test")

        @pytest.mark.parametrize("section", ["hardware", "game", "media"])
        def it_names_settings_a_section_doesnt_know(tmp_path, section):
            folder = basic_machine(tmp_path, files={"config/extra.yaml": f"{section}:\n  colour: red\n"})
            with pytest.raises(ConfigError, match=f"{section}: unknown setting\\(s\\): colour"):
                load_game_config(folder, "test")

        def it_names_settings_a_player_variable_doesnt_know(tmp_path):
            folder = basic_machine(tmp_path, files={"config/extra.yaml":
                                                    "player_vars:\n  lanes:\n    initial_value: 0\n    colour: red\n"})
            with pytest.raises(ConfigError, match="player_vars: lanes: unknown setting\\(s\\): colour"):
                load_game_config(folder, "test")

        def it_needs_a_platform_name(tmp_path):
            folder = basic_machine(tmp_path, files={"config/hardware.yaml": "hardware: {platform: [fast]}\n"})
            with pytest.raises(ConfigError, match="expected a name"):
                _ = load_game_config(folder, "test").platform
