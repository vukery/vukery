"""vukery: a very opinionated pinball framework based on the Mission Pinball Framework.

Game code needs only this::

    from vukery import BLOCK, Mode, on
"""

from vukery.core.events import BLOCK
from vukery.core.modes import Mode, on

__version__ = "0.0.2"

__all__ = ["BLOCK", "Mode", "__version__", "on"]
