# Configuration reference

!!! note "0.0.x"
    Complete for 0.0.x: every setting vukery takes is on this page. Its specs
    fail when vukery gains a setting this page doesn't show.

Every config setting vukery supports, with its default and its choices, in
one machine: [`examples/reference`](https://github.com/vukery/vukery/tree/main/examples/reference).
The files below are that machine's own config, so this page is always what
vukery really accepts:

- **Complete:** each section keeps its list of settings in vukery's code,
  and the example's specs fail if a setting or a section is missing from
  the files below. A setting vukery doesn't list is refused when the
  machine starts, with its name.
- **Real:** the specs start the machine with this config and play a game;
  the FAST section is parsed too.

The pages for each part (the [devices](../devices/coils.md),
[FAST](../hardware/fast.md), [sound](../media/sound.md),
[logging](../tools/logging.md)…) explain how the settings work. Names are
MPF's, so an MPF machine config mostly carries over; sections that hold
game logic in MPF (`variable_player`, `slide_player`…) are Python in vukery,
in a [mode](../modes/index.md).

## `config/machine.yaml`

Shared by every environment.

```yaml
--8<-- "examples/reference/config/machine.yaml"
```

## `config/environments/production.yaml`

Merged on top when `VUK_ENV=production`: the real machine's hardware.
`development` and `test` run on simulated platforms named after them and
need no `hardware:` section.

```yaml
--8<-- "examples/reference/config/environments/production.yaml"
```

## `config/dashboard.yaml`

`vuk me`'s layout, which `vuk me` keeps up to date as you drag things around.

```yaml
--8<-- "examples/reference/config/dashboard.yaml"
```
