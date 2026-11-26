"""vukery: a very opinionated pinball framework based on the Mission Pinball Framework.

Game code needs only this::

    from vukery import BLOCK, Award, Mode, Score, on
"""

from importlib.metadata import PackageNotFoundError, version

from vukery.core.events import BLOCK
from vukery.core.modes import Mode, on
from vukery.core.scoring import Award, Score

try:
    __version__ = version("vukery")  # the single source is pyproject.toml
except PackageNotFoundError:  # running from a source tree that isn't installed
    __version__ = "0.0.0+unknown"

__all__ = ["BLOCK", "Award", "Mode", "Score", "__version__", "on"]
