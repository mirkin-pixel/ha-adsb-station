"""Make the Home Assistant test harness importable on Windows.

Home Assistant is only ever run on Linux, so it imports two modules that CPython
only ships on POSIX, and the test harness inherits that. Nothing the tests touch
actually needs either of them: ``fcntl`` locks the config directory of a running
instance, and ``resource`` raises the file descriptor limit of one.

This plugin stands in for both, and gets the event loop past ``pytest-socket``.
It is loaded before the harness itself through ``-p`` in ``addopts``, which is
early enough for the stand-ins to be in place by the time the harness imports
Home Assistant. On Linux it does nothing at all, so the same ``pytest`` command
runs here and in CI.
"""

from __future__ import annotations

import socket
import sys
import types
from typing import Any


def _install_posix_stubs() -> None:
    """Register the two POSIX-only modules Home Assistant imports."""
    fcntl = types.ModuleType("fcntl")
    fcntl.LOCK_SH, fcntl.LOCK_EX, fcntl.LOCK_NB, fcntl.LOCK_UN = 1, 2, 4, 8
    # Windows has no advisory locking, and a single test run is the only thing
    # holding the config directory anyway.
    fcntl.flock = lambda fd, operation: None
    fcntl.fcntl = lambda fd, cmd, arg=0: 0
    fcntl.ioctl = lambda fd, request, arg=0, mutate_flag=True: 0
    sys.modules.setdefault("fcntl", fcntl)

    resource = types.ModuleType("resource")
    resource.RLIMIT_NOFILE = 7
    resource.RLIM_INFINITY = -1
    # Report a limit high enough that Home Assistant leaves it alone: Windows
    # has no equivalent knob to turn.
    resource.getrlimit = lambda which: (1 << 20, 1 << 20)
    resource.setrlimit = lambda which, limits: None
    sys.modules.setdefault("resource", resource)


def _allow_the_event_loop_its_self_pipe() -> None:
    """Let ``socket.socketpair`` through the block on network access.

    ``pytest-socket`` refuses every socket that is not a Unix one, which is what
    keeps a test from reaching the network. On Windows asyncio wakes its own
    event loop over a loopback socket pair rather than a pipe, so that refusal
    stops the loop from starting at all. Only the pair is let through, and only
    for as long as it takes to create: a test that tries to reach the network
    still gets blocked.
    """
    real_socket = socket.socket
    real_socketpair = socket.socketpair

    def socketpair(*args: Any, **kwargs: Any) -> Any:
        guarded, socket.socket = socket.socket, real_socket
        try:
            return real_socketpair(*args, **kwargs)
        finally:
            socket.socket = guarded

    socket.socketpair = socketpair  # type: ignore[assignment]


if sys.platform == "win32":
    _install_posix_stubs()
    _allow_the_event_loop_its_self_pipe()
