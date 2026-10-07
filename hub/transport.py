import requests

from hub import config, tmux
from hub.registry import Session


def _agent_request(session: Session, method: str, path: str, **kwargs) -> requests.Response:
    url = f"{session.host}{path}"
    headers = {"Authorization": f"Bearer {config.AGENT_SHARED_SECRET}"}
    response = requests.request(method, url, headers=headers, timeout=10, **kwargs)
    response.raise_for_status()
    return response


def send_keys(session: Session, text: str) -> None:
    if session.host == "local":
        tmux.send_keys(session.tmux_session, text)
        return
    _agent_request(session, "POST", f"/sessions/{session.tmux_session}/send-keys", json={"text": text})


def capture_pane(session: Session) -> str:
    if session.host == "local":
        return tmux.capture_pane(session.tmux_session)
    response = _agent_request(session, "GET", f"/sessions/{session.tmux_session}/capture")
    return response.json()["pane"]


def new_session(session: Session, launch_cmd: str) -> None:
    if session.host == "local":
        tmux.new_session(session.tmux_session, session.cwd, launch_cmd)
        return
    _agent_request(
        session,
        "POST",
        f"/sessions/{session.tmux_session}/new",
        json={"cwd": session.cwd, "launch_cmd": launch_cmd},
    )


def kill_session(session: Session) -> None:
    if session.host == "local":
        tmux.kill_session(session.tmux_session)
        return
    _agent_request(session, "POST", f"/sessions/{session.tmux_session}/kill")
