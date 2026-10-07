"""Process-wide singletons shared by every handler module.

Handlers must `from hub import state` and reference `state.registry` /
`state.monitor` (not `from hub.state import registry`) so they see the
instances created by init(), which runs after module import time.
"""

from hub.monitor import Monitor
from hub.registry import SessionRegistry

registry: SessionRegistry | None = None
monitor: Monitor | None = None


def init(registry_path: str) -> None:
    global registry, monitor
    registry = SessionRegistry(registry_path)
    monitor = Monitor(registry)
