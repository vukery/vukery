# Logging

!!! note "0.0.x"
    Logging is built, tested, and started by `vuk it`.

vukery's logs look like MPF's, but each environment writes to one file
instead of a new one every run, and every component can be switched on or
off.

## Where logs go

One file per environment, in the game's `log/` folder:

```text
log/development.log
log/production.log
```

Each run is appended after a separator line:

```text
===== vukery started 2026-11-25 21:04:10 (development) =====
2026-11-25 21:04:10,651 : INFO : fast.net : Connected to FP-CPU-002-2 with firmware v01.05
```

Files rotate when they reach 10 MB, and the last 5 are kept. The `test`
environment writes no file.

## The `logging:` config

```yaml
logging:
  level: info        # the default for every component
  console: info      # the most detail the console shows
  file: debug        # the most detail the log file gets
  components:        # per component; everything under a name follows it
    fast: debug      # all FAST logging
    fast.rgb: off    # except the RGB port
  max_file_mb: 10
  backups: 5
```

Levels are `off`, `error`, `warning`, `info` and `debug`.

### Component names

Every part of vukery logs under a dotted name. A level set on a name applies
to everything under it, so `fast: debug` covers `fast.net`, `fast.rgb`,
`fast.switch` and the rest.

| Name | What logs under it |
|---|---|
| `fast` | The FAST platform |
| `fast.net` | The NET port (switches, coils, I/O boards) |
| `fast.rgb` | The Nano's RGB (LED) port |
| `fast.switch` | Individual FAST switches |
| `fast.driver` | Individual FAST drivers (coils) |
| `fast.led` | FAST LEDs |

More names are added as more of vukery is built.

## Changing the level on the fly

`VUK_LOG` sets **one level for everything**. It overrides the whole
`logging:` config, components included:

```console
VUK_LOG=debug vuk it
```

It accepts `debug`, `info`, `warning` or `error`. To change one component,
use the `logging:` config.

## Coming from MPF

- **The line format is the same as MPF's.**
- **No more timestamped file per run.** vukery appends to one file per
  environment.
- **`debug: true` still works** on the settings that had it in MPF, such as
  `fast: net: debug: true`. It means the same as setting that component to
  `debug` in `logging:`.
- **MPF's `-v` and `-V` flags** become `VUK_LOG=debug`.
