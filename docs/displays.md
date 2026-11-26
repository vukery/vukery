# Displays and slides

!!! note "0.0.x"
    Slides with text, on one or more displays, drawn by the pyglet media
    controller. Images, video, sound, animations and transitions come
    later. The complete example is [`examples/display`](examples.md).

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

`vuk it` starts one media controller window per display. To start them
yourself, run `vuk it --no-mc` and then `vuk mc --display main`.

## Slides (Python)

A mode lists the slides it can show, and shows them by name:

```python
from vukery import Mode, on
from vukery.media.slides import Slide, Text


class Base(Mode):
    priority = 100
    start_on = "ball_started"

    slides = {
        "score": Slide(
            Text("{player.score:,}", y=0.55, size=0.25),
            Text("PLAYER {player.number}   BALL {player.ball}", y=0.15, size=0.07, color="aaaaaa"),
        ),
    }

    def mode_start(self, **_):
        self.show_slide("score")
```

- **Each display shows its highest-priority slide.** A slide's priority is
  the mode's priority plus the `priority=` you pass, as in MPF's
  `slide_player`.
- **A mode's slides go away when the mode stops.**
- **Slide names are shared by the whole game.** Two modes can't define the
  same name.

| Method | |
|---|---|
| `self.show_slide("score")` | Show a slide on the first display |
| `self.show_slide("score", display="apron", priority=10)` | On another display (MPF: `target`), a bit higher |
| `self.remove_slide("score")` | |

### `Slide`

`Slide(*widgets, background="000000")`. Widgets are drawn in order.

### `Text`

| Setting | Default | |
|---|---|---|
| `text` | (required) | May include live values, see below |
| `x`, `y` | `0.5`, `0.5` | Position as a fraction of the display (0,0 is bottom-left) |
| `size` | `0.1` | Height as a fraction of the display's height |
| `color` | `"ffffff"` | Six hex digits |
| `anchor` | `"center"` | `left`, `center` or `right` |

Positions and sizes are fractions, so a slide fits any display size.

### Live values

Text can include the current player's variables, with Python formatting:

| Text | Shows |
|---|---|
| `{player.score}` | `12340` |
| `{player.score:,}` | `12,340` |
| `{player.ball}` | `2` |
| `{player.number}` | `1` |
| `{player.ramps}` | any player variable |

Anything that doesn't exist yet shows as empty.

## Testing what's on screen

The test rig includes a media controller that runs in the same process, so
specs can check displays without opening a window:

```python
def it_shows_the_score(game):
    game.start_game()
    game.switch("s_target")
    expect(game.slide()).to_equal("score")
    expect(game.screen()).to_equal(["1,000", "PLAYER 1   BALL 1"])
```

`game.slide()` and `game.screen()` look at the first display. Pass a display
name for another one.

## The media protocol

The engine and media controllers talk JSON messages over a local socket
(port `5051`, or `media: port:` in the config). Anyone can write a media
controller in any language: it says hello with its displays, gets a welcome
with the slide definitions and the current state, then follows `show`,
`player` and `turn` messages. Messages it doesn't recognize must be ignored.
The message formats are in `vukery/media/protocol.py`.

## Coming from MPF

| MPF | vukery |
|---|---|
| `displays:` | `displays:` (`width`, `height`) |
| `slides:` and `widgets:` YAML | `Slide(...)` and `Text(...)` in the mode |
| `slide_player: some_event: slide_name` | `self.show_slide("slide_name")` in a handler |
| `slide_player` `target:` | `display=` |
| `(player\|score)` placeholders | `{player.score}` |
| MPF-MC (Kivy) or GMC (Godot) | the pyglet media controller, over vukery's own protocol (no BCP) |
