# Get VUKed!

An AI-assisted total vukery of a pinball framework with a different mission.

*Pronounced "vuckery."*

<span class="gh-only">[Read the documentation](https://vukery.com) (coming eventually)</span>

**A very opinionated pinball framework based on the
[Mission Pinball Framework](https://missionpinball.org) (MPF), built to be
simple, lean and LLM-friendly.**

MPF is the framework behind most homebrew pinball games and it has been this
way for some time (a decade more or less). `vukery` is an opinionated, leaner
departure from MPF: YAML where it makes sense (configs), and plain python for
game logic. kivy has issues and a pinball machine should not need to depend
on a mainstream(ish) video game framework for simple a/v IMHO.

This framework will not be the answer for all pinball projects, but if
successful, I hope it will make building simpler pinball games easier with an
emphasis on modular design, unit testing and a conventional deployment plan.

> **Status: 0.0.x, early.** A game engine, scoring, displays and the FAST
> Nano are in, with three example games. Not yet tried on a real machine.
> See the [status page](https://github.com/vukery/vukery/blob/main/docs/status.md).

## The opinions

- **Game logic is Python.** YAML describes the machine (hardware, wiring,
  devices, settings) and never contains `if` statements, shows or slides.
- **Simple.** One way to do things, with names that say what they do.
  There's no `CustomCode`: everything that hooks into the machine is a
  `Mode`.
- **Lean.** Only what real games need. vukery rewrites a lot of MPF and
  copies files from it where useful, but never depends on the `mpf`
  package.
- **LLM-friendly.** Typed APIs, stubs generated from your machine config,
  deterministic headless tests, and MPF's names, events and test API kept
  so an LLM can help migrate an MPF game.
- **Pinball basics are built in.** Attract, game, ball search, tilt, match,
  high score, credits, bonus, service, ball save, extra ball and replay.
- **Modular.** One implementation of each part, with clean places to plug
  in your own media controller, hardware platform or mode library.
- **Rails-style conventions.** `assets/` folders, `development` / `test` /
  `production` environments, and a `modes/vukery/` folder for game-specific
  overrides.
- **No kivy, no Godot, no BCP.** The media controller (slides, sound, video) uses
  pyglet and talks to the engine over a small JSON protocol.

## Hardware

FAST Nano first (it runs [COMBAT](https://github.com/deathsave/combat)),
with CobraPin to follow.

## Docs

The docs will be published at [vukery.com](https://vukery.com), built
from the `docs/` folder, once there's something to document.

## Contributing

vukery is an AI-driven project. You can open pull requests, but they'll
probably not be merged. Issues (bugs, questions, ideas) are welcome. Want it
different? **vuk yourself**: fork it, it's MIT licensed. See
[CONTRIBUTING](https://github.com/vukery/vukery/blob/main/CONTRIBUTING.md).

## Credits and license

vukery is based on the [Mission Pinball Framework](https://github.com/missionpinball/mpf)
by the Mission Pinball Framework team and other contributors. MPF is a
wonderful project, and vukery wouldn't exist without it. vukery is just an
opinionated departure from it, not a replacement or a criticism. Code
brought in from MPF keeps its MIT notice and a permalink to its origin;
see [vukery/_mpf/NOTICE](https://github.com/vukery/vukery/blob/main/vukery/_mpf/NOTICE). vukery isn't affiliated with
or endorsed by the MPF project.

MIT licensed. See [LICENSE](https://github.com/vukery/vukery/blob/main/LICENSE).
