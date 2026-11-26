"""Shows: lights, coils and events over time, as YAML files in the folder of the mode they belong to.

``modes/flash_score/bumper_flash.yaml`` is the show ``flash_score.bumper_flash``.
Its own mode plays it as ``bumper_flash``; any other mode by the full name.

A show file is one of two things:

**Frames** over lights or light groups (one row a frame, one column a light)::

    every: 0.1s
    lights: bumper1_ring          # a group, a light, or a list of them: the columns, in order
    colors: {X: (color)}          # a letter's color; (color) is a token, filled in when played
    frames: |
      X.X.X.X.X.X.X.X.X.X.X.X.
      .X.X.X.X.X.X.X.X.X.X.X.X

  ``.`` is off, ``-`` leaves the light alone, and spaces are ignored (use
  them to line columns up).

**Steps**, MPF's own show format (a list), for coils, events and anything
timed by hand::

    - time: 0
      coils: c_chime1
    - time: +0.25s
      coils: c_chime3
      events: match_chimed

  A step has ``time`` (absolute, or ``+`` relative to the step before) or
  ``duration`` (``-1`` holds until the show is stopped), and any of
  ``lights``, ``coils`` and ``events``. Lights take a color (``ff8800``),
  ``on``, ``off``, or ``{color: ..., fade: 200ms}``.

Tokens: ``(name)`` anywhere in the file is replaced by ``show_tokens`` when
the show plays, in names (``(lights): on``) and in values (``(color)``).

Playing follows MPF's ``show_player``: priority (added to the mode's),
speed, loops (``-1`` forever), start step, pause, resume, advance, and
``events_when_played/stopped/looped/completed``. A show keeps its lights on
each light's stack under its own key, so stopping it shows what was
underneath. A mode's shows stop when the mode stops.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import count
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml

from vukery.core.errors import ConfigError
from vukery.core.yaml_values import mapping, names

if TYPE_CHECKING:
    from vukery.core.machine import Machine
    from vukery.core.modes import Mode

TOKEN = re.compile(r"\(([A-Za-z_][A-Za-z0-9_]*)\)")
STEP_KEYS = {"time", "duration", "lights", "coils", "events"}
FRAME_KEYS = {"every", "lights", "colors", "frames"}
LATER = {"sounds", "slides", "widgets", "shows", "show_tokens", "light_player", "leds"}
OFF = "off"
UNCHANGED = "-"


def seconds(value: Any, where: str) -> float:
    """``0.5``, ``"500ms"``, ``"0.5s"`` or ``"+0.5s"`` (the ``+`` is for relative times) as seconds."""
    match value:
        case bool():
            raise ConfigError(f"{where}: expected a time, got {value!r}")
        case int() | float():
            return float(value)
        case str() as text:
            text = text.strip().lstrip("+")
            try:
                if text.endswith("ms"):
                    return float(text[:-2]) / 1000
                return float(text.removesuffix("s"))
            except ValueError:
                raise ConfigError(f"{where}: {value!r} isn't a time (e.g. 0.5, 500ms or 0.5s)") from None
        case _:
            raise ConfigError(f"{where}: expected a time, got {value!r}")


@dataclass(frozen=True)
class LightChange:
    target: str | int  # a light or a light group; in a frame, the column's number
    color: Any         # "on", "off", a color, or (r, g, b)
    fade_ms: int | None = None


@dataclass(frozen=True)
class Step:
    duration: float   # seconds; -1 holds until the show is stopped or advanced
    lights: tuple[LightChange, ...] = ()
    coils: tuple[tuple[str, str], ...] = ()   # (coil, "pulse" / "enable" / "disable")
    events: tuple[str, ...] = ()
    columns: tuple[str, ...] = ()   # a frame: the lights and groups its columns are, in order
    width: int = 0                  # a frame: how many columns its row has


def _replace(data: Any, tokens: Mapping[str, Any]) -> Any:
    """``data`` with every ``(token)`` replaced, in keys and values."""
    match data:
        case str() as text:
            whole = TOKEN.fullmatch(text)
            if whole and whole.group(1) in tokens:
                return tokens[whole.group(1)]  # a whole-value token keeps its type (e.g. a list)
            return TOKEN.sub(lambda m: str(tokens.get(m.group(1), m.group(0))), text)
        case dict():
            return {_replace(k, tokens): _replace(v, tokens) for k, v in cast(dict[Any, Any], data).items()}
        case list():
            return [_replace(v, tokens) for v in cast(list[Any], data)]
        case _:
            return data


def _tokens_in(data: Any) -> set[str]:
    match data:
        case str():
            return set(TOKEN.findall(data))
        case dict():
            found: set[str] = set()
            for k, v in cast(dict[Any, Any], data).items():
                found |= _tokens_in(k) | _tokens_in(v)
            return found
        case list():
            found = set[str]()
            for v in cast(list[Any], data):
                found |= _tokens_in(v)
            return found
        case _:
            return set()


class Show:
    """A show loaded from a file; ``steps()`` makes the steps for a set of token values."""

    def __init__(self, name: str, data: Any):
        self.name = name
        self.data = data
        self.tokens = _tokens_in(data)
        self._cache: dict[str, tuple[Step, ...]] = {}
        if not isinstance(data, (list, dict)) or not data:
            raise ConfigError(f"show {name}: expected frames (every, lights, colors, frames) or a list of steps")

    @classmethod
    def load(cls, name: str, path: Path) -> Show:
        try:
            return cls(name, yaml.safe_load(path.read_text()))
        except yaml.YAMLError as e:
            raise ConfigError(f"{path}: {e}") from e

    def steps(self, tokens: Mapping[str, Any] | None = None) -> tuple[Step, ...]:
        tokens = dict(tokens or {})
        if unknown := sorted(set(tokens) - self.tokens):
            raise ConfigError(f"show {self.name}: no token named {', '.join(unknown)} "
                              f"(its tokens: {', '.join(sorted(self.tokens)) or 'none'})")
        cache_key = repr(sorted(tokens.items()))
        if cache_key not in self._cache:
            data = _replace(self.data, tokens)
            self._cache[cache_key] = (self._frames(mapping(data)) if isinstance(data, dict)
                                      else self._steps(cast(list[Any], data)))
        return self._cache[cache_key]

    # --- the frames form

    def _frames(self, data: dict[str, Any]) -> tuple[Step, ...]:
        where = f"show {self.name}"
        if unknown := sorted(set(data) - FRAME_KEYS):
            raise ConfigError(f"{where}: frames take every, lights, colors and frames, not {', '.join(unknown)}")
        every = seconds(data.get("every", 0.1), f"{where}: every")
        columns = list(names(data.get("lights"), f"{where}: lights"))
        if not columns:
            raise ConfigError(f"{where}: lights: give the lights or light groups the columns are")
        colors = mapping(data.get("colors"), f"{where}: colors")
        rows = [line.replace(" ", "") for line in str(data.get("frames") or "").splitlines() if line.strip()]
        if not rows:
            raise ConfigError(f"{where}: frames: give at least one row")
        return tuple(Step(every, self._row(row, n, colors), columns=tuple(columns), width=len(row))
                     for n, row in enumerate(rows, start=1))

    def _row(self, row: str, n: int, colors: dict[str, Any]) -> tuple[LightChange, ...]:
        """One frame. Columns are numbered here; a group stands for its lights, so the
        real lights (and the row's width) are matched up once groups are known."""
        changes: list[LightChange] = []
        for column, mark in enumerate(row):
            match mark:
                case ".":
                    changes.append(LightChange(column, OFF))
                case "-":
                    pass
                case letter if letter in colors:
                    changes.append(LightChange(column, colors[letter]))
                case letter:
                    raise ConfigError(f"show {self.name}: frame {n}: {letter!r} has no color in colors:")
        return tuple(changes)

    # --- MPF's steps form

    def _steps(self, data: list[Any]) -> tuple[Step, ...]:
        steps: list[Step] = []
        total = 0.0
        if isinstance(data[0], dict) and "time" in data[0] and seconds(data[0]["time"], "") != 0:
            first = seconds(data[0]["time"], f"show {self.name}: step 1")
            steps.append(Step(first))
            total = first
        for i, raw in enumerate(data):
            where = f"show {self.name}: step {i + 1}"
            if not isinstance(raw, dict):
                raise ConfigError(f"{where}: a step is a mapping (time or duration, lights, coils, events)")
            step = cast(dict[str, Any], raw)
            if later := sorted(set(step) & LATER):
                raise ConfigError(f"{where}: {', '.join(later)} in shows isn't supported yet")
            if unknown := sorted(set(step) - STEP_KEYS):
                raise ConfigError(f"{where}: unknown section(s): {', '.join(unknown)}")
            duration = self._duration(data, i, total, where)
            if duration is None:
                break  # an empty last step only marks where the show ends (MPF)
            total = -1 if duration < 0 or total < 0 else total + duration
            steps.append(Step(duration, self._lights(step.get("lights"), where), self._coils(step.get("coils"), where),
                              names(step.get("events"), f"{where}: events")))
        return tuple(steps)

    @staticmethod
    def _duration(data: list[Any], i: int, total: float, where: str) -> float | None:
        """MPF's rules: a step lasts its ``duration``, or until the next step's ``time``, or 1 second."""
        step = data[i]
        following = data[i + 1] if i + 1 < len(data) and isinstance(data[i + 1], dict) else None
        if "duration" in step:
            if following is not None and "time" in following:
                raise ConfigError(f"{where}: has a duration, and the next step a time: use one or the other")
            return seconds(step["duration"], f"{where}: duration")
        if following is not None and "time" in following:
            next_time = following["time"]
            if str(next_time).startswith("+"):
                return seconds(next_time, where)
            if total < 0:
                raise ConfigError(f"{where}: an absolute time can't follow a step that holds (duration -1)")
            return seconds(next_time, where) - total
        if following is None and set(step) == {"time"} and i > 0:
            return None
        return 1.0

    @staticmethod
    def _lights(value: Any, where: str) -> tuple[LightChange, ...]:
        changes: list[LightChange] = []
        for target, setting in mapping(value, f"{where}: lights").items():
            match setting:
                case {"color": color, **rest}:
                    fade = rest.get("fade")
                    changes.append(LightChange(target, color, None if fade is None
                                               else round(seconds(fade, f"{where}: {target}: fade") * 1000)))
                case True:
                    changes.append(LightChange(target, "on"))
                case False | 0:
                    changes.append(LightChange(target, OFF))
                case _:
                    changes.append(LightChange(target, setting))
        return tuple(changes)

    @staticmethod
    def _coils(value: Any, where: str) -> tuple[tuple[str, str], ...]:
        match value:
            case None:
                return ()
            case dict():
                result: list[tuple[str, str]] = []
                for coil, setting in cast(dict[str, Any], value).items():
                    action = str(mapping(setting).get("action", "pulse"))
                    action = {"on": "enable", "off": "disable"}.get(action, action)
                    if action not in ("pulse", "enable", "disable"):
                        raise ConfigError(f"{where}: coils: {coil}: action is pulse, enable or disable")
                    result.append((str(coil), action))
                return tuple(result)
            case _:
                return tuple((coil, "pulse") for coil in names(value, f"{where}: coils"))


# MPF's built-in shows, by the same names. Tokens: ``lights`` (a light or a group), ``color``.
BUILT_IN: dict[str, list[dict[str, Any]]] = {
    "on": [{"duration": -1, "lights": {"(lights)": "on"}}],
    "off": [{"duration": -1, "lights": {"(lights)": "off"}}],
    "led_color": [{"duration": -1, "lights": {"(lights)": "(color)"}}],
    "flash": [{"duration": 1, "lights": {"(lights)": "on"}}, {"duration": 1, "lights": {"(lights)": "off"}}],
    "flash_color": [{"duration": 1, "lights": {"(lights)": "(color)"}},
                    {"duration": 1, "lights": {"(lights)": "off"}}],
}


# --- playing


class RunningShow:
    """A show that's playing (MPF: RunningShow)."""

    def __init__(self, shows: Shows, show: Show, steps: tuple[Step, ...], key: str, priority: int, speed: float,
                 loops: int, start_step: int, events: Mapping[str, tuple[str, ...]],
                 on_stop: Callable[[RunningShow], None]):
        self.shows, self.machine = shows, shows.machine
        self.show, self.steps, self.key = show, steps, key
        self.priority, self.speed, self.loops = priority, speed, loops
        self.events = events
        self.on_stop = on_stop
        self.context = f"show:{show.name}:{next(shows.ids)}"   # the key its lights use on the stack
        self.stopped = False
        self.paused = False
        self._timer: Any = None
        self._lit: set[str] = set()
        self.next_index = (start_step - 1) if start_step > 0 else start_step % len(steps)
        self.current_index: int | None = None
        self._run_next(self.events.get("played", ()))

    def __repr__(self) -> str:
        return f"<RunningShow {self.show.name} step {(self.current_index or 0) + 1}/{len(self.steps)}>"

    def stop(self) -> None:
        if self.stopped:
            return
        self.stopped = True
        self._cancel()
        for light in self._lit:
            self.machine.lights[light].remove(self.context)
        self._lit.clear()
        self.on_stop(self)
        self._post(self.events.get("stopped", ()))

    def pause(self) -> None:
        self.paused = True
        self._cancel()

    def resume(self) -> None:
        if self.paused and not self.stopped:
            self.paused = False
            self._run_next()

    def advance(self, steps: int = 1) -> None:
        """Go to the next step now (MPF: advance); with ``steps``, skip ahead."""
        if self.stopped:
            return
        self._cancel()
        self.next_index += steps - 1
        self._run_next()

    def _cancel(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _post(self, events: tuple[str, ...]) -> None:
        for event in events:
            self.machine.events.post(event)

    def _run_next(self, events: tuple[str, ...] = ()) -> None:
        self._timer = None
        pending = list(events)
        if self.next_index >= len(self.steps):
            if self.loops == 0:
                self.stop()
                self._post((*pending, *self.events.get("completed", ())))
                return
            self.loops -= 1 if self.loops > 0 else 0
            self.next_index = 0
            pending += self.events.get("looped", ())
        self.current_index = self.next_index
        step = self.steps[self.current_index]
        self._apply(step)
        self._post(tuple(pending))
        self.next_index += 1
        if step.duration >= 0 and not self.paused and not self.stopped:
            self._timer = self.machine.clock.call_later(step.duration / self.speed, self._run_next)

    def _apply(self, step: Step) -> None:
        for change in step.lights:
            for light in self.shows.lights_for(str(change.target)):
                if change.color == OFF:
                    light.color((0, 0, 0), change.fade_ms, self.priority, self.context)
                elif change.color == "on":
                    light.on(change.fade_ms, self.priority, self.context)
                else:
                    light.color(change.color, change.fade_ms, self.priority, self.context)
                self._lit.add(light.name)
        for coil, action in step.coils:
            getattr(self.machine.coils[coil], action)()
        for event in step.events:
            self.machine.events.post(event)


class Shows:
    """The machine's shows, from every mode's folder, and the ones playing."""

    def __init__(self, machine: Machine):
        self.machine = machine
        self.shows: dict[str, Show] = {name: Show(name, data) for name, data in BUILT_IN.items()}
        self.playing: dict[tuple[str, str], RunningShow] = {}   # (mode, key) -> show
        self.ids = count(1)

    def load(self, game_dir: Path, modes: list[str]) -> None:
        """Every ``.yaml`` file in a mode's folder is a show, named ``<mode>.<file name>``."""
        for mode in modes:
            folder = game_dir / "modes" / mode
            for path in sorted(folder.glob("*.yaml")):
                show = Show.load(f"{mode}.{path.stem}", path)
                self.check(show)
                self.shows[show.name] = show

    def check(self, show: Show) -> None:
        """Check everything that doesn't depend on tokens: lights, coils, frame widths."""
        steps = show.steps({token: f"({token})" for token in show.tokens})
        for step in steps:
            for change in step.lights:
                if isinstance(change.target, str) and "(" not in change.target:
                    self.lights_for(change.target)
            if step.columns and not any("(" in column for column in step.columns):
                self._columns(show, step, 1)
            for coil, _ in step.coils:
                if "(" not in coil and coil not in self.machine.coils:
                    raise ConfigError(f"show {show.name}: no coil named {coil!r}")

    def find(self, name: str, mode: str | None = None) -> Show:
        for candidate in ((f"{mode}.{name}",) if mode and "." not in name else ()) + (name,):
            if candidate in self.shows:
                return self.shows[candidate]
        raise ConfigError(f"No show named {name!r}" + (f" in mode {mode} or anywhere else" if mode else "")
                          + f" (shows: {', '.join(sorted(self.shows)) or 'none'})")

    def lights_for(self, target: str) -> list[Any]:
        if target in self.machine.lights:
            return [self.machine.lights[target]]
        if target in self.machine.light_groups:
            return list(self.machine.light_groups[target])
        raise ConfigError(f"No light or light group named {target!r}")

    def play(self, name: str, mode: Mode, *, priority: int = 0, speed: float = 1.0, loops: int = -1,
             start_step: int = 1, show_tokens: Mapping[str, Any] | None = None, key: str | None = None,
             events_when_played: tuple[str, ...] = (), events_when_stopped: tuple[str, ...] = (),
             events_when_looped: tuple[str, ...] = (), events_when_completed: tuple[str, ...] = ()) -> RunningShow:
        show = self.find(name, mode.name)
        steps = self._expanded(show, show.steps(show_tokens))
        key = key or show.name
        self.stop(mode.name, key)  # the same key replaces what's playing under it (MPF)
        if speed <= 0:
            raise ValueError(f"show {show.name}: speed must be above 0, got {speed}")
        running = RunningShow(
            self, show, steps, key, mode.priority + priority, speed, loops, start_step,
            {"played": events_when_played, "stopped": events_when_stopped, "looped": events_when_looped,
             "completed": events_when_completed},
            on_stop=lambda r: self._forget(mode.name, r))
        if not running.stopped:
            self.playing[(mode.name, key)] = running
        return running

    def _forget(self, mode: str, running: RunningShow) -> None:
        if self.playing.get((mode, running.key)) is running:
            del self.playing[(mode, running.key)]

    def stop(self, mode: str, key: str | None = None) -> None:
        """Stop one of a mode's shows (by key), or all of them."""
        for (owner, running_key), running in list(self.playing.items()):
            if owner == mode and key in (None, running_key):
                running.stop()

    def _expanded(self, show: Show, steps: tuple[Step, ...]) -> tuple[Step, ...]:
        """Frames number their columns: turn the numbers into the lights of the show's columns."""
        result: list[Step] = []
        for n, step in enumerate(steps, start=1):
            if not step.columns:
                result.append(step)
                continue
            lights = self._columns(show, step, n)
            result.append(Step(step.duration, tuple(LightChange(lights[int(c.target)], c.color, c.fade_ms)
                                                    for c in step.lights), step.coils, step.events))
        return tuple(result)

    def _columns(self, show: Show, step: Step, n: int) -> list[str]:
        lights = [light.name for column in step.columns for light in self.lights_for(column)]
        if step.width != len(lights):
            raise ConfigError(f"show {show.name}: frame {n} has {step.width} columns, but its lights are "
                              f"{len(lights)} ({', '.join(lights)})")
        return lights
