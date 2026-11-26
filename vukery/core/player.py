"""Players and their variables.

Setting a player variable posts ``player_<name>`` with ``value``,
``prev_value``, ``change`` and ``player_num``, as in MPF, so scenes, sounds
and other modes can react to it.
"""

from typing import Any

from vukery.core.events import EventManager

STANDARD_VARS = {"score": 0, "ball": 0, "extra_balls": 0}


class Player:
    """One player in a game. Variables are plain attributes: ``player.score += 100``."""

    def __init__(self, events: EventManager, number: int, initial: dict[str, Any] | None = None):
        object.__setattr__(self, "_events", events)
        object.__setattr__(self, "number", number)
        object.__setattr__(self, "_vars", {**STANDARD_VARS, **(initial or {})})

    def __getattr__(self, name: str) -> Any:
        vars_: dict[str, Any] = object.__getattribute__(self, "_vars")
        if name in vars_:
            return vars_[name]
        raise AttributeError(f"Player {self.number} has no variable {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        vars_: dict[str, Any] = self._vars
        previous = vars_.get(name)
        vars_[name] = value
        if previous == value:
            return
        match previous, value:
            case int() | float(), int() | float() if not isinstance(value, bool):
                change: Any = value - previous
            case _:
                change = True
        self._events.post(f"player_{name}", value=value, prev_value=previous, change=change,
                          player_num=self.number)

    def get(self, name: str, default: Any = None) -> Any:
        return self._vars.get(name, default)

    @property
    def vars(self) -> dict[str, Any]:
        """A copy of every variable."""
        return dict(self._vars)

    def __repr__(self) -> str:
        return f"<Player {self.number} score={self._vars.get('score')}>"
