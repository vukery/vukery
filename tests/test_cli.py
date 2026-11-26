"""The vuk command."""

import pytest

from vukery.cli import main


def describe_vuk():
    def it_prints_help_without_a_command(capsys):
        assert main([]) == 0
        assert "usage: vuk" in capsys.readouterr().out

    def it_has_no_env_flag():  # the environment comes from VUK_ENV
        with pytest.raises(SystemExit):
            main(["--env", "production", "it"])

    def it_has_no_log_flag():  # log levels come from VUK_LOG
        with pytest.raises(SystemExit):
            main(["--log", "fast=debug", "it"])

    def it_runs_doctor(capsys):
        assert main(["doctor"]) == 0
        assert "Python" in capsys.readouterr().out

    def it_explains_a_folder_that_isnt_a_game(capsys, tmp_path):
        assert main(["-C", str(tmp_path), "it"]) == 1
        assert "has no config/ folder" in capsys.readouterr().err

    def it_runs_a_game_with_vuk_it_not_run():
        with pytest.raises(SystemExit):
            main(["run"])

    def it_says_when_a_command_isnt_built_yet(capsys):
        assert main(["hardware", "scan"]) == 2
        assert "isn't built yet" in capsys.readouterr().err


def describe_vuk_it_media_controllers():
    """vuk it starts exactly the media controllers the config asks for."""

    def _started(monkeypatch, capsys, tmp_path, example):
        import os
        from pathlib import Path

        from vukery import cli

        started = []
        monkeypatch.setattr(cli, "_start_media_controllers",
                            lambda game_dir, displays: started.extend(displays) or [])
        read_end, write_end = os.pipe()  # vuk it reads switch names from stdin; send "quit"
        os.write(write_end, b"quit\n")
        os.close(write_end)
        with os.fdopen(read_end) as stdin:
            monkeypatch.setattr("sys.stdin", stdin)
            game = Path(__file__).parents[1] / "examples" / example
            assert cli.main(["-C", str(game), "it", "--log-dir", str(tmp_path)]) == 0
        capsys.readouterr()
        return started

    def it_starts_none_for_a_game_without_displays(monkeypatch, capsys, tmp_path):
        assert _started(monkeypatch, capsys, tmp_path, "basic") == []

    def it_starts_one_per_display(monkeypatch, capsys, tmp_path):
        assert _started(monkeypatch, capsys, tmp_path, "display") == ["main"]
