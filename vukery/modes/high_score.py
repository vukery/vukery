"""High score: when a game ends, players who beat a table enter their initials, and the tables are saved.

An optional built-in mode, as MPF's ``high_score``: list ``high_score`` in
``modes:`` to use it. It holds ``game_ending`` until it's done, so the game
ends after it. For each player who beat an entry in any category, in turn,
they enter initials (flippers choose a letter, start takes it), then each
award is shown.

A game customizes it with a subclass (``modes/high_score/mode.py``):

- ``categories``: player variable → its labels, best first (one entry per label);
- ``defaults``: player variable → the starting table, ``[(name, value), …]``;
- ``enter_initials_seconds``, ``award_seconds``;
- ``look``: ``HighScore.Look(enter_initials=..., award=..., music=...)``.

Or replaces it (a game's own ``high_score`` mode that isn't a subclass).

**Scenes** read what it publishes: ``{high_score.player}``,
``{high_score.award}``, ``{high_score.initials}``, ``{high_score.letter}``
(the one being chosen), ``{high_score.name}``, ``{high_score.value}``, and the
tables as MPF's machine variables do: ``{high_score.score1_name}``,
``{high_score.score1_value}``, ``{high_score.score1_label}``.

**Events** (MPF's): ``high_score_enter_initials`` (player_num, award),
``high_score_award_display`` (player_name, award, value),
``high_score_complete``. The tables are saved in ``data/high_scores.yaml``.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import yaml

from vukery.core.errors import ConfigError
from vukery.core.modes import on
from vukery.media.scenes import Scene, SceneFunction, Text, scene
from vukery.modes.built_in import BuiltInMode

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ "
INITIALS = 3
NO_NAME = "???"   # when the time runs out before any letter is taken


@scene
def high_score_enter_initials() -> Scene:
    return Scene(
        Text("PLAYER {high_score.player}", y=0.8, size=0.12),
        Text("{high_score.award}", y=0.6, size=0.12, color="ffcc00"),
        Text("{high_score.initials}{high_score.letter}", y=0.35, size=0.2),
        Text("{high_score.letter}", x=0.9, y=0.35, size=0.2, color="ff0000").blinks(every=0.3),
    )


@scene
def high_score_award() -> Scene:
    return Scene(
        Text("{high_score.name}", y=0.7, size=0.2, color="00ff00"),
        Text("{high_score.award}", y=0.45, size=0.12, color="ffcc00"),
        Text("{high_score.value:,}", y=0.2, size=0.15),
    )


class Initials:
    """Choosing initials one letter at a time: left and right change the letter, select takes it."""

    def __init__(self) -> None:
        self.taken = ""
        self.index = 0

    @property
    def letter(self) -> str:
        return LETTERS[self.index]

    @property
    def done(self) -> bool:
        return len(self.taken) >= INITIALS

    def left(self) -> None:
        self.index = (self.index - 1) % len(LETTERS)

    def right(self) -> None:
        self.index = (self.index + 1) % len(LETTERS)

    def select(self) -> None:
        if not self.done:
            self.taken += self.letter

    def name(self) -> str:
        return self.taken.strip() or NO_NAME


@dataclass(frozen=True)
class Award:
    player: int
    category: str
    label: str
    value: int


class HighScore(BuiltInMode, built_in=True):
    optional = True
    customizable = frozenset({"categories", "defaults", "enter_initials_seconds", "award_seconds", "look"})
    priority = 500                     # over everything, as in MPF
    start_on = "game_ending"
    game_mode = False                  # it runs as the game ends
    stop_on_ball_end = False

    @dataclass(frozen=True)
    class Look:
        enter_initials: SceneFunction = high_score_enter_initials
        award: SceneFunction = high_score_award
        music: str | None = None       # a sound to play while it runs

    categories: ClassVar[dict[str, list[str]]] = {
        "score": ["GRAND CHAMPION", "HIGH SCORE 1", "HIGH SCORE 2", "HIGH SCORE 3", "HIGH SCORE 4"],
    }
    defaults: ClassVar[dict[str, list[tuple[str, int]]]] = {
        "score": [("VUK", 50_000), ("ERY", 40_000), ("PIN", 30_000), ("BAL", 20_000), ("LZZ", 10_000)],
    }
    enter_initials_seconds: ClassVar[float] = 20
    award_seconds: ClassVar[float] = 4
    look: ClassVar[Look] = Look()

    def __init__(self, machine: Any):
        super().__init__(machine)
        self._check()
        self.tables = self._load()
        self._queue: Any = None
        self._entering: list[int] = []
        self._names: dict[int, str] = {}
        self._awards: list[Award] = []
        self._initials: Initials | None = None
        self._publish_tables()   # for scenes any time, as MPF's machine variables are

    # --- settings

    def _check(self) -> None:
        for category, labels in self.categories.items():
            if not labels:
                raise ConfigError(f"{type(self).__name__}: categories: {category} needs at least one label")
        for category, table in self.defaults.items():
            if category not in self.categories:
                raise ConfigError(f"{type(self).__name__}: defaults: {category} isn't one of the categories")
            if len(table) > len(self.categories[category]):
                raise ConfigError(f"{type(self).__name__}: defaults: {category} has more entries than labels")

    def scene_functions(self) -> tuple[SceneFunction, ...]:
        return (self.look.enter_initials, self.look.award)

    # --- the tables

    @property
    def file(self) -> Path:
        return self.machine.config.game_dir / "data" / "high_scores.yaml"

    def _load(self) -> dict[str, list[tuple[str, int]]]:
        saved: dict[str, Any] = {}
        if self.file.is_file():
            saved = yaml.safe_load(self.file.read_text()) or {}
        tables: dict[str, list[tuple[str, int]]] = {}
        for category, labels in self.categories.items():
            rows = saved.get(category) or self.defaults.get(category, [])
            tables[category] = [(str(name), int(value)) for name, value in rows][: len(labels)]
        return tables

    def _save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        data = {category: [[name, value] for name, value in rows] for category, rows in self.tables.items()}
        self.file.write_text("# vukery's high scores (the high_score mode keeps this file up to date)\n"
                             + yaml.safe_dump(data, sort_keys=False))

    def _publish_tables(self) -> None:
        values: dict[str, Any] = {}
        for category, rows in self.tables.items():
            for i, label in enumerate(self.categories[category], start=1):
                name, value = rows[i - 1] if i <= len(rows) else ("", 0)
                values |= {f"{category}{i}_name": name, f"{category}{i}_value": value, f"{category}{i}_label": label}
        self.publish(**values)

    def awards(self) -> list[Award]:
        """Who beat which entry, best first in each category. A tie doesn't beat an entry."""
        game = self.machine.game
        if game is None:
            return []
        found: list[Award] = []
        for category, labels in self.categories.items():
            rows: list[tuple[int | None, int]] = [(None, value) for _, value in self.tables[category]]
            for player in game.players:
                value = int(player.get(category, 0) or 0)
                if value > 0:
                    rows.append((player.number, value))
            rows.sort(key=lambda row: (-row[1], row[0] is not None))   # on a tie, the table's entry stays ahead
            for rank, (player, value) in enumerate(rows[: len(labels)]):
                if player is not None:
                    found.append(Award(player, category, labels[rank], value))
        return found

    # --- running

    def start(self, **kwargs: Any) -> None:
        self._queue = kwargs.get("queue")   # hold the game's end until we're done
        if self._queue is not None:
            self._queue.wait()
        super().start(**kwargs)

    def mode_start(self, **_: Any) -> None:
        self._awards = self.awards()
        self._entering = sorted({award.player for award in self._awards})
        self._names = {}
        if self.look.music:
            self.play_sound(self.look.music)
        self._next_player()

    def mode_stop(self, **_: Any) -> None:
        if self._queue is not None:
            self._queue.clear()
            self._queue = None

    def _next_player(self) -> None:
        if not self._entering:
            self._record()
            return
        player = self._entering[0]
        self._initials = Initials()
        first = next(a for a in self._awards if a.player == player)
        self.post("high_score_enter_initials", player_num=player, award=first.label)
        self.publish(player=player, award=first.label, initials="", letter=self._initials.letter)
        self.show_scene(self.look.enter_initials)
        self.delay("initials", self.enter_initials_seconds, self._initials_done)

    @on.event("sw_left_flipper")
    def _letter_left(self, **_: Any) -> None:
        if self._initials is not None:
            self._initials.left()
            self.publish(letter=self._initials.letter)

    @on.event("sw_right_flipper")
    def _letter_right(self, **_: Any) -> None:
        if self._initials is not None:
            self._initials.right()
            self.publish(letter=self._initials.letter)

    @on.event("sw_start")
    def _letter_taken(self, **_: Any) -> None:
        if self._initials is None:
            return
        self._initials.select()
        self.publish(initials=self._initials.taken, letter="" if self._initials.done else self._initials.letter)
        if self._initials.done:
            self._initials_done()

    def _initials_done(self) -> None:
        if self._initials is None:
            return
        self.cancel_delay("initials")
        self._names[self._entering.pop(0)] = self._initials.name()
        self._initials = None
        self.remove_scene(self.look.enter_initials)
        self._next_player()

    def _record(self) -> None:
        """Put the awards in the tables, save them, then show each one."""
        for category in self.categories:
            rows: list[tuple[str, int]] = list(self.tables[category])
            for award in (a for a in self._awards if a.category == category):
                rows.append((self._names[award.player], award.value))
            rows.sort(key=lambda row: -row[1])   # a stable sort: older entries stay ahead on a tie
            self.tables[category] = rows[: len(self.categories[category])]
        if self._awards:
            self._save()
        self._publish_tables()
        self._show_awards(list(self._awards))

    def _show_awards(self, left: list[Award]) -> None:
        if not left:
            self.post("high_score_complete")
            self.stop()
            return
        award, rest = left[0], left[1:]
        name = self._names[award.player]
        self.post("high_score_award_display", player_name=name, award=award.label, value=award.value)
        self.publish(name=name, award=award.label, value=award.value)
        self.show_scene(self.look.award)
        self.delay("award", self.award_seconds, lambda: self._show_awards(rest))
