# The vuk command

`vuk` is vukery's command-line tool. Its commands follow MPF's, renamed so
each one does one thing.

```console
vuk it my_machine  # create a machine, ready to play and test
cd my_machine
vuk me             # play the game on your computer, with the dashboard
vuk us             # run the game the way a machine does: displays full screen
vuk you            # run the specs, with coverage
vuk health         # check your setup
vuk --help
```

- **`vuk it NAME`** creates a new machine folder, much like `rails new`: a
  commented machine config, a base mode, specs, asset folders, and a
  `pyproject.toml` that pins vukery. Leave out the name and it asks. See
  [Getting started](../getting-started/index.md#make-a-machine-vuk-it).

`vuk me` and `vuk us` run the game whose `config/` folder is in the current
folder (or in the folder given with `-C DIR`):

- **`vuk me`** is for working on a game. The game runs with a
  [dashboard](dashboard.md) showing every switch, light, coil and mode, the
  displays, and a virtual playfield you click to play.
- **`vuk us`** is how a machine runs, usually with `VUK_ENV=production`: the
  game and its displays, full screen, with no dashboard.

## Environment variables

vukery uses environment variables for the settings you change on the fly,
not command-line flags.

| Variable | What it sets | Values | Default |
|---|---|---|---|
| `VUK_ENV` | The [environment](#environments) | `development`, `test`, `production` | `development` |
| `VUK_LOG` | One log level for everything (see [Logging](logging.md)) | `debug`, `info`, `warning`, `error` | from the `logging:` config |

```console
VUK_ENV=production vuk us
VUK_LOG=debug vuk us
```

### Environments

- **development** (the default) uses simulated hardware unless you pass
  `--hardware`.
- **test** is what `vuk you` always uses. It never touches hardware.
- **production** runs the real machine.

## Commands

| Command | Status | What it does | MPF equivalent |
|---|---|---|---|
| `vuk health` | **works** | Shows versions, where vukery was installed from, pyglet and FFmpeg | `mpf diagnosis` |
| `vuk it NAME` | **works** | Creates a machine folder, ready to play and test | `mpf create_config` |
| `vuk me` | **works** on the simulated platforms | Runs the game with the [dashboard](dashboard.md), in a window | `mpf both` plus `mpf monitor` |
| `vuk you` (or `vuk test`) | **works** | Runs the specs with pytest, always in the test environment, and measures coverage (`--no-cov` turns it off). In a machine folder it covers `modes/`; in vukery itself, the `vukery/` package. Extra arguments go to pytest (`vuk you -k scoring`). | `mpf test` |
| `vuk us` | **works** in development | Runs the game and a full-screen media controller per display. On the development platform you can also type a switch name in the terminal to tap it. | `mpf`, `mpf game`, `mpf both` |
| `vuk top` | planned | Terminal dashboard of a running game; works over SSH | `mpf -t` |
| `vuk console` | planned | Python prompt attached to the running game | `mpf service` |
| `vuk hardware scan` | planned | Lists boards and firmware | `mpf hardware scan` |
| `vuk hardware switches` | planned | Shows switch changes live | |
| `vuk hardware lights` | planned | Walks every LED | |
| `vuk hardware coil NAME` | planned | Pulses one coil, after asking | |
| `vuk generate mode\|show\|scene NAME` | planned | Adds a mode, show or scene | `mpf create_config` |
| `vuk wire` | planned | FAST wiring instructions from your config | `mpf wire` |
| `vuk stubs` | planned | Typed stubs from your machine config | |

A command that isn't built yet says so and exits with code 2.

### `vuk us` and `vuk me` options

The config decides whether media controllers start: `vuk us` starts one per
display in `displays:`, none without it. `vuk me` starts none, because the
dashboard shows the displays in its own panes. Sound will work the same way, from the
config. (MPF chose with `mpf game` versus `mpf both`, and `--no-sound`.)

| Option | Status | What it does | MPF flag |
|---|---|---|---|
| `--log-dir DIR` | works | Where log files go (default `log/`) | `-l` |
| `--hardware` | works | Allow real hardware in development | |
| `--preload` | planned | Load every asset at startup | `-f` |

### Global options

| Option | What it does |
|---|---|
| `-C DIR` | The game folder (default: the current folder) |
| `--version` | Print vukery's version |

## Coming from MPF

| MPF | vukery |
|---|---|
| `-X` (smart virtual), `-x` (virtual), `-P` (production) | `VUK_ENV=development`, `VUK_ENV=test`, `VUK_ENV=production` |
| `-v`, `-V` (verbose logging) | `VUK_LOG=debug`, or per component in the `logging:` config |
| `-a`, `-A` (config cache) | not needed: vukery has no config cache |
| `-b` (no BCP) | not needed: vukery doesn't use BCP |
| `mpf build` | not needed: no production bundle |
| `mpf mc` | not needed: `vuk us` starts a media controller per display, and `vuk me` draws them itself |
