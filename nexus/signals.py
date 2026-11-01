"""Graceful Ctrl+C / SIGTERM inside the Qt event loop without polling.

Python runs signal handlers only when the interpreter gets control; a timer that wakes it
several times a second costs measurable idle CPU on the Pi. Instead the signal is written to a
socket (signal.set_wakeup_fd) that Qt watches, so Python wakes only when a signal arrives."""
import signal
import socket

from PyQt6.QtCore import QSocketNotifier, QTimer


def quit_on_signals(app, signals=(signal.SIGINT, signal.SIGTERM)):
    rsock, wsock = socket.socketpair()
    for s in (rsock, wsock):
        s.setblocking(False)
    signal.set_wakeup_fd(wsock.fileno())
    for sig in signals:
        # queued, not direct: a signal arriving before app.exec() starts would otherwise be lost
        # (quit() is ignored when no event loop runs yet) and the app would never stop
        signal.signal(sig, lambda *_: QTimer.singleShot(0, app.quit))
    notifier = QSocketNotifier(rsock.fileno(), QSocketNotifier.Type.Read, app)
    notifier.activated.connect(lambda *_: rsock.recv(64))  # Python's handler has run by now
    app._signal_keepalive = (rsock, wsock, notifier)
    return notifier
