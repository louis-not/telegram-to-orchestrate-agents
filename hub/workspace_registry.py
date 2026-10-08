import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# Opt-in marker: an empty file, independent of whether a project also keeps
# a real .creds.md — tying workspace membership to the presence of a live
# secrets file was a design smell (and meant plenty of real projects with
# no stored creds could never opt in). See docs/prd-workspace-mapping.md
# §10 ("Opt-in marker" decision).
WORKSPACE_MARKER = ".hub-workspace"


@dataclass
class Workspace:
    name: str
    path: str
    host: str
    discovered_from: str
    registered_at: float


def find_workspace_root(cwd: str) -> str | None:
    home = Path.home()
    current = Path(cwd)
    while True:
        if (current / WORKSPACE_MARKER).exists():
            return str(current)
        if current == current.parent or current == home:
            return None
        current = current.parent


class WorkspaceRegistry:
    def __init__(self, path: str):
        self._path = Path(path)
        self._workspaces: dict[str, Workspace] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        data = json.loads(self._path.read_text())
        self._workspaces = {
            name: Workspace(**fields)
            for name, fields in data.get("workspaces", {}).items()
        }

    def _save(self) -> None:
        data = {"workspaces": {name: asdict(w) for name, w in self._workspaces.items()}}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, indent=2))

    def all(self) -> dict[str, Workspace]:
        return dict(self._workspaces)

    def get(self, name: str) -> Workspace | None:
        return self._workspaces.get(name)

    def put(self, name: str, workspace: Workspace) -> None:
        self._workspaces[name] = workspace
        self._save()

    def remove(self, name: str) -> None:
        self._workspaces.pop(name, None)
        self._save()

    def register(self, path: str, host: str, discovered_from: str) -> str:
        basename = Path(path).name
        existing = self._workspaces.get(basename)
        if existing is not None and existing.path == path:
            name = basename
        elif existing is not None:
            name = f"{basename}@{host}"
        else:
            name = basename
        self.put(
            name,
            Workspace(
                name=name,
                path=path,
                host=host,
                discovered_from=discovered_from,
                registered_at=time.time(),
            ),
        )
        return name
