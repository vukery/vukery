"""Small machines for specs: examples/basic, copied and changed."""

import shutil
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

EXAMPLES = Path(__file__).parents[1] / "examples"


def basic_machine(tmp_path: Path, edit: Callable[[dict[str, Any]], None] | None = None,
                  files: dict[str, str] | None = None, example: str = "basic") -> Path:
    """A copy of an example (basic by default): ``edit`` changes its machine.yaml; ``files`` adds or
    replaces files."""
    folder = tmp_path / "machine"
    shutil.copytree(EXAMPLES / example, folder)
    if edit:
        path = folder / "config" / "machine.yaml"
        config = yaml.safe_load(path.read_text())
        edit(config)
        path.write_text(yaml.safe_dump(config, sort_keys=False))
    for name, text in (files or {}).items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(textwrap.dedent(text))
    return folder
