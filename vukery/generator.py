"""``vuk it NAME``: create a new machine folder, ready to play and test (like ``rails new``).

The files come from ``vukery/templates/machine/``. Each template ends in
``.tmpl`` (so vukery's own tools don't treat it as vukery code) and may use:

- ``{{name}}``: the machine's folder name;
- ``{{module}}``: the same, as a Python identifier (for the spec file);
- ``{{version}}``: the vukery version that made the machine, which its
  ``pyproject.toml`` pins.

``gitignore`` and ``python-version`` become dotfiles. The asset folders are
created empty, with a ``.gitkeep`` so git keeps them.
"""

import re
from pathlib import Path

from vukery import __version__
from vukery.core.errors import ConfigError

TEMPLATE = Path(__file__).parent / "templates" / "machine"
DOTFILES = {"gitignore", "python-version"}
ASSET_FOLDERS = ("sounds", "images", "videos", "fonts")
NAME = re.compile(r"[a-z][a-z0-9_-]*")


def create_machine(folder: Path) -> list[Path]:
    """Create a machine in ``folder`` (new or empty). Returns the files created, relative to it."""
    name = folder.name
    if not NAME.fullmatch(name):
        raise ConfigError(f"{name!r} isn't a good machine name: use lowercase letters, digits, - and _, "
                          "starting with a letter (e.g. combat, grand-prix)")
    if folder.exists() and any(folder.iterdir()):
        raise ConfigError(f"{folder} already exists and isn't empty")
    values = {"{{name}}": name, "{{module}}": name.replace("-", "_"), "{{version}}": __version__}

    def fill(text: str) -> str:
        for key, value in values.items():
            text = text.replace(key, value)
        return text

    created: list[Path] = []
    for template in sorted(TEMPLATE.rglob("*.tmpl")):
        relative = Path(fill(str(template.relative_to(TEMPLATE).with_suffix(""))))
        if relative.name in DOTFILES:
            relative = relative.with_name("." + relative.name)
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(fill(template.read_text()))
        created.append(relative)
    for asset in ASSET_FOLDERS:
        keep = Path("assets") / asset / ".gitkeep"
        (folder / keep).parent.mkdir(parents=True, exist_ok=True)
        (folder / keep).touch()
        created.append(keep)
    return sorted(created)
