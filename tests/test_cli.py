"""The vuk command."""

import pytest

from vukery.cli import main


def describe_vuk():
    def it_prints_help_without_a_command(capsys):
        assert main([]) == 0
        assert "usage: vuk" in capsys.readouterr().out

    def it_has_no_env_flag():  # the environment comes from VUK_ENV
        with pytest.raises(SystemExit):
            main(["--env", "production", "us"])

    def it_has_no_log_flag():  # log levels come from VUK_LOG
        with pytest.raises(SystemExit):
            main(["--log", "fast=debug", "us"])

    def it_reports_the_version_from_pyproject(capsys):
        import tomllib
        from pathlib import Path

        import vukery

        project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())["project"]
        assert vukery.__version__ == project["version"]
        with pytest.raises(SystemExit):
            main(["--version"])
        assert capsys.readouterr().out.strip() == f"vukery {project['version']}"

    def it_runs_doctor(capsys):
        assert main(["doctor"]) == 0
        assert "Python" in capsys.readouterr().out

    def it_explains_a_folder_that_isnt_a_game(capsys, tmp_path):
        assert main(["-C", str(tmp_path), "us"]) == 1
        assert "has no config/ folder" in capsys.readouterr().err

    def it_runs_a_game_with_vuk_us_not_run():
        with pytest.raises(SystemExit):
            main(["run"])

    def it_says_when_a_command_isnt_built_yet(capsys):
        assert main(["hardware", "scan"]) == 2
        assert "isn't built yet" in capsys.readouterr().err


def describe_vuk_it_media_controllers():
    """vuk us starts exactly the media controllers the config asks for."""

    def _started(monkeypatch, capsys, tmp_path, example):
        import os
        from pathlib import Path

        from vukery import cli

        started = []
        monkeypatch.setattr(cli, "_start_media_controllers",
                            lambda game_dir, displays: started.extend(displays) or [])
        read_end, write_end = os.pipe()  # vuk us reads switch names from stdin; send "quit"
        os.write(write_end, b"quit\n")
        os.close(write_end)
        with os.fdopen(read_end) as stdin:
            monkeypatch.setattr("sys.stdin", stdin)
            game = Path(__file__).parents[1] / "examples" / example
            assert cli.main(["-C", str(game), "us", "--log-dir", str(tmp_path)]) == 0
        capsys.readouterr()
        return started

    def it_starts_none_for_a_game_without_displays(monkeypatch, capsys, tmp_path):
        assert _started(monkeypatch, capsys, tmp_path, "basic") == []

    def it_starts_one_per_display(monkeypatch, capsys, tmp_path):
        assert _started(monkeypatch, capsys, tmp_path, "display") == ["main"]

    def it_starts_one_for_each_of_two_displays(monkeypatch, capsys, tmp_path):
        assert _started(monkeypatch, capsys, tmp_path, "dual_display") == ["main", "apron"]


def describe_vuk_me():
    """vuk me runs the game with the dashboard instead of display windows."""

    def _run(monkeypatch, capsys, tmp_path, example):
        from pathlib import Path

        from vukery import cli

        started = {"dashboard": [], "media_controllers": []}

        class ClosedDashboard:  # stands in for the dashboard process; "closed" right away
            def __init__(self, command):
                started["dashboard"].append(command)

            def poll(self):
                return 0

            def wait(self, timeout=None):
                return 0

        monkeypatch.setattr(cli.subprocess, "Popen", ClosedDashboard)
        monkeypatch.setattr(cli, "_start_media_controllers",
                            lambda game_dir, displays: started["media_controllers"].extend(displays) or [])
        game = Path(__file__).parents[1] / "examples" / example
        assert cli.main(["-C", str(game), "me", "--log-dir", str(tmp_path)]) == 0
        capsys.readouterr()
        return started

    def it_starts_the_dashboard_and_no_display_windows(monkeypatch, capsys, tmp_path):
        started = _run(monkeypatch, capsys, tmp_path, "dual_display")
        assert len(started["dashboard"]) == 1
        assert started["dashboard"][0][1:3] == ["-m", "vukery.dashboard"]
        assert started["media_controllers"] == []  # the dashboard draws the displays itself

    def it_works_for_a_game_without_displays(monkeypatch, capsys, tmp_path):
        assert len(_run(monkeypatch, capsys, tmp_path, "basic")["dashboard"]) == 1

    def it_has_no_vuk_view():
        with pytest.raises(SystemExit):
            main(["view"])


def describe_vuk_you():
    """vuk you runs a machine folder's specs, always in the test environment."""

    def _machine(tmp_path):
        from vukery.generator import create_machine

        folder = tmp_path / "pinbot"
        create_machine(folder)
        return folder

    def it_runs_the_specs_and_passes(tmp_path, capsys):
        assert main(["-C", str(_machine(tmp_path)), "you"]) == 0

    def it_fails_when_a_spec_fails(tmp_path, capsys):
        folder = _machine(tmp_path)
        spec = folder / "tests" / "test_pinbot.py"
        spec.write_text(spec.read_text().replace("to_equal(1000)", "to_equal(999)"))
        assert main(["-C", str(folder), "you"]) != 0

    def it_passes_arguments_to_pytest(tmp_path, capfd):
        assert main(["-C", str(_machine(tmp_path)), "you", "-k", "scores_1000", "-q"]) == 0
        assert "1 passed" in capfd.readouterr().out

    def it_always_uses_the_test_environment(tmp_path, capfd, monkeypatch):
        folder = _machine(tmp_path)
        (folder / "tests" / "test_env.py").write_text(
            "import os\n\ndef test_env():\n    assert os.environ['VUK_ENV'] == 'test'\n")
        monkeypatch.setenv("VUK_ENV", "production")
        assert main(["-C", str(folder), "you", "-k", "test_env"]) == 0

    def it_answers_to_vuk_test_too(tmp_path, capsys):
        assert main(["-C", str(_machine(tmp_path)), "test"]) == 0

    def it_explains_a_folder_that_isnt_a_machine(tmp_path, capsys):
        assert main(["-C", str(tmp_path), "you"]) == 1
        assert "isn't a machine folder" in capsys.readouterr().err
