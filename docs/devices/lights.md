# Lights

!!! note "0.0.x"
    Lights are built and tested on the FAST Nano's RGB port: channel
    numbering, colors, fades and RGBW. The priority stack (shows and modes
    restoring the color underneath) comes with shows.

Lights use the `lights:` section. Numbering matches MPF, so a migrated
config lights up the same LEDs.

```yaml
lights:
  l_shoot_again:
    number: 3-24          # Nano: LED port 3, LED 24 (both counted from 1)
  l_bonus_1:
    previous: l_shoot_again
    type: grb             # this strip's LEDs take green first
  l_insert:
    number: 151           # Nano: LED index 151 (0x97)
  l_rgbw:
    start_channel: 33-0   # first channel: LED 33, channel 0
    type: rgbw
  l_custom:
    channels:             # each color on any channel
      red:
        number: 40-0
      green:
        number: 40-2
      blue:
        number: 40-1
      white:
        number: 41-2
```

## Settings

| Setting | Notes |
|---|---|
| `number` | A light's LED. On a Nano: `port-led` (both counted from 1) or a plain index. |
| `type` | Channel order: `rgb` (default for 3 channels), `grb`, `rgbw`, `w` (default for 1 channel)… |
| `previous` | Continue on the channel right after another light's last one. Needs `type`. |
| `start_channel` | Start at a specific channel (`LED-channel`) and continue in sequence. Needs `type`. |
| `channels` | Name each color's channel yourself. Can't be combined with `number`. |
| `default_on_color` | Color for `on()`. Default `ffffff`. |
| `fade_ms` | Default fade time |

Use one of `number`, `previous`, `start_channel` or `channels`.

## Colors and fades

Colors are 6-digit hex strings (`"ff8800"`) or `(red, green, blue)` with
each value from 0 to 255.

```python
light.on()
light.color("112233")
light.color((100, 100, 100), fade_ms=100)
light.off()
```

A fade starts from the light's current color, including partway through
another fade.

## RGBW lights

For a light with red, green, blue and white channels, the shared part of the
color goes to the white channel and the rest stays on red, green and blue.
`ffffff` turns on only white, and `445566` sets white to `44`, green to `11`
and blue to `22`. This is MPF's default (`duck_rgb`).

## Coming from MPF

- `number`, `previous`, `start_channel`, `channels` and `type` work the same.
- Color correction profiles and gamma aren't supported yet.
- Show and mode priorities aren't supported yet: setting a color replaces
  the current one.
