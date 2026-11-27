# FAST hardware

!!! note "0.0.x"
    The **FAST Nano** is supported: its NET port (I/O boards, switches,
    coils) and its RGB port (LEDs). It's tested against MPF's mock FAST
    boards and hasn't been tried on a real machine yet. The **Neuron** and
    **EXP** expansion boards come later.

vukery's FAST support is ported from MPF's, so the `fast:` section of an
MPF config works as is.

## Config

```yaml
fast:
  net:
    controller: nano
    port: auto            # or a device, e.g. /dev/ttyUSB1
    io_loop:
      pf3208:
        model: FP-I/O-3208
        order: 1
      pf0804:
        model: FP-I/O-0804
        order: 2
  rgb:
    port: auto
```

### `net:`

| Setting | Default | Notes |
|---|---|---|
| `controller` | (required) | `nano` (`neuron` comes later) |
| `port` | `auto` | One device or a list. `auto` detects it (see below). |
| `io_loop` | | Your I/O boards: a name for each, with its `model` and its `order` in the loop (starting at 1, no gaps) |
| `baud` | `921600` | |
| `watchdog` | `1000` (ms) | If vukery stops talking to the board for this long, the board turns every coil off |
| `default_quick_debounce_open` / `_close` | `2` (ms) | For switches with `debounce: quick` |
| `default_normal_debounce_open` / `_close` | `4` (ms) | For switches with `debounce: normal` or `auto` |
| `mute_unconfigured_switches` | `false` | Ignore switches that aren't in your config |
| `debug` | `false` | Same as setting `fast.net: debug` in [logging](../tools/logging.md) |

### `rgb:`

| Setting | Default | Notes |
|---|---|---|
| `port` | `auto` | |
| `baud` | `921600` | |
| `led_hz` | `30` | LED updates per second. FAST's maximum is 30. |
| `ignore_reboot` | `true` | If the RGB processor reboots, log it and carry on. With `false`, the machine stops. |
| `debug` | `false` | Same as `fast.rgb: debug` in logging |

These MPF `fast:` sections aren't supported (yet): `exp`, `exp_int`, `aud`,
`dmd`, `seg`, `emu`. vukery stops with an error if your config has one.

## Port auto-detection

With `port: auto`, vukery finds the ports itself:

1. It looks for USB serial devices with FAST's vendor and product IDs. A
   Nano is one FTDI chip that shows up as **four** serial ports.
2. It sends `ID:` to each one. The ports that answer `NET` and `RGB` are
   used. The other two never answer.

If nothing answers, vukery stops with an error saying which ports it
couldn't find. Check that the controller is connected and powered, or set
`port:` to the device directly.

## Switch and coil numbers

Numbers name the board and the position on it, as in MPF:

```yaml
switches:
  s_trough1:
    number: pf3208-2     # board pf3208, switch 2
coils:
  c_trough_eject:
    number: pf3208-4     # board pf3208, driver 4
```

On a Nano, a hardware rule (like a slingshot) needs the switch and the coil
on the same I/O board, unless the switch is one of the first 8 switches. vukery
stops with an error if a rule breaks this.

## Firmware

vukery checks the firmware when it connects and refuses to start if a board
is older than this:

| Board | Minimum firmware |
|---|---|
| Nano (NET) | 01.05 |
| Nano I/O boards | 01.05 |
| RGB | 00.87 |

## Safety

- **The watchdog** turns every coil off if vukery stops talking to the
  board. When vukery stops normally, it tells the board to expire the
  watchdog right away.
- **If the Nano reboots** while running, vukery stops the machine.
- **If a board sends something vukery can't handle at startup** (such as old
  firmware, or I/O boards that don't match the config), startup fails with
  that error and the serial ports are closed.

## Coming from MPF

- The `fast:` section and the switch and coil numbers are unchanged.
- Only the Nano for now. Retro controllers, FAST audio, DMD and segment
  displays aren't supported.
- Config errors are reported as vukery errors with the setting's name,
  instead of Python `AssertionError`s.
