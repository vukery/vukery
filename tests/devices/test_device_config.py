"""What flippers, autofire coils and ball devices don't support yet, and say so."""

import pytest

from tests.helpers import basic_machine
from vukery.core.errors import ConfigError
from vukery.testing import GameRig


def _with(section, name, entry):
    def edit(config):
        config[section][name] = entry

    return edit


@pytest.mark.parametrize(("section", "name", "entry", "message"), [
    ("flippers", "left_flipper", {"main_coil": "c_left_flipper", "activation_switch": "s_left_flipper",
                                  "hold_coil": "c_right_flipper"}, "hold_coil isn't supported yet"),
    ("flippers", "left_flipper", {"main_coil": "c_left_flipper", "activation_switch": "s_left_flipper",
                                  "power_setting_name": "x"}, "not supported yet: power_setting_name"),
    ("autofire_coils", "left_sling", {"coil": "c_left_sling", "switch": "s_left_sling", "playfield": "pf"},
     "not supported yet: playfield"),
    ("ball_devices", "bd_trough", {"ball_switches": "s_trough1", "eject_timeouts": "1s", "tags": "trough"},
     "not supported yet: eject_timeouts"),
    ("ball_devices", "bd_trough", {"tags": "trough"}, "needs ball_switches"),
])
def it_names_settings_it_doesnt_support_yet(tmp_path, section, name, entry, message):
    with pytest.raises(ConfigError, match=message):
        GameRig(basic_machine(tmp_path, edit=_with(section, name, entry)))
