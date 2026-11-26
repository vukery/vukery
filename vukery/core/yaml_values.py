"""Small, typed readers for values that come from YAML config."""

from typing import Any, cast

from vukery.core.errors import ConfigError


def names(value: Any, where: str = "") -> tuple[str, ...]:
    """A name, a comma-separated string of names, or a list of names (MPF accepts all three)."""
    match value:
        case None:
            return ()
        case str():
            return tuple(part.strip() for part in value.split(",") if part.strip())
        case list() | tuple():
            return tuple(str(part) for part in cast(list[Any], value))
        case _:
            raise ConfigError(f"{where}: expected a name or a list of names, got {value!r}")


def mapping(value: Any, where: str = "") -> dict[str, Any]:
    """A YAML mapping (or nothing, as an empty one)."""
    match value:
        case None:
            return {}
        case dict():
            return {str(key): item for key, item in cast(dict[Any, Any], value).items()}
        case _:
            raise ConfigError(f"{where}: expected a mapping, got {value!r}")
