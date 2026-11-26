# The vuk command

`vuk` is vukery's command-line tool. Its commands follow MPF's, renamed so
each one does one thing.

```console
cd my_game
vuk it          # run the game in this folder
vuk doctor      # check your setup
vuk --help
```

`vuk it` runs the game whose `config/` folder is in the current folder (or
in the folder given with `-C DIR`).

## Environment variables

vukery uses environment variables for the settings you change on the fly,
not command-line flags.

| Variable | What it sets | Values | Default |
|---|---|---|---|
| `VUK_ENV` | The [environment](#environments) | `development`, `test`, `production` | `development` |
| `VUK_LOG` | One log level for everything (see [Logging](logging.md)) | `debug`, `info`, `warning`, `error` | from the `logging:` config |

```console
VUK_ENV=production vuk it
VUK_LOG=debug vuk it
```

### Environments

- **development** (the default) uses simulated hardware unless you pass
  `--hardware`.
- **test** is what `vuk test` always uses. It never touches hardware.
- **production** runs the real machine.

## Commands

| Command | Status | What it does | MPF equivalent |
|---|---|---|---|
| `vuk doctor` | **works** | Shows versions and checks for FFmpeg | `mpf diagnosis` |
| `vuk it` | **works** in development | Runs the game and a media controller per display. In development, type a switch name to tap it. | `mpf`, `mpf game`, `mpf both` |
| `vuk mc` | **works** | Runs a media controller only (`--display NAME`) | `mpf mc` |
| `vuk view` | planned | Playfield GUI: lights, switches, coils | `mpf monitor` |
| `vuk top` | planned | Terminal dashboard of a running game; works over SSH | `mpf -t` |
| `vuk console` | planned | Python prompt attached to the running game | `mpf service` |
| `vuk hardware scan` | planned | Lists boards and firmware | `mpf hardware scan` |
| `vuk hardware switches` | planned | Shows switch changes live | |
| `vuk hardware lights` | planned | Walks every LED | |
| `vuk hardware coil NAME` | planned | Pulses one coil, after asking | |
| `vuk test` | planned | Runs the game's specs | `mpf test` |
| `vuk new NAME` | planned | Creates a game folder | `mpf create_config` |
| `vuk generate mode\|show\|slide NAME` | planned | Adds a mode, show or slide | `mpf create_config` |
| `vuk wire` | planned | FAST wiring instructions from your config | `mpf wire` |
| `vuk stubs` | planned | Typed stubs from your machine config | |

A command that isn't built yet says so and exits with code 2.

### `vuk it` options

| Option | Status | What it does | MPF flag |
|---|---|---|---|
| `--log-dir DIR` | works | Where log files go (default `log/`) | `-l` |
| `--hardware` | works | Allow real hardware in development | |
| `--no-mc` | works | Don't start the media controllers | (`mpf game` instead of `mpf both`) |
| `--no-sound` | planned | Run without audio | `--no-sound` |
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
