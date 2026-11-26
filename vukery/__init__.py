"""vukery: a very opinionated pinball framework based on the Mission Pinball Framework.

Game code needs only this::

    from vukery import BLOCK, Award, Mode, Score, on
"""

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from vukery.core.events import BLOCK
from vukery.core.modes import Mode, on
from vukery.core.scoring import Award, Score


def _version() -> str:
    """The single source is pyproject.toml. Running from a checkout (an editable install),
    read it there: the installed metadata keeps the version it had when it was installed."""
    source = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if source.is_file():
        project = tomllib.loads(source.read_text()).get("project", {})
        if project.get("name") == "vukery" and "version" in project:
            return str(project["version"])
    try:
        return version("vukery")
    except PackageNotFoundError:
        return "0.0.0+unknown"


__version__ = _version()

__all__ = ["BLOCK", "Award", "Mode", "Score", "__version__", "on"]
