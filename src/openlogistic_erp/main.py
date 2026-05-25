"""Application bootstrap and dependency container factory."""
import faulthandler

faulthandler.enable()

import argparse
import logging
import sys

from .bootstrap.container import AppContainer
from .presentation.qt import QQmlDebuggingEnabler

logger = logging.getLogger(__name__)


def _enable_qml_debugging_from_argv() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-qmljsdebugger", action="store", dest="qmljsdebugger")
    options, _ = parser.parse_known_args(sys.argv[1:])
    if options.qmljsdebugger:
        QQmlDebuggingEnabler.enableDebugging(True)


def main() -> int:
    """Entry point for the new architecture app."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        _enable_qml_debugging_from_argv()
        container = AppContainer.build_from_env()
        app = container.create_app()
        return app.run()
    except Exception:
        logger.exception("OpenLogisticERP failed during startup")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
