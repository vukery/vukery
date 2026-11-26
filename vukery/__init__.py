"""vukery: a very opinionated pinball framework based on the Mission Pinball Framework.

Game code needs only this::

    from vukery import BLOCK, Award, Mode, Score, on
"""

from vukery.core.events import BLOCK
from vukery.core.modes import Mode, on
from vukery.core.scoring import Award, Score

__version__ = "0.0.3"

__all__ = ["BLOCK", "Award", "Mode", "Score", "__version__", "on"]
