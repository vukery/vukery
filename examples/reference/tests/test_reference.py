"""examples/reference: every config setting vukery supports, and proof of it.

- **It's complete:** each section's settings, as vukery's code lists them,
  must all be in the reference config. A setting added to vukery fails these
  specs until the reference shows it (and a new section, until it's listed
  in SETTINGS below and shown).
- **Every choice is named:** settings with a fixed set of values list them
  in a comment.
- **It loads:** the machine starts and plays with this config, so every
  setting shown is real; the production config (FAST) parses too.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from vukery.core import config as core_config
from vukery.core import log, switches
from vukery.core.config import load_game_config
from vukery.devices import ball_device, ball_save, ball_search
from vukery.devices.coil import CoilConfig
from vukery.devices.light import LightConfig
from vukery.devices.rules import AutofireCoil, Flipper
from vukery.media import dashboard, keyboard, sounds
from vukery.media.server import DisplayConfig
from vukery.platforms.fast import config as fast_config
from vukery.platforms.fast.fast import COIL_PLATFORM_SETTINGS, SWITCH_PLATFORM_SETTINGS
from vukery.testing import GameRig, expect

GAME = Path(__file__).parents[1]
EACH = "*"   # every entry of a section of named entries


def fields(cls: Any) -> set[str]:
    return set(cls.__dataclass_fields__) - {"name"}


# Where each setting lives (a path into the config) → every setting vukery takes there.
SETTINGS: dict[tuple[str, ...], set[str]] = {
    ("switches", EACH): set(switches.SETTINGS),
    ("switches", EACH, "platform_settings"): set(SWITCH_PLATFORM_SETTINGS),
    ("coils", EACH): fields(CoilConfig),
    ("coils", EACH, "platform_settings"): set(COIL_PLATFORM_SETTINGS),
    ("lights", EACH): fields(LightConfig),
    ("ball_devices", EACH): set(ball_device.SETTINGS),
    ("flippers", EACH): set(Flipper.SETTINGS),
    ("autofire_coils", EACH): set(AutofireCoil.SETTINGS),
    ("playfields", "playfield"): set(ball_search.SETTINGS),
    ("ball_saves", EACH): set(ball_save.SETTINGS),
    ("game",): set(core_config.GAME_SETTINGS),
    ("player_vars", EACH): set(core_config.PLAYER_VAR_SETTINGS),
    ("hardware",): set(core_config.HARDWARE_SETTINGS),
    ("media",): set(core_config.MEDIA_SETTINGS),
    ("displays", EACH): set(DisplayConfig.SETTINGS),
    ("sound_system",): set(sounds.SYSTEM_SETTINGS),
    ("sound_system", "tracks", EACH): set(sounds.TRACK_SETTINGS),
    ("sounds", EACH): set(sounds.SOUND_SETTINGS),
    ("sounds", EACH, "ducking"): set(sounds.DUCKING_SETTINGS),
    ("sound_pools", EACH): set(sounds.POOL_SETTINGS),
    ("keyboard", EACH): set(keyboard.SETTINGS),
    ("logging",): set(log.SETTINGS),
    ("dashboard",): set(dashboard.SETTINGS),
    ("fast",): set(fast_config.SETTINGS),
    ("fast", "net"): set(fast_config.NET_SETTINGS),
    ("fast", "net", "io_loop", EACH): set(fast_config.IO_BOARD_SETTINGS),
    ("fast", "rgb"): set(fast_config.RGB_SETTINGS),
}
LISTS = {"modes", "light_groups"}   # sections that are lists, with no settings of their own
SECTION_SETTINGS = {("keyboard",): set(keyboard.SECTION_SETTINGS)}   # a section's own settings beside its entries

# Settings with a fixed set of values → those values, each named in the reference.
CHOICES: dict[str, tuple[str, ...]] = {
    "switch type": ("NO", "NC"),
    "debounce": ("auto", "quick", "normal"),
    "ball_search_failed_action": ball_search.FAILED_ACTIONS,
    "mode_end_action": sounds.MODE_END_ACTIONS,
    "sound pool type": sounds.POOL_TYPES,
    "FAST controller": fast_config.CONTROLLERS,
    "logging level": tuple(log.LEVELS),
}


@pytest.fixture(scope="module")
def merged() -> dict[str, Any]:
    """Everything the reference sets: the shared config with production's on top."""
    return load_game_config(GAME, env="production").data


@pytest.fixture(scope="module")
def text() -> str:
    return "\n".join(path.read_text() for path in sorted((GAME / "config").rglob("*.yaml")))


def entries(data: Any, path: tuple[str, ...]) -> Iterator[dict[str, Any]]:
    """Every mapping at ``path`` (EACH: every entry there)."""
    if not isinstance(data, dict):
        return
    if not path:
        yield data
        return
    head, rest = path[0], path[1:]
    for key in (list(data) if head == EACH else [head]):
        yield from entries(data.get(key), rest)


def shown(merged: dict[str, Any], path: tuple[str, ...]) -> set[str]:
    """The settings the reference uses at ``path``, across all its entries there."""
    parent, last = path[:-1], path[-1]
    own = SECTION_SETTINGS.get(parent, set())   # e.g. keyboard: debug, beside the keys
    used: set[str] = set()
    for found in entries(merged, parent):
        for key, value in found.items():
            if (last == EACH or key == last) and key not in own and isinstance(value, dict):
                used |= set(value)
    return used


def describe_the_reference_config():
    def describe_completeness():
        def it_shows_every_section_vukery_supports(merged):
            listed = {path[0] for path in SETTINGS} | LISTS
            expect(sorted(core_config.SUPPORTED_SECTIONS - listed)).to_equal([])   # new? list it in SETTINGS
            expect(sorted(core_config.SUPPORTED_SECTIONS - set(merged))).to_equal([])

        @pytest.mark.parametrize("path", list(SETTINGS), ids=lambda path: ": ".join(path))
        def it_shows_every_setting(merged, path):
            missing = SETTINGS[path] - shown(merged, path)
            expect(sorted(missing)).to_equal([])

        def it_shows_the_sections_own_settings(merged):
            for (section,), settings in SECTION_SETTINGS.items():
                expect(sorted(settings - set(merged[section]))).to_equal([])

        @pytest.mark.parametrize("setting", list(CHOICES))
        def it_names_every_choice(text, setting):
            missing = [choice for choice in CHOICES[setting] if choice not in text]
            expect(missing).to_equal([])

    def describe_loading():
        def it_starts_and_plays_a_game():
            game = GameRig(GAME)
            try:
                game.start_game()
                game.switch("s_target")
                expect(game.machine.game.player.score).to_equal(1000)
            finally:
                game.stop()

        def it_parses_the_production_hardware(merged):
            fast = fast_config.FastConfig.from_yaml(merged["fast"])
            expect(fast.net is not None and fast.net.board_names_in_order()).to_equal(["io3208", "io0804"])
            expect(core_config.load_game_config(GAME, env="production").platform).to_equal("fast")
