"""
GraphIV: a knowledge graph over all of arXiv, and the research endpoint on top of it

Importing this is cheap and side-effect free, with no config read until a class is built
"""

from typing import TYPE_CHECKING

from graphiv.core.config import Config

if TYPE_CHECKING:
    from graphiv.download import Downloader
    from graphiv.preprocess import Preprocessor

__all__ = ["Config", "Downloader", "Preprocessor"]


def __getattr__(name: str) -> object:
    """
    Load the pipeline primaries lazily, since both read config at subpackage import

    Args:
        name: attribute requested on the graphiv package.

    Returns:
        The requested class.

    Raises:
        AttributeError: for any other name.
    """
    if name == "Downloader":
        from graphiv.download import Downloader

        return Downloader
    if name == "Preprocessor":
        from graphiv.preprocess import Preprocessor

        return Preprocessor
    raise AttributeError(name)
