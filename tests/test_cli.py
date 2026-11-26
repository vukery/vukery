"""The vuk command."""

import socket

import pytest

from vukery.cli import main
from vukery.testing import expect


@pytest.fixture(autouse=True)
def development(monkeypatch):
    """These specs run vuk us and vuk me as you would: on the development platform.

    (vuk you runs specs with VUK_ENV=test, and on the test platform a game runs
    until it's stopped.)
    """
    monkeypatch.setenv("VUK_ENV", "development")


@pytest.fixture(autouse=True)
def free_media_port(monkeypatch):
    """Games started here listen on a free port, so a vuk me left open (port 5051) doesn't get in the way."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    monkeypatch.setattr("vukery.media.protocol.DEFAULT_PORT", port)


def describe_vuk():
    def it_prints_help_without_a_command(capsys):
        expect(main([])).to_equal(0)
        expect(capsys.readouterr().out).to_contain("usage: vuk")

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
        expect(vukery.__version__).to_equal(project["version"])
        with pytest.raises(SystemExit):
            main(["--version"])
        expect(capsys.readouterr().out.strip()).to_equal(f"vukery {project['version']}")

    def it_runs_health(capsys):
        expect(main(["health"])).to_equal(0)
        expect(capsys.readouterr().out).to_contain("Python")

    @pytest.mark.parametrize(("direct_url", "says"), [
        ('{"url": "https://github.com/vukery/vukery", "vcs_info": {"vcs": "git", "commit_id": "62a2e29abc"}}',
         "git https://github.com/vukery/vukery at 62a2e29"),
        ('{"url": "file:///src/vukery", "dir_info": {"editable": true}}', "/src/vukery (editable"),
        ('{"url": "file:///src/vukery", "dir_info": {}}', "/src/vukery"),
        (None, "a package index"),
    ])
    def it_says_where_vukery_was_installed_from(monkeypatch, direct_url, says):
        import importlib.metadata

        from vukery.cli import installed_from

        class Installed:
            def read_text(self, name):
                return direct_url

        monkeypatch.setattr(importlib.metadata, "distribution", lambda name: Installed())
        expect(installed_from()).to_contain(says)

    def it_explains_a_folder_that_isnt_a_game(capsys, tmp_path):
        expect(main(["-C", str(tmp_path), "us"])).to_equal(1)
        expect(capsys.readouterr().err).to_contain("has no config/ folder")

    def it_runs_a_game_with_vuk_us_not_run():
        with pytest.raises(SystemExit):
            main(["run"])

    def it_says_when_a_command_isnt_built_yet(capsys):
        expect(main(["hardware", "scan"])).to_equal(2)
        expect(capsys.readouterr().err).to_contain("isn't built yet")


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
            expect(cli.main(["-C", str(game), "us", "--log-dir", str(tmp_path)])).to_equal(0)
        capsys.readouterr()
        return started

    def it_starts_none_for_a_game_without_displays(monkeypatch, capsys, tmp_path):
        expect(_started(monkeypatch, capsys, tmp_path, "basic")).to_equal([])

    def it_starts_one_per_display(monkeypatch, capsys, tmp_path):
        expect(_started(monkeypatch, capsys, tmp_path, "display")).to_equal(["main"])

    def it_starts_one_for_each_of_two_displays(monkeypatch, capsys, tmp_path):
        expect(_started(monkeypatch, capsys, tmp_path, "dual_display")).to_equal(["main", "apron"])


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
        expect(cli.main(["-C", str(game), "me", "--log-dir", str(tmp_path)])).to_equal(0)
        capsys.readouterr()
        return started

    def it_starts_the_dashboard_and_no_display_windows(monkeypatch, capsys, tmp_path):
        started = _run(monkeypatch, capsys, tmp_path, "dual_display")
        expect(len(started["dashboard"])).to_equal(1)
        expect(started["dashboard"][0][1:3]).to_equal(["-m", "vukery.dashboard"])
        expect(started["media_controllers"]).to_equal([])  # the dashboard draws the displays itself

    def it_works_for_a_game_without_displays(monkeypatch, capsys, tmp_path):
        expect(len(_run(monkeypatch, capsys, tmp_path, "basic")["dashboard"])).to_equal(1)

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
        expect(main(["-C", str(_machine(tmp_path)), "you"])).to_equal(0)

    def it_fails_when_a_spec_fails(tmp_path, capsys):
        folder = _machine(tmp_path)
        spec = folder / "tests" / "test_pinbot.py"
        spec.write_text(spec.read_text().replace("to_equal(1000)", "to_equal(999)"))
        expect(main(["-C", str(folder), "you"])).not_to_equal(0)

    def it_passes_arguments_to_pytest(tmp_path, capfd):
        expect(main(["-C", str(_machine(tmp_path)), "you", "-k", "scores_1000", "-q"])).to_equal(0)
        expect(capfd.readouterr().out).to_contain("1 passed")

    def it_always_uses_the_test_environment(tmp_path, capfd, monkeypatch):
        folder = _machine(tmp_path)
        (folder / "tests" / "test_env.py").write_text(
            "import os\n\ndef test_env():\n    assert os.environ['VUK_ENV'] == 'test'\n")
        monkeypatch.setenv("VUK_ENV", "production")
        expect(main(["-C", str(folder), "you", "-k", "test_env"])).to_equal(0)

    def it_answers_to_vuk_test_too(tmp_path, capsys):
        expect(main(["-C", str(_machine(tmp_path)), "test"])).to_equal(0)

    def it_measures_the_machines_own_code(tmp_path, capfd):
        expect(main(["-C", str(_machine(tmp_path)), "you", "-q"])).to_equal(0)
        out = capfd.readouterr().out
        expect(out).to_contain("coverage")
        expect(out).to_contain("TOTAL")

    def it_still_measures_the_code_when_given_a_test_path(tmp_path, capfd):
        folder = tmp_path / "project"
        folder.mkdir()
        (folder / "pyproject.toml").write_text("[tool.coverage.run]\nsource = ['lib']\n")
        (folder / "lib.py").write_text("def answer():\n    return 42\n")
        (folder / "tests").mkdir()
        (folder / "tests" / "test_lib.py").write_text("from lib import answer\n\ndef test_it():\n    assert answer() == 42\n")
        expect(main(["-C", str(folder), "you", "tests/test_lib.py", "-q", "-p", "no:spec"])).to_equal(0)
        table = capfd.readouterr().out.split("coverage:")[-1]  # the coverage report, after the results
        expect(table).to_contain("lib.py")
        expect(table).not_to_contain("tests/test_lib.py")

    def it_runs_without_coverage_when_asked(tmp_path, capfd):
        expect(main(["-C", str(_machine(tmp_path)), "you", "-q", "--no-cov"])).to_equal(0)
        expect(capfd.readouterr().out).not_to_contain("TOTAL")

    def it_runs_a_python_projects_specs_too(tmp_path, capfd):  # like vukery's own
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_it.py").write_text("def test_it():\n    assert True\n")
        expect(main(["-C", str(tmp_path), "you", "-q", "-p", "no:spec"])).to_equal(0)
        expect(capfd.readouterr().out).to_contain("1 passed")

    def it_explains_a_folder_that_isnt_a_machine(tmp_path, capsys):
        expect(main(["-C", str(tmp_path), "you"])).to_equal(1)
        expect(capsys.readouterr().err).to_contain("isn't a machine folder (no config/) or a Python project")


def describe_the_media_controller():
    """Display windows run as python -m vukery.mc, started by vuk us; there's no vuk mc."""

    def it_has_no_vuk_mc():
        with pytest.raises(SystemExit):
            main(["mc"])

    def it_is_started_per_display_by_vuk_us(monkeypatch):
        from pathlib import Path

        from vukery import cli

        commands = []
        monkeypatch.setattr(cli.subprocess, "Popen", lambda command: commands.append(command))
        cli._start_media_controllers(Path("game"), ["main", "apron"])
        expect([c[1:] for c in commands]).to_equal([["-m", "vukery.mc", "game", "--display", "main"],
                                             ["-m", "vukery.mc", "game", "--display", "apron"]])

    def it_explains_a_machine_without_displays(capsys):
        from pathlib import Path

        from vukery.mc.__main__ import main as mc

        expect(mc([str(Path(__file__).parents[1] / "examples" / "basic")])).to_equal(1)
        expect(capsys.readouterr().err).to_contain("no displays: section")

    def it_explains_an_unknown_display(capsys):
        from pathlib import Path

        from vukery.mc.__main__ import main as mc

        expect(mc([str(Path(__file__).parents[1] / "examples" / "display"), "--display", "apron"])).to_equal(1)
        expect(capsys.readouterr().err).to_contain("no display named 'apron'")
