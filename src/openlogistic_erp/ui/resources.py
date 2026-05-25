"""Qt resource registration for packaged UI assets."""

from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)


def register_qt_resources() -> None:
    """Import the generated Qt resource module so qrc:/ URLs are available."""

    try:
        importlib.import_module(f"{__package__}.resources_rc")
    except ModuleNotFoundError as exc:
        if exc.name == f"{__package__}.resources_rc":
            logger.warning("Qt resource module was not generated; qrc:/ assets will be unavailable.")
            return
        raise
