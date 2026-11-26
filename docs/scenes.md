# Displays and scenes

!!! note "0.0.x"
    Scenes with text and nested scenes, entrances and exits, moves and
    blinks, on one or more displays, drawn by the pyglet media controller. Images, sprite sheets,
    video and sound come later. The complete examples are
    [`examples/display` and `examples/dual_display`](examples.md).

vukery's game engine decides what each display shows. A **media
controller**, a separate process, only draws it. The default media
controller uses [pyglet](https://pyglet.org).

## Displays (YAML)

```yaml
displays:
  main:
    width: 800
    height: 480
```

**The config decides whether there's a media controller.** With a
`displays:` section, `vuk us` starts one full-screen media controller window
per display. Without one, none is loaded. There's no command-line switch for
it. To run a game without its display in one environment, leave
`displays:` out of the config that environment uses.

**Each display goes full screen on its own monitor**, in config order: the
first display on the first monitor, and so on. To choose, give its monitor
number (from 0):

```yaml
displays:
  main:
    width: 800
    height: 480
    screen: 1    # the second monitor
```

`width` and `height` give the display's shape; full screen, the scene fills
the monitor.

`vuk us` runs each display as its own process. To restart one, or to look
at one at its configured size in a window, run it by hand:

```console
uv run python -m vukery.mc . --display main --windowed
```

[`vuk me`](dashboard.md) doesn't open these windows: its dashboard shows each
display in a pane of its own.

## Scenes and actors (Python)

A **scene** is what a display shows: a container with a background and the
**actors** in it. An actor is a `Text`, or another scene placed inside this
one. (In MPF terms, a scene on a display is a slide, and a scene inside a
scene is a widget or a group of them: one idea instead of two.)

Scenes are functions marked `@scene`, in a `scenes.py` file next to the
mode's `mode.py`:

```python
# modes/base/scenes.py
from vukery.media.scenes import Scene, Text, scene


@scene
def ball_info():
    return Scene(
        Text("PLAYER {player.number}", y=0.65, size=0.2),
        Text("BALL {player.ball}", y=0.3, size=0.2, color="ffcc00"),
        background="202060",
    )


@scene
def score():
    return Scene(
        Text("{player.score:,}", y=0.6, size=0.3).enters("left"),
        ball_info().placed(x=0.75, y=0.15, width=0.4, height=0.25),   # a scene inside a scene
    )
```

The mode lists the scenes it can show, and shows them:

```python
# modes/base/mode.py
from vukery import Mode

from .scenes import ball_info, score


class Base(Mode):
    priority = 100
    start_on = "ball_started"
    scenes = (score, ball_info)

    def mode_start(self, **_):
        self.show_scene(score)
```

- **Each display shows its highest-priority scene.** A scene's priority is
  the mode's priority plus the `priority=` you pass, as in MPF's
  `slide_player`.
- **A mode's scenes go away when the mode stops.**
- **Scene names are the functions' names, shared by the whole game.** Two
  modes can't define the same name.
- **The functions run once, when the machine starts.** What they return is
  sent to the media controller as data; live values are filled in there.

| Method | |
|---|---|
| `self.show_scene(score)` | Show a scene on the first display (its function, or its name) |
| `self.show_scene(score, display="apron", priority=10)` | On another display (MPF: `target`), a bit higher |
| `self.remove_scene(score)` | |

### `Scene`

`Scene(*actors, background=None)`. Actors are drawn in order. A scene on a
display has a black background unless you give one.

**Placing a scene inside another:**
`ball_info().placed(x=0.75, y=0.15, width=0.4, height=0.25)`. Its center goes
at `x`, `y`, and it's `width` and `height` of its parent, as fractions. Its
actors are placed in it in turn, so everything scales together.

### `Text`

| Setting | Default | |
|---|---|---|
| `text` | (required) | May include live values, see below |
| `x`, `y` | `0.5`, `0.5` | Where its anchor point goes, as a fraction of its scene (0,0 is bottom-left) |
| `size` | `0.1` | Height as a fraction of its scene's height |
| `color` | `"ffffff"` | Six hex digits |
| `anchor` | `"center"` | `left`, `center` or `right` |

### Entrances and exits

Every actor (a text, or a placed scene with everything in it) can move:

| | |
|---|---|
| `.enters("left", seconds=0.3)` | slides in from that side when its scene appears |
| `.exits("right", seconds=0.3)` | slides out to that side when its scene goes away |

Sides are `left`, `right`, `top` and `bottom`. Entrances ease out, and exits
ease in. While actors exit, they're drawn over the scene that replaced them;
actors without an exit just disappear.

### Animations: moves and blinks

Any actor (a text, or a placed scene with everything in it) can move and
blink. Both start once it has made its entrance, and both keep going while it
exits.

**`.moves(x=, y=, seconds=1.0, repeat=False, back=False)`** moves it from
where it's placed to `x`, `y` (fractions of its scene; leave one out to keep
it). Moves are linear: the same speed all the way.

```python
# A scroll: from off the right edge to off the left edge, every 4 seconds
Text("SHOOT THE GUN", x=1.5, y=0.5, size=0.2).moves(x=-0.5, seconds=4, repeat=True)

# A bob: up a little and back down, forever
Text("vukery", y=0.45).moves(y=0.55, seconds=2, repeat=True, back=True)
```

| `repeat` | `back` | |
|---|---|---|
| `False` | `False` | moves once and stays there |
| `False` | `True` | goes there and comes back once |
| `True` | `False` | moves, jumps back to the start, moves again |
| `True` | `True` | goes there and back, forever |

**`.blinks(every=0.5, times=None, fade=False)`** shows it for `every` seconds,
then hides it for `every` seconds. With `times`, it blinks that many times
and then stays on; without it, it blinks forever. With `fade=True`, it fades
out and back in instead.

```python
Text("PRESS START", y=0.3).blinks(every=0.5)
Text("{player.score:,}", y=0.6, size=0.3).blinks(every=0.25, fade=True)   # MPF: pulsate_fast
Text("JACKPOT").blinks(every=0.1, times=5)
```

A blinking scene blinks everything in it. `game.screen()` in specs lists only
what you'd see at that moment, so a text that's blinked off isn't in it.

### Live values

Text can include the current player's variables, with Python formatting:

| Text | Shows |
|---|---|
| `{player.score}` | `12340` |
| `{player.score:,}` | `12,340` |
| `{player.ball}` | `2` |
| `{player.number}` | `1` |
| `{player.ramps}` | any player variable |
| `{players[2].score:,}` | player 2's score, whoever's turn it is |

Anything that doesn't exist yet shows as empty: `{players[3].score}` before
there's a third player, say.

### Clipped to the display

Nothing is drawn outside a display, as on real glass: an actor moving past
the edge is cut off there. That holds for the display panes in `vuk me` too.

## Testing what's on screen

The test rig includes a media controller that runs in the same process, on
the specs' virtual clock, so specs can check displays without opening a
window:

```python
def it_shows_the_score(game):
    game.start_game()
    game.switch("s_target")
    expect(game.scene()).to_equal("score")
    expect(game.screen()).to_equal(["1,000", "PLAYER 1   BALL 1"])
```

`game.scene()` and `game.screen()` look at the first display. Pass a display
name for another one.

## The media protocol

The engine and media controllers talk JSON messages over a local socket
(port `5051`, or `media: port:` in the config). Anyone can write a media
controller in any language: it says hello with its displays, gets a welcome
with every scene (as data) and the current state, then follows `show`,
`player` and `turn` messages. Messages it doesn't recognize must be ignored.
The protocol is version 2 (version 1 had slides).
The [`vuk me` dashboard](dashboard.md) is a media controller too: it says
`"dashboard": true` in its hello and also gets the machine's layout and
`state` messages, and it may send `switch` messages back.
The message formats are in `vukery/media/protocol.py`.

## Coming from MPF

| MPF | vukery |
|---|---|
| `displays:` | `displays:` (`width`, `height`, `screen`) |
| `slides:` | a `@scene` function returning a `Scene` |
| `widgets:` | actors: `Text(...)`, or a scene placed in another with `.placed(...)` |
| `slide_player: some_event: slide_name` | `self.show_scene(slide_name)` in a handler |
| `slide_player` `target:` | `display=` |
| `widget_player` | a scene placed inside the scene that's showing |
| widget `animations:` (`move_in`, `move_out`) | `.enters(side)`, `.exits(side)` |
| `animations:` on `x` or `y` (scrolls), with `repeat: true` | `.moves(x=..., seconds=..., repeat=True)` |
| `animations:` on `opacity` (pulsate, flash) | `.blinks(every=..., fade=True)`, or without `fade` for on and off |
| `(player\|score)` placeholders | `{player.score}` |
| `(player2\|score)` | `{players[2].score}` |
| MPF-MC (Kivy) or GMC (Godot) | the pyglet media controller, over vukery's own protocol (no BCP) |
