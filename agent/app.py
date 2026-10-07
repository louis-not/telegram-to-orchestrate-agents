from flask import Flask, abort, jsonify, request

from agent import config
from hub import tmux

app = Flask(__name__)


@app.before_request
def _check_auth() -> None:
    if request.headers.get("Authorization") != f"Bearer {config.SHARED_SECRET}":
        abort(401)


@app.route("/sessions/<session_id>/send-keys", methods=["POST"])
def send_keys(session_id: str):
    tmux.send_keys(session_id, request.json["text"])
    return jsonify(ok=True)


@app.route("/sessions/<session_id>/capture", methods=["GET"])
def capture(session_id: str):
    return jsonify(pane=tmux.capture_pane(session_id))


@app.route("/sessions/<session_id>/new", methods=["POST"])
def new_session(session_id: str):
    data = request.json
    tmux.new_session(session_id, data["cwd"], data["launch_cmd"])
    return jsonify(ok=True)


@app.route("/sessions/<session_id>/kill", methods=["POST"])
def kill(session_id: str):
    tmux.kill_session(session_id)
    return jsonify(ok=True)
