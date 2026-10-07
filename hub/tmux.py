import subprocess


def send_keys(tmux_session: str, text: str) -> None:
    subprocess.run(["tmux", "send-keys", "-t", tmux_session, text, "Enter"], check=True)


def capture_pane(tmux_session: str) -> str:
    result = subprocess.run(
        ["tmux", "capture-pane", "-p", "-t", tmux_session], check=True, capture_output=True, text=True
    )
    return result.stdout


def new_session(tmux_session: str, cwd: str, launch_cmd: str) -> None:
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", tmux_session, "-c", cwd], check=True
    )
    send_keys(tmux_session, launch_cmd)


def kill_session(tmux_session: str) -> None:
    subprocess.run(["tmux", "kill-session", "-t", tmux_session], check=True)
