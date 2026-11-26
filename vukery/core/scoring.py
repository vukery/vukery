"""Scoring tables: what a mode scores, written as data on the mode class.

The Python equivalent of MPF's ``variable_player``::

    class Base(Mode):
        scoring = {
            "s_target": 1000,                                   # a switch
            "sw_pops": 100,                                      # a switch tag event
            "ramp_made": 2500,                                   # any event
            "s_spinner": lambda mode: 50 * mode.player.spins_lit,
            "s_hole": Score(5000, block=True),                   # MPF's |block
            "s_lane": Award(lanes=1),                            # another player variable
        }

A value is points (an ``int``), a function of the mode that returns points,
a ``Score`` or an ``Award``. Points pass through every running mode's
``adjust_score()`` (multipliers and the like). ``Award`` variables don't.

Blocking is per variable, as in MPF: ``Score(..., block=True)`` stops
lower-priority modes from scoring that switch or event, but their other
handlers (sounds, lights) still run, and their ``Award`` entries for other
variables still count.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vukery.core.modes import Mode

Amount = int | Callable[["Mode"], int]
Condition = bool | Callable[["Mode"], bool]


def facility(variable: str) -> str:
    """The blocking facility for scoring one player variable."""
    return f"score:{variable}"


@dataclass(frozen=True)
class Score:
    """Points for the player's ``score``. ``block``: stop lower-priority modes scoring this too."""

    points: Amount
    block: Condition = False


class Award:
    """Add to other player variables: ``Award(lanes=1)``, ``Award(ramps=1, block=True)``."""

    def __init__(self, block: Condition = False, **variables: Amount):
        if not variables:
            raise ValueError("Award needs at least one variable, e.g. Award(lanes=1)")
        if "score" in variables:
            raise ValueError("Use Score(...) (or a plain number) for the score")
        self.variables = variables
        self.block = block

    def __repr__(self) -> str:
        return f"Award({', '.join(f'{k}={v!r}' for k, v in self.variables.items())}, block={self.block!r})"


Entry = int | Callable[["Mode"], int] | Score | Award


def resolve(value: Any, mode: Mode) -> Any:
    """A number or condition from a table entry: call it with the mode if it's a function."""
    return value(mode) if callable(value) else value


def entries(value: Entry) -> list[tuple[str, Amount, Condition]]:
    """(variable, amount, block) for each variable an entry changes."""
    match value:
        case Score(points=points, block=block):
            return [("score", points, block)]
        case Award():
            return [(name, amount, value.block) for name, amount in value.variables.items()]
        case bool():
            raise TypeError(f"Not a scoring value: {value!r}")
        case int():
            return [("score", value, False)]
        case _ if callable(value):
            return [("score", value, False)]
        case _:
            raise TypeError(f"Not a scoring value: {value!r} (use points, a function, Score(...) or Award(...))")
