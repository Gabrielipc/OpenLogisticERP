from __future__ import annotations

from collections.abc import Callable
from typing import Any

from openlogistic_erp.presentation.catalog.screen_view_model import CatalogScreenViewModel
from openlogistic_erp.presentation.qt import QEventLoop, QTimer


def run_action_and_wait_for_request(
    screen: CatalogScreenViewModel,
    action: Callable[[], int | None],
    *,
    timeout_ms: int = 3000,
) -> tuple[int, bool]:
    state: dict[str, Any] = {"events": []}
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)

    def on_timeout() -> None:
        loop.quit()

    def on_finished(request_id: int, applied: bool) -> None:
        state["events"].append((int(request_id), bool(applied)))
        expected_request_id = state.get("expected_request_id")
        if expected_request_id is None:
            return
        if int(request_id) == int(expected_request_id):
            state["result"] = (int(request_id), bool(applied))
            loop.quit()

    screen.loadFinished.connect(on_finished)
    timer.timeout.connect(on_timeout)
    try:
        request_id = action()
        if request_id is None:
            raise AssertionError("La accion no disparo ninguna carga.")
        state["expected_request_id"] = int(request_id)

        for event in list(state["events"]):
            if event[0] == state["expected_request_id"]:
                state["result"] = event
                break

        if "result" not in state:
            timer.start(timeout_ms)
            loop.exec()
        if "result" not in state:
            raise AssertionError(
                f"Timeout esperando loadFinished para request_id={state['expected_request_id']}"
            )
        return state["result"]
    finally:
        timer.stop()
        try:
            screen.loadFinished.disconnect(on_finished)
        except TypeError:
            pass
        try:
            timer.timeout.disconnect(on_timeout)
        except TypeError:
            pass


def run_action_and_wait_for_applied_load(
    screen: CatalogScreenViewModel,
    action: Callable[[], object],
    *,
    timeout_ms: int = 3000,
) -> tuple[int, bool]:
    state: dict[str, Any] = {}
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)

    def on_timeout() -> None:
        loop.quit()

    def on_finished(request_id: int, applied: bool) -> None:
        if not applied:
            return
        state["result"] = (int(request_id), bool(applied))
        loop.quit()

    screen.loadFinished.connect(on_finished)
    timer.timeout.connect(on_timeout)
    try:
        action()
        if "result" not in state:
            timer.start(timeout_ms)
            loop.exec()
        if "result" not in state:
            raise AssertionError("Timeout esperando una carga aplicada.")
        return state["result"]
    finally:
        timer.stop()
        try:
            screen.loadFinished.disconnect(on_finished)
        except TypeError:
            pass
        try:
            timer.timeout.disconnect(on_timeout)
        except TypeError:
            pass
