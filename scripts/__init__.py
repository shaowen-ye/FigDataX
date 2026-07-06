"""FigDataX — High-Precision Scientific Figure Data Extraction.

Re-exports the engine package so ``from scripts.figdatax import ...`` and
``from scripts import figdatax`` both work from the skill root on sys.path.
"""

from .figdatax import *  # noqa: F401,F403
from .figdatax import __version__, __all__  # noqa: F401
