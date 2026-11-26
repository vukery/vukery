"""Game: players, balls and turns, as an async loop with MPF's events.

Ported in structure from MPF's game mode:
https://github.com/missionpinball/mpf/blob/9ef886f4f263db44704f09a87bfd11229036ab5c/mpf/modes/game/code/game.py

Events, in order (``(queue)`` events can be held by any handler)::

    game_will_start → game_starting (queue) → game_started
    per turn:  player_turn_will_start → player_turn_starting (queue) → player_turn_started
    per ball:  ball_will_start → ball_starting (queue) → ball_started
               … the ball drains …
               ball_will_end → ball_ending (queue) → ball_ended
    game_will_end → game_ending (queue) → game_ended

Adding a player: ``player_add_request`` (boolean, can be refused) →
``player_will_add`` → ``player_adding`` (queue) → ``player_added``.
"""

import asyncio
from typing import Any

from vukery.core.modes import Mode, on
from vukery.core.player import Player


class Game(Mode):
    priority = 20
    start_on = "game_start"
    stop_on = "game_ended"
    game_mode = False  # the game itself starts outside a game
    stop_on_ball_end = False

    def __init__(self, machine: Any):
        super().__init__(machine)
        self.players: list[Player] = []
        self._player: Player | None = None
        self.balls_in_play = 0
        self.ending = False
        self._ball_over: asyncio.Event | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def player(self) -> Player | None:
        """The player whose turn it is."""
        return self._player

    @player.setter
    def player(self, value: Player | None) -> None:
        self._player = value

    @property
    def balls_per_game(self) -> int:
        return int(self.machine.config.section("game").get("balls_per_game", 3))

    @property
    def max_players(self) -> int:
        return int(self.machine.config.section("game").get("max_players", 4))

    def mode_start(self, **_: Any) -> None:
        self.players, self.player, self.balls_in_play, self.ending = [], None, 0, False
        self.machine.game = self
        self._ball_over = asyncio.Event()
        self._task = self.machine.create_task(self._run())

    def mode_stop(self, **_: Any) -> None:
        if self.machine.game is self:
            self.machine.game = None

    def _current(self) -> Player:
        if self._player is None:
            raise RuntimeError("The game has no player yet")
        return self._player

    def _ball_over_event(self) -> asyncio.Event:
        if self._ball_over is None:
            self._ball_over = asyncio.Event()
        return self._ball_over

    # --- the loop

    async def _run(self) -> None:
        events = self.machine.events
        await events.post_async("game_will_start")
        await events.post_queue_async("game_starting", game=self)
        await self._add_player()
        await events.post_async("game_started")

        while not self.ending:
            await self._start_turn()
            await self._run_ball()
            while self._current().extra_balls and not self.ending:
                self._current().extra_balls -= 1
                await self._run_ball(extra_ball=True)
            await self._end_turn()
            player = self._current()
            if player.ball >= self.balls_per_game and player.number == len(self.players):
                self.ending = True
            else:
                self._player = self.players[player.number % len(self.players)]

        await events.post_async("game_will_end")
        await events.post_queue_async("game_ending")
        self.machine.modes.stop_game_modes()
        await events.post_async("game_ended")

    async def _start_turn(self) -> None:
        events, player = self.machine.events, self._current()
        await events.post_async("player_turn_will_start", player=player, number=player.number)
        await events.post_queue_async("player_turn_starting", player=player, number=player.number)
        await events.post_async("player_turn_started", player=player, number=player.number)

    async def _end_turn(self) -> None:
        events, player = self.machine.events, self._current()
        await events.post_async("player_turn_will_end", player=player, number=player.number)
        await events.post_queue_async("player_turn_ending", player=player, number=player.number)
        await events.post_async("player_turn_ended", player=player, number=player.number)

    async def _run_ball(self, extra_ball: bool = False) -> None:
        events, player = self.machine.events, self._current()
        if not extra_ball:
            player.ball += 1
        info: dict[str, Any] = {"ball": player.ball, "player": player.number, "is_extra_ball": extra_ball}
        await events.post_async("ball_will_start", **info)
        await events.post_queue_async("ball_starting", **info)
        ball_over = self._ball_over_event()
        ball_over.clear()
        trough = self.machine.trough()
        if trough and trough.eject():
            self.balls_in_play = 1
        await events.post_async("ball_started", **info)
        if len(self.players) == 1:
            await events.post_async("single_player_ball_started")
        else:
            await events.post_async("multi_player_ball_started")

        await ball_over.wait()

        await events.post_async("ball_will_end")
        await events.post_queue_async("ball_ending")
        self.machine.modes.stop_for_ball_end()
        await events.post_async("ball_ended")

    # --- reacting to the playfield

    @on.event("ball_drain", priority=-1000)  # after anything (like a ball save) that changes `balls`
    def ball_drained(self, balls: int = 0, **_: Any) -> None:
        if balls <= 0 or self.balls_in_play <= 0:
            return
        self.balls_in_play = max(self.balls_in_play - balls, 0)
        if self.balls_in_play == 0:
            self.end_ball()

    def end_ball(self) -> None:
        """End the current ball now (e.g. after a tilt)."""
        self.balls_in_play = 0
        if self._ball_over:
            self._ball_over.set()

    # --- players

    @on.event("sw_start")
    def start_pressed(self, **_: Any) -> None:
        """During the first ball, the start button adds a player (MPF's add_player_switch_tag)."""
        if self.player and self.player.ball <= 1 and len(self.players) < self.max_players:
            self.events.post_boolean("player_add_request", callback=self._player_add_allowed)

    def _player_add_allowed(self, ev_result: bool = True, **_: Any) -> None:
        if ev_result:
            self.machine.create_task(self._add_player())

    def _initial_player_vars(self) -> dict[str, Any]:
        """From ``player_vars:`` (MPF: ``initial_value`` per variable)."""
        initial: dict[str, Any] = {}
        for name, spec in self.machine.config.section("player_vars").items():
            match spec:
                case {"initial_value": value}:
                    initial[str(name)] = value
                case dict():
                    initial[str(name)] = 0
                case value:
                    initial[str(name)] = value
        return initial

    async def _add_player(self) -> None:
        events = self.machine.events
        number = len(self.players) + 1
        await events.post_async("player_will_add", number=number)
        player = Player(events, number, self._initial_player_vars())
        self.players.append(player)
        if self.player is None:
            self.player = player
        await events.post_queue_async("player_adding", player=player, number=number)
        await events.post_async("player_added", player=player, num=number, number=number)
