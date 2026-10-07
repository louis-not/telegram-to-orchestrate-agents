import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Session:
    host: str
    tmux_session: str
    cwd: str
    claude_session_id: str | None = None


class SessionRegistry:
    def __init__(self, path: str):
        self._path = Path(path)
        self._sessions: dict[str, Session] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        data = json.loads(self._path.read_text())
        self._sessions = {
            session_id: Session(**fields)
            for session_id, fields in data.get("sessions", {}).items()
        }

    def _save(self) -> None:
        data = {"sessions": {sid: asdict(s) for sid, s in self._sessions.items()}}
        self._path.write_text(json.dumps(data, indent=2))

    def all(self) -> dict[str, Session]:
        return dict(self._sessions)

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def put(self, session_id: str, session: Session) -> None:
        self._sessions[session_id] = session
        self._save()

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._save()
