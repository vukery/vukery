"""Built-in modes: what vukery ships, and the only ways a game may change it.

A built-in mode declares what a game can change (``customizable``): settings
(class attributes), its look (scenes, sounds, shows for each moment) and a
few hooks (methods with a fixed signature that return a decision). A game
changes those in a subclass, in ``modes/<name>/mode.py``, and lists the mode
in ``modes:`` as usual::

    from vukery.modes import HighScore

    class CombatHighScore(HighScore):      # still the "high_score" mode
        enter_initials_seconds = 45

Anything else is refused as the class is defined, with a list of what can
change: overriding ``mode_start``, a private method, or adding an ``@on``
handler. Extra behavior goes in a mode of the game's own, reacting to the
built-in mode's events.

**Optional** built-in modes (high score, replay, match…) can also be
replaced outright: a mode of the game's own with the same name, not a
subclass, runs instead. **Core** ones (attract, game) can't.
"""

from typing import Any, ClassVar

from vukery.core.errors import ConfigError
from vukery.core.modes import Mode

ALWAYS_ALLOWED = {"__module__", "__qualname__", "__doc__", "__annotations__", "__firstlineno__",
                  "__static_attributes__", "__dict__", "__weakref__", "__annotate_func__", "__annotate__",
                  "__classdictcell__", "__orig_bases__", "__parameters__", "name"}


class BuiltInMode(Mode):
    """Base class for vukery's own modes. ``built_in=True`` marks vukery's classes."""

    customizable: ClassVar[frozenset[str]] = frozenset()
    optional: ClassVar[bool] = False
    built_in_class: ClassVar[type[BuiltInMode]]   # the vukery class a game's subclass customizes

    def __init_subclass__(cls, built_in: bool = False, **kwargs: Any) -> None:
        if built_in:
            super().__init_subclass__(**kwargs)
            cls.built_in_class = cls
            return
        base = cls.built_in_class
        cls.name = base.name   # a customization is still the built-in mode, by its name
        super().__init_subclass__(**kwargs)
        refused = sorted(attribute for attribute, value in cls.__dict__.items()
                         if attribute not in ALWAYS_ALLOWED and attribute not in base.customizable
                         and (_overrides(cls, attribute) or getattr(value, "_vukery_hooks", None)))
        if refused:
            raise ConfigError(_refusal(cls, base, refused))


def _overrides(cls: type, attribute: str) -> bool:
    return any(attribute in vars(parent) for parent in cls.__mro__[1:])


def _refusal(cls: type, base: type[BuiltInMode], refused: list[str]) -> str:
    can = ", ".join(sorted(base.customizable)) or "nothing yet"
    message = (f"{cls.__name__} customizes vukery's {base.name} mode, which can change only: {can}. "
               f"It can't change: {', '.join(refused)}. For more, react to the mode's events in a mode of your own")
    if base.optional:
        message += f", or replace it: a mode named {base.name} that isn't a subclass of {base.__name__} runs instead"
    return message + "."


def resolve(built_in: type[BuiltInMode], game_class: type[Mode]) -> type[Mode]:
    """What runs as a built-in mode when the game has a mode of the same name."""
    if issubclass(game_class, built_in):
        return game_class   # customized
    if built_in.optional:
        return game_class   # replaced
    raise ConfigError(f"modes: {built_in.name} is vukery's {built_in.__name__}, which a game can't replace. "
                      f"Customize it with a subclass of vukery.modes.{built_in.__name__} "
                      f"(it can change: {', '.join(sorted(built_in.customizable)) or 'nothing yet'}).")
