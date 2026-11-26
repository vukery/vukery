"""The vuk command."""

import pytest

from vukery.cli import main


def describe_vuk():
    def it_prints_help_without_a_command(capsys):
        assert main([]) == 0
        assert "usage: vuk" in capsys.readouterr().out

    def it_has_no_env_flag():  # the environment comes from VUK_ENV
        with pytest.raises(SystemExit):
            main(["--env", "production", "run"])

    def it_has_no_log_flag():  # log levels come from VUK_LOG
        with pytest.raises(SystemExit):
            main(["--log", "fast=debug", "run"])

    def it_runs_doctor(capsys):
        assert main(["doctor"]) == 0
        assert "Python" in capsys.readouterr().out

    def it_explains_a_folder_that_isnt_a_game(capsys, tmp_path):
        assert main(["-C", str(tmp_path), "run"]) == 1
        assert "has no config/ folder" in capsys.readouterr().err

    def it_says_when_a_command_isnt_built_yet(capsys):
        assert main(["hardware", "scan"]) == 2
        assert "isn't built yet" in capsys.readouterr().err
