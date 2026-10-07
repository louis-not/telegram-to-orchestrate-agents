import fcntl
import sys
from pathlib import Path

# Kept open for the process lifetime; the OS releases the lock on exit/crash.
_lock_file = None


def acquire(lock_path: str = "./hub.lock") -> None:
    """Fails fast if another hub process already holds the lock file."""
    global _lock_file
    handle = open(Path(lock_path), "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(f"another hub process is already running (lock held on {lock_path})", file=sys.stderr)
        sys.exit(1)
    _lock_file = handle
