"""Zentrales Fehler- und Exception-Handling (OWASP-PC-C10).

Ziele:
- Keine Stacktraces/Interna im UI.
- Vollständiges Logging für Debug/Forensik.
- Optional: Audit-Event für kritische Fehler.
"""

from __future__ import annotations

import logging
import threading
import traceback
from typing import Any, Callable


def _safe_user_message(title: str, exc: BaseException) -> tuple[str, str]:
    # Keep user-facing messages generic; details are in logs.
    msg = (
        "Die Aktion ist fehlgeschlagen.\n\n"
        "Details wurden in logs/app.log protokolliert."
    )
    return title, msg


def install_tk_global_exception_handler(root: Any) -> None:
    """Installiert einen globalen Tkinter-Exception-Handler auf dem Root.

    Tkinter ruft `report_callback_exception` für Exceptions aus Event-Callbacks auf.
    """
    try:
        import tkinter.messagebox as mb
    except Exception:
        return

    log = logging.getLogger("app")

    def _handler(exc_type, exc, tb):
        try:
            log.error("Uncaught Tk exception: %s", exc, exc_info=(exc_type, exc, tb))
        except Exception:
            pass
        title, msg = _safe_user_message("Fehler", exc)
        try:
            mb.showerror(title, msg, parent=root)
        except Exception:
            # As last resort, ignore UI errors.
            pass

    try:
        root.report_callback_exception = _handler  # type: ignore[attr-defined]
    except Exception:
        pass


def run_in_thread(
    *,
    name: str,
    target: Callable[[], None],
    on_error_ui: Callable[[str], None] | None = None,
) -> threading.Thread:
    """Startet einen Thread mit robustem Exception-Handling.

    Args:
        name: Log-/Thread-Name
        target: Funktion, die im Thread läuft
        on_error_ui: Optionaler Callback, der eine userfreundliche Fehlermeldung anzeigt
                    (muss UI-thread-sicher sein, z.B. via root.after).
    """
    log = logging.getLogger("app")

    def _wrapped() -> None:
        try:
            target()
        except Exception as exc:
            log.error("Thread '%s' crashed: %s\n%s", name, exc, traceback.format_exc())
            if on_error_ui:
                try:
                    title, msg = _safe_user_message("Fehler", exc)
                    on_error_ui(f"{title}: {msg}")
                except Exception:
                    pass

    th = threading.Thread(target=_wrapped, name=name, daemon=True)
    th.start()
    return th
