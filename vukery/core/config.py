"""Loading a game's config: ``config/*.yaml``, then the environment's files on top.

    config/
      machine.yaml          shared by every environment (any number of .yaml files)
      environments/
        development.yaml    or a folder: development/*.yaml
        test.yaml
        production.yaml

Shared files load in alphabetical order, then the environment's file (or
every file in its folder, alphabetically) is deep-merged on top: the later
value wins wherever both define something.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from vukery.core.errors import ConfigError
from vukery.core.yaml_values import mapping, names

ENVIRONMENTS = ("development", "test", "production")
DEFAULT_ENVIRONMENT = "development"

SUPPORTED_SECTIONS = {
    "hardware", "fast", "switches", "coils", "lights", "ball_devices", "flippers", "autofire_coils",
    "game", "modes", "player_vars", "logging", "displays", "media", "dashboard", "light_groups",
    "sound_system", "sounds", "sound_pools", "keyboard",
}

# MPF sections that hold game logic. In vukery that's Python, in a mode.
GAME_LOGIC_SECTIONS = {
    "variable_player", "event_player", "queue_event_player", "queue_relay_player", "random_event_player",
    "show_player", "light_player", "coil_player", "slide_player", "widget_player", "sound_player",
    "track_player", "segment_display_player", "blinkenlight_player", "score_queue_player", "custom_code",
}


def environment() -> str:
    """The environment to run in: ``VUK_ENV``, or ``development``."""
    env = os.environ.get("VUK_ENV", DEFAULT_ENVIRONMENT).strip() or DEFAULT_ENVIRONMENT
    if env not in ENVIRONMENTS:
        raise ConfigError(f"VUK_ENV must be one of {', '.join(ENVIRONMENTS)}, got {env!r}")
    return env


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        old = merged.get(key)
        if isinstance(old, dict) and isinstance(value, dict):
            merged[key] = deep_merge(mapping(old), mapping(value))
        else:
            merged[key] = value
    return merged


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data: Any = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: {e}") from e
    return mapping(data, str(path))


@dataclass(frozen=True)
class GameConfig:
    """A game's merged config."""

    game_dir: Path
    environment: str
    data: dict[str, Any]

    def section(self, name: str) -> dict[str, Any]:
        return mapping(self.data.get(name), name)

    @property
    def platform(self) -> str:
        """``hardware: platform:``, defaulting to the environment's simulated platform."""
        configured: Any = self.section("hardware").get("platform")
        match configured, self.environment:
            case None, "production":
                raise ConfigError("production needs hardware: platform: (e.g. fast) in "
                                  "config/environments/production.yaml")
            case None, env:
                return env
            case str() as name, _:
                return name
            case other, _:
                raise ConfigError(f"hardware: platform: expected a name, got {other!r}")

    @property
    def modes(self) -> list[str]:
        return list(names(self.data.get("modes"), "modes"))


def load_game_config(game_dir: Path, env: str | None = None) -> GameConfig:
    env = env or environment()
    game_dir = game_dir.resolve()   # absolute: media controllers open its files from other folders
    config_dir = game_dir / "config"
    if not config_dir.is_dir():
        raise ConfigError(f"{game_dir} has no config/ folder. Is this a vukery game?")

    data: dict[str, Any] = {}
    for path in sorted(config_dir.glob("*.yaml")):
        data = deep_merge(data, _load_yaml(path))

    env_dir = config_dir / "environments"
    env_file = env_dir / f"{env}.yaml"
    env_folder = env_dir / env
    match env_file.is_file(), env_folder.is_dir():
        case True, True:
            raise ConfigError(f"Use either {env_file} or {env_folder}/, not both")
        case True, False:
            data = deep_merge(data, _load_yaml(env_file))
        case False, True:
            for path in sorted(env_folder.glob("*.yaml")):
                data = deep_merge(data, _load_yaml(path))
        case _:
            pass

    logic = sorted(set(data) & GAME_LOGIC_SECTIONS)
    if logic:
        raise ConfigError(
            f"{', '.join(logic)}: that's game logic, which vukery writes in Python, in a mode. "
            "See the Modes page of the docs.")
    unknown = sorted(set(data) - SUPPORTED_SECTIONS)
    if unknown:
        raise ConfigError(f"Config sections vukery doesn't support (yet): {', '.join(unknown)}")
    return GameConfig(game_dir=game_dir, environment=env, data=data)
